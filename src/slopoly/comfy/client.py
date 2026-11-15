"""Client for the user's ComfyUI over its HTTP API: upload inputs, queue a prompt, follow it over the websocket,
download outputs. Nothing relies on a shared filesystem, so ComfyUI may run on another machine."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from websockets.sync.client import connect

from .. import config
from ..core import SlopolyError

SETUP_HINT = "run slopoly doctor; check that ComfyUI runs and comfyui.url is right (slopoly config set comfyui.url ...)"


class ComfyClient:
    def __init__(self, base_url: str, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.client_id = uuid.uuid4().hex
        self.http = httpx.Client(base_url=self.base_url, timeout=timeout)

    @classmethod
    def from_config(cls) -> ComfyClient:
        return cls(config.require("comfyui.url"))

    def get(self, path: str, **params) -> Any:
        try:
            response = self.http.get(path, params=params or None)
        except httpx.TransportError as error:
            raise SlopolyError("comfyui_unreachable", f"ComfyUI at {self.base_url} is not reachable: {error}",
                               SETUP_HINT) from None
        response.raise_for_status()
        return response.json()

    def system_stats(self) -> dict:
        return self.get("/system_stats")

    def object_info(self) -> dict:
        return self.get("/object_info")

    def models(self, folder: str) -> list[str]:
        return self.get(f"/models/{folder}")

    def upload(self, data: bytes, name: str, subfolder: str = "slopoly") -> str:
        """Uploads an input image; returns the name LoadImage takes."""
        try:
            response = self.http.post("/upload/image", files={"image": (name, data, "image/png")},
                                      data={"subfolder": subfolder, "type": "input", "overwrite": "true"})
        except httpx.TransportError as error:
            raise SlopolyError("comfyui_unreachable", f"ComfyUI at {self.base_url} is not reachable: {error}",
                               SETUP_HINT) from None
        response.raise_for_status()
        body = response.json()
        return f"{body['subfolder']}/{body['name']}" if body.get("subfolder") else body["name"]

    def run(self, prompt: dict[str, Any], on_progress: Callable[[float], None] | None = None,
            on_queued: Callable[[str], None] | None = None) -> dict[str, Any]:
        """Queues the API-format prompt and returns its history outputs ({node_id: {images: [...]}})."""
        ws_url = self.base_url.replace("http", "ws", 1) + f"/ws?clientId={self.client_id}"
        try:
            ws = connect(ws_url, max_size=None, open_timeout=30)
        except OSError as error:
            raise SlopolyError("comfyui_unreachable", f"ComfyUI at {self.base_url} is not reachable: {error}",
                               SETUP_HINT) from None
        with ws:
            response = self.http.post("/prompt", json={"prompt": prompt, "client_id": self.client_id})
            if response.status_code != 200:
                raise prompt_error(response)
            prompt_id = response.json()["prompt_id"]
            if on_queued:
                on_queued(prompt_id)
            self._follow(ws, prompt_id, len(prompt), on_progress)
        history = self.get(f"/history/{prompt_id}").get(prompt_id, {})
        return history.get("outputs", {})

    def _follow(self, ws, prompt_id: str, nodes: int, on_progress) -> None:
        done = 0
        for raw in ws:
            if not isinstance(raw, str):
                continue  # binary previews
            message = json.loads(raw)
            kind, data = message.get("type"), message.get("data") or {}
            if data.get("prompt_id") not in (None, prompt_id):
                continue
            if kind == "execution_error":
                raise SlopolyError("comfy_error", f"{data.get('node_type')}: {data.get('exception_message', '').strip()}")
            if kind == "execution_interrupted":
                raise SlopolyError("interrupted", "ComfyUI interrupted the run")
            if kind == "execution_success" or (kind == "executing" and data.get("node") is None):
                return
            if on_progress is None:
                continue
            if kind == "executed":
                done += 1
                on_progress(min(done / max(nodes, 1), 0.99))
            elif kind == "progress" and data.get("max"):
                on_progress(min((done + data["value"] / data["max"]) / max(nodes, 1), 0.99))

    def cancel(self, prompt_id: str) -> None:
        """Drops a queued prompt, or interrupts it when it is running."""
        try:
            self.http.post("/queue", json={"delete": [prompt_id]})
            running = self.get("/queue").get("queue_running", [])
            if any(len(item) > 1 and item[1] == prompt_id for item in running):
                self.http.post("/interrupt", json={"prompt_id": prompt_id})
        except (httpx.HTTPError, SlopolyError):
            pass

    def image(self, item: dict[str, Any]) -> bytes:
        response = self.http.get("/view", params={
            "filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")})
        response.raise_for_status()
        return response.content


def prompt_error(response: httpx.Response) -> SlopolyError:
    """Turns ComfyUI's validation error into a readable failure; missing models and nodes get their own codes."""
    try:
        body = response.json()
    except ValueError:
        return SlopolyError("comfy_rejected", f"ComfyUI rejected the workflow: {response.text[:500]}")
    error = body.get("error") or {}
    message = error.get("message") or ""
    if error.get("type") == "invalid_prompt" and "does not exist" in message:
        return SlopolyError("missing_node", f"ComfyUI lacks a node the workflow needs: {message}",
                            "run slopoly doctor to list missing nodes and how to install them")
    details, missing_model = [], False
    for node_id, node in (body.get("node_errors") or {}).items():
        for e in node.get("errors", []):
            text = f"{node.get('class_type', node_id)}: {e.get('message')} {e.get('details', '')}".strip()
            if e.get("type") == "value_not_in_list" and any(k in e.get("details", "") for k in ("_name", "model", "ckpt")):
                missing_model = True
                text = f"missing model file: {e.get('details', '').split(' not in ')[0]}"
            details.append(text)
    text = "; ".join(details) or message or "ComfyUI rejected the workflow"
    if missing_model:
        return SlopolyError("missing_model", text, "run slopoly doctor --fetch to download the missing models")
    return SlopolyError("comfy_rejected", text, "run slopoly doctor")
