"""Detail comparison inside and around the silhouette, from a view image and the build's render of that view (they
overlay pixel for pixel; see render.py).

IoU hides small features: a missing handle, an extra plank or a dark band across a wall changes it by a percent or
two. This finds them as regions:

- **missing:** covered in the view but not by the model (a part left out, or too small);
- **extra:** covered by the model but not in the view;
- **colour:** covered by both, but the colours differ (a missing trim, band, window or panel, or a wrong role);
- **edge:** lines in the view (board edges, frames, seams, panel outlines) with no line near them in the render.

Each region has a number (drawn on the comparison image), a box as fractions of the object's box (x0, y0, x1, y1;
origin top left), its area as a fraction of the silhouette (edges: the lines' length as a fraction of the object's
width), the part masks it overlaps, and its view and model colours.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage.color import deltaE_ciede2000, rgb2gray, rgb2lab
from skimage.feature import canny
from skimage.measure import label, regionprops

MIN_AREA = 0.004  # regions smaller than this fraction of the silhouette are noise
OUTLINE_PX = 2  # misalignment along the outline that is ignored
COLOUR_DELTA_E = 20.0  # beyond this (lightness weighted half, so lighting matters less) colours differ
BLUR_SIGMA = 1.5
MAX_REGIONS = 6  # per kind, largest first
EDGE_SIGMA, EDGE_LOW, EDGE_HIGH = 1.5, 0.04, 0.1  # Canny on the grey images
EDGE_NEAR_PX = 4  # a view line with a render line this close counts as present
MIN_EDGE_LENGTH = 0.12  # lines shorter than this fraction of the object's width are noise


def _hex(pixels: np.ndarray) -> str:
    return "#{:02x}{:02x}{:02x}".format(*np.median(pixels.reshape(-1, 3), 0).round().astype(int))


def _clean(mask: np.ndarray, px: int) -> np.ndarray:
    return ndimage.binary_opening(mask, iterations=px) if px else mask


def _regions(kind: str, mask: np.ndarray, silhouette_area: float, box, view: np.ndarray, model: np.ndarray,
             parts: dict[str, np.ndarray]) -> list[tuple[dict, np.ndarray]]:
    x0, y0, w, h = box
    edges = kind == "edge"
    found = []
    labels = label(ndimage.binary_dilation(mask, iterations=2) if edges else mask)  # edges: group nearby lines
    for region in regionprops(labels):
        inside = labels == region.label
        if edges:
            inside &= mask
        size = float(inside.sum())
        amount = size / w if edges else size / silhouette_area
        if amount < (MIN_EDGE_LENGTH if edges else MIN_AREA):
            continue
        pixels = np.nonzero(inside)
        rmin, cmin, rmax, cmax = region.bbox
        overlapping = sorted(name for name, m in parts.items() if (m & inside).sum() >= 0.3 * size)
        row = {"kind": kind, "box": [round(float(cmin - x0) / w, 3), round(float(rmin - y0) / h, 3),
                                     round(float(cmax - x0) / w, 3), round(float(rmax - y0) / h, 3)],
               ("length" if edges else "area"): round(amount, 4), "masks": overlapping}
        if kind in ("missing", "colour"):
            row["view_color"] = _hex(view[pixels])
        if kind in ("extra", "colour"):
            row["model_color"] = _hex(model[pixels])
        found.append((row, inside))
    found.sort(key=lambda r: -r[0].get("area", r[0].get("length", 0)))
    return found[:MAX_REGIONS]


def compare(view: np.ndarray, render: np.ndarray, silhouette: np.ndarray, parts: dict[str, np.ndarray] | None = None
            ) -> tuple[dict, list[np.ndarray]]:
    """``view`` RGB uint8, ``render`` RGBA uint8 (same size), ``silhouette`` the view's object mask, ``parts`` the
    view's part masks. Returns ({"regions": [...], "colour_match"}, region pixel masks in the same order)."""
    parts = parts or {}
    model = render[:, :, 3] >= 128
    ys, xs = np.nonzero(silhouette)
    if len(xs) == 0:
        return {"regions": [], "colour_match": None}, []
    box = (xs.min(), ys.min(), max(xs.max() + 1 - xs.min(), 1), max(ys.max() + 1 - ys.min(), 1))
    area = float(silhouette.sum())
    view_rgb, model_rgb = view[:, :, :3], render[:, :, :3]

    both = ndimage.binary_erosion(silhouette & model, iterations=OUTLINE_PX + 1)
    blur = [ndimage.gaussian_filter(img.astype(float) / 255.0, (BLUR_SIGMA, BLUR_SIGMA, 0)) for img in (view_rgb, model_rgb)]
    delta = deltaE_ciede2000(rgb2lab(blur[0]), rgb2lab(blur[1]), kL=2)
    differs = both & (delta > COLOUR_DELTA_E)
    match = round(1.0 - float(differs.sum()) / max(float(both.sum()), 1.0), 4) if both.any() else None

    inner = ndimage.binary_erosion(silhouette & model, iterations=EDGE_NEAR_PX)
    lines = [canny(rgb2gray(img), sigma=EDGE_SIGMA, low_threshold=EDGE_LOW, high_threshold=EDGE_HIGH)
             for img in (view_rgb, model_rgb)]
    lacking = lines[0] & inner & (ndimage.distance_transform_edt(~lines[1]) > EDGE_NEAR_PX)

    found = []
    for kind, mask in (("missing", silhouette & ~model), ("extra", model & ~silhouette), ("colour", differs),
                       ("edge", lacking)):
        found += _regions(kind, mask if kind == "edge" else _clean(mask, OUTLINE_PX if kind != "colour" else 1), area, box, view_rgb, model_rgb,
                          parts)
    rows = []
    for number, (row, _) in enumerate(found, 1):
        rows.append({"id": number, **row})
    return {"regions": rows, "colour_match": match}, [inside for _, inside in found]
