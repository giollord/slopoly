"""Comfy worker: runs the job's workflow file on the local ComfyUI and reports images, views and part masks.

Operations (job.operation = workflow name):
- style-anchor, turnaround: inputs {prompt, references[], count, seed}; outputs {images: [{fileId, width, height, views}]}.
  Turnaround sheets are 3:1; their views are the three horizontal thirds: front, side, top.
- segment-parts: inputs {conceptImageId, image, views, parts[], object}; the workflow runs once per view and part on the
  view's crop, plus once for the whole object. Outputs {masks: [{part, view, fileId, bounds, area, colors}],
  missing: [{part, view, reason}]}. A mask PNG covers its view's rectangle; bounds are in the whole image's pixels.
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

from PIL import Image

import colors
import workflow
from comfy_client import ComfyClient
from slopoly_worker import Job, JobFailed, run

COMFY_DIR = Path(os.environ.get("COMFYUI_DIR", "/opt/ComfyUI"))
WORKFLOWS = Path(os.environ.get("SLOPOLY_WORKFLOWS", "/opt/slopoly/workflows"))
TURNAROUND_VIEWS = ("front", "side", "top")
MIN_MASK_SHARE = 0.002  # a "found" part covers at least 0.2 % of its view
WHOLE_OBJECT_IOU = 0.9

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
            if job.operation == "turnaround":
                entry["views"] = thirds(image.width, image.height)
            images.append(entry)
    if not images:
        raise JobFailed(f"The {job.operation} workflow produced no image (it needs a save node titled out:image).", "bad_workflow")
    return {"images": images}


def thirds(width: int, height: int) -> dict[str, dict[str, int]]:
    third = width // 3
    return {view: {"x": i * third, "y": 0, "width": third, "height": height} for i, view in enumerate(TURNAROUND_VIEWS)}


async def segment(job: Job, prompt: dict, staging: Staging) -> dict[str, Any]:
    image = Image.open(io.BytesIO(await job.read(job.inputs["image"]))).convert("RGB")
    views = job.inputs.get("views") or {"full": {"x": 0, "y": 0, "width": image.width, "height": image.height}}
    parts = list(job.inputs.get("parts") or [])
    object_name = job.inputs.get("object") or "object"
    masks, missing = [], []
    runs, done = len(views) * (len(parts) + 1), 0
    for view, rect in views.items():
        x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
        crop = image.crop((x, y, x + w, y + h))
        image_ref = staging.save(crop, f"{view}.png")

        async def detect(text: str):
            nonlocal done
            produced = await run_prompt(job, prompt, {"image": image_ref, "prompt": text}, (done / runs, 1 / runs))
            done += 1
            data = (produced.get("mask") or [None])[0]
            return colors.mask_array(Image.open(io.BytesIO(data)).resize(crop.size)) if data else None

        whole = await detect(object_name)
        for part in parts:
            mask = await detect(part)
            box = colors.bounds(mask) if mask is not None else None
            if box is None or mask.mean() < MIN_MASK_SHARE:
                missing.append({"part": part, "view": view, "reason": "not_found"})
                continue
            if len(parts) > 1 and whole is not None and colors.iou(mask, whole) >= WHOLE_OBJECT_IOU:
                missing.append({"part": part, "view": view, "reason": "whole_object"})
                continue
            buffer = io.BytesIO()
            Image.fromarray((mask * 255).astype("uint8"), "L").save(buffer, "PNG")
            masks.append({
                "part": part, "view": view,
                "fileId": await job.upload(buffer.getvalue(), f"mask_{part}_{view}.png", "image/png"),
                "bounds": {"x": x + box[0], "y": y + box[1], "width": box[2], "height": box[3]},
                "area": int(mask.sum()),
                "colors": colors.dominant_colors(crop, mask),
            })
    return {"masks": masks, "missing": missing}


if __name__ == "__main__":
    run({"comfy": handle})
