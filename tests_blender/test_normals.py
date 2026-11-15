"""Normal repair before export, shading defects in the report, and the Blender file (tasks 8.1-8.3, 10.1)."""
import bpy
import numpy as np
import pytest

from conftest import PALETTE, glb_accessor, glb_json
from slopoly_model.runner import build

SMOOTH = {"mode": "smooth", "hardEdgeAngle": 60}


def built(tmp_path, source: str, shading: dict | None = None) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    report = build({"source": source, "palette": PALETTE, "shading": shading}, tmp_path)
    assert "error" not in report
    return report


def mesh_data(tmp_path, mesh: int = 0):
    gltf = glb_json(tmp_path / "model.glb")
    attributes = gltf["meshes"][mesh]["primitives"][0]["attributes"]
    path = tmp_path / "model.glb"
    return glb_accessor(path, gltf, attributes["POSITION"]), glb_accessor(path, gltf, attributes["NORMAL"])


def outward(positions, normals) -> bool:
    centre = positions.mean(axis=0)
    return bool(np.all(np.einsum("ij,ij->i", positions - centre, normals) > 0))


def test_inward_wound_box_is_turned_outward(tmp_path):
    report = built(tmp_path, "s = box(1, 1, 1, tag='wood')\n"
                             "bmesh.ops.reverse_faces(s.bm, faces=list(s.bm.faces))\n"
                             "part('crate', s)")
    assert report["shading"]["flipped"] == 6
    assert report["shading"]["parts"] == [{"part": "crate", "openEdges": 0, "nonManifold": 0, "selfIntersecting": 0, "inward": 0, "bent": 0}]
    assert outward(*mesh_data(tmp_path))


def test_single_plane_reports_its_open_edges(tmp_path):
    report = built(tmp_path, "part('leaf', ngon(4, r=0.5, tag='wood'))")
    assert report["shading"]["parts"][0]["openEdges"] == 4
    assert not report["validated"]
    assert any(i["issue"] == "not_solid" for i in report["validation"]["issues"])


def test_fin_on_a_shared_edge_is_non_manifold_and_fails_validation(tmp_path):
    report = built(tmp_path, "\n".join([
        "s = box(1, 1, 1, tag='wood')",
        "e = next(e for e in s.bm.edges if e.verts[0].co.y > 0.4 and e.verts[1].co.y > 0.4)",
        "v = s.bm.verts.new((0, 1.5, 0))",
        "f = s.bm.faces.new((e.verts[0], e.verts[1], v))",
        "f[s.tags] = e.link_faces[0][s.tags]",
        "part('crate', s)"]))
    assert report["shading"]["parts"][0]["nonManifold"] >= 1
    issue = next(i for i in report["validation"]["issues"] if i["issue"] == "not_solid")
    assert issue["parts"][0]["part"] == "crate"
    assert not report["validated"]


def test_raised_corner_is_reported_as_bent_and_still_exported(tmp_path):
    report = built(tmp_path, "s = box(1, 1, 1, tag='wood')\n"
                             "corner = max(s.bm.verts, key=lambda v: (v.co.y, v.co.x, v.co.z))\n"
                             "corner.co.y += 0.4\n"
                             "part('crate', s)")
    assert report["shading"]["parts"][0]["bent"] == 1  # the top; the sides stay planar (the corner moves within them)
    assert (tmp_path / "model.glb").exists()


def test_clean_build_has_no_defects(tmp_path):
    report = built(tmp_path, "part('crate', box(1, 1, 1, tag='wood'))")
    shading = report["shading"]
    assert (shading["merged"], shading["removed"], shading["flipped"]) == (0, 0, 0)
    assert shading["parts"] == [{"part": "crate", "openEdges": 0, "nonManifold": 0, "selfIntersecting": 0, "inward": 0, "bent": 0}]


def test_duplicate_vertices_are_merged(tmp_path):
    report = built(tmp_path, "s = box(1, 1, 1, tag='wood')\n"
                             "bmesh.ops.split_edges(s.bm, edges=[e for e in s.bm.edges if e.verts[0].co.y > 0.4 and e.verts[1].co.y > 0.4])\n"
                             "part('crate', s)")
    assert report["shading"]["merged"] > 0
    assert report["shading"]["parts"][0]["openEdges"] == 0


def test_smooth_bevelled_box_shades_its_large_faces_evenly(tmp_path):
    built(tmp_path, "part('crate', bevel(box(1, 1, 1, tag='wood'), 0.05))", SMOOTH)
    positions, normals = mesh_data(tmp_path)
    top = positions[:, 1] > 0.499
    tilt = np.degrees(np.arccos(np.clip(normals[top][:, 1], -1, 1)))
    assert top.sum() >= 4 and tilt.max() < 3, tilt


def _matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"]).reshape(4, 4).T
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    rotation = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = rotation * np.array(node.get("scale", [1, 1, 1]))
    m[:3, 3] = node.get("translation", [0, 0, 0])
    return m


def test_mirrored_part_shows_outward_normals(tmp_path):
    built(tmp_path, "part('block', box(0.2, 0.4, 0.4, tag='wood'), at=(0.5, 0.2, 0), mirror='x')")
    gltf = glb_json(tmp_path / "model.glb")
    path = tmp_path / "model.glb"
    meshes = [n for n in gltf["nodes"] if "mesh" in n]
    assert len(meshes) == 2
    for node in meshes:  # world normals as a viewer computes them: inverse-transpose of the node matrix
        attributes = gltf["meshes"][node["mesh"]]["primitives"][0]["attributes"]
        positions, normals = glb_accessor(path, gltf, attributes["POSITION"]), glb_accessor(path, gltf, attributes["NORMAL"])
        m = _matrix(node)
        world = positions @ m[:3, :3].T + m[:3, 3]
        world_normals = normals @ np.linalg.inv(m[:3, :3])
        assert outward(world, world_normals), node["name"]


def test_blender_file_matches_the_glb(tmp_path, cart_source):
    report = built(tmp_path, cart_source)
    gltf = glb_json(tmp_path / "model.glb")
    glb_triangles = sum(gltf["accessors"][p["indices"]]["count"] // 3 for m in gltf["meshes"] for p in m["primitives"])

    bpy.ops.wm.open_mainfile(filepath=str(tmp_path / "model.blend"))
    objects = bpy.data.objects
    assert {"bed", "axle", "wheel_L", "wheel_R", "socket_hitch"} <= set(objects.keys())
    assert objects["axle"].parent.name == "bed" and objects["wheel_L"].parent.name == "axle"
    assert objects["socket_hitch"].type == "EMPTY"
    assert objects["axle"]["joint"]["type"] == "rotate"
    images = list(bpy.data.images)
    assert len(images) == 1 and images[0].filepath == "//palette.png" and images[0].packed_file is None
    assert bpy.context.scene.unit_settings.system == "METRIC"
    triangles = 0
    for obj in objects:
        if obj.type == "MESH":
            obj.data.calc_loop_triangles()
            triangles += len(obj.data.loop_triangles)
    assert triangles == glb_triangles
    assert report["validated"]


def test_overlapping_solids_joined_into_one_mesh_fail_validation(tmp_path):
    report = built(tmp_path, "part('crate', join(box(1, 1, 1, tag='wood'), box(0.4, 2, 0.4, tag='wood')))")
    assert report["shading"]["parts"][0]["selfIntersecting"] > 0
    assert not report["validated"]


def test_overlapping_parts_still_validate(tmp_path):
    report = built(tmp_path, "part('crate', box(1, 1, 1, tag='wood'));"
                             "part('post', box(0.4, 2, 0.4, tag='wood'), parent='crate')")
    assert report["validated"], report["validation"]
