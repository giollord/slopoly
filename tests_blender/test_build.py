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


def test_overlap_between_parts_is_reported_but_allowed():
    sm.part("bed", sm.box(1, 0.3, 1))
    sm.part("handle", sm.box(0.1, 0.1, 1), parent="bed", at=(0, 0, 0.6))
    report = validate(assembly.current, budget=2000)
    pair = report["intersections"][0]
    assert (pair["a"], pair["b"], pair["ok"]) == ("bed", "handle", False)
    assert pair["volume"] == pytest.approx(0.1 * 0.1 * 0.4)
    assert report["validated"]  # parts may overlap; only a part's own mesh must not cut through itself


def test_floating_part_is_disconnected():
    sm.part("bed", sm.box(1, 0.3, 1))
    sm.part("wheel", sm.prism(8, r=0.3, length=0.1, axis="x"), parent="bed", at=(2, 0, 0))
    report = validate(assembly.current, budget=2000)
    assert report["disconnected"] == ["wheel"]
    contact = report["contacts"][0]
    assert {k: contact[k] for k in ("part", "parent", "ok")} == {"part": "wheel", "parent": "bed", "ok": False}
    assert contact["gap"] == pytest.approx(1.45, abs=0.01)
    # the nearest points say where to move: the wheel's inner face at x=1.95 and the bed's side at x=0.5
    assert contact["nearest"][0] == pytest.approx(1.95, abs=0.01)
    assert contact["parent_nearest"][0] == pytest.approx(0.5, abs=0.01)


def test_budget_is_checked():
    sm.part("ball", sm.prism(64, r=1, length=1))
    report = validate(assembly.current, budget=100)
    assert report["triangles"] == {"count": 64 * 2 + 62 * 2, "budget": 100, "ok": False}


# --- silhouettes ---

def masks_of(model, view, size=(400, 300), margin=20):
    """Synthetic masks: each part's projection fitted into an image, like a perfect segmentation."""
    project = silhouette.VIEWS[view]
    tris = {p.name: silhouette._projected(p, project) for p in model.parts.values()}
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


def with_object(masks):
    """Adds each view's silhouette (the union of its part masks), as the views job renders it."""
    views = {}
    for m in masks:
        views[m["view"]] = views[m["view"]] | m["mask"] if m["view"] in views else m["mask"]
    return masks + [{"part": "object", "view": v, "mask": mask} for v, mask in views.items()]


def test_matching_silhouette_scores_high_in_every_view(cart_source):
    model = runner.run_program(cart_source)
    masks = with_object(merged([m for view in silhouette.VIEWS for m in masks_of(model, view)]))
    result = silhouette.score(runner.run_program(cart_source), masks)
    assert result["mean_object_iou"] > 0.9
    assert {v["view"] for v in result["views"]} == {"front", "side", "top", "back"}
    assert all(v["object"]["iou"] > 0.9 for v in result["views"])


def test_misplaced_small_part_lowers_only_its_part_score(cart_source):
    masks = with_object(merged(masks_of(runner.run_program(cart_source), "top")))
    good = silhouette.score(runner.run_program(cart_source), masks)["views"][0]
    moved = cart_source.replace("at=(0.3, 0.55, -0.35)", "at=(0.2, 0.55, -0.35)")  # handles 10 cm further in
    assert moved != cart_source
    bad = silhouette.score(runner.run_program(moved), masks)["views"][0]
    part = lambda r, name: next(p for p in r["parts"] if p["mask"] == name)["iou"]
    assert part(bad, "handle") < part(good, "handle") - 0.3
    assert part(bad, "bed") == part(good, "bed")  # the other parts keep their scores
    assert good["object"]["iou"] - bad["object"]["iou"] < (part(good, "handle") - part(bad, "handle")) / 2


def test_mirrored_view_scores_low(cart_source):
    masks = with_object(merged(masks_of(runner.run_program(cart_source), "side")))
    for m in masks:
        m["mask"] = m["mask"][:, ::-1]
    side = silhouette.score(runner.run_program(cart_source), masks)["views"][0]
    assert side["mean_iou"] < 0.9


def test_mask_matches_every_part_named_after_it():
    sm.part("bed", sm.box(1, 0.2, 1))
    for name in ("wheel_front_L", "wheel_back_R"):
        sm.part(name, sm.prism(8, r=0.3, length=0.08, axis="x"), parent="bed", at=(0.5, 0, 0))
    sm.part("wheelbarrow", sm.box(0.1, 0.1, 0.1), parent="bed")
    names = [p.name for p in silhouette.parts_for(assembly.current, "wheel")]
    assert names == ["wheel_front_L", "wheel_back_R"]


def test_empty_model_is_not_scored():
    mask = {"part": "wheel", "view": "front", "mask": np.ones((10, 10), dtype=bool)}
    assert silhouette.score(assembly.current, [mask]) == {"views": [], "mean_iou": None, "mean_object_iou": None}


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


def test_metric_view_fit_reports_absolute_size():
    # a 1 m wide, 1 m tall view silhouette at 100 px per metre, standing on the ground at row 150
    mask = np.zeros((200, 200), bool)
    mask[50:150, 50:150] = True
    fit = {"scale": 100.0, "offset": [100.0, 150.0], "image": [200, 200]}
    sm.part("bed", sm.box(1.1, 1.0, 1.0).move(y=0.5))  # 10 % too wide
    result = silhouette.score(assembly.current, [{"part": "object", "view": "front", "mask": mask}], {"front": fit})
    front = result["views"][0]
    assert front["scaling"] == "metric"
    assert front["object"]["width_error"] == pytest.approx(0.1, abs=0.011)
    assert front["object"]["height_error"] == pytest.approx(0.0, abs=0.011)
    fitted = silhouette.score(assembly.current, [{"part": "object", "view": "front", "mask": mask}])["views"][0]
    assert fitted["scaling"] == "fitted" and abs(fitted["object"]["width_error"]) < 0.06  # proportions only
