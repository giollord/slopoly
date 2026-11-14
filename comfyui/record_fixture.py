"""Development only: records one real ComfyUI run (HTTP /prompt + websocket messages + /history) as a test fixture.
Copy into the comfyui container and run: python record_fixture.py <input image name> > containers/comfyui/tests/fixtures/segment_run.json"""
import asyncio, json, sys, uuid
import httpx, websockets
sys.path.insert(0, "/opt/slopoly")
import workflow
from pathlib import Path

async def main():
    prompt = workflow.fill(workflow.load(Path("/opt/slopoly/workflows"), "segment-parts"), {"image": sys.argv[1], "prompt": "wheel"})
    client_id = uuid.uuid4().hex
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8188") as http, websockets.connect(f"ws://127.0.0.1:8188/ws?clientId={client_id}") as ws:
        response = await http.post("/prompt", json={"prompt": prompt, "client_id": client_id})
        response.raise_for_status()
        queued = response.json()
        messages = []
        async for raw in ws:
            if not isinstance(raw, str): continue
            m = json.loads(raw); messages.append(m)
            d = m.get("data") or {}
            if m["type"] == "execution_success" or (m["type"] == "executing" and d.get("node") is None and d.get("prompt_id") == queued["prompt_id"]): break
        history = (await http.get(f"/history/{queued['prompt_id']}")).json()
    json.dump({"prompt": prompt, "queued": queued, "messages": messages, "history": history}, sys.stdout, indent=1)

asyncio.run(main())
