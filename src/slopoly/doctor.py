"""``slopoly doctor``: checks ComfyUI (reachable, nodes, models), Blender (found, version, build libraries) and the
settings, with a fix for each failure. ``--fetch`` downloads missing models and installs the Blender libraries."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import yaml

from . import blender, config
from .comfy import workflow
from .comfy.client import ComfyClient
from .core import SlopolyError

MODELS_FILE = Path(__file__).parent / "comfy" / "models.yaml"
NODES_HINT = ("update ComfyUI to a recent version (tested with 0.38.0): the workflows use its core Mage-Flow-Edit, "
              "TripoSplat, TRELLIS.2, background removal and SAM 3 nodes; see the skill's comfyui-setup reference")


def required_models() -> list[dict]:
    return yaml.safe_load(MODELS_FILE.read_text(encoding="utf-8"))["models"]


def required_nodes() -> dict[str, list[str]]:
    """Node class -> the workflows that use it, from the shipped workflow files."""
    nodes: dict[str, list[str]] = {}
    for name in workflow.names():
        for cls in workflow.class_types(workflow.load(name)):
            nodes.setdefault(cls, []).append(name)
    return nodes


def check(name: str, ok: bool, detail: str, fix: str | None = None, **extra) -> dict:
    out = {"check": name, "ok": ok, "detail": detail}
    if not ok and fix:
        out["fix"] = fix
    return out | {k: v for k, v in extra.items() if v is not None}


def comfy_checks(client: ComfyClient, models_dir: str | None) -> tuple[list[dict], list[dict]]:
    """Checks and the list of missing models."""
    try:
        stats = client.system_stats()
    except SlopolyError as error:
        missing = [m for m in required_models() if not (models_dir and (Path(models_dir) / m["subfolder"] / m["file"]).exists())]
        return [check("comfyui", False, error.message, f"start ComfyUI, or run slopoly config set comfyui.url <url>")], missing
    version = (stats.get("system") or {}).get("comfyui_version", "unknown")
    out = [check("comfyui", True, f"reachable at {client.base_url} (ComfyUI {version})")]
    available = set(client.object_info())
    lacking = {cls: wfs for cls, wfs in required_nodes().items() if cls not in available}
    out.append(check("comfyui nodes", not lacking,
                     "all nodes of the shipped workflows are available" if not lacking else
                     "missing: " + ", ".join(f"{cls} (used by {', '.join(w)})" for cls, w in sorted(lacking.items())),
                     NODES_HINT, missing=sorted(lacking) or None))
    listed: dict[str, set[str]] = {}
    missing = []
    for model in required_models():
        folder = model["subfolder"]
        if folder not in listed:
            try:
                listed[folder] = set(client.models(folder))
            except (httpx.HTTPError, SlopolyError):
                listed[folder] = set()
        if model["file"] not in listed[folder]:
            missing.append(model)
    fix = ("run slopoly doctor --fetch" if models_dir else
           "run slopoly config set comfyui.models_dir <your ComfyUI models folder>, then slopoly doctor --fetch")
    out.append(check("comfyui models", not missing,
                     "all required models are installed" if not missing else
                     f"{len(missing)} missing: " + ", ".join(f"{m['subfolder']}/{m['file']}" for m in missing),
                     fix, missing=[{"file": m["file"], "subfolder": m["subfolder"], "url": m["url"],
                                    "size_gb": m["size_gb"]} for m in missing] or None))
    return out, missing


def blender_checks() -> list[dict]:
    blender.find.cache_clear()
    try:
        found = blender.find()
    except SlopolyError as error:
        return [check("blender", False, error.message, error.hint)]
    out = [check("blender", True, f"Blender {found.version_text} at {found.path.as_posix()}")]
    missing = blender.missing_libs(found)
    out.append(check("blender libraries", not missing,
                     f"installed in {found.libs.as_posix()}" if not missing else f"missing: {', '.join(missing)}",
                     "run slopoly doctor --fetch"))
    return out


def download(model: dict, models_dir: Path) -> Path:
    """Downloads one model into <models_dir>/<subfolder>/, resuming a partial .part file."""
    target = models_dir / model["subfolder"] / model["file"]
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    done = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={done}-"} if done else {}
    with httpx.stream("GET", model["url"], headers=headers, follow_redirects=True, timeout=60) as response:
        if response.status_code == 416:  # already complete
            part.rename(target)
            return target
        response.raise_for_status()
        mode = "ab" if done and response.status_code == 206 else "wb"
        total = int(response.headers.get("content-length", 0)) + (done if mode == "ab" else 0)
        written = done if mode == "ab" else 0
        last = -1
        with part.open(mode) as out:
            for chunk in response.iter_bytes(1 << 20):
                out.write(chunk)
                written += len(chunk)
                if total and (pct := written * 100 // total) != last and pct % 5 == 0:
                    last = pct
                    print(f"  {model['file']}: {pct}%", file=sys.stderr, flush=True)
    part.replace(target)
    return target


def fetch(missing: list[dict], models_dir: str | None) -> dict:
    out: dict = {}
    if missing:
        if not models_dir:
            out["models"] = {"downloaded": [], "note": "comfyui.models_dir is not configured; nothing was downloaded",
                             "fix": "slopoly config set comfyui.models_dir <your ComfyUI models folder>",
                             "missing": [{"subfolder": m["subfolder"], "file": m["file"], "url": m["url"]} for m in missing]}
        else:
            root = Path(models_dir)
            if not root.is_dir():
                raise SlopolyError("bad_models_dir", f"comfyui.models_dir {models_dir} is not a folder")
            total = sum(m["size_gb"] for m in missing)
            print(f"downloading {len(missing)} model(s), about {total:.1f} GB, into {root.as_posix()}",
                  file=sys.stderr, flush=True)
            downloaded, failed = [], []
            for model in missing:
                try:
                    downloaded.append(download(model, root).as_posix())
                except httpx.HTTPError as error:
                    failed.append({"file": model["file"], "error": str(error)})
            out["models"] = {"downloaded": downloaded, "failed": failed}
    blender.find.cache_clear()
    try:
        found = blender.find()
        if blender.missing_libs(found):
            out["blender_libraries"] = blender.install_libs(found)
    except SlopolyError as error:
        out["blender_libraries"] = {"skipped": error.message}
    return out


WINDOW_FILES = ("pick.html", "view.html", "review.html", "style.css", "theme.js", "viewer3d.js",
                "three/build/three.module.min.js", "three/examples/jsm/controls/OrbitControls.js")


def window_check() -> dict:
    """The pages and scripts of the pick, view and review windows, which an incomplete install can miss."""
    static = Path(__file__).parent / "windows" / "static"
    lacking = [name for name in WINDOW_FILES if not (static / name).is_file()]
    return check("window files", not lacking, "the pick, view and review pages are installed" if not lacking else
                 "missing: " + ", ".join(lacking), "reinstall slopoly: uv tool install --force --reinstall <source>")


def doctor(fetch_missing: bool = False) -> dict:
    models_dir = config.get("comfyui.models_dir")
    checks, missing = comfy_checks(ComfyClient(config.require("comfyui.url"), timeout=30), models_dir)
    checks += blender_checks()
    checks.append(window_check())
    checks.append(check("settings", True, f"stored in {config.describe()['file']}",
                        models_dir=models_dir or "(not set: doctor --fetch cannot download models)"))
    result = {"ok": all(c["ok"] for c in checks), "checks": checks}
    if fetch_missing:
        result["fetched"] = fetch(missing, models_dir)
        after, _ = comfy_checks(ComfyClient(config.require("comfyui.url"), timeout=30), models_dir)
        checks = [c for c in checks if not c["check"].startswith("comfyui")] + after
        checks = [c for c in checks if not c["check"].startswith("blender")] + blender_checks()
        result.update(ok=all(c["ok"] for c in checks), checks=checks)
    return result
