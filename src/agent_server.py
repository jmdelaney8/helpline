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

import openai
import requests
import websockets

import agent as agent_module
import call as call_module
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
    try:
        resp = requests.post(url, json=payload)
        print("DTMF send response:", resp.json())
    except Exception as e:
        print("Failed to send DTMF:", e)

def send_handoff(call_sid):
    url = "http://localhost:5050/handoff"
    payload = {"call_sid": call_sid}

    try:
        resp = requests.post(url, json=payload)
        print("Handing off:", resp.json())
    except Exception as e:
        print("Failed to handoff:", e)



def extract_dtmf(action):
    # Match 'press ' or 'enter ' followed by contiguous digits
    dtmf_match = re.search(r"(?:press|enter) (\d+)", action, re.IGNORECASE)
    if dtmf_match:
        return dtmf_match.group(1)
    return None

def agent_action(transcript):
    """The agent acts upon the transcript."""
    action = agent.get_action(transcript.strip())
    print("Agent response:", action)

    if digit := extract_dtmf(action):
        print(f"Sending dtmf {digit}")
        send_dtmf_to_callee(sid, digit)
    if "handoff" in action.lower():
        # Trigger handoff endpoint
        print("Handing off to user")
        send_handoff(sid)

def transcribe_audio_thread(buffer, queue):
    """Threaded function to process and transcribe audio chunks."""

    try:
        # Convert from µ-law to 16-bit PCM
        print("Transcribing...")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            utils.ulaw_to_wav_file(buffer, _SAMPLE_RATE, f)

            # Pass the file path (f.name) to the OpenAI API
            with open(f.name, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=audio_file, language="en"
                )
            print("Transcript:", transcript.text)

        agent_action(transcript.text)

    except Exception as e:
        print("Error transcribing or getting action:", e)
    finally:
        # Save the file for debugging instead of deleting it
        debug_dir = "debug_audio"
        filename = (
            f"{transcript.text[:15]}.wav" if transcript and transcript.text else f.name
        )
        os.makedirs(debug_dir, exist_ok=True)
        shutil.move(f.name, os.path.join(debug_dir, filename))
        queue.task_done()  # Mark the task as done


async def transcribe_audio(queue):
    """Asynchronous task to manage transcription threads."""
    while True:
        buffer = await queue.get()  # Wait for the next audio chunk
        threading.Thread(target=transcribe_audio_thread, args=(buffer, queue)).start()


async def capture_utterances(websocket, queue, record_audio=True):
    """Ingests audio from the websocket, chunking them up into utterances and sends
    them off for transcription and action.
    """
    buffer = bytearray()  # Buffer to accumulate audio chunks
    full_call_audio = bytearray()
    speaking_detector = speaking_detector_module.SpeakingDetector(
        silence_threshold_ms=1000
    )

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=30)
                data = json.loads(message)
                if not data.get("event") == "media":
                    continue

                payload = data["media"]["payload"]
                audio_chunk = base64.b64decode(payload)
                buffer.extend(audio_chunk)

                if record_audio:
                    full_call_audio.extend(audio_chunk)

                if speaking_detector.is_speaking(buffer):
                    continue

                if speaking_detector.contains_speech(buffer):
                    print("Silence after speech detected, transcribing")
                    await queue.put(bytes(buffer))
                    buffer.clear()
                else:
                    print("Silence without speech detected, clearing buffer")
                    buffer.clear()

            except asyncio.TimeoutError:
                print("Call timed out")
    finally:
        if full_call_audio:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_filename = f"full_audio/call_recording_{ts}.wav"
            utils.ulaw_to_wav_file(full_call_audio, _SAMPLE_RATE, wav_filename)
            print(f"Full call audio saved to {wav_filename}")


async def handle_media(websocket):
    print("WebSocket connected")
    queue = Queue()  # Create a queue for audio chunks

    # Start the transcription task
    asyncio.create_task(transcribe_audio(queue))

    try:
        await capture_utterances(websocket, queue, record_audio=True)
    except websockets.exceptions.ConnectionClosed as e:
        print("WebSocket connection closed:", e)

    print("No more messages, closing")


async def main():
    global agent, sid

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    args = parser.parse_args()

    agent = agent_module.HelplineAgent()
    agent.handle_user_prompt(args.prompt)

    sid = call_module.call()

    async with websockets.serve(handle_media, "0.0.0.0", 8765):
        print("WebSocket server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # Run forever


asyncio.run(main())
