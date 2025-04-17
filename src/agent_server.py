import argparse
import asyncio
import base64
import datetime
import json
import os
import re
import shutil
import tempfile
import threading
from asyncio import Queue
import uuid

import openai
import websockets
import fastapi
import pydantic
import uvicorn

import agent as agent_module
import call as call_module
import log
import speaking_detector as speaking_detector_module
import audio_utils
import call_actions


# Load OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")


_SAMPLE_RATE = 8000  # Hz
_SILENCE_THRESHOLD = 3.0  # s

app = fastapi.FastAPI()
agent_wrapper = None


class AgentRequest(pydantic.BaseModel):
    phone: str
    request: str


@app.post("/agent")
async def agent_endpoint(data: AgentRequest):
    global agent_wrapper
    log.info(f"Agent endpoint hit, {data=}")
    agent_wrapper = AgentWrapper(data.phone, data.request)
    agent_wrapper.call()


@app.websocket("/ws/media")
async def websocket_media_endpoint(websocket: fastapi.WebSocket):
    await websocket.accept()

    try:
        await agent_wrapper.handle_media(websocket)
    except fastapi.WebSocketDisconnect:
        log.info("WebSocket disconnected")
    except Exception as e:
        log.error(f"WebSokcet error: {e}")


class AgentWrapper:
    def __init__(self, phone_number, user_request):
        self.agent = agent_module.HelplineAgent(user_request)
        self.sid = None
        self.phone_number = phone_number
    
    def call(self):
        self.sid = call_module.call(self.phone_number)

    def transcribe_audio_thread(self, buffer, queue, stream_id=None):
        """Threaded function to process and transcribe audio chunks."""
        thread_name = threading.current_thread().name
        try:
            # Convert from µ-law to 16-bit PCM
            log.info(f"[{stream_id}] [{thread_name}] Transcribing...")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                audio_utils.ulaw_to_wav_file(buffer, _SAMPLE_RATE, f)

                # Pass the file path (f.name) to the OpenAI API
                with open(f.name, "rb") as audio_file:
                    transcript = openai.audio.transcriptions.create(
                        model="gpt-4o-transcribe", file=audio_file, language="en"
                    )
                log.info(f"[{stream_id}] [{thread_name}] Transcript: {transcript.text}")

            action, arg = self.agent.get_action(transcript.text)

            if action == "send_dtfm":
                call_actions.send_dtmf_to_callee(self.sid, arg)
            elif action == "handoff":
                call_actions.send_handoff(self.sid)
            elif action == "end_call":
                call_actions.send_end_call(self.sid)

        except Exception as e:
            log.error(
                f"[{stream_id}] [{thread_name}] Error transcribing or getting action: {e}"
            )
        finally:
            # Save the file for debugging instead of deleting it
            debug_dir = "debug_audio"
            filename = (
                f"[{stream_id}] [{thread_name}] {transcript.text[:15]}.wav"
                if transcript and transcript.text
                else f.name
            )
            os.makedirs(debug_dir, exist_ok=True)
            shutil.move(f.name, os.path.join(debug_dir, filename))
            queue.task_done()  # Mark the task as done

    async def transcribe_audio(self, queue, stream_id=None):
        """Asynchronous task to manage transcription threads."""
        while True:
            buffer = await queue.get()  # Wait for the next audio chunk
            threading.Thread(
                target=self.transcribe_audio_thread, args=(buffer, queue, stream_id)
            ).start()

    async def capture_utterances(
        self, websocket, queue, record_audio=True, stream_id=None
    ):
        """Ingests audio from the websocket, chunking them up into utterances and sends
        them off for transcription and action.
        """
        full_buffer = bytearray()  # Buffer to accumulate audio chunks
        incremental_buffer = bytearray()
        full_call_audio = bytearray()
        speaking_detector = speaking_detector_module.SpeakingDetector(
            silence_threshold_ms=1000
        )

        try:
            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=3)
                    data = json.loads(message)
                    if not data.get("event") == "media":
                        continue

                    payload = data["media"]["payload"]
                    audio_chunk = base64.b64decode(payload)
                    incremental_buffer.extend(audio_chunk)

                    # Process the incremental buffer every second
                    if len(incremental_buffer) / _SAMPLE_RATE < 1.0:
                        continue

                    if record_audio:
                        full_call_audio.extend(incremental_buffer)

                    full_buffer.extend(incremental_buffer)
                    incremental_buffer.clear()

                    if speaking_detector.is_speaking(full_buffer):
                        continue

                    if speaking_detector.contains_speech(full_buffer):
                        log.info(
                            f"[{stream_id}] Silence after speech detected, transcribing"
                        )
                        await queue.put(bytes(full_buffer))
                        full_buffer.clear()
                    else:
                        log.info(
                            f"[{stream_id}] Silence without speech detected, clearing buffer"
                        )
                        full_buffer.clear()

                except asyncio.TimeoutError:
                    log.error(f"[{stream_id}] Call timed out")
        finally:
            if full_call_audio:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                wav_filename = f"full_audio/call_recording_{ts}.wav"
                audio_utils.ulaw_to_wav_file(
                    full_call_audio, _SAMPLE_RATE, wav_filename
                )
                log.info(f"[{stream_id}] Full call audio saved to {wav_filename}")

    async def handle_media(self, websocket):
        stream_id = str(uuid.uuid4())[:8]
        log.info(f"[{stream_id}] WebSocket connected")

        queue = Queue()  # Create a queue for audio chunks

        # Start the transcription task
        transcription_task = asyncio.create_task(
            self.transcribe_audio(queue, stream_id)
        )

        try:
            await self.capture_utterances(
                websocket, queue, record_audio=True, stream_id=stream_id
            )
        except websockets.exceptions.ConnectionClosed as e:
            log.info(f"[{stream_id}] WebSocket connection closed: {e}")
        finally:
            log.info(f"[{stream_id}] No more messages, closing")
            transcription_task.cancel()


if __name__ == "__main__":
    uvicorn.run("agent_server:app", host="0.0.0.0", port=8765)