"""Reference meshes: rendering conventions, orientation against the hero, real-size placement and metric views."""
import numpy as np
import pytest

from slopoly import meshview as mv
from slopoly import reference as ref


def box(lo, hi, colour):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    verts = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], float)
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))])
    return mv.Mesh(verts, tris, np.tile(colour, (8, 1)))


def merge(*meshes):
    count, tris = 0, []
    for m in meshes:
        tris.append(m.tris + count)
        count += len(m.verts)
    return mv.Mesh(np.concatenate([m.verts for m in meshes]), np.concatenate(tris),
                   np.concatenate([m.colors for m in meshes]))


@pytest.fixture
def cart():
    """A long body (along Z, front at +Z) with a red pole sticking out of the front on the left (+X) side only, so
    the object has a front and a handedness."""
    body = box((-0.5, 0.2, -1.0), (0.5, 0.8, 1.0), (0.8, 0.6, 0.2))
    pole = box((0.3, 0.3, 1.0), (0.45, 0.45, 2.0), (0.9, 0.1, 0.1))
    stand = box((-0.2, 0.0, -0.2), (0.2, 0.2, 0.2), (0.2, 0.2, 0.2))
    return merge(body, pole, stand)


def hero_of(mesh):
    camera = mv.framed(mesh.verts, *mv.NAMED["hero"], (256, 256))
    return mv.render(mesh, camera)


def test_side_view_has_the_front_on_the_left(cart):
    camera = mv.framed(cart.verts, *mv.NAMED["side"], (200, 200))
    _, mask = mv.render(cart, camera)
    xs = np.nonzero(mask.any(0))[0]
    pole_rows = mask[:, : xs.min() + 20]  # the pole (front) is the leftmost part
    assert pole_rows.any() and not mask[:, xs.max() - 3:].any(0).sum() > mask[:, : xs.min() + 3].any(0).sum() + 5


def test_scorer_projection_matches_the_camera(cart):
    camera = mv.framed(cart.verts, *mv.NAMED["front"], (100, 100))
    pts, _ = camera.project(cart.verts)
    fit = camera.fit()
    proj = np.stack([cart.verts[:, 0], -cart.verts[:, 1]], 1)  # the scorer's front projection
    assert np.allclose(proj * fit["scale"] + fit["offset"], pts)


@pytest.mark.parametrize("turn,mirrored", [(0, False), (90, False), (-130, False), (37, False), (40, True)])
def test_orient_recovers_turn_and_mirror(cart, turn, mirrored):
    hero_rgb, hero_mask = hero_of(cart)
    generated = cart.transformed(mv.rotation_y(turn))
    if mirrored:
        generated = mv.mirror_x(generated)
    found = ref.orient(generated, hero_rgb, hero_mask)
    assert found["mirrored"] == mirrored
    placed = generated.transformed(ref.Placement(yaw=found["yaw"], mirrored=found["mirrored"]).matrix())
    assert np.allclose(placed.bounds()[0], cart.bounds()[0], atol=0.08)
    assert np.allclose(placed.bounds()[1], cart.bounds()[1], atol=0.08)
    assert found["how"] == "detected"


def test_place_scales_to_the_stated_size_on_the_ground(cart):
    placement, how = ref.place(cart, 0.0, False, {"axis": "z", "metres": 9.0})
    lo, hi = cart.transformed(placement.matrix()).bounds()
    assert how == "given"
    assert hi[2] - lo[2] == pytest.approx(9.0)
    assert lo[1] == pytest.approx(0.0) and lo[0] == pytest.approx(-hi[0]) and lo[2] == pytest.approx(-hi[2])
    _, assumed = ref.place(cart, 0.0, False, None)
    assert assumed == "assumed"


def test_long_object_views_share_a_scale_and_are_not_cropped(cart):
    placement, _ = ref.place(cart, 0.0, False, {"axis": "z", "metres": 9.0})
    placed = cart.transformed(placement.matrix())
    views = ref.render_views(placed, 200)
    scales = {info["m_per_px"] for _, _, info in views.values()}
    assert len(scales) == 1
    for name, (_, mask, _) in views.items():
        assert not (mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()), name
    _, side_mask, side = views["side"]
    xs = np.nonzero(side_mask.any(0))[0]
    assert (xs.max() - xs.min() + 1) * side["m_per_px"] == pytest.approx(9.0, rel=0.02)
    rows = np.nonzero(side_mask.any(1))[0]
    assert side["ground_row"] == pytest.approx(rows.max() + 1, abs=1.5)
    # front width equals top width, side depth equals top depth (one shared scale)
    _, front_mask, _ = views["front"]
    _, top_mask, _ = views["top"]
    assert front_mask.any(0).sum() == pytest.approx(top_mask.any(0).sum(), rel=0.02)
    assert side_mask.any(0).sum() == pytest.approx(top_mask.any(1).sum(), rel=0.02)


def test_glb_round_trip_keeps_geometry_and_colours(cart):
    loaded = mv.load_glb(mv.write_glb(cart))
    assert np.allclose(loaded.verts, cart.verts, atol=1e-5)
    assert np.array_equal(loaded.tris, cart.tris)
    assert np.allclose(loaded.colors, cart.colors, atol=1e-3)


def test_face_id_render_finds_faces(cart):
    camera = mv.framed(cart.verts, 0, 0, (120, 120))
    image, mask = mv.render(cart, camera, ids=True)
    ids = mv.face_ids(image)
    assert (ids[mask] >= 0).all() and (ids[~mask] == -1).all()
    assert ids.max() < len(cart.tris)


def test_compare3d_finds_the_missing_side_of_a_v(cart):
    from slopoly import compare3d
    # the reference: a body with a V-shaped plough in front; the build: the body with a straight bar instead
    body = box((-0.5, 0.2, -1.0), (0.5, 0.8, 1.0), (0.8, 0.6, 0.2))
    left = box((0.1, 0.0, 1.0), (0.5, 0.3, 1.6), (0.3, 0.3, 0.3))
    right = box((-0.5, 0.0, 1.0), (-0.1, 0.3, 1.6), (0.3, 0.3, 0.3))
    bar = box((-0.1, 0.0, 1.0), (0.1, 0.3, 1.6), (0.3, 0.3, 0.3))
    reference = merge(body, left, right)
    build = merge(body, bar)
    build.face_parts = np.array(["body"] * len(body.tris) + ["plough"] * len(bar.tris), dtype=object)
    result = compare3d.compare(build, reference)
    assert result["volume_iou"] < 0.95
    sides = [r for r in result["missing"] if r["bounds"][0][2] > 0.9]
    assert {round(np.sign(np.mean([r["bounds"][0][0], r["bounds"][1][0]]))) for r in sides} == {-1, 1}
    assert all("plough" in r["parts"] or "body" in r["parts"] for r in sides)
    same = compare3d.compare(reference, reference)
    assert same["volume_iou"] > 0.98 and not same["missing"] and not same["extra"]


def test_region_drops_stray_faces_and_keeps_both_wheels():
    from slopoly import segmentation as seg
    wheels = [box((x - 0.05, 0, -1), (x + 0.05, 0.6, -0.4), (0.2, 0.2, 0.2)) for x in (-0.6, 0.6)]
    stray = box((0, 0.9, 0.9), (0.01, 0.91, 0.91), (0.2, 0.2, 0.2))
    mesh = merge(*wheels, *[box((-0.5 + i, 0.3, 0), (-0.45 + i, 0.35, 0.05), (0.2, 0.2, 0.2)) for i in range(40)],
                 stray)
    votes = seg.Votes(mesh)
    voted = np.r_[0:24, 24 + 40 * 12]  # both wheels and one face of the stray box
    kept = votes.main_pieces(voted)
    assert set(kept.tolist()) == set(range(24))


def test_small_part_in_front_of_a_large_slanted_face_is_drawn_in_front():
    # a long plate leaning towards the camera: its centre is nearer than the small box at its far end
    plate = mv.Mesh(np.array([[-1, 0, -2], [1, 0, -2], [1, 1, 2], [-1, 1, 2]], float), np.array([[0, 1, 2], [0, 2, 3]]),
                    np.tile((0.5, 0.5, 0.5), (4, 1)))
    small = box((-0.1, 0.05, -1.95), (0.1, 0.3, -1.6), (0.9, 0.1, 0.1))
    mesh = merge(plate, small)
    camera = mv.framed(mesh.verts, 0, 80, (256, 256))  # from above, a little in front
    ids = mv.face_ids(mv.render(mesh, camera, ids=True)[0])
    u, v = camera.project(np.array([[0, 0.3, -1.8]]))[0][0]
    assert ids[int(v), int(u)] >= 2  # the box, not the plate's faces 0 and 1
