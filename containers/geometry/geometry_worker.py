"""Geometry worker: builds part programs into validated, scored GLB files.

build: inputs {programVersionId, source, polyBudget, palette: [entries], turnaround, masks: [{part, view, fileId}]};
  outputs {glbFileId, validated, report, paletteEntryIds}. The program runs in a subprocess (slopoly_model.runner)
  with a timeout, so a runaway or crashing program can't take the worker down.
palette-render: inputs {main: [entries], variants: [{id, name, entries}], builds: [{buildId, glbFileId}]};
  outputs {textureFileId, variants: {variantId: fileId}, builds: {buildId: glbFileId}}. Builds get the new main
  texture embedded; their meshes, UVs and programs are untouched.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from slopoly_model import glb
from slopoly_model import palette as pal
from slopoly_worker import Job, JobFailed, run

BUILD_TIMEOUT = float(os.environ.get("SLOPOLY_BUILD_TIMEOUT", "120"))


async def run_runner(folder: Path) -> str:
    """Runs the build subprocess; returns its output. Kills it on timeout or cancellation."""
    process = await asyncio.create_subprocess_exec(sys.executable, "-m", "slopoly_model.runner", str(folder),
                                                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), BUILD_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError) as error:
        process.kill()
        await process.wait()
        if isinstance(error, TimeoutError):
            raise JobFailed(f"The program did not finish within {BUILD_TIMEOUT:.0f} s.", "timeout") from None
        raise
    if process.returncode not in (0, 2):
        tail = output.decode(errors="replace").strip().splitlines()[-15:]
        raise JobFailed("The build crashed:\n" + "\n".join(tail), "build_crashed")
    return output.decode(errors="replace")


async def build(job: Job) -> dict[str, Any]:
    inputs = job.inputs
    with tempfile.TemporaryDirectory(prefix=f"build_{job.id}_") as directory:
        folder = Path(directory)
        masks = []
        for i, mask in enumerate(inputs.get("masks") or []):
            path = await job.download(mask["fileId"], folder / "masks" / f"{i}.png")
            masks.append({"part": mask["part"], "view": mask["view"], "path": str(path), "colors": mask.get("colors") or []})
        job_file = {"source": inputs.get("source") or "", "polyBudget": inputs.get("polyBudget"),
                    "palette": inputs.get("palette") or [], "masks": masks}
        (folder / "job.json").write_text(json.dumps(job_file), encoding="utf-8")
        await job.progress(0.2)

        await run_runner(folder)
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        if "error" in report:
            where = f"line {report['line']}: " if report.get("line") else ""
            raise JobFailed(f"Program error at {where}{report['error']}", "program_error")
        await job.progress(0.9)

        glb = await job.upload(folder / "model.glb", "model.glb", "model/gltf-binary")
        roles = set(report["palette"]["roles"])
        entry_ids = [e["id"] for e in inputs.get("palette") or [] if e.get("role") in roles and e.get("id")]
        return {"glbFileId": glb, "validated": report["validated"], "report": report, "paletteEntryIds": entry_ids}


def png(entries: list[dict]) -> bytes:
    buffer = io.BytesIO()
    pal.render([pal.Entry.parse(e) for e in entries]).save(buffer, "PNG")
    return buffer.getvalue()


async def palette_render(job: Job) -> dict[str, Any]:
    inputs = job.inputs
    main = png(inputs.get("main") or [])
    outputs: dict[str, Any] = {"textureFileId": await job.upload(main, "palette.png", "image/png"),
                               "variants": {}, "builds": {}}
    for variant in inputs.get("variants") or []:
        outputs["variants"][variant["id"]] = await job.upload(png(variant["entries"]), f"palette_{variant['name']}.png",
                                                              "image/png")
    builds = inputs.get("builds") or []
    for i, item in enumerate(builds):
        recoloured = glb.replace_image(await job.read(item["glbFileId"]), main)
        outputs["builds"][item["buildId"]] = await job.upload(recoloured, "model.glb", "model/gltf-binary")
        await job.progress((i + 1) / len(builds))
    return outputs


if __name__ == "__main__":
    run({"build": build, "palette-render": palette_render})
