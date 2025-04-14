import os
import requests
import wave
import shutil
import array
import argparse

import agent as agent_module
import call

import asyncio
import websockets
import base64
import json
import openai
import tempfile

# Load OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

agent = None

def ulaw_to_pcm16(data):
    """Convert G.711 µ-law bytes to 16-bit PCM."""
    MULAW_MAX = 0x1FFF
    BIAS = 0x84

    exp_lut = [
        0, 132, 396, 924, 1980, 4092, 8316, 16764
    ]

    pcm_samples = array.array("h")
    for byte in data:
        byte = ~byte & 0xFF
        sign = byte & 0x80
        exponent = (byte & 0x70) >> 4
        mantissa = byte & 0x0F
        sample = exp_lut[exponent] + (mantissa << (exponent + 3))
        sample -= BIAS
        if sign != 0:
            sample = -sample
        pcm_samples.append(sample)
    return pcm_samples.tobytes()



async def handle_media(websocket):
    print("WebSocket connected")
    buffer = bytearray()

    try:
        while True:
            # Wait for a message or timeout to send a keep-alive ping
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                if data.get("event") == "media":
                    payload = data["media"]["payload"]
                    audio_chunk = base64.b64decode(payload)
                    buffer.extend(audio_chunk)

                    if len(buffer) > 16000 * 5:  # ~5 seconds of audio at 16kHz
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            try:
                               # Convert from µ-law to 16-bit PCM
                                pcm_audio = ulaw_to_pcm16(buffer)

                                with wave.open(f, "wb") as wav_file:
                                    wav_file.setnchannels(1)
                                    wav_file.setsampwidth(2)
                                    wav_file.setframerate(8000)
                                    wav_file.writeframes(pcm_audio)

                                # Pass the file path (f.name) to the OpenAI API
                                with open(f.name, "rb") as audio_file:
                                    transcript = openai.audio.transcriptions.create(
                                        model="gpt-4o-transcribe", file=audio_file, language="en"
                                    )
                                print("Transcript:", transcript.text)
                                action = agent.get_action(transcript.text)
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
                                os.makedirs(debug_dir, exist_ok=True)
                                shutil.move(f.name, os.path.join(debug_dir, os.path.basename(f.name)))
                        buffer = bytearray()
                
            except asyncio.TimeoutError:
                # Send a ping to keep the connection alive
                await websocket.ping()

    except websockets.exceptions.ConnectionClosed as e:
        print("WebSocket connection closed:", e)

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
