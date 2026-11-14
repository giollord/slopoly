"""Silhouette scoring without rendering (design section 8).

Each part's triangles are projected orthographically into a turnaround view and filled with Pillow at the mask's
resolution. The whole object's projection is scaled (uniformly) and centred onto the union of that view's masks, so
absolute size comes from the program. Per mask: IoU and signed width/height/centre errors as fractions of the
object's size in the image. Projections ignore occlusion; masks show only visible pixels.
"""

from __future__ import annotations

import re
from itertools import product

import numpy as np
from PIL import Image, ImageDraw

from .assembly import Model, Part

# Image axes (u right, v down) per view, from world coordinates (Y up, front faces +Z).
VIEWS = {
    "front": lambda p: np.stack([p[:, 0], -p[:, 1]], 1),  # looking at the front (from +Z)
    "side": lambda p: np.stack([-p[:, 2], -p[:, 1]], 1),  # looking from +X
    "top": lambda p: np.stack([p[:, 0], p[:, 2]], 1),  # looking down from +Y, front at the bottom
}
FLIPS = list(product((1, -1), repeat=2))  # generated sheets may show a view mirrored


def base_name(name: str) -> str:
    return re.sub(r"(_[LRlr]|Left|Right|left|right|_mirror)$", "", name)


def parts_for(model: Model, mask_part: str) -> list[Part]:
    """Parts a mask name stands for: the part itself, both mirror halves (wheel -> wheel_L, wheel_R), or all
    instances of a mesh (plank -> plank_1..plank_N)."""
    exact = [p for p in model.parts.values() if p.name == mask_part]
    return exact or [p for p in model.parts.values() if mask_part in (base_name(p.name), p.mesh)]


def bbox(mask: np.ndarray) -> tuple[float, float, float, float] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def _fill(polygons: list[np.ndarray], size: tuple[int, int]) -> np.ndarray:
    image = Image.new("1", size, 0)
    draw = ImageDraw.Draw(image)
    for tri in polygons:
        draw.polygon([tuple(pt) for pt in tri], fill=1)
    return np.asarray(image, dtype=bool)


def _projected(part: Part, project, flip) -> np.ndarray:
    """Triangles of the part in view coordinates, shape (n, 3, 2)."""
    uv = project(part.world_vertices()) * np.array(flip, dtype=float)
    return uv[part.shape.triangles()]


def score_view(model: Model, view: str, masks: dict[str, np.ndarray]) -> dict:
    """Scores one view. ``masks`` maps mask part names to boolean arrays covering the view (all the same size)."""
    if view not in VIEWS or not masks:
        return {"view": view, "skipped": "unknown view" if view not in VIEWS else "no masks"}
    height, width = next(iter(masks.values())).shape
    target = bbox(np.logical_or.reduce(list(masks.values())))
    if target is None:
        return {"view": view, "skipped": "empty masks"}
    tx0, ty0, tx1, ty1 = target
    object_w, object_h = tx1 - tx0, ty1 - ty0

    best = None
    for flip in FLIPS:
        tris = {p.name: _projected(p, VIEWS[view], flip) for p in model.parts.values()}
        every = np.concatenate([t.reshape(-1, 2) for t in tris.values()])
        lo, hi = every.min(0), every.max(0)
        size = np.maximum(hi - lo, 1e-9)
        scale = float(np.sqrt((object_w / size[0]) * (object_h / size[1])))  # uniform: keeps the program's aspect
        offset = np.array([(tx0 + tx1) / 2, (ty0 + ty1) / 2]) - (lo + hi) / 2 * scale
        result = {"view": view, "flip": list(flip), "scale": round(scale, 3), "parts": [],
                  "object": {"width_error": round((size[0] * scale - object_w) / object_w, 4),
                             "height_error": round((size[1] * scale - object_h) / object_h, 4)}}
        for name, mask in masks.items():
            members = parts_for(model, name)
            if not members:
                result["parts"].append({"mask": name, "parts": [], "unmatched": True})
                continue
            filled = _fill([t * scale + offset for p in members for t in tris[p.name]], (width, height))
            result["parts"].append(_compare(name, members, filled, mask, object_w, object_h))
        matched = [p["iou"] for p in result["parts"] if "iou" in p]
        result["mean_iou"] = round(float(np.mean(matched)), 4) if matched else 0.0
        if best is None or result["mean_iou"] > best["mean_iou"]:
            best = result
    return best


def _compare(name: str, members: list[Part], filled: np.ndarray, mask: np.ndarray, object_w: float,
             object_h: float) -> dict:
    row = {"mask": name, "parts": [p.name for p in members], "iou": round(iou(filled, mask), 4)}
    got, want = bbox(filled), bbox(mask)
    if got is None or want is None:
        row["empty"] = "projection" if got is None else "mask"
        return row
    row.update({
        "width_error": round(((got[2] - got[0]) - (want[2] - want[0])) / object_w, 4),
        "height_error": round(((got[3] - got[1]) - (want[3] - want[1])) / object_h, 4),
        "centre_offset": [round(((got[0] + got[2]) - (want[0] + want[2])) / 2 / object_w, 4),
                          round(((got[1] + got[3]) - (want[1] + want[3])) / 2 / object_h, 4)],
    })
    return row


def score(model: Model, masks: list[dict]) -> dict:
    """Scores every view that has masks. ``masks`` items: {"part", "view", "mask": bool array}."""
    if not model.parts:
        return {"views": [], "mean_iou": None}
    views: dict[str, dict[str, np.ndarray]] = {}
    for m in masks:
        views.setdefault(m["view"], {})[m["part"]] = m["mask"]
    results = [score_view(model, view, by_part) for view, by_part in views.items()]
    scored = [r["mean_iou"] for r in results if "mean_iou" in r]
    return {"views": results, "mean_iou": round(float(np.mean(scored)), 4) if scored else None}
