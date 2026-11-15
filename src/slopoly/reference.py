"""The reference mesh of a hero: orientation against the hero image, real-size normalisation, metric views and
close-up renders. Pure numpy/Pillow (see meshview); the CLI's views job and `slopoly look` use it."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import meshview as mv

VIEW_SIZE = 768
VIEW_MARGIN = 0.05
SWEEP_STEP = 10  # degrees between hero-camera candidates
REFINE_CANDIDATES = 4  # the best coarse candidates refined in 2 degree steps
HERO_PITCH = 20.0  # the hero prompt asks for a view slightly from above
MATCH_SIZE = 96  # px: silhouettes are compared at this size
SYMMETRY_WINDOW = 15  # degrees around the detected front searched for the mirror plane
DETECTED_IOU = 0.7  # hero match at least this good: the front counts as detected
VIEW_DIRECTIONS = {"front": (0.0, 0.0), "side": (90.0, 0.0), "top": (0.0, 90.0), "back": (180.0, 0.0)}
VIEW_AXES = {  # model axis along the image's x (right) and y (down)
    "front": ("+x", "-y"), "side": ("-z", "-y"), "top": ("+x", "+z"), "back": ("-x", "-y")}
DEFAULT_SIZE = 1.0  # metres along the longest axis when the asset states no size


@dataclass
class Placement:
    """How the generated mesh is turned into the asset's frame: mirrored across X first, then turned ``yaw``
    degrees around Y, then scaled and moved so it stands on y = 0, centred on X and Z."""
    yaw: float = 0.0
    mirrored: bool = False
    scale: float = 1.0
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def matrix(self) -> np.ndarray:
        m = mv.rotation_y(self.yaw)
        if self.mirrored:
            m = m @ np.diag([-1.0, 1.0, 1.0, 1.0])
        s = np.diag([self.scale, self.scale, self.scale, 1.0])
        t = np.eye(4)
        t[:3, 3] = self.offset
        return t @ s @ m


def _normalised_crop(mask: np.ndarray, rgb: np.ndarray | None = None, size: int = MATCH_SIZE
                     ) -> tuple[np.ndarray, np.ndarray | None]:
    """The mask (and colours) cropped to its bounds and scaled, keeping the aspect, into a size x size square."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return np.zeros((size, size), bool), None
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    h, w = y1 - y0, x1 - x0
    k = (size - 2) / max(h, w)
    nh, nw = max(1, round(h * k)), max(1, round(w * k))
    oy, ox = (size - nh) // 2, (size - nw) // 2
    out = np.zeros((size, size), bool)
    small = Image.fromarray(mask[y0:y1, x0:x1].astype(np.uint8) * 255).resize((nw, nh), Image.Resampling.BILINEAR)
    out[oy:oy + nh, ox:ox + nw] = np.asarray(small) >= 128
    colours = None
    if rgb is not None:
        colours = np.zeros((size, size, 3), np.float64)
        part = Image.fromarray(rgb[y0:y1, x0:x1]).resize((nw, nh), Image.Resampling.BILINEAR)
        colours[oy:oy + nh, ox:ox + nw] = np.asarray(part, dtype=np.float64) / 255
    return out, colours


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def hero_match(mesh: mv.Mesh, yaw: float, pitch: float, hero: tuple[np.ndarray, np.ndarray | None]) -> dict:
    """How well the mesh seen from (yaw, pitch) matches the hero: silhouette IoU and colour difference."""
    camera = mv.framed(mesh.verts, yaw, pitch, (MATCH_SIZE * 2, MATCH_SIZE * 2))
    rgb, mask = mv.render(mesh, camera)
    shape, colours = _normalised_crop(mask, rgb)
    iou = _iou(shape, hero[0])
    both = shape & hero[0]
    colour = (float(np.abs(colours[both] - hero[1][both]).mean())
              if hero[1] is not None and colours is not None and both.any() else 0.0)
    return {"yaw": yaw, "pitch": pitch, "iou": round(iou, 4), "colour": round(colour, 4),
            "score": iou - 0.5 * colour}


SYMMETRY_PITCH = 30.0  # seen from above: a turned box shows its top askew (from level it is always a rectangle)


def symmetry(mesh: mv.Mesh, yaw: float) -> float:
    """Mirror symmetry (IoU with its left-right flip) of the silhouette seen from ``yaw``, a little from above."""
    camera = mv.framed(mesh.verts, yaw, SYMMETRY_PITCH, (MATCH_SIZE * 2, MATCH_SIZE * 2))
    _, mask = mv.render(mesh, camera)
    shape, _ = _normalised_crop(mask)
    return _iou(shape, shape[:, ::-1])


def orient(mesh: mv.Mesh, hero_rgb: np.ndarray, hero_mask: np.ndarray) -> dict:
    """Finds the turn (and whether to mirror) that puts the object's front towards +Z, by matching renders of the
    mesh against the hero (a three-quarter view from the front-left) over a sweep of camera yaws, plain and
    mirrored; the mirror symmetry of the front silhouette then refines the yaw. Returns the placement fields with
    the evidence: {"yaw", "mirrored", "how", "hero_iou", "symmetry"}."""
    hero = _normalised_crop(hero_mask, hero_rgb)
    meshes = {False: mesh, True: mv.mirror_x(mesh)}
    coarse = sorted(((m, hero_match(meshes[m], float(yaw), HERO_PITCH, hero))
                     for m in meshes for yaw in range(0, 360, SWEEP_STEP)), key=lambda c: -c[1]["score"])
    best = coarse[0]
    for mirrored, match in coarse[:REFINE_CANDIDATES]:  # the grid is coarse: refine the best few in fine steps
        for step in range(-SWEEP_STEP // 2 - 1, SWEEP_STEP // 2 + 2, 2):
            if step:
                fine = hero_match(meshes[mirrored], match["yaw"] + step, HERO_PITCH, hero)
                if fine["score"] > best[1]["score"]:
                    best = (mirrored, fine)
    mirrored, match = best
    hero_yaw = mv.NAMED["hero"][0]
    turn = hero_yaw - match["yaw"]  # turning the object by this brings the hero's side to the hero camera
    turned = (mv.mirror_x(mesh) if mirrored else mesh).transformed(mv.rotation_y(turn))
    scores = {d: symmetry(turned, float(d)) for d in range(-SYMMETRY_WINDOW, SYMMETRY_WINDOW + 1, 1)}
    best_d = max(scores, key=lambda d: (round(scores[d], 3), -abs(d)))  # ties: the smallest correction
    if scores[best_d] - scores[0] > 0.01:
        turn -= best_d  # the mirror plane is best seen from best_d: turn the object so that is straight on
    how = "detected" if match["iou"] >= DETECTED_IOU else "assumed"
    return {"yaw": round((turn + 180) % 360 - 180, 2), "mirrored": mirrored, "how": how,
            "hero_iou": match["iou"], "symmetry": round(max(scores.values()), 4)}


def place(mesh: mv.Mesh, yaw: float, mirrored: bool, size: dict | None) -> tuple[Placement, str]:
    """The placement that turns the mesh and scales it to ``size`` ({"axis": x|y|z|longest, "metres": m}), on the
    ground and centred. Without a size the longest axis becomes DEFAULT_SIZE and the scale is "assumed"."""
    placement = Placement(yaw=yaw, mirrored=mirrored)
    turned = mesh.transformed(placement.matrix())
    lo, hi = turned.bounds()
    extent = hi - lo
    if size:
        axis = size.get("axis", "longest")
        along = float(extent.max() if axis == "longest" else extent["xyz".index(axis)])
        placement.scale, how = float(size["metres"]) / max(along, 1e-9), "given"
    else:
        placement.scale, how = DEFAULT_SIZE / max(float(extent.max()), 1e-9), "assumed"
    lo, hi = lo * placement.scale, hi * placement.scale
    placement.offset = (-float(lo[0] + hi[0]) / 2, -float(lo[1]), -float(lo[2] + hi[2]) / 2)
    return placement, how


def view_cameras(mesh: mv.Mesh, size: int = VIEW_SIZE, margin: float = VIEW_MARGIN) -> dict[str, mv.Camera]:
    """Orthographic front, side, top and back cameras that frame the placed mesh with one shared scale, so that no
    view crops the object whatever its proportions."""
    scale = min(mv.framed(mesh.verts, yaw, pitch, (size, size), margin).scale
                for yaw, pitch in VIEW_DIRECTIONS.values())
    return {name: mv.framed(mesh.verts, yaw, pitch, (size, size), margin, scale=scale)
            for name, (yaw, pitch) in VIEW_DIRECTIONS.items()}


def view_camera(name: str, fit: dict) -> mv.Camera:
    """The camera a view was rendered with, from its fit."""
    yaw, pitch = VIEW_DIRECTIONS[name]
    (w, h), scale, (ox, oy) = fit["image"], float(fit["scale"]), fit["offset"]
    return mv.Camera(yaw, pitch, scale=scale, centre=((w / 2 - ox) / scale, (oy - h / 2) / scale), size=(w, h))


def view_info(name: str, camera: mv.Camera) -> dict:
    """Metric facts of a view: metres per pixel, the model axes along the image axes, the ground row and the fit."""
    info = {"m_per_px": round(1 / camera.scale, 6), "axes": {"x": VIEW_AXES[name][0], "y": VIEW_AXES[name][1]},
            "fit": camera.fit()}
    if name != "top":
        info["ground_row"] = round(camera.size[1] / 2 + camera.centre[1] * camera.scale, 2)  # y = 0 in the image
    return info


def render_views(mesh: mv.Mesh, size: int = VIEW_SIZE) -> dict[str, tuple[np.ndarray, np.ndarray, dict]]:
    """name -> (RGB image, silhouette mask, view info) for the placed mesh."""
    out = {}
    for name, camera in view_cameras(mesh, size).items():
        rgb, mask = mv.render(mesh, camera)
        out[name] = (rgb, mask, view_info(name, camera))
    return out


def look_camera(mesh: mv.Mesh, yaw: float, pitch: float, box: tuple[np.ndarray, np.ndarray] | None = None,
                zoom: float = 1.0, perspective: bool = False, size: int = VIEW_SIZE) -> mv.Camera:
    """A camera for a close-up: framing ``box`` (lo, hi corners in metres) or the whole mesh, ``zoom`` times
    closer. Perspective close-ups look at the box centre from a distance that fits it."""
    lo, hi = box if box is not None else mesh.bounds()
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    camera = mv.framed(corners, yaw, pitch, (size, size), margin=0.1)
    camera.scale *= zoom
    if perspective:
        _, _, back = camera.axes()
        radius = float(np.linalg.norm(hi - lo)) / 2
        camera.perspective, camera.target = True, tuple(float(c) for c in (lo + hi) / 2)
        camera.distance = radius / math.tan(math.radians(35) / 2) / zoom + radius
    return camera


def png(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(rgb)


def mask_png(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(mask.astype(np.uint8) * 255)
