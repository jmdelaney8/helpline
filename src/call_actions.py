import requests

import log

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

def send_end_call(call_sid):
    log.info("ending call")
    url = "http://localhost:5050/end_call"
    payload = {"call_sid": call_sid}
    try:
        resp = requests.post(url, json=payload)
        log.info(f"End call response: {resp.json()}")
    except Exception as e:
        log.error(f"Failed to end call: {e}")
