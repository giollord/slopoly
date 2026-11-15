"""Colour likeness (design section 13): per mask, CIEDE2000 between the main palette colour of the role covering most
of the matched parts' surface (a gradient's mean) and the mask's dominant measured colour."""

from __future__ import annotations

from collections import Counter

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

from . import palette as pal
from .assembly import Model
from .silhouette import parts_for

MAX_DELTA_E = 20.0  # beyond this the colours read as different


def _lab(hex_color: str) -> np.ndarray:
    return rgb2lab(np.array([[pal.rgb(hex_color)]], dtype=float) / 255.0)[0, 0]


def role_colour(entry: pal.Entry) -> str:
    if not entry.gradient or not entry.color2:
        return entry.color
    a, b = np.array(pal.rgb(entry.color)), np.array(pal.rgb(entry.color2))
    return "#{:02x}{:02x}{:02x}".format(*((a + b) / 2).round().astype(int))


def _area(points: np.ndarray) -> float:
    """Area of a planar polygon (fan of cross products)."""
    edges = points[1:] - points[0]
    return float(np.linalg.norm(np.cross(edges[:-1], edges[1:]).sum(0))) / 2


def main_role(model: Model, names: list[str]) -> str | None:
    """The role on the largest share of the parts' surface."""
    area: Counter[str] = Counter()
    for name in names:
        p = model.parts[name]
        verts = p.world_vertices()
        for face, tag in zip(p.shape.faces(), p.face_tags()):
            area[pal.split_tag(tag)[0]] += _area(verts[face])
    return area.most_common(1)[0][0] if area else None


def likeness(model: Model, masks: list[dict], entries: list[pal.Entry]) -> list[dict]:
    """``masks`` items: {"part", "view", "colors": [{"hex", "coverage"}]}. One row per mask with a measured colour."""
    by_role = {e.role: e for e in entries}
    rows = []
    for m in masks:
        colors = m.get("colors") or []
        parts = [p.name for p in parts_for(model, m["part"])]
        role = main_role(model, parts) if parts else None
        if not colors or role not in by_role:
            continue
        expected, measured = role_colour(by_role[role]), colors[0]["hex"]
        delta = float(deltaE_ciede2000(_lab(expected), _lab(measured)))
        rows.append({"mask": m["part"], "view": m["view"], "role": role, "role_color": expected,
                     "mask_color": measured, "delta_e": round(delta, 2), "ok": delta <= MAX_DELTA_E})
    return rows
