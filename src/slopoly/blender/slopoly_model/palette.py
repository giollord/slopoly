"""Palette texture layout (design section 13): the one place that knows where a slot lives in the texture, so the
rendered PNG and the UVs can't drift apart.

256x256 px. Top half: 8x8 px solid cells, 32 per row, slots 0..255. Bottom half: 4 px high gradient strips, slots
0..31, running left (colour) to right (colour2). Image coordinates have y down; UVs follow glTF (v down) and are
converted by the exporter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

SIZE = 256
CELL = 8
COLUMNS = SIZE // CELL
MAX_SOLIDS = 256
STRIP = 4
GRADIENT_TOP = SIZE // 2
MAX_GRADIENTS = (SIZE - GRADIENT_TOP) // STRIP


@dataclass(frozen=True)
class Entry:
    role: str
    kind: str  # "Solid" or "Gradient"
    slot: int
    color: str
    color2: str | None = None
    id: str | None = None

    @property
    def gradient(self) -> bool:
        return self.kind.lower() == "gradient"

    @classmethod
    def parse(cls, data: dict) -> Entry:
        return cls(data["role"], data.get("kind", "Solid"), int(data["slot"]), data["color"], data.get("color2"),
                   data.get("id"))


def rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def cell_centre(slot: int) -> tuple[float, float]:
    """UV (v down) of a solid slot's cell centre."""
    if not 0 <= slot < MAX_SOLIDS:
        raise ValueError(f"solid slot {slot} out of range")
    x, y = (slot % COLUMNS) * CELL + CELL / 2, (slot // COLUMNS) * CELL + CELL / 2
    return x / SIZE, y / SIZE


def strip_uv(slot: int, t: float) -> tuple[float, float]:
    """UV (v down) at position t (0..1) along a gradient strip, inset half a pixel from its ends."""
    if not 0 <= slot < MAX_GRADIENTS:
        raise ValueError(f"gradient slot {slot} out of range")
    t = min(max(t, 0.0), 1.0)
    x = 0.5 + t * (SIZE - 1)
    y = GRADIENT_TOP + slot * STRIP + STRIP / 2
    return x / SIZE, y / SIZE


def render(entries: list[Entry], overrides: dict[str, tuple[str, str | None]] | None = None) -> Image.Image:
    """The palette texture. ``overrides`` maps roles to (color, color2) for a variant; others use the main colours."""
    pixels = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    for e in entries:
        color, color2 = (overrides or {}).get(e.role, (e.color, e.color2))
        if e.gradient:
            start, end = np.array(rgb(color), float), np.array(rgb(color2 or color), float)
            ramp = start + (end - start) * (np.arange(SIZE) / (SIZE - 1))[:, None]
            y = GRADIENT_TOP + e.slot * STRIP
            pixels[y:y + STRIP] = ramp.round().astype(np.uint8)[None]
        else:
            x, y = (e.slot % COLUMNS) * CELL, (e.slot // COLUMNS) * CELL
            pixels[y:y + CELL, x:x + CELL] = rgb(color)
    return Image.fromarray(pixels, "RGB")


def split_tag(tag: str) -> tuple[str, str | None]:
    """"role" or "role@axis" (from gradient())."""
    role, _, axis = tag.partition("@")
    return role, axis or None


def face_uvs(vertices: np.ndarray, faces: list[list[int]], tags: list[str], palette: dict[str, Entry]
             ) -> tuple[list[list[tuple[float, float]]], list[str]]:
    """UVs per face corner, and the roles that are missing from the palette. Solid faces map to the cell centre;
    gradient faces map each vertex's position along the axis, normalised over all faces with that tag."""
    axes = {"x": 0, "y": 1, "z": 2}
    extents: dict[str, tuple[float, float]] = {}
    for face, tag in zip(faces, tags):
        role, axis = split_tag(tag)
        entry = palette.get(role)
        if entry and entry.gradient:
            values = vertices[face, axes[axis or "y"]]
            lo, hi = extents.get(tag, (np.inf, -np.inf))
            extents[tag] = (min(lo, values.min()), max(hi, values.max()))
    uvs, missing = [], set()
    for face, tag in zip(faces, tags):
        role, axis = split_tag(tag)
        entry = palette.get(role)
        if entry is None:
            if role:
                missing.add(role)  # untagged faces are reported by the runner
            uvs.append([(0.0, 0.0)] * len(face))
        elif entry.gradient:
            lo, hi = extents[tag]
            span = (hi - lo) or 1.0
            uvs.append([strip_uv(entry.slot, (vertices[i, axes[axis or "y"]] - lo) / span) for i in face])
        else:
            uvs.append([cell_centre(entry.slot)] * len(face))
    return uvs, sorted(missing)
