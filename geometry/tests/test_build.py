import json

import numpy as np
import pytest
from conftest import PALETTE, glb_json

import slopoly_model as sm
from slopoly_model import assembly, runner, silhouette
from slopoly_model.validate import validate


# --- validators ---

def test_clean_cart_validates(cart_source):
    model = runner.run_program(cart_source)
    report = validate(model, budget=2000)
    assert report["validated"], report
    assert {c["part"] for c in report["contacts"]} == {"axle", "wheel_L", "wheel_R", "handle_L", "handle_R"}
    allowed = [i for i in report["intersections"] if i["allowed"]]
    assert {(i["a"], i["b"]) for i in allowed} == {("axle", "wheel_L"), ("axle", "wheel_R")}


def test_overlap_is_reported_with_its_volume():
    sm.part("bed", sm.box(1, 0.3, 1))
    sm.part("handle", sm.box(0.1, 0.1, 1), parent="bed", at=(0, 0, 0.6))
    report = validate(assembly.current, budget=2000)
    pair = report["intersections"][0]
    assert (pair["a"], pair["b"], pair["ok"]) == ("bed", "handle", False)
    assert pair["volume"] == pytest.approx(0.1 * 0.1 * 0.4)
    assert not report["validated"]


def test_floating_part_is_disconnected():
    sm.part("bed", sm.box(1, 0.3, 1))
    sm.part("wheel", sm.prism(8, r=0.3, length=0.1, axis="x"), parent="bed", at=(2, 0, 0))
    report = validate(assembly.current, budget=2000)
    assert report["disconnected"] == ["wheel"]
    assert report["contacts"] == [{"part": "wheel", "parent": "bed", "gap": pytest.approx(1.45, abs=0.01), "ok": False}]


def test_budget_is_checked():
    sm.part("ball", sm.prism(64, r=1, length=1))
    report = validate(assembly.current, budget=100)
    assert report["triangles"] == {"count": 64 * 2 + 62 * 2, "budget": 100, "ok": False}


# --- silhouettes ---

def masks_of(model, view, size=(400, 300), margin=20):
    """Synthetic masks: each part's projection fitted into an image, like a perfect segmentation."""
    project = silhouette.VIEWS[view]
    tris = {p.name: silhouette._projected(p, project, (1, 1)) for p in model.parts.values()}
    every = np.concatenate([t.reshape(-1, 2) for t in tris.values()])
    lo, hi = every.min(0), every.max(0)
    scale = min((size[0] - 2 * margin) / (hi - lo)[0], (size[1] - 2 * margin) / (hi - lo)[1])
    offset = np.array(size) / 2 - (lo + hi) / 2 * scale
    return [{"part": silhouette.base_name(name), "view": view,
             "mask": silhouette._fill([t * scale + offset for t in tri], size)} for name, tri in tris.items()]


def merged(masks):
    by_part = {}
    for m in masks:
        key = (m["part"], m["view"])
        by_part[key] = by_part[key] | m["mask"] if key in by_part else m["mask"]
    return [{"part": p, "view": v, "mask": mask} for (p, v), mask in by_part.items()]


def test_matching_program_scores_high(cart_source):
    masks = merged(masks_of(runner.run_program(cart_source), "front") + masks_of(assembly.current, "side"))
    result = silhouette.score(runner.run_program(cart_source), masks)
    assert result["mean_iou"] > 0.95
    wheel = next(p for p in result["views"][0]["parts"] if p["mask"] == "wheel")
    assert wheel["parts"] == ["wheel_L", "wheel_R"]


def test_narrow_wheel_gives_negative_width_error(cart_source):
    masks = merged(masks_of(runner.run_program(cart_source), "front"))
    narrow = runner.run_program(cart_source.replace("length=0.08", "length=0.04"))
    front = silhouette.score(narrow, masks)["views"][0]
    wheel = next(p for p in front["parts"] if p["mask"] == "wheel")
    assert wheel["width_error"] < -0.01
    assert wheel["iou"] < 0.9


def test_mirrored_sheet_is_matched_by_flipping(cart_source):
    masks = merged(masks_of(runner.run_program(cart_source), "side"))
    for m in masks:
        m["mask"] = m["mask"][:, ::-1]
    side = silhouette.score(runner.run_program(cart_source), masks)["views"][0]
    assert side["flip"] == [-1, 1] and side["mean_iou"] > 0.95


def test_empty_model_is_not_scored():
    mask = {"part": "wheel", "view": "front", "mask": np.ones((10, 10), dtype=bool)}
    assert silhouette.score(assembly.current, [mask]) == {"views": [], "mean_iou": None}


# --- runner and export ---

def run_build(tmp_path, source, **extra):
    (tmp_path / "job.json").write_text(json.dumps({"source": source, "polyBudget": 2000, "palette": PALETTE, **extra}))
    status = runner.main(str(tmp_path))
    return status, json.loads((tmp_path / "report.json").read_text())


def test_program_error_reports_its_line(tmp_path):
    status, report = run_build(tmp_path, "part('bed', box(1, 1, 1))\n\npart('wheel', prism(2, r=1, length=1))\n")
    assert status == 2 and report["line"] == 3 and "segment count" in report["error"]
    status, report = run_build(tmp_path, "part('bed', box(1, 1, 1)\n")
    assert status == 2 and report["line"] == 1 and report["error"].startswith("SyntaxError")


def test_cart_exports_pivots_hierarchy_and_sockets(tmp_path, cart_source):
    status, report = run_build(tmp_path, cart_source)
    assert status == 0 and report["validated"], report["validation"]
    assert report["palette"] == {"roles": ["metal", "wood", "wood dark"], "missing": []}
    gltf = glb_json(tmp_path / "model.glb")
    nodes = {n["name"]: n for n in gltf["nodes"]}
    names = [n["name"] for n in gltf["nodes"]]
    axle = nodes["axle"]
    # axle is a child of bed (at y=0.49): its local origin is on the axle axis (x, y=0.3, z=0 in world)
    assert axle["translation"] == pytest.approx([0, 0.3 - 0.49, 0], abs=1e-6)
    assert axle["extras"]["joint"] == {"type": "rotate", "axis": [1.0, 0.0, 0.0]}
    assert sorted(names[i] for i in axle["children"]) == ["wheel_L", "wheel_R"]
    assert nodes["wheel_L"]["translation"] == pytest.approx([0.5, 0, 0], abs=1e-6)
    assert "socket_hitch" in nodes and "mesh" not in nodes["socket_hitch"]
    sampler = gltf["samplers"][0]
    assert sampler["magFilter"] == 9728  # NEAREST
    assert len(gltf["materials"]) == 1 and len(gltf["images"]) == 1


def test_instances_export_as_shared_meshes(tmp_path):
    source = "\n".join([
        "part('frame', box(2, 0.1, 1), color='wood')",
        "for i in range(3):",
        "    instance(f'plank{i}', box(0.1, 0.05, 0.3 + 0.1 * i), [(-0.9 + 0.2 * j, 0.075, 0) for j in range(10)],",
        "             parent='frame', color='wood dark')",
    ])
    status, report = run_build(tmp_path, source)
    assert status == 0, report
    gltf = glb_json(tmp_path / "model.glb")
    planks = [n for n in gltf["nodes"] if n["name"].startswith("plank")]
    assert len(planks) == 30
    assert len({n["mesh"] for n in planks}) == 3
    assert len(gltf["meshes"]) == 4


def test_unknown_roles_and_untagged_parts_fail_validation(tmp_path):
    status, report = run_build(tmp_path, "part('bed', box(1, 1, 1), color='gold')\npart('lid', box(1, 0.1, 1), parent='bed', at=(0, 0.55, 0))")
    assert status == 0 and not report["validated"]
    issues = {i["issue"]: i for i in report["validation"]["issues"]}
    assert issues["unknown_roles"]["roles"] == ["gold"]
    assert issues["untagged"]["parts"] == ["lid"]
