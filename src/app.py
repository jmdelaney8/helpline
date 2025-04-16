import os

from flask import Flask, Response, request
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

import config
import log

_TWILIO_PHONE_NUMBER = "+18336411266"

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)


app = Flask(__name__)

hit_count = 0


@app.route("/voice", methods=["POST"])
def voice():
    """Respond to Twilio with instructions to start bidirectional media streaming."""
    global hit_count
    try:
        log.info("Voice endpoint hit")
        response = VoiceResponse()

        # TODO: REMOVE! Breaking everything. Figure out why we fail at the initial
        # language selection
        if hit_count < 1:
            response.play("", digits="1")
        hit_count += 1

        connect = response.connect()
        connect.stream(
            url=config.AGENT_SERVER_URL,
            status_callback=f"{config.APP_URL}/stream_status",
            status_callback_method="POST",
        )
        response.say("One moment please")

        return Response(str(response), mimetype="application/xml")
    except Exception as e:
        log.error("Exception in /voice:", e)
        raise e


@app.route("/stream_status", methods=["POST"])
def stream_status():
    """Handle status callbacks from Twilio <Stream>."""
    data = request.form.to_dict()
    log.info(f"Stream status callback received: {data}")
    return "OK", 200


@app.route("/send_dtmf", methods=["POST"])
def send_dtmf():
    """Send DTMF tones to the active call."""
    response = VoiceResponse()
    call_sid = request.json.get("call_sid")
    digits = request.json.get("digits")
    response.play("", digits=digits)
    response.redirect(f"{config.APP_URL}/voice", method="POST")
    log.info(response)
    client.calls(call_sid).update(twiml=response)
    if not call_sid or not digits:
        return {"error": "Missing call_sid or digits"}, 400

    try:
        log.info(f"Sent DTMF digits '{digits}' to call {call_sid}")
        return {}, 200
    except Exception as e:
        log.error("Error sending DTMF:", e)
        return {"error": str(e)}, 500


@app.route("/handoff", methods=["POST"])
def handoff():
    """Placeholder endpoint for handling agent handoff."""
    call_sid = request.json.get("call_sid")
    human_phone = "3179184060"
    if not call_sid or not human_phone:
        return {"error": "Missing call_sid or HUMAN_PHONE_NUMBER"}, 400

    response = VoiceResponse()
    response.dial(human_phone)

    try:
        client.calls(call_sid).update(twiml=str(response))
        log.info(f"Handed off call {call_sid} to human at {human_phone}")
        return "OK", 200
    except Exception as e:
        log.error(f"Error during handoff: {e}")
        return {"error": str(e)}, 500


@app.route("/end_call", methods=["POST"])
def end_call():
    """End the active call."""
    log.info("Recieved request to end call")
    call_sid = request.json.get("call_sid")
    if not call_sid:
        return {"error": "Missing call_sid"}, 400

    try:
        client.calls(call_sid).update(status="completed")
        log.info(f"Ended call {call_sid}")
        return "OK", 200
    except Exception as e:
        log.error(f"Error ending call: {e}")
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
