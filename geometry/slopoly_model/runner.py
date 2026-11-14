"""Build runner, run in a subprocess by the geometry worker: ``python -m slopoly_model.runner <dir>``.

Reads ``<dir>/job.json`` {source, polyBudget, shading, palette: [entries], masks: [{part, view, path, colors}],
views: [{view, path}]}, runs the program, validates, exports, scores silhouettes and renders each view with a
comparison image, then writes ``<dir>/report.json``, ``<dir>/model.glb`` and ``render_<view>.png``/``compare_<view>.png``.
A program error writes {"error", "line"} to report.json and exits with status 2.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path

import bmesh
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image

import slopoly_model as sm

from . import palette as pal
from .assembly import Model, new_model
from .export import export
from .likeness import likeness
from .render import render_views
from .silhouette import OBJECT, score
from .validate import summary, validate

PROGRAM_FILE = "program.py"  # the program's filename in tracebacks; assembly records part lines by it


class ProgramError(Exception):
    def __init__(self, message: str, line: int | None):
        super().__init__(message)
        self.line = line


def run_program(source: str) -> Model:
    """Runs a part program with the slopoly_model API as globals and returns the model it defined."""
    model = new_model()
    namespace = {name: getattr(sm, name) for name in sm.__all__}
    namespace.update(bmesh=bmesh, math=math, Vector=Vector, Matrix=Matrix)  # raw Blender mesh operations
    namespace["__name__"] = "program"
    try:
        exec(compile(source, PROGRAM_FILE, "exec"), namespace)
    except SyntaxError as error:
        raise ProgramError(f"SyntaxError: {error.msg}", error.lineno) from error
    except Exception as error:
        frames = [f for f in traceback.extract_tb(error.__traceback__) if f.filename == PROGRAM_FILE]
        raise ProgramError(f"{type(error).__name__}: {error}", frames[-1].lineno if frames else None) from error
    return model


def load_masks(items: list[dict]) -> list[dict]:
    return [{"part": m["part"], "view": m["view"], "mask": np.asarray(Image.open(m["path"]).convert("L")) >= 128}
            for m in items]


def build(job: dict, out: Path) -> dict:
    """Runs the whole build; returns the report (the GLB is written to out/model.glb)."""
    model = run_program(job.get("source") or "")
    entries = [pal.Entry.parse(e) for e in job.get("palette") or []]
    texture = out / "palette.png"
    pal.render(entries).save(texture)

    validation = validate(model, int(job.get("polyBudget") or 2000))
    untagged = sorted({p.name for p in model.parts.values() if "" in p.face_tags()})
    if untagged:
        validation["issues"].append({"issue": "untagged", "parts": untagged,
                                     "message": "faces without a palette role: set color= on the part or paint()"})
    missing, stats = export(model, out / "model.glb", entries, texture, job.get("shading"))
    if missing:
        validation["issues"].append({"issue": "unknown_roles", "roles": missing,
                                     "message": "palette roles not in the pack palette: add them first"})
    validation["validated"] = validation["validated"] and not untagged and not missing
    used = sorted({pal.split_tag(t)[0] for p in model.parts.values() for t in p.face_tags() if t})
    masks = load_masks(job.get("masks") or [])
    silhouette = score(model, masks)
    objects = {m["view"]: m["mask"] for m in masks if m["part"] == OBJECT}
    views = {v["view"]: Path(v["path"]) for v in job.get("views") or [] if v.get("path")}
    if model.parts:
        render_views(silhouette, views, objects, out)
    if not objects:
        silhouette["renders"] = "missing: the asset has no picked hero with views and masks yet"
    parts = summary(model)
    corners = np.array([b for p in parts for b in p["bounds"]]).reshape(-1, 3)
    return {
        "validated": validation["validated"],
        "bounds": [corners.min(0).tolist(), corners.max(0).tolist()] if len(corners) else None,  # whole model, metres
        "parts": parts,
        "validation": validation,
        "silhouette": silhouette,
        "colors": likeness(model, job.get("masks") or [], entries),
        "palette": {"roles": used, "missing": missing},
        "export": {**stats, "shading": job.get("shading")},
    }


def main(directory: str) -> int:
    folder = Path(directory)
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    try:
        report = build(job, folder)
        status = 0
    except ProgramError as error:
        report, status = {"error": str(error), "line": error.line}, 2
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
