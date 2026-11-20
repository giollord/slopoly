"""Machine settings: ComfyUI URL and models folder, Blender path. Stored in the user's config folder, never in the
workspace; each can be overridden by an environment variable (SLOPOLY_COMFYUI_URL, ...)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import platformdirs

from .core import SlopolyError, read_yaml, write_atomic, write_yaml

SETTINGS = {
    "comfyui.url": ("http://127.0.0.1:8188", "URL of your ComfyUI"),
    "comfyui.models_dir": (None, "your ComfyUI's models folder, for slopoly doctor --fetch"),
    "blender.path": (None, "path of the Blender executable (found automatically when unset)"),
    "images.model": ("krea2", "image model for anchors and heroes: krea2 (Krea 2 Turbo; its licence allows commercial "
                              "use only under $1M yearly revenue, with content filtering) or z-image-turbo (Apache "
                              "2.0, no style references)"),
}


def config_dir() -> Path:
    return Path(os.environ.get("SLOPOLY_CONFIG_DIR") or platformdirs.user_config_dir("slopoly", appauthor=False))


def data_dir() -> Path:
    return Path(os.environ.get("SLOPOLY_DATA_DIR") or platformdirs.user_data_dir("slopoly", appauthor=False))


def _file() -> Path:
    return config_dir() / "config.yaml"


def _stored() -> dict:
    return (read_yaml(_file()) or {}) if _file().exists() else {}


def env_name(key: str) -> str:
    return "SLOPOLY_" + key.replace(".", "_").upper()


def get(key: str) -> str | None:
    if key not in SETTINGS:
        raise SlopolyError("unknown_setting", f"unknown setting {key!r}", settings=list(SETTINGS))
    return os.environ.get(env_name(key)) or _stored().get(key) or SETTINGS[key][0]


def set_(key: str, value: str | None) -> None:
    get(key)  # validates the key
    stored = _stored()
    if value in (None, ""):
        stored.pop(key, None)
    else:
        stored[key] = value
    write_yaml(_file(), stored)


def describe() -> dict:
    stored = _stored()
    return {"file": _file().as_posix(),
            "settings": {k: {"value": get(k), "source": "env" if os.environ.get(env_name(k)) else
                             "config" if k in stored else "default", "about": about}
                         for k, (_, about) in SETTINGS.items()}}


def require(key: str) -> str:
    value = get(key)
    if not value:
        raise SlopolyError("missing_setting", f"setting {key} is not configured",
                           f"run slopoly config set {key} <value> (or set {env_name(key)})")
    return value


def prefs() -> dict:
    path = config_dir() / "viewer.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_prefs(values: dict) -> None:
    write_atomic(config_dir() / "viewer.json", json.dumps(values))
