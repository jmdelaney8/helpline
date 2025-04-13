import os

import agent

from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
from twilio.rest import Client

_TWILIO_PHONE_NUMBER = "+18336411266"

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)


app = Flask(__name__)


    

@app.route("/handoff", methods=["POST"])
def handoff():
    """Placeholder endpoint for handling agent handoff."""
    # This could be used to notify the developer or trigger call bridging
    print("Agent has detected a human operator. Notify developer or bridge call here.")
    return "OK", 200

if __name__ == "__main__":
    call = client.calls.create(
        url="http://demo.twilio.com/docs/voice.xml",
        to="+13179184060",
        from_=_TWILIO_PHONE_NUMBER,
    )
    
    # app.run(port =5000)

