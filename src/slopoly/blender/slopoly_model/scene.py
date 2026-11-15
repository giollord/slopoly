"""Scene composer, run inside Blender by ``slopoly scene build`` (through ``slopoly/blender/launcher.py``).

Reads ``<dir>/scene.json`` {placements: [{name, path, at, rot, scale}]} (metres, Y up, Euler degrees X then Y then Z),
imports each asset GLB under an empty named after its placement, and writes ``<dir>/scene.glb`` and
``<dir>/report.json`` {bounds, placements: [{name, bounds, grounded}], overlaps: [{a, b, fraction}]}.
Bounding boxes are enough to place assets; the user judges the rest by looking.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

from .export import FROM_BLENDER, TO_BLENDER
from .shapes import rotation_matrix

GROUND_TOLERANCE = 0.02  # metres
OVERLAP_LIMIT = 0.10  # of the smaller box's volume


def _world_bounds(root) -> np.ndarray:
    """[min, max] in program space (Y up) of every mesh under ``root``."""
    points = [FROM_BLENDER @ (obj.matrix_world @ v.co)
              for obj in root.children_recursive if obj.type == "MESH" for v in obj.data.vertices]
    if not points:
        return np.zeros((2, 3))
    array = np.array([p[:] for p in points])
    return np.round(np.array([array.min(0), array.max(0)]), 4)


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    size = np.clip(np.minimum(a[1], b[1]) - np.maximum(a[0], b[0]), 0, None)
    smaller = min(np.prod(a[1] - a[0]), np.prod(b[1] - b[0]))
    return float(np.prod(size) / smaller) if smaller > 0 else 0.0


def _grounded(box: np.ndarray, others: list[np.ndarray]) -> bool:
    """On the ground, or resting on top of a placement whose footprint it shares."""
    bottom = box[0][1]
    if abs(bottom) <= GROUND_TOLERANCE:
        return True
    return any(abs(o[1][1] - bottom) <= GROUND_TOLERANCE
               and box[0][0] < o[1][0] and o[0][0] < box[1][0] and box[0][2] < o[1][2] and o[0][2] < box[1][2]
               for o in others)


def compose(placements: list[dict], out: Path) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    material = None
    roots = {}
    for p in placements:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=p["path"])
        imported = set(bpy.data.objects) - before
        empty = bpy.data.objects.new(p["name"], None)
        scene.collection.objects.link(empty)
        transform = (Matrix.Translation(p["at"]) @ rotation_matrix(p.get("rot"))
                     @ Matrix.Diagonal((*([float(p.get("scale") or 1)] * 3), 1.0)))
        empty.matrix_world = TO_BLENDER @ transform @ FROM_BLENDER
        for obj in imported:
            if obj.type == "MESH":  # all assets share the palette texture: keep one material
                material = material or obj.data.materials[0]
                for i in range(len(obj.data.materials)):
                    obj.data.materials[i] = material
            if obj.parent is None:
                obj.parent = empty
                obj.matrix_parent_inverse = Matrix.Identity(4)
        roots[p["name"]] = empty
    bpy.context.view_layer.update()

    boxes = {name: _world_bounds(root) for name, root in roots.items()}
    report = {
        "bounds": [np.min([b[0] for b in boxes.values()], 0).tolist(), np.max([b[1] for b in boxes.values()], 0).tolist()]
        if boxes else None,
        "placements": [{"name": name, "bounds": box.tolist(),
                        "grounded": _grounded(box, [b for n, b in boxes.items() if n != name])}
                       for name, box in boxes.items()],
        "overlaps": [{"a": a, "b": b, "fraction": round(f, 3)}
                     for (a, ba), (b, bb) in itertools.combinations(boxes.items(), 2)
                     if (f := _overlap(ba, bb)) > OVERLAP_LIMIT],
    }
    for block in list(bpy.data.materials):
        if block is not material and block.users == 0:
            bpy.data.materials.remove(block)
    bpy.ops.export_scene.gltf(filepath=str(out / "scene.glb"), export_format="GLB", export_yup=True, export_extras=True,
                              export_apply=False, export_animations=False, export_cameras=False, export_lights=False)
    return report


def main(directory: str) -> int:
    folder = Path(directory)
    job = json.loads((folder / "scene.json").read_text(encoding="utf-8"))
    report = compose(job.get("placements") or [], folder)
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
