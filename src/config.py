import os
import json

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/urls.json")

with open(_CONFIG_PATH) as f:
    _URLS = json.load(f)

APP_URL = _URLS["app"]
AGENT_SERVER_URL = _URLS["agent_server"]