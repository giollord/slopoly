"""`slopoly look`: close-up renders of a variant's reference mesh, optionally beside its build from the same camera."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import meshview as mv
from . import reference
from .core import SlopolyError
from .workspace import Variant

KEEP = 50  # newest close-ups kept in a variant's looks/ folder
SIZE = 768


def looks_dir(variant: Variant) -> Path:
    return variant.root / "looks"


def reference_mesh(variant: Variant) -> tuple[mv.Mesh, str]:
    hero = variant.meta.reference
    if not hero:
        raise SlopolyError("no_reference", f"{variant.address} has no reference hero",
                           f"pick one: slopoly pick {variant.asset.address} --heroes")
    views = variant.asset.views(hero)
    folder = variant.asset.views_dir(hero)
    if views is None or not views.mesh or not (folder / views.mesh).exists():
        raise SlopolyError("no_reference_mesh", f"the reference hero {hero} has no reference mesh",
                           f"make its views: slopoly gen views {variant.address}")
    return mv.load_glb((folder / views.mesh).read_bytes()), hero


def region_bounds(variant: Variant, hero: str, part: str) -> np.ndarray:
    masks = variant.asset.masks(hero)
    found = {r.part: r for r in (masks.regions if masks else [])}
    if part not in found or found[part].bounds is None:
        known = sorted(p for p, r in found.items() if r.bounds)
        raise SlopolyError("no_region", f"no 3D region for {part!r} on the reference mesh",
                           f"segment it: slopoly segment {variant.address} --parts {part}"
                           + (f" (regions: {', '.join(known)})" if known else ""))
    if found[part].implausible:
        raise SlopolyError("implausible_region", f"the 3D region of {part!r} {found[part].implausible}, so it is not "
                           "that part", "look at the part with --box x0,y0,z0,x1,y1,z1 (metres) from the views instead")
    return np.array(found[part].bounds, float)


def build_mesh(variant: Variant, number: int | None) -> tuple[mv.Mesh, int]:
    number = number if number is not None else variant.meta.current
    if number is None:
        raise SlopolyError("no_build", f"{variant.address} has no current build", f"slopoly build {variant.address}")
    path = variant.build_dir(number) / "model.glb"
    if not path.exists():
        raise SlopolyError("no_build", f"build {number} of {variant.address} has no model")
    return mv.load_glb(path.read_bytes()), number


def parse_box(text: str) -> np.ndarray:
    try:
        values = [float(x) for x in text.split(",")]
    except ValueError:
        values = []
    if len(values) != 6:
        raise SlopolyError("bad_box", f"can't read the box {text!r}", "give x0,y0,z0,x1,y1,z1 in metres")
    box = np.array(values).reshape(2, 3)
    return np.stack([box.min(0), box.max(0)])


def prune(folder: Path) -> None:
    files = sorted(folder.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for old in files[:-KEEP]:
        old.unlink(missing_ok=True)


def look(variant: Variant, direction: str = "hero", region: str | None = None, box: str | None = None,
         zoom: float = 1.0, perspective: bool = False, with_build: bool = False, build: int | None = None) -> dict:
    """Renders the reference mesh (and the build) from ``direction`` (a name or "<yaw>,<pitch>"), framing a part's
    3D region or a box in metres, ``zoom`` times closer. Returns image paths, the camera and the framed bounds."""
    try:
        yaw, pitch = mv.direction(direction)
    except ValueError:
        raise SlopolyError("bad_direction", f"unknown direction {direction!r}",
                           f"use {', '.join(mv.NAMED)} or <yaw>,<pitch> in degrees") from None
    if zoom <= 0:
        raise SlopolyError("bad_zoom", "zoom must be above 0")
    ref_mesh, hero = reference_mesh(variant)
    framed = (region_bounds(variant, hero, region) if region else parse_box(box) if box else None)
    meshes = {"reference": ref_mesh}
    number = None
    if with_build or build is not None:
        meshes["build"], number = build_mesh(variant, build)
    if framed is None:
        every = np.concatenate([m.verts for m in meshes.values()])
        framed = np.stack([every.min(0), every.max(0)])
    camera = reference.look_camera(ref_mesh, yaw, pitch, (framed[0], framed[1]), zoom, perspective, SIZE)
    folder = looks_dir(variant)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    label = (region or "box" if (region or box) else "whole") + f"_{direction.replace(',', '_')}"
    ws = variant.pack.ws
    out = {"camera": camera.as_dict(), "bounds": np.round(framed, 4).tolist()}
    for name, mesh in meshes.items():
        rgb, _ = mv.render(mesh, camera)
        path = folder / f"{stamp}_{label}_{name}.png"
        Image.fromarray(rgb).save(path)
        out[name] = ws.rel(path)
    if number is not None:
        out["build_number"] = number
    prune(folder)
    return out
