"""Pick and view windows (see interaction-windows). Both run as detached jobs: a native pywebview window on the local
page server, or the default browser when no native window can be opened (or SLOPOLY_WINDOW=browser)."""

from __future__ import annotations

import os
import threading
import time
import webbrowser
from pathlib import Path

from .. import jobs
from .. import models as m
from ..core import SlopolyError, load
from ..workspace import Asset, ImageRef, Variant, Workspace, check_name, images, new_variant, set_reference
from .server import PageServer

BROWSER_IDLE = 30  # seconds without a request from the page before a browser-tab window counts as closed


# --- selection (shared by the pick window and `slopoly pick --set`) -----------------------------------------------

def variant_names(asset: Asset, count: int, first: str | None = None) -> list[str]:
    """Suggested variant names for ``count`` picked heroes: ``first`` when given (a pick that replaces that
    variant's reference, e.g. after gen revise), else the default variant while it has no reference; then
    variant_2, variant_3, ... that don't exist yet."""
    names, n = [], 2
    default = asset.meta.default_variant
    taken = {v.name for v in asset.variants()}
    if count and first:
        names.append(first)
    elif count and (default not in taken or not asset.variant(default).meta.reference):
        names.append(default)
    while len(names) < count:
        if f"variant_{n}" not in taken:
            names.append(f"variant_{n}")
        n += 1
    return names


def pick_hero(asset: Asset, hero: ImageRef, variant_name: str) -> dict:
    """Makes the hero the reference of the named variant, creating the variant when it doesn't exist."""
    check_name(variant_name, "variant")
    if (asset.root / "variants" / variant_name / "variant.yaml").exists():
        return set_reference(asset.variant(variant_name), hero)
    variant = new_variant(asset, variant_name, hero=hero)
    return {"variant": variant.address, "reference": hero.path.name, "created": True}


def choose(ws: Workspace, shown: list[ImageRef], picked: list[tuple[ImageRef, str | None]]) -> dict:
    """Applies a pick: picked anchors are marked picked, each picked hero becomes the reference of its variant (a new
    variant when the name is new), and every shown image that wasn't picked is rejected (moved to rejected/)."""
    names = [name for ref, name in picked if ref.asset is not None]
    if len(names) != len(set(names)):
        raise SlopolyError("duplicate_variant", "each picked hero needs its own variant name")
    outcome: dict = {"picked": [], "variants": [], "rejected": []}
    chosen = {ref.path for ref, _ in picked}
    for ref, name in picked:
        if ref.asset is None:
            outcome["picked"].append(ws.rel(ref.restore("picked").path))
            continue
        if not name:
            raise SlopolyError("variant_name_required", f"name the variant for {ref.path.name}")
        result = pick_hero(ref.asset, ref, name)
        outcome["picked"].append(ws.rel(ref.asset.hero(ref.path.name).path))
        outcome["variants"].append(result)
        if "rejected" in result:
            outcome["rejected"].append(result.pop("rejected"))
    for ref in shown:
        if ref.path not in chosen and not ref.rejected and not ref.variants:
            outcome["rejected"].append(ws.rel(ref.reject().path))
    return {k: v for k, v in outcome.items() if v}


# --- showing a page ----------------------------------------------------------------------------------------------

class CloseGuard:
    """Asks before a window with unsent work closes. The page reports whether it has any (``api/dirty``); when the
    user closes the native window, the page is asked (``askClose()``) and answers by sending, or by closing anyway
    (``api/close``). A browser tab asks with its own leave prompt instead."""

    def __init__(self):
        self.dirty = False
        self.discard = threading.Event()

    def routes(self) -> dict:
        return {"api/dirty": self.set_dirty, "api/close": self.close}

    def set_dirty(self, body: dict) -> dict:
        self.dirty = bool(body.get("dirty"))
        return {"dirty": self.dirty}

    def close(self, _body: dict) -> dict:
        self.discard.set()
        return {"closing": True}


def show(server: PageServer, title: str, done: threading.Event, context: jobs.JobContext, size=(1280, 860),
         guard: CloseGuard | None = None) -> str:
    """Shows the page until ``done`` is set, the window is closed or the job is cancelled; returns how it was shown."""
    discarded = guard.discard if guard else threading.Event()
    context.update(message=f"window open (if none appeared, browse {server.url})")
    if os.environ.get("SLOPOLY_WINDOW") != "browser":
        try:
            import webview

            window = webview.create_window(title, server.url, width=size[0], height=size[1])

            def closing():
                if guard is None or done.is_set() or discarded.is_set() or not guard.dirty:
                    return True
                # the page asks; evaluate_js waits for the GUI thread, which is busy closing, so it runs apart
                threading.Thread(target=window.evaluate_js, args=("window.askClose && window.askClose()",),
                                 daemon=True).start()
                return False
            window.events.closing += closing

            def watch():
                while not done.wait(0.5) and not discarded.is_set():
                    try:
                        context.check()
                    except (jobs.Cancelled, SlopolyError):
                        break
                window.destroy()
            threading.Thread(target=watch, daemon=True).start()
            webview.start()
            return "window"
        except Exception as error:  # no GUI backend (headless, missing GTK/Qt, ...): fall back to the browser
            print(f"native window unavailable ({type(error).__name__}: {error}); using the browser", flush=True)
    context.update(message=f"open in your browser: {server.url}")
    webbrowser.open(server.url)
    started = time.monotonic()
    while not done.wait(0.5) and not discarded.is_set():  # the page polls its state; a tab that stopped polling was closed
        context.check()
        if server.last_seen and time.monotonic() - server.last_seen > BROWSER_IDLE:
            break
        if not server.last_seen and time.monotonic() - started > 300:
            break
    return "browser"


def url_of(ws: Workspace, path: Path) -> str:
    stamp = int(path.stat().st_mtime) if path.exists() else 0
    return f"files/{path.resolve().relative_to(ws.root).as_posix()}?v={stamp}"


# --- pick --------------------------------------------------------------------------------------------------------

def start_pick(ws: Workspace, spec: dict) -> dict:
    pack = ws.pack(spec["pack"])
    if not spec.get("question") and not pick_images(ws, spec):
        raise SlopolyError("nothing_to_pick", "there are no undecided or picked images to pick from")
    return with_address(pack, jobs.start(pack, "pick", spec.get("target") or pack.name, spec))


def pick_images(ws: Workspace, spec: dict) -> list[tuple[ImageRef, m.Image]]:
    """The images to choose from: undecided ones, picked anchors (picked heroes are references, shown apart), and
    rejected ones when asked."""
    states = ("undecided", "picked", "rejected") if spec.get("show_rejected") else ("undecided", "picked")
    if spec.get("paths"):
        refs = [ws.image(p) for p in spec["paths"]]
        found = [(r, r.meta) for r in refs if r.meta.state in states]
    else:
        pack = ws.pack(spec["pack"])
        folder = pack.anchors_dir if spec["set"] == "anchors" else ws.target(spec["target"]).asset.heroes_dir
        found = [(ws.image(ws.rel(p)), meta) for p, meta in images(folder, states)]
    return [(r, meta) for r, meta in found if not r.variants]


def references(ws: Workspace, spec: dict) -> list[dict]:
    """The asset's current references (heroes picked earlier), for display."""
    if spec.get("set") != "heroes":
        return []
    asset = ws.target(spec["target"]).asset
    return [{"variant": v.name, "name": ref.path.name, "url": url_of(ws, ref.path)}
            for v in asset.variants() if (ref := v.reference) and ref.path.exists()]


def pick_state(ws: Workspace, spec: dict) -> dict:
    found = pick_images(ws, spec)
    items = [{"path": ws.rel(ref.path), "url": url_of(ws, ref.path), "name": ref.path.name, "state": meta.state,
              "kind": meta.kind, "prompt": meta.prompt, "seed": meta.seed} for ref, meta in found]
    heroes = spec.get("set") == "heroes"
    asset = ws.target(spec["target"]).asset if heroes else None
    return {"title": spec.get("title") or "Pick", "question": spec.get("question"), "options": spec.get("options") or [],
            "limit": spec.get("limit"), "images": items, "heroes": heroes, "references": references(ws, spec),
            "variants": [v.name for v in asset.variants()] if asset else [],
            "replacing": spec.get("for"),
            "suggested": variant_names(asset, len(items), spec.get("for")) if asset else []}


@jobs.kind("pick")
def pick(context: jobs.JobContext) -> dict:
    ws, spec = context.ws, context.inputs
    done, outcome = threading.Event(), {}

    def on_choice(body: dict) -> dict:
        if done.is_set():
            return outcome
        picks = [p if isinstance(p, dict) else {"path": p} for p in body.get("picked") or []]
        if spec.get("limit") and len(picks) > int(spec["limit"]):
            raise SlopolyError("too_many", f"pick at most {spec['limit']}")
        if spec.get("options") and body.get("option") not in spec["options"]:
            raise SlopolyError("option_required", "choose one of the options")
        shown = [ref for ref, _ in pick_images(ws, spec)]
        result = choose(ws, shown, [(ws.image(p["path"]), (p.get("variant") or "").strip() or None) for p in picks])
        result |= {"note": (body.get("note") or "").strip() or None, "option": body.get("option")}
        outcome.update({k: v for k, v in result.items() if v is not None})
        done.set()
        return outcome

    with PageServer(ws.root, "pick.html", lambda: pick_state(ws, spec), on_choice) as server:
        how = show(server, spec.get("title") or "Slopoly: pick", done, context)
    if not done.is_set():
        raise jobs.Cancelled()
    return outcome | {"shown_in": how}


# --- view --------------------------------------------------------------------------------------------------------

def view_state(ws: Workspace, spec: dict) -> dict:
    target = ws.target(spec["target"])
    pack = target.pack
    textures = {p.stem: url_of(ws, p) for p in sorted(pack.palette_dir.glob("*.png"))} if pack.palette_dir.is_dir() else {}
    if target.scene:
        from ..workspace import build_dirs
        builds = build_dirs(target.scene.builds_dir)
        if not builds:
            raise SlopolyError("not_built", f"scene {target.scene.name!r} has no build", "run slopoly scene build")
        number, folder = builds[-1]
        report = _json(folder / "report.json")
        return {"title": f"{target.scene.address} (build {number})", "kind": "scene", "build": number,
                "model": url_of(ws, folder / "scene.glb"), "textures": textures, "report": report}
    variant: Variant = target.need_variant()
    number = spec.get("build") or variant.meta.current
    if number is None:
        raise SlopolyError("not_built", f"{variant.address} has no current build", "build it first")
    folder = variant.build_dir(int(number))
    report = _json(folder / "report.json") or {}
    silhouette = report.get("silhouette") or {}
    comparisons = [{"view": s.get("view"), "compare": url_of(ws, folder / s["compare"]) if s.get("compare") else None,
                    "object_iou": (s.get("object") or {}).get("iou")} for s in silhouette.get("views", [])]
    shading = report.get("shading") or {}
    validation = report.get("validation") or {}
    return {"title": f"{variant.address} (build {number}{', current' if number == variant.meta.current else ''})",
            "kind": "build", "build": number, "model": url_of(ws, folder / "model.glb"), "textures": textures,
            "validated": report.get("validated"),
            "triangles": sum(p.get("triangles", 0) for p in report.get("parts", [])), "budget": variant.asset.budget,
            "mean_object_iou": silhouette.get("mean_object_iou"), "comparisons": comparisons,
            "renders_note": silhouette.get("renders") if isinstance(silhouette.get("renders"), str) else None,
            "issues": validation.get("issues", []),
            "failing": {"intersections": [i for i in validation.get("intersections", []) if not i.get("ok")],
                        "contacts": [c for c in validation.get("contacts", []) if not c.get("ok")],
                        "disconnected": validation.get("disconnected", [])},
            "shading": shading, "parts": [p.get("name") for p in report.get("parts", [])]}


def _json(path: Path):
    import json
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def start_view(ws: Workspace, target: str, build: int | None = None) -> dict:
    t = ws.target(target)
    spec = {"target": target, "build": build}
    view_state(ws, spec)  # fails now when there is nothing to show
    return with_address(t.pack, jobs.start(t.pack, "view", target, spec))


@jobs.kind("view")
def view(context: jobs.JobContext) -> dict:
    ws, spec = context.ws, context.inputs
    with PageServer(ws.root, "view.html", lambda: view_state(ws, spec)) as server:
        how = show(server, f"Slopoly: {spec['target']}", threading.Event(), context)
    return {"closed": True, "shown_in": how}


# --- review ------------------------------------------------------------------------------------------------------

HERO_CAMERA = {"yaw": 45.0, "pitch": 20.0}  # the hero image's view: three-quarter from the front-left, a little above


def review_state(ws: Workspace, spec: dict) -> dict:
    from .. import review
    variant: Variant = ws.target(spec["target"]).need_variant()
    number = spec.get("build") or variant.meta.current
    if number is None:
        raise SlopolyError("not_built", f"{variant.address} has no current build", f"slopoly build {variant.address}")
    folder = variant.build_dir(int(number))
    pack, hero = variant.pack, variant.reference
    views = variant.asset.views(hero.path.name) if hero else None
    mesh = variant.asset.views_dir(hero.path.name) / views.mesh if views and views.mesh else None
    textures = {p.stem: url_of(ws, p) for p in sorted(pack.palette_dir.glob("*.png"))} if pack.palette_dir.is_dir() else {}
    notes = review.load_notes(variant)
    pins = [{"number": n.number, "comment": n.comment, "camera": n.camera, "left": n.left,
             "reason": next((e.text for e in reversed(n.history) if e.status == "addressed"), None),
             "build": next((e.build for e in reversed(n.history) if e.status == "addressed"), None),
             "images": {k: url_of(ws, review.notes_dir(variant) / v) for k, v in n.images.items()}}
            for n in notes.notes if n.status == "addressed"]
    return {"title": f"Review {variant.address} (build {number})", "variant": variant.address, "build": int(number),
            "model": url_of(ws, folder / "model.glb"), "textures": textures,
            "hero": url_of(ws, hero.path) if hero else None,
            "mesh": url_of(ws, mesh) if mesh is not None and mesh.exists() else None,
            "mesh_reason": None if mesh is not None and mesh.exists() else
            "no reference mesh yet: make the views with slopoly gen views",
            "hero_camera": HERO_CAMERA, "pins": pins,
            "open": [{"number": n.number, "comment": n.comment} for n in notes.notes if n.status == "open"]}


def start_review(ws: Workspace, target: str, build: int | None = None) -> dict:
    t = ws.target(target)
    spec = {"target": t.need_variant().address, "build": build}
    review_state(ws, spec)  # fails now when there is nothing to review
    return with_address(t.pack, jobs.start(t.pack, "review", spec["target"], spec))


@jobs.kind("review")
def review_job(context: jobs.JobContext) -> dict:
    from .. import meshview as mv
    from .. import review
    ws, spec = context.ws, context.inputs
    variant = ws.target(spec["target"]).need_variant()
    done, outcome = threading.Event(), {}

    def on_send(body: dict) -> dict:
        if done.is_set():
            return outcome
        state = review_state(ws, spec)
        number = state["build"]
        build = mv.load_glb((variant.build_dir(number) / "model.glb").read_bytes())
        hero = variant.reference
        views = variant.asset.views(hero.path.name) if hero else None
        mesh_path = variant.asset.views_dir(hero.path.name) / views.mesh if views and views.mesh else None
        reference = mv.load_glb(mesh_path.read_bytes()) if mesh_path is not None and mesh_path.exists() else None
        added = review.add_notes(variant, number, body.get("notes") or [], build, reference)
        verdicts = review.confirm(variant, body.get("confirm") or [], number)
        outcome.update({"notes": [review.summary(variant, n) for n in added], **verdicts,
                        "open": review.open_count(variant)})
        done.set()
        return outcome

    guard = CloseGuard()
    with PageServer(ws.root, "review.html", lambda: review_state(ws, spec), on_send, guard.routes()) as server:
        how = show(server, f"Slopoly: review {spec['target']}", done, context, size=(1500, 900), guard=guard)
    if not done.is_set():
        raise jobs.Cancelled()
    return outcome | {"shown_in": how}


ADDRESS_WAIT = 10.0  # seconds a window command waits for its page's address


def with_address(pack, started: dict) -> dict:
    """Adds the window's local address to a started window job's result as soon as its page server is up."""
    deadline = time.monotonic() + ADDRESS_WAIT
    path = pack.jobs_dir / f"{started['job']}.yaml"
    while time.monotonic() < deadline and path.exists():
        try:
            job = load(m.Job, path)
        except SlopolyError:  # caught mid-write
            time.sleep(0.2)
            continue
        message = job.message or ""
        if job.state not in ("queued", "running"):
            break
        if "http://" in message:
            started["url"] = "http://" + message.split("http://", 1)[1].rstrip(")").split()[0].rstrip(")")
            break
        time.sleep(0.2)
    return started
