import os

from flask import Flask, Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client

_TWILIO_PHONE_NUMBER = "+18336411266"

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)


app = Flask(__name__)


@app.route("/voice", methods=["POST"])
def voice():
    """Respond to Twilio with instructions to start bidirectional media streaming."""
    try:
        print("Voice endpoint hit")
        response = VoiceResponse()
        connect = response.connect()
        connect.stream(url="wss://d541-73-162-172-228.ngrok-free.app")

        return Response(str(response), mimetype="application/xml")
    except Exception as e:
        print("Exception in /voice:", e)
        raise e


@app.route("/handoff", methods=["POST"])
def handoff():
    """Placeholder endpoint for handling agent handoff."""
    # This could be used to notify the developer or trigger call bridging
    print("Agent has detected a human operator. Notify developer or bridge call here.")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)

