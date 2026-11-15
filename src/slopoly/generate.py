"""Image generation on the user's ComfyUI: style anchors, heroes, revisions, views and part segmentation.

The ``start_*`` functions check the request and start a detached job; the job kinds below run the workflows and write
images with their metadata only when everything succeeded (a cancelled or failed job attaches nothing).
"""

from __future__ import annotations

import io
import random
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from . import jobs
from . import models as m
from .comfy import colors
from .comfy import views as turntable
from .comfy import workflow
from .comfy.client import ComfyClient
from .core import SlopolyError, write_yaml
from .workspace import Asset, ImageRef, Pack, images, next_name

MAX_REFERENCES = 3
MIN_MASK_SHARE = 0.002  # a "found" part covers at least 0.2 % of its view
WHOLE_OBJECT_IOU = 0.9
# SAM 3 keeps only the best object per text prompt unless the prompt says "name:N"; a view can show several of a part
# (both wheels, both handles), so every part asks for up to this many and gets their union.
MAX_INSTANCES = 8
HERO_IMAGE = ("ONE object only, whole and centred: {0}. Three-quarter front view from the front-left, slightly from "
              "above. Plain light grey background, nothing else in the image. Copy only the colours, materials and "
              "style of the reference images, not their objects.")


def style_text(pack: Pack) -> str:
    """The '# Style' section of style.md (the whole file when it has no such heading)."""
    text = pack.style()
    match = re.search(r"^#\s*Style\s*$(.*?)(?=^#\s|\Z)", text, re.M | re.S | re.I)
    return (match.group(1) if match else text).strip()


def rel(pack: Pack, path: Path) -> str:
    return path.resolve().relative_to(pack.ws.root).as_posix()


def count_of(count: int) -> int:
    if not 1 <= count <= 4:
        raise SlopolyError("bad_count", "count must be 1 to 4")
    return count


# --- starting jobs -----------------------------------------------------------------------------------------------

def start_anchor(pack: Pack, description: str, count: int = 2, seed: int | None = None) -> dict:
    refs = [rel(pack, p) for p, _ in images(pack.style_dir, ("undecided", "picked"))][:MAX_REFERENCES]
    prompt = "\n\n".join(t for t in (style_text(pack), description.strip()) if t)
    inputs = {"workflow": "style-anchor", "kind": "anchor", "prompt": prompt, "references": refs,
              "count": count_of(count), "seed": seed, "folder": rel(pack, pack.anchors_dir), "prefix": "anchor"}
    return jobs.start(pack, "generate", pack.name, inputs)


def picked_anchors(pack: Pack) -> list[str]:
    picked = [p for p, _ in images(pack.anchors_dir, ("picked",))]
    return [rel(pack, p) for p in sorted(picked, reverse=True)][:MAX_REFERENCES]


def start_hero(asset: Asset, description: str | None = None, count: int = 2, seed: int | None = None) -> dict:
    pack = asset.pack
    anchors = picked_anchors(pack)
    if not anchors:
        raise SlopolyError("no_picked_anchor", f"pack {pack.name!r} has no picked style anchor",
                           f"pick one: slopoly pick {pack.name} --anchors")
    style = style_text(pack)
    prompt = HERO_IMAGE.format(description or f"{asset.name}, {asset.meta.description}".strip(", ")) + (
        f" Style notes for colours and materials only: {style}" if style else "")
    asset.heroes_dir.mkdir(parents=True, exist_ok=True)
    inputs = {"workflow": "hero", "kind": "hero", "prompt": prompt, "references": anchors, "count": count_of(count),
              "seed": seed, "folder": rel(pack, asset.heroes_dir), "prefix": "hero"}
    return jobs.start(pack, "generate", asset.address, inputs)


def start_revise(image: ImageRef, change: str | None, count: int = 2) -> dict:
    meta = image.meta
    if meta.kind not in ("anchor", "hero") or not meta.prompt:
        raise SlopolyError("not_revisable", "only generated anchors and heroes can be revised")
    prompt, refs = meta.prompt, list(meta.references)
    own = rel(image.pack, image.path)
    if change and change.strip():
        prompt = f"{prompt}\n\nChange from image 1: {change.strip()}"
        refs = [own, *[r for r in refs if r != own]][:MAX_REFERENCES]
    inputs = {"workflow": "style-anchor" if meta.kind == "anchor" else "hero", "kind": meta.kind, "prompt": prompt,
              "references": refs, "count": count_of(count), "seed": None,
              "folder": rel(image.pack, image.path.parent.parent if image.rejected else image.path.parent),
              "prefix": meta.kind, "source": own, "change": change.strip() if change else None}
    target = image.asset.address if image.asset else image.pack.name
    return jobs.start(image.pack, "generate", target, inputs)


def hero_of(image: ImageRef) -> tuple[ImageRef, m.Image]:
    meta = image.meta
    if meta.kind != "hero" or image.asset is None:
        raise SlopolyError("not_a_hero", "views and segmentation work on hero images")
    if image.rejected:
        raise SlopolyError("hero_rejected", "this hero was rejected by the user")
    return image, meta


def start_views(image: ImageRef, front_yaw: float | None = None) -> dict:
    image, meta = hero_of(image)
    if not image.variants:
        raise SlopolyError("hero_not_picked", "the hero must be picked (a variant's reference) before making its views",
                           f"pick it: slopoly pick {image.asset.address} --heroes")
    old = image.asset.views(image.path.name)
    seed = old.seed if front_yaw is not None and old and old.seed is not None else random.randrange(1, 2**48)
    inputs = {"hero": rel(image.pack, image.path), "seed": seed,
              "front_yaw": None if front_yaw is None else front_yaw % 360}
    return jobs.start(image.pack, "views", image.asset.address, inputs)


def start_segment(image: ImageRef, parts: list[str]) -> dict:
    image, meta = hero_of(image)
    if not image.asset.views(image.path.name):
        raise SlopolyError("no_views", "make the hero's views before segmenting it",
                           f"slopoly gen views {image.pack.ws.rel(image.path)}")
    names = list(dict.fromkeys(p.strip() for p in parts if p.strip() and p.strip() != "object"))
    if not names:
        raise SlopolyError("no_parts", "name at least one part to segment")
    return jobs.start(image.pack, "segment", image.asset.address, {"hero": rel(image.pack, image.path), "parts": names})


# --- running jobs ------------------------------------------------------------------------------------------------

def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def mask_png(mask: np.ndarray) -> bytes:
    return png_bytes(Image.fromarray((mask * 255).astype("uint8"), "L"))


def mask_of(data: bytes) -> np.ndarray:
    return colors.mask_array(Image.open(io.BytesIO(data)))


def box(mask: np.ndarray) -> dict[str, int] | None:
    found = colors.bounds(mask)
    return None if found is None else {"x": found[0], "y": found[1], "width": found[2], "height": found[3]}


class Runner:
    """Runs workflows for one job: uploads inputs, records prompt ids for cancelling, reports progress."""

    def __init__(self, context: jobs.JobContext, client: ComfyClient | None = None):
        self.context, self.client = context, client or ComfyClient.from_config()
        self.client.system_stats()

    def upload(self, path: Path) -> str:
        return self.client.upload(path.read_bytes(), f"{self.context.job.id}_{path.name}")

    def placeholder(self) -> str:
        return self.client.upload(png_bytes(Image.new("RGB", (64, 64))), "placeholder.png")

    def run(self, name: str, values: dict[str, Any], share: tuple[float, float] = (0.0, 1.0)) -> dict[str, list[bytes]]:
        """Runs a workflow; returns image bytes per output name. ``share`` is this run's (start, span) of progress."""
        prompt = workflow.load(name)
        start, span = share
        self.context.progress(start)
        outputs = self.client.run(workflow.fill(prompt, values), lambda p: self.context.progress(start + span * p),
                                  self.context.remember_prompt)
        named = workflow.outputs(prompt)
        return {named[node]: [self.client.image(item) for item in out.get("images", [])]
                for node, out in outputs.items() if node in named}


def write_outputs(context: jobs.JobContext, files: dict[Path, bytes | Any]) -> None:
    """Writes all outputs only after a last cancellation check; YAML values are models or dicts."""
    context.check()
    for path, value in files.items():
        if isinstance(value, bytes):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        else:
            write_yaml(path, value)


@jobs.kind("generate")
def generate(context: jobs.JobContext, client: ComfyClient | None = None) -> dict:
    inputs, ws = context.inputs, context.ws
    runner = Runner(context, client)
    values: dict[str, Any] = {"prompt": inputs["prompt"]}
    refs = list(inputs.get("references") or [])
    prompt = workflow.load(inputs["workflow"])
    for i, slot in enumerate(workflow.reference_slots(prompt)):
        if i < len(refs):
            values[f"reference_{slot}"] = runner.upload(ws.root / refs[i])
            values[f"use_reference_{slot}"] = True
        else:
            values[f"reference_{slot}"] = runner.placeholder()
            values[f"use_reference_{slot}"] = False
    count = int(inputs.get("count") or 1)
    seed = inputs.get("seed")
    seed = int(seed) if seed is not None else random.randrange(2**48)
    produced = []
    for i in range(count):
        out = runner.run(inputs["workflow"], {**values, "seed": seed + i}, (i / count, 1 / count))
        produced += [(data, seed + i) for data in out.get("image", [])]
    if not produced:
        raise SlopolyError("bad_workflow", f"the {inputs['workflow']} workflow produced no image (it needs out:image)")
    folder = ws.root / inputs["folder"]
    context.check()
    first = int(next_name(folder, inputs["prefix"]).stem.rsplit("_", 1)[1])
    files, results = {}, []
    for i, (data, image_seed) in enumerate(produced):
        path = folder / f"{inputs['prefix']}_{first + i:03d}.png"
        size = Image.open(io.BytesIO(data)).size
        files[path] = data
        files[path.with_suffix(".yaml")] = m.Image(
            kind=inputs["kind"], prompt=inputs["prompt"], change=inputs.get("change"), seed=image_seed,
            references=refs, source=inputs.get("source"), job=context.job.id, width=size[0], height=size[1])
        results.append({"path": ws.rel(path), "seed": image_seed, "width": size[0], "height": size[1]})
    write_outputs(context, files)
    return {"images": results}


@jobs.kind("views")
def make_views(context: jobs.JobContext, client: ComfyClient | None = None) -> dict:
    inputs, ws = context.inputs, context.ws
    hero = ws.image(inputs["hero"])
    runner = Runner(context, client)
    produced = runner.run("views", {"image": runner.upload(hero.path), "seed": int(inputs["seed"])}, (0.0, 0.9))
    if not produced.get("ring") or not produced.get("hero_mask"):
        raise SlopolyError("bad_workflow", "the views workflow produced no turntable (it needs out:ring, out:ring_mask, "
                           "out:above, out:above_mask and out:hero_mask)")
    ring_masks = [mask_of(x) for x in produced["ring_mask"]]
    n = len(ring_masks)
    if inputs.get("front_yaw") is not None:
        front, how = turntable.frame_of(float(inputs["front_yaw"]), n), "given"
    else:
        hero_rgb = np.asarray(Image.open(hero.path).convert("RGB"))
        picked = turntable.pick_front(ring_masks, mask_of(produced["hero_mask"][0]),
                                      [np.asarray(Image.open(io.BytesIO(c)).convert("RGB")) for c in produced["ring"]],
                                      hero_rgb)
        front, how = picked["front"], picked["how"]
    folder = hero.asset.views_dir(hero.path.name)
    files, out = {}, []
    for view, (kind, k) in turntable.frames(front, n).items():
        mask = ring_masks[k] if kind == "ring" else mask_of(produced["above_mask"][k])
        colour = produced[kind][k]
        size = Image.open(io.BytesIO(colour)).size
        files[folder / f"{view}.png"] = colour
        files[folder / f"{view}_mask.png"] = mask_png(mask)
        out.append(m.View(view=view, image=f"{view}.png", mask=f"{view}_mask.png", width=size[0], height=size[1],
                          bounds=box(mask)))
    meta = m.Views(hero=hero.path.name, seed=int(inputs["seed"]), front_yaw=turntable.yaw_of(front, n), front=how,
                   job=context.job.id, views=out)
    files[folder / "views.yaml"] = meta
    context.check()
    for stale in (folder, hero.asset.masks_dir(hero.path.name)):  # new views replace the old ones and their masks
        if stale.exists():
            shutil.rmtree(stale)
    write_outputs(context, files)
    return {"hero": ws.rel(hero.path), "front_yaw": meta.front_yaw, "front": how,
            "views": [{"view": v.view, "image": ws.rel(folder / v.image), "mask": ws.rel(folder / v.mask),
                       "width": v.width, "height": v.height, "bounds": v.bounds} for v in out]}


@jobs.kind("segment")
def segment(context: jobs.JobContext, client: ComfyClient | None = None) -> dict:
    inputs, ws = context.inputs, context.ws
    hero = ws.image(inputs["hero"])
    asset = hero.asset
    views = asset.views(hero.path.name)
    parts = list(inputs["parts"])
    runner = Runner(context, client)
    views_folder, folder = asset.views_dir(hero.path.name), asset.masks_dir(hero.path.name)
    files, masks, missing = {}, [], []
    runs, done = max(len(views.views) * len(parts), 1), 0
    for v in views.views:
        image = Image.open(views_folder / v.image).convert("RGB")
        whole = colors.mask_array(Image.open(views_folder / v.mask))
        image_ref = runner.upload(views_folder / v.image)

        def record(part: str, mask: np.ndarray, path: str):
            masks.append(m.Mask(part=part, view=v.view, path=path, bounds=box(mask), area=int(mask.sum()),
                                colors=colors.dominant_colors(image, mask)))

        record("object", whole, Path("..", "..", "views", views_folder.name, v.mask).as_posix())
        for part in parts:
            produced = runner.run("segment-parts", {"image": image_ref, "prompt": f"{part}:{MAX_INSTANCES}"},
                                  (done / runs, 1 / runs))
            done += 1
            data = (produced.get("mask") or [None])[0]
            mask = colors.mask_array(Image.open(io.BytesIO(data)).resize(image.size)) if data else None
            if mask is None or colors.bounds(mask) is None or mask.mean() < MIN_MASK_SHARE:
                missing.append({"part": part, "view": v.view, "reason": "not_found"})
                continue
            if len(parts) > 1 and colors.iou(mask, whole) >= WHOLE_OBJECT_IOU:
                missing.append({"part": part, "view": v.view, "reason": "whole_object"})
                continue
            name = f"{part}_{v.view}.png"
            files[folder / name] = mask_png(mask)
            record(part, mask, name)
    meta = m.Masks(hero=hero.path.name, parts=parts, job=context.job.id, masks=masks, missing=missing)
    files[folder / "masks.yaml"] = meta
    context.check()
    if folder.exists():
        shutil.rmtree(folder)
    write_outputs(context, files)
    return {"hero": ws.rel(hero.path),
            "views": [{"view": v.view, "width": v.width, "height": v.height, "bounds": v.bounds} for v in views.views],
            "masks": [{"part": k.part, "view": k.view, "path": ws.rel(folder / k.path), "bounds": k.bounds,
                       "area": k.area, "colors": k.colors} for k in masks],
            "missing": missing}
