import numpy as np
import pytest

import slopoly_model as sm
from slopoly_model import assembly


def rim_faces(shape, axis=0, r=0.3):
    """Side faces of a round part: normal perpendicular to the axis, centre near the rim."""
    found = 0
    for f in shape.bm.faces:
        centre = np.array(f.calc_center_median())
        if abs(f.normal[axis]) < 0.1 and np.linalg.norm(np.delete(centre, axis)) > 0.8 * r:
            found += 1
    return found


def test_wheel_has_exactly_n_rim_faces_and_quads():
    wheel = sm.prism(8, r=0.3, length=0.08, axis="x")
    assert rim_faces(wheel) == 8
    assert sorted(len(f) for f in wheel.faces()) == [4] * 8 + [8, 8]


def test_wheel_with_hub_keeps_its_rim():
    wheel = sm.prism(8, r=0.3, length=0.08, axis="x", tag="wood")
    hub = sm.extrude(sm.inset(wheel, "+x", 0.2, tag="metal"), "metal", 0.03)
    assert rim_faces(hub) == 8
    assert all(e.is_manifold for e in hub.bm.edges)
    assert "metal" in hub.face_tags() and "wood" in hub.face_tags()


def test_extrude_keeps_a_closed_mesh_and_quads():
    shape = sm.extrude(sm.box(1, 1, 1), "top", 0.5)
    assert len(shape.faces()) == 10
    assert all(e.is_manifold for e in shape.bm.edges)
    assert shape.bounds()[1][1] == pytest.approx(1.0)


def test_operations_do_not_change_their_input():
    base = sm.box(1, 1, 1)
    sm.extrude(base, "top", 0.5)
    sm.bevel(base, 0.05)
    assert len(base.faces()) == 6


def test_sweep_keeps_thickness_at_corners():
    handle = sm.sweep([(0, 0, 0), (0, 0, 1), (0, 1, 1)], sm.ngon(6, r=0.03))
    assert all(e.is_manifold for e in handle.bm.edges)
    assert len(handle.faces()) == 6 * 2 + 2
    lo, hi = handle.bounds()
    assert hi[1] == pytest.approx(1.0) and lo[2] == pytest.approx(0.0)
    assert hi[2] == pytest.approx(1.03, abs=1e-6)  # outer corner is mitred, not pinched


def test_boolean_cuts_and_keeps_tags():
    import manifold3d  # noqa: F401
    from slopoly_model.shapes import to_manifold

    holed = sm.boolean(sm.box(1, 1, 1, tag="wood"), sm.prism(6, r=0.2, length=2, tag="hole"))
    assert holed.booleans == 1
    assert set(holed.face_tags()) == {"wood", "hole"}
    assert to_manifold(holed).volume() < 1.0
    assert len(holed.faces()) < 60  # coplanar triangles merged back


def test_mirrored_part_is_x_negated():
    sm.part("bed", sm.box(1.2, 0.3, 0.7), at=(0, 0.5, 0))
    handle = sm.sweep([(0.3, 0.5, 0.35), (0.3, 0.5, 1.0), (0.35, 0.6, 1.3)], sm.ngon(6, r=0.03))
    left = sm.part("handle_L", handle, parent="bed", at=(0.1, 0, 0), rot=(0, 10, 5), mirror="x")
    right = assembly.current.parts["handle_R"]
    assert right.parent == "bed" and right.mirror_of == "handle_L"
    expected = left.world_vertices() * np.array([-1, 1, 1])
    np.testing.assert_allclose(right.world_vertices(), expected, atol=1e-6)
    # outward normals after mirroring: the signed volume stays positive
    from slopoly_model.shapes import to_manifold
    assert to_manifold(right.shape).volume() > 0


def test_mirrored_children_follow_mirrored_parents():
    sm.part("axle", sm.prism(6, r=0.04, length=1.0, axis="x"), at=(0, 0.3, 0), joint=sm.rotate("x"))
    sm.part("arm_L", sm.box(0.1, 0.1, 0.1), at=(0.3, 0.3, 0), parent="axle", mirror="x")
    sm.part("finger_L", sm.box(0.05, 0.05, 0.05), at=(0.35, 0.4, 0), parent="arm_L", mirror="x",
            joint=sm.slide("x"))
    parts = assembly.current.parts
    assert parts["finger_R"].parent == "arm_R"
    assert parts["finger_R"].joint.axis == pytest.approx((-1, 0, 0))


def test_instances_share_meshes():
    planks = [sm.box(0.1, 0.02, 0.4 + 0.1 * i) for i in range(3)]
    for i, plank in enumerate(planks):
        sm.instance(f"plank{i}", plank, [(0.11 * j, 0, i) for j in range(10)])
    model = assembly.current
    assert len(model.parts) == 30
    meshes = model.meshes()
    assert len(meshes) == 3 and all(len(p) == 10 for p in meshes.values())
    assert all(len({id(p.shape) for p in group}) == 1 for group in meshes.values())


def test_model_errors_are_explicit():
    with pytest.raises(sm.ModelError, match="parent 'bed' is not defined"):
        sm.part("wheel", sm.box(1, 1, 1), parent="bed")
    sm.part("bed", sm.box(1, 1, 1))
    with pytest.raises(sm.ModelError, match="defined twice"):
        sm.part("bed", sm.box(1, 1, 1))
    with pytest.raises(sm.ShapeError, match="segment count"):
        sm.prism(2, r=1, length=1)
    with pytest.raises(sm.ShapeError, match="no faces match"):
        sm.extrude(sm.box(1, 1, 1), "lid", 0.1)


def test_jitter_is_seeded_closed_and_limited_to_the_selection():
    base = sm.bevel(sm.box(1, 0.4, 1), 0.03)
    a, b = sm.jitter(base, 0.02, seed=3), sm.jitter(base, 0.02, seed=3)
    assert np.array_equal(a.vertices(), b.vertices())
    assert not np.array_equal(a.vertices(), base.vertices())
    assert np.abs(a.vertices() - base.vertices()).max() <= 0.02
    assert all(e.is_manifold for e in a.bm.edges)
    top = sm.jitter(sm.box(1, 1, 1), 0.05, faces="top")
    assert top.vertices()[:, 1].min() == pytest.approx(-0.5)  # bottom vertices stay put
