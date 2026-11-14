"""Comfy worker: runs the job's workflow file on the local ComfyUI and reports images, views and part masks.

Operations (job.operation = workflow name):
- style-anchor, hero: inputs {prompt, references[], count, seed}; outputs {images: [{fileId, width, height, seed}]}.
- views: inputs {image (hero file id), seed, frontYaw?}; builds the hero's splat and renders orthographic turntables
  (see views.py). Outputs {frontYaw, front: detected|assumed|given, views: [{view, fileId, maskFileId, width, height,
  bounds}]} for the views front, side, top and back. The same seed rebuilds the same splat, so a given frontYaw only
  changes which frames are kept.
- segment-parts: inputs {views: [{conceptImageId, view, image, mask}], parts[]}; the workflow runs once per view
  image and part. Each view's render silhouette is its whole-object mask, stored as part "object". Outputs
  {masks: [{conceptImageId, part, view, fileId, bounds, area, colors}], missing: [{part, view, reason}]}.
  Open-vocabulary detection returns the most salient object for names it can't find, so a part whose mask is about the
  whole object (IoU >= WHOLE_OBJECT_IOU) is reported missing with reason "whole_object" (unless it is the only part).
"""

from __future__ import annotations

import io
import os
import random
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

import colors
import views as turntable
import workflow
from comfy_client import ComfyClient
from slopoly_worker import Job, JobFailed, run

COMFY_DIR = Path(os.environ.get("COMFYUI_DIR", "/opt/ComfyUI"))
WORKFLOWS = Path(os.environ.get("SLOPOLY_WORKFLOWS", "/opt/slopoly/workflows"))
MIN_MASK_SHARE = 0.002  # a "found" part covers at least 0.2 % of its view
WHOLE_OBJECT_IOU = 0.9
# SAM 3 keeps only the best object per text prompt unless the prompt says "name:N"; a view can show several of a part
# (both wheels, both handles), so every part asks for up to this many and gets their union.
MAX_INSTANCES = 8

comfy = ComfyClient(f"http://127.0.0.1:{os.environ.get('COMFYUI_PORT', '8188')}")


class Staging:
    """Job input files in ComfyUI's input folder, removed after the job."""

    def __init__(self, job: Job):
        self.job = job
        self.folder = COMFY_DIR / "input" / f"slopoly_{job.id}"
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> tuple[Path, str]:
        """Local path and the name LoadImage takes (relative to the input folder)."""
        return self.folder / name, f"{self.folder.name}/{name}"

    def save(self, image: Image.Image, name: str) -> str:
        path, ref = self.path(name)
        image.save(path)
        return ref

    async def fetch(self, file_id: str, name: str) -> str:
        path, ref = self.path(name)
        await self.job.download(file_id, path)
        return ref

    def placeholder(self) -> str:
        path, ref = self.path("placeholder.png")
        if not path.exists():
            Image.new("RGB", (64, 64)).save(path)
        return ref

    def cleanup(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)


async def handle(job: Job) -> dict[str, Any]:
    await comfy.wait_ready()
    prompt = workflow.load(WORKFLOWS, job.operation or "")
    staging = Staging(job)
    try:
        if job.operation == "segment-parts":
            return await segment(job, prompt, staging)
        if job.operation == "views":
            return await make_views(job, prompt, staging)
        return await generate(job, prompt, staging)
    finally:
        staging.cleanup()


async def run_prompt(job: Job, prompt: dict, values: dict[str, Any], share: tuple[float, float] = (0.0, 1.0)) -> dict[str, list[bytes]]:
    """Runs the filled prompt; returns image bytes per output name. ``share`` is this run's (start, span) of the job progress."""
    start, span = share
    outputs = await comfy.run(workflow.fill(prompt, values), lambda p: job.progress(start + span * p))
    named = workflow.outputs(prompt)
    result: dict[str, list[bytes]] = {}
    for node_id, node_out in outputs.items():
        if node_id in named:
            result[named[node_id]] = [await comfy.image(item) for item in node_out.get("images", [])]
    return result


async def generate(job: Job, prompt: dict, staging: Staging) -> dict[str, Any]:
    values: dict[str, Any] = {"prompt": job.inputs.get("prompt", "")}
    references = list(job.inputs.get("references") or [])
    slots = workflow.reference_slots(prompt)
    for i, slot in enumerate(slots):
        if i < len(references):
            values[f"reference_{slot}"] = await staging.fetch(references[i], f"reference_{slot}.png")
            values[f"use_reference_{slot}"] = True
        else:
            values[f"reference_{slot}"] = staging.placeholder()
            values[f"use_reference_{slot}"] = False

    count = max(1, min(int(job.inputs.get("count") or 1), 4))
    seed = job.inputs.get("seed")
    seed = int(seed) if seed is not None else random.randrange(2**48)
    images = []
    for i in range(count):
        produced = await run_prompt(job, prompt, {**values, "seed": seed + i}, (i / count, 1 / count))
        for data in produced.get("image", []):
            image = Image.open(io.BytesIO(data))
            entry = {"fileId": await job.upload(data, f"{job.operation}_{len(images) + 1}.png", "image/png"),
                     "width": image.width, "height": image.height, "seed": seed + i}
            images.append(entry)
    if not images:
        raise JobFailed(f"The {job.operation} workflow produced no image (it needs a save node titled out:image).", "bad_workflow")
    return {"images": images}


def mask_of(data: bytes) -> np.ndarray:
    return colors.mask_array(Image.open(io.BytesIO(data)))


def rgb_of(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))


def png(mask: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray((mask * 255).astype("uint8"), "L").save(buffer, "PNG")
    return buffer.getvalue()


def box(mask: np.ndarray) -> dict[str, int] | None:
    found = colors.bounds(mask)
    return None if found is None else {"x": found[0], "y": found[1], "width": found[2], "height": found[3]}


async def make_views(job: Job, prompt: dict, staging: Staging) -> dict[str, Any]:
    image_ref = await staging.fetch(job.inputs["image"], "hero.png")
    seed = int(job.inputs.get("seed") or 0)
    produced = await run_prompt(job, prompt, {"image": image_ref, "seed": seed}, (0.0, 0.9))
    if not produced.get("ring") or not produced.get("hero_mask"):
        raise JobFailed("The views workflow produced no turntable (it needs out:ring, out:ring_mask, out:above, "
                        "out:above_mask and out:hero_mask).", "bad_workflow")
    ring_masks = [mask_of(m) for m in produced["ring_mask"]]
    n = len(ring_masks)
    if job.inputs.get("frontYaw") is not None:
        front, how = turntable.frame_of(float(job.inputs["frontYaw"]), n), "given"
    else:
        hero = np.asarray(Image.open(io.BytesIO(await job.read(job.inputs["image"]))).convert("RGB"))
        picked = turntable.pick_front(ring_masks, mask_of(produced["hero_mask"][0]),
                                      [rgb_of(c) for c in produced["ring"]], hero)
        front, how = picked["front"], picked["how"]
    out = []
    for view, (kind, k) in turntable.frames(front, n).items():
        mask = ring_masks[k] if kind == "ring" else mask_of(produced["above_mask"][k])
        color = produced[kind][k]
        size = Image.open(io.BytesIO(color)).size
        out.append({
            "view": view,
            "fileId": await job.upload(color, f"view_{view}.png", "image/png"),
            "maskFileId": await job.upload(png(mask), f"view_{view}_mask.png", "image/png"),
            "width": size[0], "height": size[1], "bounds": box(mask),
        })
    return {"frontYaw": turntable.yaw_of(front, n), "front": how, "views": out}


async def segment(job: Job, prompt: dict, staging: Staging) -> dict[str, Any]:
    parts = list(job.inputs.get("parts") or [])
    items = list(job.inputs.get("views") or [])
    masks, missing = [], []
    runs, done = max(len(items) * len(parts), 1), 0
    for item in items:
        view = item["view"]
        image = Image.open(io.BytesIO(await job.read(item["image"]))).convert("RGB")
        whole = mask_of(await job.read(item["mask"])) if item.get("mask") else None
        image_ref = staging.save(image, f"{view}.png")

        def record(part: str, mask: np.ndarray, file_id: str):
            masks.append({"conceptImageId": item["conceptImageId"], "part": part, "view": view, "fileId": file_id,
                          "bounds": box(mask), "area": int(mask.sum()), "colors": colors.dominant_colors(image, mask)})

        if whole is not None:
            record("object", whole, item["mask"])
        for part in parts:
            produced = await run_prompt(job, prompt, {"image": image_ref, "prompt": f"{part}:{MAX_INSTANCES}"}, (done / runs, 1 / runs))
            done += 1
            data = (produced.get("mask") or [None])[0]
            mask = colors.mask_array(Image.open(io.BytesIO(data)).resize(image.size)) if data else None
            if mask is None or colors.bounds(mask) is None or mask.mean() < MIN_MASK_SHARE:
                missing.append({"part": part, "view": view, "reason": "not_found"})
                continue
            if len(parts) > 1 and whole is not None and colors.iou(mask, whole) >= WHOLE_OBJECT_IOU:
                missing.append({"part": part, "view": view, "reason": "whole_object"})
                continue
            record(part, mask, await job.upload(png(mask), f"mask_{part}_{view}.png", "image/png"))
    return {"masks": masks, "missing": missing}


if __name__ == "__main__":
    run({"comfy": handle})
