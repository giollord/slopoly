"""Modelling API behaviour found lacking on a complex asset: join, straight curves, jitter on thin walls and
placing parts on curved surfaces."""
import numpy as np
import pytest

import slopoly_model as sm
from slopoly_model import assembly
from slopoly_model.normals import defects
from slopoly_model.validate import validate


def _rib(i: int) -> sm.Shape:
    """A rib made the way the locomotive's were: a curve, a boolean union with a knob, then jitter."""
    bone = sm.curve([(0, 0, 0), (0.1, 0.5, 0), (0, 1, 0)], sm.ngon(6, 0.05, axis="z"), resolution=3, tag="bone")
    knob = sm.prism(6, r=0.08, length=0.12, axis="z").move(y=1.0)
    return sm.jitter(sm.boolean(bone, knob, "union"), 0.005, seed=i).move(x=0.3 * i)


def test_join_of_unioned_jittered_ribs_succeeds():
    ribs = sm.join(*[_rib(i) for i in range(5)])
    assert len(ribs.faces()) == sum(len(_rib(i).faces()) for i in range(5))


def test_join_drops_a_face_with_repeated_vertices():
    shape = sm.box(1, 1, 1, tag="wood")
    bm = shape.bm
    top = [f for f in bm.faces if f.normal.y > 0.5][0]
    a, b, c, _ = top.verts
    copy = bm.verts.new(a.co)  # a face over a duplicated vertex: three distinct corners after merging is fine,
    bm.faces.new([a, b, copy])  # but a sliver whose corners repeat must not break join
    joined = sm.join(shape, sm.box(1, 1, 1).move(x=2))
    assert len(joined.faces()) == len(shape.faces()) + 6


def test_straight_two_point_curve_gets_resolution_rings():
    pole = sm.curve([(0, 0, 0), (0, 1, 0)], sm.ngon(4, 0.1, axis="y"), resolution=8, smooth=False)
    heights = sorted({round(float(y), 4) for y in pole.vertices()[:, 1]})
    assert len(heights) == 9  # 8 segments: 9 rings along the pole
    tapered = sm.group(pole, "tip", weight=sm.ramp("y")).scale(0.2, 1, 0.2, group="tip")
    widths = {round(float(y), 4): float(np.abs(tapered.vertices()[np.isclose(tapered.vertices()[:, 1], y)][:, 0]).max())
              for y in heights}
    assert widths[heights[0]] > widths[heights[4]] > widths[heights[-1]]  # tapers ring by ring


def test_straight_curve_keeps_one_segment_by_default():
    pole = sm.curve([(0, 0, 0), (0, 1, 0)], sm.ngon(4, 0.1, axis="y"), smooth=False)
    assert len({round(float(y), 4) for y in pole.vertices()[:, 1]}) == 2


def test_jitter_is_limited_on_a_thin_banner():
    banner = sm.box(1.0, 1.2, 0.05, tag="cloth")
    rough = sm.jitter(banner, 0.04, seed=3)
    found = defects(rough.bm)
    assert found["selfIntersecting"] == 0 and found["nonManifold"] == 0
    assert not rough.warnings
    depth = rough.vertices()[:, 2]
    assert depth.max() - depth.min() < 0.05 + 2 * 0.45 * 0.05 + 1e-6


def test_jitter_still_moves_thick_shapes_fully():
    rock = sm.jitter(sm.box(1, 1, 1), 0.05, seed=1)
    moved = np.abs(rock.vertices() - sm.box(1, 1, 1).vertices()).max()
    assert moved > 0.03


def test_surface_point_places_spikes_on_an_arched_roof():
    roof = sm.curve([(-1, 2.0, 0), (0, 2.4, 0), (1, 2.0, 0)], [(-0.05, -1), (0.05, -1), (0.05, 1), (-0.05, 1)],
                    resolution=6, tag="roof")
    sm.part("roof", roof)
    for i, x in enumerate((-0.6, 0.0, 0.6)):
        point, normal = sm.surface_point(roof, (x, 5, 0), (0, -1, 0))
        assert normal[1] > 0.5
        spike = sm.cone(6, 0.06, 0.3, tag="horn")  # centred: its base is 0.15 below its origin
        sm.part(f"spike_{i}", spike, parent="roof", at=(point[0], point[1] + 0.15 - 0.01, point[2]))
    report = validate(assembly.current, budget=5000)
    assert all(c["ok"] for c in report["contacts"]), report["contacts"]
    assert all(i["fraction"] < 0.2 for i in report["intersections"]), report["intersections"]


def test_surface_point_reports_a_miss():
    with pytest.raises(sm.ShapeError, match="misses"):
        sm.surface_point(sm.box(1, 1, 1), (5, 5, 5), (0, 1, 0))
