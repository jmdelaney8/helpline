import os

from twilio.rest import Client

import config
import log

_TWILIO_PHONE_NUMBER = "+18336411266"
_TARGET_NUMBER = "8772384373"  # "+13179184060"


account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(account_sid, auth_token)


def call(phone_number=None):
    call = client.calls.create(
        url=f"{config.APP_URL}/voice",
        to=phone_number if phone_number else _TARGET_NUMBER,
        from_=_TWILIO_PHONE_NUMBER,
    )
    log.info(f"Call SID: {call.sid}")
    return call.sid
