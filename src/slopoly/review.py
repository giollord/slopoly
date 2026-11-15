"""Review notes: the user's painted comments on a build beside its reference, the build parts their strokes hit,
and the notes' status as the agent works through them (see review-notes)."""

from __future__ import annotations

import base64
import io
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import meshview as mv
from . import models as m
from .core import SlopolyError, load, write_yaml
from .workspace import Variant

HIT_SIZE = 512  # px: the longest side of the image strokes are evaluated on
MIN_SHARE = 0.10  # parts with less of a note's stroke weight are left out
STATUSES = ("open", "addressed", "wontfix")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def notes_file(variant: Variant):
    return variant.root / "notes.yaml"


def notes_dir(variant: Variant):
    return variant.root / "notes"


def load_notes(variant: Variant) -> m.ReviewNotes:
    path = notes_file(variant)
    return load(m.ReviewNotes, path) if path.exists() else m.ReviewNotes()


def save_notes(variant: Variant, notes: m.ReviewNotes) -> None:
    write_yaml(notes_file(variant), notes)


def open_count(variant: Variant) -> int:
    return sum(1 for n in load_notes(variant).notes if n.status == "open")


# --- strokes and hits --------------------------------------------------------------------------------------------

def pane_size(aspect: float) -> tuple[int, int]:
    aspect = min(max(float(aspect or 1.0), 0.2), 5.0)
    return (HIT_SIZE, max(1, round(HIT_SIZE / aspect))) if aspect >= 1 else (max(1, round(HIT_SIZE * aspect)), HIT_SIZE)


def stroke_weights(strokes: list[dict], size: tuple[int, int]) -> np.ndarray:
    """Per pixel, how much the strokes count: 1 on a stroke's centre line, falling to 0 at its edge. Strokes are
    {"points": [[x, y], ...] as fractions of the pane, "width": fraction of the pane's width}."""
    w, h = size
    weights = np.zeros((h, w))
    for stroke in strokes:
        points = [(float(x) * w, float(y) * h) for x, y in stroke.get("points") or []]
        if not points:
            continue
        radius = max(1.0, float(stroke.get("width", 0.02)) * w / 2)
        line = Image.new("L", size, 0)
        ImageDraw.Draw(line).line(points if len(points) > 1 else points * 2, fill=255, width=1)
        distance = ndimage.distance_transform_edt(np.asarray(line) == 0)
        weights = np.maximum(weights, np.clip(1 - distance / radius, 0, 1))
    return weights


def camera_of(camera: dict, size: tuple[int, int]) -> mv.Camera:
    """The page's camera ({"position", "target", "fov"}) as a meshview camera rendering ``size`` pixels."""
    try:
        return mv.look_at(camera["position"], camera["target"], float(camera.get("fov") or 35), size)
    except (KeyError, TypeError, ValueError):
        raise SlopolyError("bad_note", "a note's camera needs position, target and fov") from None


def hits(mesh: mv.Mesh, camera: mv.Camera, weights: np.ndarray) -> dict:
    """The parts under the strokes (first surface along each pixel's ray only), each with its share of the stroke
    weight and the weighted centre of its hit faces, plus the share over empty space and the hit pixels."""
    ids = mv.face_ids(mv.render(mesh, camera, ids=True)[0])
    total = float(weights.sum())
    if total <= 0:
        return {"parts": [], "empty": 0.0, "ids": ids}
    painted = weights > 0
    names = mesh.face_parts if mesh.face_parts is not None else np.full(len(mesh.tris), "", dtype=object)
    centres = mesh.verts[mesh.tris].mean(1)
    parts: dict[str, list] = {}
    for face, weight in zip(ids[painted].tolist(), weights[painted].tolist()):
        if face < 0:
            continue
        entry = parts.setdefault(str(names[face]), [0.0, np.zeros(3)])
        entry[0] += weight
        entry[1] += centres[face] * weight
    empty = float(weights[painted & (ids < 0)].sum()) / total
    found = [{"part": name, "share": round(value / total, 3), "centre": np.round(at / value, 3).tolist()}
             for name, (value, at) in parts.items() if value / total >= MIN_SHARE]
    return {"parts": sorted(found, key=lambda p: -p["share"]), "empty": round(empty, 3), "ids": ids}


def region(mesh: mv.Mesh, camera: mv.Camera, weights: np.ndarray) -> list[list[float]] | None:
    """Bounds (metres) of the reference mesh's faces under the strokes."""
    ids = mv.face_ids(mv.render(mesh, camera, ids=True)[0])
    faces = np.unique(ids[(weights > 0.25) & (ids >= 0)])
    if not len(faces):
        return None
    verts = mesh.verts[np.unique(mesh.tris[faces])]
    return [np.round(verts.min(0), 3).tolist(), np.round(verts.max(0), 3).tolist()]


def evaluate(note: dict, build: mv.Mesh, reference: mv.Mesh | None) -> dict:
    """Hits of one note sent by the page: its strokes on the build pane and, with the mesh on the left, on the
    reference pane. Strokes over empty space on the build are looked for on the reference instead."""
    size = pane_size(note.get("aspect", 1.0))
    model_strokes = note.get("model_strokes") or []
    ref_strokes = note.get("reference_strokes") or []
    out = {"hits": [], "empty": 0.0, "region": None}
    model_camera = camera_of(note["camera"], size) if model_strokes or (reference is not None and ref_strokes) else None
    if model_strokes:
        weights = stroke_weights(model_strokes, size)
        found = hits(build, model_camera, weights)
        out["hits"], out["empty"] = found["parts"], found["empty"]
        if reference is not None and found["empty"] > 0:
            out["region"] = region(reference, model_camera, weights * (found["ids"] < 0))
    if reference is not None and ref_strokes and note.get("left") == "mesh":
        ref_camera = camera_of(note.get("reference_camera") or note["camera"], size)
        painted = region(reference, ref_camera, stroke_weights(ref_strokes, size))
        out["region"] = painted or out["region"]
    return out


def decode_png(data_url: str | None) -> bytes | None:
    if not data_url or "," not in data_url:
        return None
    raw = base64.b64decode(data_url.split(",", 1)[1])
    Image.open(io.BytesIO(raw)).verify()  # only images are stored
    return raw


# --- the note lifecycle ------------------------------------------------------------------------------------------

def add_notes(variant: Variant, build_number: int, sent: list[dict], build: mv.Mesh,
              reference: mv.Mesh | None) -> list[m.ReviewNote]:
    """Stores the notes sent from a review: their images, hits and an `open` status."""
    notes = load_notes(variant)
    folder = notes_dir(variant)
    folder.mkdir(parents=True, exist_ok=True)
    number = max((n.number for n in notes.notes), default=0)
    added = []
    for note in sent:
        if not (note.get("comment") or "").strip() and not note.get("model_strokes") and not note.get("reference_strokes"):
            continue
        number += 1
        images = {}
        for pane in ("reference", "model"):
            if (data := decode_png((note.get("images") or {}).get(pane))) is not None:
                (folder / f"{number:03d}_{pane}.png").write_bytes(data)
                images[pane] = f"{number:03d}_{pane}.png"
        found = evaluate(note, build, reference) if note.get("camera") else {"hits": [], "empty": 0.0, "region": None}
        entry = m.ReviewNote(number=number, build=build_number, comment=(note.get("comment") or "").strip(),
                       camera=note.get("camera") or {}, left="mesh" if note.get("left") == "mesh" else "hero",
                       images=images, hits=found["hits"], empty=found["empty"], region=found["region"],
                       history=[m.ReviewEvent(at=now(), status="open", build=build_number,
                                            text=(note.get("comment") or "").strip() or None)])
        notes.notes.append(entry)
        added.append(entry)
    save_notes(variant, notes)
    return added


def confirm(variant: Variant, answers: list[dict], build_number: int | None) -> dict:
    """The user's verdicts on earlier addressed notes: {"number", "fixed": bool, "comment"}."""
    notes = load_notes(variant)
    by_number = {n.number: n for n in notes.notes}
    closed, reopened = [], []
    for answer in answers:
        note = by_number.get(int(answer.get("number", -1)))
        if note is None:
            continue
        if answer.get("fixed"):
            note.status = "closed"
            note.history.append(m.ReviewEvent(at=now(), status="closed", build=build_number))
            closed.append(note.number)
        else:
            note.status = "open"
            note.history.append(m.ReviewEvent(at=now(), status="open", build=build_number,
                                            text=(answer.get("comment") or "").strip() or None))
            reopened.append(note.number)
    save_notes(variant, notes)
    return {"closed": closed, "reopened": reopened}


def set_status(variant: Variant, number: int, status: str, build: int | None, reason: str | None) -> dict:
    """The agent's update of a note: addressed (by a build) or wontfix, with a reason; or open again."""
    if status not in STATUSES:
        raise SlopolyError("bad_status", f"unknown status {status!r}", f"use one of {', '.join(STATUSES)}")
    notes = load_notes(variant)
    note = next((n for n in notes.notes if n.number == number), None)
    if note is None:
        raise SlopolyError("not_found", f"{variant.address} has no note {number}",
                           notes=[n.number for n in notes.notes])
    if status == "addressed" and build is None:
        raise SlopolyError("build_required", "say which build addressed the note: --by <build>")
    if status in ("addressed", "wontfix") and not (reason or "").strip():
        raise SlopolyError("reason_required", "give a short reason: --reason \"...\"")
    note.status = status
    note.history.append(m.ReviewEvent(at=now(), status=status, build=build, text=(reason or "").strip() or None))
    save_notes(variant, notes)
    return {"note": number, "status": status, "build": build, "open": open_count(variant)}


def summary(variant: Variant, note: m.ReviewNote) -> dict:
    ws = variant.pack.ws
    folder = notes_dir(variant)
    return {"number": note.number, "build": note.build, "comment": note.comment, "status": note.status,
            "left": note.left, "camera": note.camera,
            "images": {k: ws.rel(folder / v) for k, v in note.images.items()},
            "hits": note.hits, "empty": note.empty, "region": note.region}
