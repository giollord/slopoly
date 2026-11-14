"""Pack shading in the export: flat, smooth with a hard-edge angle, program overrides, palette boundaries."""
from collections import defaultdict

import numpy as np

from conftest import PALETTE, glb_accessor, glb_json
from slopoly_model.runner import build

SMOOTH = {"mode": "smooth", "hardEdgeAngle": 60}


def exported(tmp_path, source: str, shading: dict | None = None):
    """(positions, normals) of the first mesh of the built GLB."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    report = build({"source": source, "palette": PALETTE, "shading": shading}, tmp_path)
    assert "error" not in report
    gltf = glb_json(tmp_path / "model.glb")
    attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
    path = tmp_path / "model.glb"
    return glb_accessor(path, gltf, attributes["POSITION"]), glb_accessor(path, gltf, attributes["NORMAL"])


def side(positions, normals):
    keep = np.abs(normals[:, 1]) < 0.9
    return positions[keep], normals[keep]


def radial(positions):
    flat = positions * np.array([1, 0, 1])
    return flat / np.linalg.norm(flat, axis=1, keepdims=True)


def test_smooth_cylinder_shares_side_normals_and_keeps_caps_hard(tmp_path):
    positions, normals = exported(tmp_path, "part('wheel', prism(8, r=0.3, length=0.1, tag='wood'))", SMOOTH)
    sides, side_normals = side(positions, normals)
    np.testing.assert_allclose(side_normals, radial(sides), atol=1e-3)  # averaged around the rim
    caps = normals[np.abs(normals[:, 1]) >= 0.9]
    assert len(caps) == 16 and np.allclose(np.abs(caps[:, 1]), 1, atol=1e-4)  # caps split off: hard edges
    assert len(positions) == 32  # 16 rim vertices shared by the side, plus 16 cap copies


def test_flat_build_has_per_face_normals(tmp_path):
    positions, normals = exported(tmp_path, "part('wheel', prism(8, r=0.3, length=0.1, tag='wood'))")
    sides, side_normals = side(positions, normals)
    deviation = np.degrees(np.arccos(np.clip((side_normals * radial(sides)).sum(1), -1, 1)))
    assert np.allclose(deviation, 22.5, atol=0.1)  # face normals, half a segment off the vertex direction
    assert len(positions) == 8 * 4 + 2 * 8


def test_smooth_override_shares_box_corners(tmp_path):
    positions, normals = exported(tmp_path, "part('cushion', smooth(box(1, 1, 1, tag='wood')))", SMOOTH)
    assert len(positions) == 8
    np.testing.assert_allclose(np.abs(normals), 1 / np.sqrt(3), atol=1e-3)


def test_sharp_override_splits_a_seam(tmp_path):
    plain, _ = exported(tmp_path / "a", "part('post', prism(8, r=0.3, length=1, tag='wood'))", SMOOTH)
    seamed, _ = exported(tmp_path / "b", "part('post', sharp(prism(8, r=0.3, length=1, tag='wood'), "
                                         "lambda c, n: n[0] > 0.9))", SMOOTH)
    assert len(seamed) == len(plain) + 4  # the selected face's two side edges are hard: their vertices split


def test_part_flat_override_in_a_smooth_pack(tmp_path):
    positions, normals = exported(tmp_path, "part('wheel', prism(8, r=0.3, length=0.1, tag='wood'), shading='flat')",
                                  SMOOTH)
    assert len(positions) == 8 * 4 + 2 * 8


def test_palette_boundary_is_not_a_hard_edge(tmp_path):
    source = "part('post', paint(prism(8, r=0.3, length=1, tag='wood'), 'metal', lambda c, n: c[0] > 0))"
    positions, normals = exported(tmp_path, source, SMOOTH)
    sides, side_normals = side(positions, normals)
    by_position = defaultdict(list)
    for p, n in zip(np.round(sides, 5), side_normals):
        by_position[tuple(p)].append(n)
    split = [ns for ns in by_position.values() if len(ns) > 1]
    assert split, "the role boundary should split vertices (different palette UVs)"
    for ns in split:
        np.testing.assert_allclose(ns, [ns[0]] * len(ns), atol=1e-5)


SHADED = {"mode": "flat", "shadeStrength": 0.5}
OPEN_BOX = ("bed = box(0.8, 0.4, 0.8, tag='wood')\n"
            "bed = extrude(inset(bed, 'top', 0.05, tag='wood dark'), 'wood dark', -0.3, tag='wood dark')\n"
            "part('bed', bed)\n")


def colours(tmp_path, source, shading):
    """(gltf, positions, normals, COLOR_0 as floats or None) of the first mesh."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    report = build({"source": source, "palette": PALETTE, "shading": shading}, tmp_path)
    path = tmp_path / "model.glb"
    gltf = glb_json(path)
    attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
    color = None
    if "COLOR_0" in attributes:
        accessor = gltf["accessors"][attributes["COLOR_0"]]
        scale = {5121: 255.0, 5123: 65535.0}.get(accessor["componentType"], 1.0)
        color = glb_accessor(path, gltf, attributes["COLOR_0"]).astype(float) / scale
    return (report, gltf, glb_accessor(path, gltf, attributes["POSITION"]), glb_accessor(path, gltf, attributes["NORMAL"]),
            color)


def test_open_box_is_darker_inside(tmp_path):
    report, _, positions, normals, color = colours(tmp_path, OPEN_BOX, SHADED)
    assert color is not None
    up = normals[:, 1] > 0.9
    floor = color[up & (positions[:, 1] < 0.0), 0]
    rim = color[up & (positions[:, 1] > 0.19), 0]
    assert floor.mean() < rim.mean() - 0.1
    assert np.allclose(color[:, 0], color[:, 1]) and np.allclose(color[:, 1], color[:, 2])  # grey
    assert color[:, :3].min() >= 0.35 - 1e-3 and color[:, :3].max() <= 1.0
    assert report["export"]["vertices"] == len(positions) and report["export"]["shadeSeconds"] >= 0


def test_instances_share_one_shaded_mesh(tmp_path):
    source = "instance('crate', box(0.5, 0.5, 0.5, tag='wood'), [(0, 0.25, 0), (0.5, 0.25, 0), (1.0, 0.25, 0)])\n"
    _, gltf, _, _, color = colours(tmp_path, source, SHADED)
    assert len(gltf["meshes"]) == 1 and color is not None
    assert sum(1 for n in gltf["nodes"] if "mesh" in n) == 3


def test_strength_zero_has_no_vertex_colour(tmp_path):
    _, _, _, _, color = colours(tmp_path, OPEN_BOX, {"mode": "flat", "shadeStrength": 0})
    assert color is None


def test_curve_parts_use_only_the_palette_uvs(tmp_path):
    source = "part('h', curve([(0, 0, 0), (0, 0.1, -0.5), (0, 0.3, -0.9)], ngon(6, r=0.03), resolution=3, tag='wood dark'))\n"
    tmp_path.mkdir(parents=True, exist_ok=True)
    build({"source": source, "palette": PALETTE}, tmp_path)
    gltf = glb_json(tmp_path / "model.glb")
    attributes = gltf["meshes"][0]["primitives"][0]["attributes"]
    assert "TEXCOORD_1" not in attributes
    uvs = glb_accessor(tmp_path / "model.glb", gltf, attributes["TEXCOORD_0"])
    assert len(np.unique(np.round(uvs, 5), axis=0)) == 1  # one solid palette cell for the whole tube
