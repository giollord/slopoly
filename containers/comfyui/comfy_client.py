"""Minimal client for the local headless ComfyUI: queue a prompt, follow it over the websocket, fetch outputs."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import websockets

from slopoly_worker import JobFailed


class ComfyClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = uuid.uuid4().hex
        self.http = httpx.AsyncClient(base_url=self.base_url, timeout=60)

    async def wait_ready(self, timeout: float = 900) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            try:
                if (await self.http.get("/system_stats")).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            if asyncio.get_running_loop().time() > deadline:
                raise RuntimeError("ComfyUI did not start")
            await asyncio.sleep(1)

    async def run(self, prompt: dict[str, Any], on_progress: Callable[[float], Awaitable[None]] | None = None) -> dict[str, Any]:
        """Queues the API-format prompt and returns its history outputs ({node_id: {images: [...]}})."""
        ws_url = self.base_url.replace("http", "ws", 1) + f"/ws?clientId={self.client_id}"
        async with websockets.connect(ws_url, max_size=None) as ws:
            response = await self.http.post("/prompt", json={"prompt": prompt, "client_id": self.client_id})
            if response.status_code != 200:
                raise prompt_error(response)
            prompt_id = response.json()["prompt_id"]
            try:
                await self._follow(ws, prompt_id, len(prompt), on_progress)
            except asyncio.CancelledError:
                await self.interrupt(prompt_id)
                raise
        history = (await self.http.get(f"/history/{prompt_id}")).json().get(prompt_id, {})
        return history.get("outputs", {})

    async def _follow(self, ws, prompt_id: str, nodes: int, on_progress) -> None:
        done = 0
        async for raw in ws:
            if not isinstance(raw, str):
                continue  # binary previews
            message = json.loads(raw)
            kind, data = message.get("type"), message.get("data") or {}
            if data.get("prompt_id") not in (None, prompt_id):
                continue
            if kind == "execution_error":
                raise JobFailed(f"{data.get('node_type')}: {data.get('exception_message', '').strip()}", "comfy_error")
            if kind == "execution_interrupted":
                raise JobFailed("ComfyUI interrupted the run.", "interrupted")
            if kind == "execution_success" or (kind == "executing" and data.get("node") is None):
                return
            if on_progress is None:
                continue
            if kind == "executed":
                done += 1
                await on_progress(min(done / max(nodes, 1), 0.99))
            elif kind == "progress" and data.get("max"):
                await on_progress(min((done + data["value"] / data["max"]) / max(nodes, 1), 0.99))

    async def interrupt(self, prompt_id: str) -> None:
        try:
            await self.http.post("/queue", json={"delete": [prompt_id]})
            await self.http.post("/interrupt", json={"prompt_id": prompt_id})
        except httpx.HTTPError:
            pass

    async def image(self, item: dict[str, Any]) -> bytes:
        response = await self.http.get("/view", params={
            "filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")})
        response.raise_for_status()
        return response.content


def prompt_error(response: httpx.Response) -> JobFailed:
    """Turns ComfyUI's validation error into a readable failure; missing model files get their own code."""
    try:
        body = response.json()
    except ValueError:
        return JobFailed(f"ComfyUI rejected the workflow: {response.text[:500]}", "comfy_rejected")
    details = []
    missing_model = False
    for node_id, error in (body.get("node_errors") or {}).items():
        for e in error.get("errors", []):
            text = f"{error.get('class_type', node_id)}: {e.get('message')} {e.get('details', '')}".strip()
            if e.get("type") == "value_not_in_list" and any(k in e.get("details", "") for k in ("_name", "model", "ckpt")):
                missing_model = True
                text = f"Missing model file: {e.get('details', '').split(' not in ')[0]} (see comfyui/README.md)"
            details.append(text)
    message = "; ".join(details) or (body.get("error") or {}).get("message") or "ComfyUI rejected the workflow."
    return JobFailed(message, "missing_model" if missing_model else "comfy_rejected")
