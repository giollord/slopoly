"""The local page server behind the pick and view windows: loopback only, a random token in every path, workspace
files served only from inside the workspace."""

from __future__ import annotations

import json
import mimetypes
import secrets
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import config
from ..core import SlopolyError

STATIC = Path(__file__).parent / "static"
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("model/gltf-binary", ".glb")


class PageServer:
    """Serves ``page`` at ``/<token>/``, ``static/``, ``files/<workspace path>`` and a small JSON API:
    ``GET api/state`` (``state()``), ``POST api/choice`` (``choose(body)``), ``GET``/``POST api/prefs``."""

    def __init__(self, workspace_root: Path, page: str, state: Callable[[], dict],
                 choose: Callable[[dict], dict] | None = None):
        self.root, self.page, self.state, self.choose = workspace_root.resolve(), page, state, choose
        self.token = secrets.token_urlsafe(16)
        self.last_seen = 0.0
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # quiet
                pass

            def send(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def send_json(self, value, status: int = 200) -> None:
                self.send(status, json.dumps(value).encode("utf-8"), "application/json")

            def route(self) -> str | None:
                path = unquote(urlsplit(self.path).path)
                prefix = f"/{server.token}/"
                return path[len(prefix):] if path.startswith(prefix) else None

            def do_GET(self):
                rest = self.route()
                if rest is None:
                    return self.send(404, b"not found", "text/plain")
                server.last_seen = time.monotonic()
                if rest == "":
                    return self.send(200, (STATIC / server.page).read_bytes(), "text/html; charset=utf-8")
                if rest == "api/state":
                    try:
                        return self.send_json(server.state())
                    except SlopolyError as error:
                        return self.send_json(error.as_dict(), 500)
                if rest == "api/prefs":
                    return self.send_json(config.prefs())
                base, sub = (STATIC, rest[7:]) if rest.startswith("static/") else \
                    (server.root, rest[6:]) if rest.startswith("files/") else (None, None)
                if base is None:
                    return self.send(404, b"not found", "text/plain")
                path = server.safe(base, sub)
                if path is None:
                    return self.send(404, b"not found", "text/plain")
                self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

            def do_POST(self):
                rest = self.route()
                if rest is None:
                    return self.send(404, b"not found", "text/plain")
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                except ValueError:
                    return self.send_json({"error": "invalid JSON", "code": "bad_request"}, 400)
                if rest == "api/prefs":
                    config.save_prefs(body if isinstance(body, dict) else {})
                    return self.send_json({"ok": True})
                if rest == "api/choice" and server.choose:
                    try:
                        return self.send_json(server.choose(body))
                    except SlopolyError as error:
                        return self.send_json(error.as_dict(), 400)
                self.send(404, b"not found", "text/plain")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @staticmethod
    def safe(base: Path, sub: str) -> Path | None:
        """A file under ``base``, or None for anything outside it (``..``, absolute paths, links out)."""
        try:
            path = (base / sub).resolve()
        except (OSError, ValueError):
            return None
        if base.resolve() not in path.parents or not path.is_file():
            return None
        return path

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/{self.token}/"

    def __enter__(self) -> PageServer:
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.httpd.shutdown()
        self.httpd.server_close()
