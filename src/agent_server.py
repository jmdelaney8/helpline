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
import datetime

import openai
import requests
import websockets

import agent as agent_module
import call as call_module
import log
import speaking_detector as speaking_detector_module
import utils

# Load OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

agent = None
sid = None

_SAMPLE_RATE = 8000  # Hz
_SILENCE_THRESHOLD = 3.0  # s


def send_dtmf_to_callee(call_sid, digits):
    url = "http://localhost:5050/send_dtmf"
    payload = {"call_sid": call_sid, "digits": digits}
    log.info(f"Sending dtmf: {call_sid=}, {digits=}")
    try:
        resp = requests.post(url, json=payload)
        log.info(f"DTMF send response: {resp.json()}")
    except Exception as e:
        log.error(f"Failed to send DTMF: {e}")


def send_handoff(call_sid):
    url = "http://localhost:5050/handoff"
    payload = {"call_sid": call_sid}

    try:
        resp = requests.post(url, json=payload)
        log.info(f"Handing off: {resp.json()}")
    except Exception as e:
        log.error(f"Failed to handoff: {e}")


def extract_dtmf(action):
    # Match 'press ' or 'enter ' followed by contiguous digits
    dtmf_match = re.search(r"(?:press|enter) (\d+)", action, re.IGNORECASE)
    if dtmf_match:
        return dtmf_match.group(1)
    return None

def end_call(call_sid):
    log.info("ending call")
    url = "http://localhost:5050/end_call"
    payload = {"call_sid": call_sid}
    try:
        resp = requests.post(url, json=payload)
        log.info(f"End call response: {resp.json()}")
    except Exception as e:
        log.error(f"Failed to end call: {e}")


def agent_action(transcript):
    """The agent acts upon the transcript."""
    action = agent.get_action(transcript.strip())
    log.info(f"Agent response: {action}")

    if digit := extract_dtmf(action):
        log.info(f"Sending dtmf {digit}")
        send_dtmf_to_callee(sid, digit)
    if "handoff" in action.lower():
        # Trigger handoff endpoint
        log.info("Handing off to user")
        send_handoff(sid)
    if "report" in action.lower():
        log.info(f"Reporting to user: {action}")
        end_call(sid)



def transcribe_audio_thread(buffer, queue, stream_id=None):
    """Threaded function to process and transcribe audio chunks."""
    thread_name = threading.current_thread().name
    try:
        # Convert from µ-law to 16-bit PCM
        log.info(f"[{stream_id}] [{thread_name}] Transcribing...")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            utils.ulaw_to_wav_file(buffer, _SAMPLE_RATE, f)

            # Pass the file path (f.name) to the OpenAI API
            with open(f.name, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=audio_file, language="en"
                )
            log.info(f"[{stream_id}] [{thread_name}] Transcript: {transcript.text}")

        agent_action(transcript.text)

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


async def transcribe_audio(queue, stream_id=None):
    """Asynchronous task to manage transcription threads."""
    while True:
        buffer = await queue.get()  # Wait for the next audio chunk
        threading.Thread(
            target=transcribe_audio_thread, args=(buffer, queue, stream_id)
        ).start()


async def keepalive_ping(websocket):
    """Sends a ping every 10 s to ensure the websocket stays alive."""
    while True:
        await websocket.ping()
        await asyncio.sleep(10)


async def capture_utterances(websocket, queue, record_audio=True, stream_id=None):
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
                message = await asyncio.wait_for(websocket.recv(), timeout=3)
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
            utils.ulaw_to_wav_file(full_call_audio, _SAMPLE_RATE, wav_filename)
            log.info(f"[{stream_id}] Full call audio saved to {wav_filename}")


async def handle_media(websocket):
    stream_id = str(uuid.uuid4())[:8]
    log.info(f"[{stream_id}] WebSocket connected")

    ping_task = asyncio.create_task(keepalive_ping(websocket))

    queue = Queue()  # Create a queue for audio chunks

    # Start the transcription task
    transcription_task = asyncio.create_task(transcribe_audio(queue, stream_id))

    try:
        await capture_utterances(
            websocket, queue, record_audio=True, stream_id=stream_id
        )
    except websockets.exceptions.ConnectionClosed as e:
        log.info(f"[{stream_id}] WebSocket connection closed: {e}")
    finally:
        log.info(f"[{stream_id}] No more messages, closing")
        ping_task.cancel()
        transcription_task.cancel()


async def main():
    global agent, sid

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()

    agent = agent_module.HelplineAgent()
    agent.handle_user_prompt(args.prompt)

    sid = call_module.call()

    async with websockets.serve(
        handle_media, "0.0.0.0", 8765, close_timeout=10, ping_interval=20, ping_timeout=20
    ):
        log.info("WebSocket server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # Run forever


asyncio.run(main())
