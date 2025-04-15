import os
import requests
import shutil
import argparse
import threading
import datetime

import agent as agent_module
import call
import utils
import speaking_detector as speaking_detector_module

import asyncio
from asyncio import Queue
import websockets
import base64
import json
import openai
import tempfile

# Load OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

agent = None

_SAMPLE_RATE = 8000  # Hz
_SILENCE_DURATION = 0.0  # s
_SILENCE_THRESHOLD = 3.0  # s


def transcribe_audio_thread(buffer, queue):
    """Threaded function to process and transcribe audio chunks."""

    try:
        # Convert from µ-law to 16-bit PCM
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            utils.ulaw_to_wav_file(buffer, _SAMPLE_RATE, f)

            # Pass the file path (f.name) to the OpenAI API
            with open(f.name, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=audio_file, language="en"
                )
            print("Transcript:", transcript.text)

            action = agent.get_action(transcript.text.strip())
            print("Agent response:", action)
            if "handoff" in action.lower():
                # Trigger handoff endpoint
                print("Handing off to user")
                requests.post("http://localhost:5050/handoff")

    except Exception as e:
        print("Error transcribing or getting action:", e)
    finally:
        # Save the file for debugging instead of deleting it
        debug_dir = "debug_audio"
        filename = f"{transcript.text}.wav" if transcript and transcript.text else f.name
        os.makedirs(debug_dir, exist_ok=True)
        shutil.move(f.name, os.path.join(debug_dir, filename))
        queue.task_done()  # Mark the task as done


async def transcribe_audio(queue):
    """Asynchronous task to manage transcription threads."""
    while True:
        # print(f"{time.time()} | Waiting for audio chunk in queue")
        buffer = await queue.get()  # Wait for the next audio chunk
        # print(f"{time.time()} | Audio chunk retrieved from queue")
        threading.Thread(target=transcribe_audio_thread, args=(buffer, queue)).start()


async def handle_media(websocket):
    print("WebSocket connected")
    queue = Queue()  # Create a queue for audio chunks
    buffer = bytearray()  # Buffer to accumulate audio chunks

    speaking_detector = speaking_detector_module.SpeakingDetector(
        silence_threshold_ms=1000
    )

    RECORD_CALL_AUDIO = True  # Set to False to disable full call recording
    full_call_audio = bytearray()

    # Start the transcription task
    asyncio.create_task(transcribe_audio(queue))

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                if data.get("event") == "media":
                    payload = data["media"]["payload"]
                    audio_chunk = base64.b64decode(payload)
                    buffer.extend(audio_chunk)

                    if RECORD_CALL_AUDIO:
                        full_call_audio.extend(audio_chunk)

                    if not speaking_detector.is_speaking(buffer):
                        if speaking_detector.contains_speech(buffer):
                            print("Silence after speech detected, transcribing")
                            await queue.put(bytes(buffer))
                            buffer.clear()
                        else:
                            print("Silence without speech detected, clearing buffer")
                            buffer.clear()

            except asyncio.TimeoutError:
                # Send a ping to keep the connection alive
                await websocket.ping()

    except websockets.exceptions.ConnectionClosed as e:
        print("WebSocket connection closed:", e)

    # --- Save full call audio to file ---
    if RECORD_CALL_AUDIO and full_call_audio:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_filename = f"full_audio/call_recording_{ts}.wav"
        utils.ulaw_to_wav_file(full_call_audio, _SAMPLE_RATE, wav_filename)
        print(f"Full call audio saved to {wav_filename}")
    # --- End save ---

    print("No more messages, closing")


async def main():
    global agent

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()

    agent = agent_module.HelplineAgent()
    agent.handle_user_prompt(args.prompt)

    call.call()

    async with websockets.serve(handle_media, "0.0.0.0", 8765):
        print("WebSocket server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # Run forever


asyncio.run(main())
