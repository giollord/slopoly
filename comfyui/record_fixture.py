"""Development only: records one real ComfyUI run (HTTP /prompt + websocket messages + /history) as a test fixture.

    uv run python comfyui/record_fixture.py <input image name in ComfyUI> [comfyui url] > tests/fixtures/segment_run.json
"""
import json
import sys
import uuid

import httpx
from websockets.sync.client import connect

from slopoly.comfy import workflow

url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8188"
prompt = workflow.fill(workflow.load("segment-parts"), {"image": sys.argv[1], "prompt": "wheel"})
client_id = uuid.uuid4().hex
with httpx.Client(base_url=url) as http, connect(url.replace("http", "ws", 1) + f"/ws?clientId={client_id}") as ws:
    response = http.post("/prompt", json={"prompt": prompt, "client_id": client_id})
    response.raise_for_status()
    queued = response.json()
    messages = []
    for raw in ws:
        if not isinstance(raw, str):
            continue
        message = json.loads(raw)
        messages.append(message)
        data = message.get("data") or {}
        if message["type"] == "execution_success" or (
                message["type"] == "executing" and data.get("node") is None and data.get("prompt_id") == queued["prompt_id"]):
            break
    history = http.get(f"/history/{queued['prompt_id']}").json()
json.dump({"prompt": prompt, "queued": queued, "messages": messages, "history": history}, sys.stdout, indent=1)
