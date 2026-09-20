import json
import requests

API_ENDPOINT = "http://127.0.0.1:8000/api/v1/chat/message"


def stream_chat(payload: dict):
    """Sendet den Request und yieldet geparste JSON-Chunks aus dem SSE-Stream."""
    with requests.post(API_ENDPOINT, json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()

        for line in r.iter_lines():
            if not line:
                continue

            decoded = line.decode("utf-8").strip()
            if not decoded.startswith("data:"):
                continue

            data_str = decoded[5:].strip()
            if data_str == "[DONE]" or '"status": "done"' in data_str:
                continue

            try:
                yield json.loads(data_str)
            except json.JSONDecodeError:
                continue