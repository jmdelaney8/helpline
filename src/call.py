import os

from twilio.rest import Client

_TWILIO_PHONE_NUMBER = "+18336411266"

_TARGET_NUMBER = "8772384373"  # "+13179184060"

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)

def call():
    call = client.calls.create(
        url="https://cd69-73-162-172-228.ngrok-free.app/voice",  # Replace with your server's public URL
        to=_TARGET_NUMBER,
        from_=_TWILIO_PHONE_NUMBER,
    )
    print("Call SID:", call.sid)
    return call.sid