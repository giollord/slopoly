"""Segmentation helpers: part specs with regions, crops for the detector, implausible-mask flags and the voting of
view masks onto the reference mesh's faces."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import meshview as mv
from .comfy import colors
from .core import SlopolyError

VIEWS = ("front", "side", "top", "back")
CROP_SIZE = 768  # a region is enlarged to this longest side before the detector sees it
CROP_PAD = 0.1  # share of the region added on each side
IMPLAUSIBLE_AREA = 0.5  # a part mask covering more than this share of the object is suspect
SAME_BOX_IOU = 0.9  # two parts with boxes this alike in one view are suspect
# extra directions the reference mesh is segmented from for 3D regions (yaw, pitch)
VOTE_DIRECTIONS = [(yaw, 20.0) for yaw in range(0, 360, 45)]
VOTE_SIZE = 512
VOTE_SHARE = 0.5  # a face belongs to a part when the part's masks cover it in at least this share of its renders
UNCERTAIN = 0.6  # regions whose mean agreement is lower are reported as uncertain
SPAN = 0.8  # a region wider than this share of the object along two or more axes is implausible for one part
SPEC = re.compile(r"^(?P<part>[^@]+?)(?:@(?P<view>[a-z]+)(?::(?P<box>[-\d.,\s]+))?)?$")


@dataclass
class PartSpec:
    """A part to segment, optionally only in one view and within a box (pixels, or fractions of the image when every
    value is at most 1)."""
    part: str
    view: str | None = None
    box: tuple[float, float, float, float] | None = None

    def as_dict(self) -> dict:
        return {"part": self.part, "view": self.view, "box": list(self.box) if self.box else None}


def parse(text: str) -> PartSpec:
    """"wheel", "spike@side" or "spike@side:0.6,0,1,0.3"."""
    match = SPEC.match(text.strip())
    if not match:
        raise SlopolyError("bad_part", f"can't read the part {text!r}", "use name, name@view or name@view:x0,y0,x1,y1")
    view, box = match["view"], match["box"]
    if view is not None and view not in VIEWS:
        raise SlopolyError("bad_part", f"unknown view {view!r} in {text!r}", f"views: {', '.join(VIEWS)}")
    numbers = None
    if box:
        numbers = tuple(float(x) for x in box.split(","))
        if len(numbers) != 4 or numbers[2] <= numbers[0] or numbers[3] <= numbers[1]:
            raise SlopolyError("bad_part", f"the box in {text!r} needs x0,y0,x1,y1 with x1 > x0 and y1 > y0")
    return PartSpec(match["part"].strip(), view, numbers)


def pixel_box(box: tuple[float, float, float, float], size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    if max(box) <= 1.0:
        box = (box[0] * w, box[1] * h, box[2] * w, box[3] * h)
    x0, y0, x1, y1 = box
    return max(0, int(x0)), max(0, int(y0)), min(w, int(np.ceil(x1))), min(h, int(np.ceil(y1)))


def padded(box: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    px, py = (x1 - x0) * CROP_PAD, (y1 - y0) * CROP_PAD
    return pixel_box((x0 - px, y0 - py, x1 + px, y1 + py), size) if (x1 - x0) > 1 else box


def crop(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """The region enlarged so its longest side is CROP_SIZE."""
    region = image.crop(box)
    k = CROP_SIZE / max(region.size)
    return region.resize((max(1, round(region.width * k)), max(1, round(region.height * k))),
                         Image.Resampling.LANCZOS)


def paste(mask: np.ndarray, box: tuple[int, int, int, int], size: tuple[int, int]) -> np.ndarray:
    """A mask of the enlarged crop put back into a full view's pixels."""
    x0, y0, x1, y1 = box
    small = Image.fromarray(mask.astype(np.uint8) * 255).resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR)
    out = np.zeros((size[1], size[0]), bool)
    out[y0:y1, x0:x1] = np.asarray(small) >= 128
    return out


def implausible(masks: dict[str, np.ndarray], whole: np.ndarray) -> dict[str, str]:
    """Part name -> why its mask in this view is suspect: covering most of the object, or the same box as another
    part (the detector returned one thing for several names)."""
    area = max(int(whole.sum()), 1)
    out: dict[str, str] = {}
    boxes = {name: colors.bounds(mask) for name, mask in masks.items()}
    for name, mask in masks.items():
        share = float(mask.sum()) / area
        if share > IMPLAUSIBLE_AREA:
            out[name] = f"covers {share:.0%} of the object"
    names = list(masks)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if boxes[a] and boxes[b] and _box_iou(boxes[a], boxes[b]) > SAME_BOX_IOU:
                out.setdefault(a, f"the same box as {b}")
                out.setdefault(b, f"the same box as {a}")
    return out


def _box_iou(a, b) -> float:
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ix = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    iy = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    inter = ix * iy
    return inter / (aw * ah + bw * bh - inter) if inter else 0.0


def vote_cameras(mesh: mv.Mesh) -> list[mv.Camera]:
    return [mv.framed(mesh.verts, yaw, pitch, (VOTE_SIZE, VOTE_SIZE)) for yaw, pitch in VOTE_DIRECTIONS]


PIECE_SHARE = 0.1  # a region's connected pieces under this share of its largest piece are strays


class Votes:
    """Per part, how often each face of the reference mesh was visible and covered by the part's mask."""

    def __init__(self, mesh: mv.Mesh):
        self.mesh = mesh
        self.seen = np.zeros(len(mesh.tris))
        self.hits: dict[str, np.ndarray] = {}
        self.counted: set[int] = set()

    def add(self, ids: np.ndarray, render: int, part: str, mask: np.ndarray | None) -> None:
        """One render's face-id image and the part's mask in it (None when the part wasn't found there)."""
        faces, counts = np.unique(ids[ids >= 0], return_counts=True)
        if render not in self.counted:  # a face counts as seen once per render
            self.counted.add(render)
            self.seen[faces] += 1
        hits = self.hits.setdefault(part, np.zeros(len(self.mesh.tris)))
        if mask is not None:
            covered, n = np.unique(ids[(ids >= 0) & mask], return_counts=True)
            share = dict(zip(faces.tolist(), counts.tolist()))
            hits[covered[n * 2 >= np.array([share[f] for f in covered.tolist()])]] += 1  # most of the face covered

    def main_pieces(self, faces: np.ndarray) -> np.ndarray:
        """The faces of the connected pieces (faces sharing vertices) at least PIECE_SHARE the size of the largest: both
        wheels of a pair stay, stray faces voted in elsewhere by a loose mask go."""
        if len(faces) < 2:
            return faces
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        tris = self.mesh.tris[faces]
        rows = np.repeat(np.arange(len(faces)), 3)
        graph = coo_matrix((np.ones(len(rows)), (rows, tris.ravel())), shape=(len(faces), len(self.mesh.verts)))
        _, labels = connected_components((graph @ graph.T).tocsr(), directed=False)
        sizes = np.bincount(labels)
        return faces[sizes[labels] >= PIECE_SHARE * sizes.max()]

    def too_wide(self, verts: np.ndarray) -> str | None:
        """Why a part's region is implausible: it spans most of the object along two or more axes."""
        extent = np.maximum(np.ptp(self.mesh.verts, axis=0), 1e-9)
        span = np.ptp(verts, axis=0) / extent
        wide = [f"{axis} {share:.0%}" for axis, share in zip("xyz", span) if share > SPAN]
        return f"spans most of the object ({', '.join(wide)})" if len(wide) >= 2 else None

    def regions(self) -> dict[str, dict]:
        out = {}
        for part, hits in self.hits.items():
            seen = np.maximum(self.seen, 1)
            share = hits / seen
            faces = self.main_pieces(np.nonzero((share >= VOTE_SHARE) & (self.seen >= 2))[0])
            if not len(faces):
                out[part] = {"faces": [], "bounds": None, "agreement": 0.0, "uncertain": True}
                continue
            verts = self.mesh.verts[np.unique(self.mesh.tris[faces])]
            agreement = round(float(share[faces].mean()), 3)
            out[part] = {"faces": faces.tolist(), "agreement": agreement, "uncertain": agreement < UNCERTAIN,
                         "bounds": [np.round(verts.min(0), 4).tolist(), np.round(verts.max(0), 4).tolist()],
                         "implausible": self.too_wide(verts)}
        return out
