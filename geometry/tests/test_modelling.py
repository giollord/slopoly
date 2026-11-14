"""Blender modelling in programs: modifier stacks, vertex groups, curves and raw bmesh operations."""
import math

import numpy as np
import pytest

import slopoly_model as sm
from slopoly_model.runner import build, run_program
from slopoly_model.shapes import MODIFIERS

from conftest import PALETTE


def test_untagged_faces_are_reported_with_the_part(tmp_path):
    source = ("s = box(1, 1, 1, tag='wood')\n"
              "top = [f for f in s.bm.faces if f.normal.y > 0.5][0]\n"
              "vs = list(top.verts)\n"
              "bmesh.ops.delete(s.bm, geom=[top], context='FACES_ONLY')\n"
              "s.bm.faces.new(vs)\n"
              "part('crate', s)\n")
    report = build({"source": source, "palette": PALETTE}, tmp_path)
    assert not report["validated"]
    assert any(i["issue"] == "untagged" and i["parts"] == ["crate"] for i in report["validation"]["issues"])


def test_radial_array_makes_evenly_spaced_spokes_with_gaps():
    spoke = sm.box(0.04, 0.5, 0.04, tag="spoke").move(y=0.25)
    wheel = spoke.modify("ARRAY", count=6, use_relative_offset=False, use_object_offset=True,
                         offset_object=sm.empty(rot=(0, 0, 60)))
    assert len(wheel.faces()) == 36
    assert set(wheel.face_tags()) == {"spoke"}
    verts = wheel.vertices()
    tips = verts[np.linalg.norm(verts[:, :2], axis=1) > 0.49]
    angles = sorted({round(math.degrees(math.atan2(y, x))) % 360 // 10 * 10 for x, y, _ in tips})
    assert len(angles) >= 6  # one cluster of tip vertices per 60 degrees
    # gaps: a point between two spokes, at half radius, is outside every spoke
    half = 0.25 * np.array([math.cos(math.radians(120)), math.sin(math.radians(120))])
    assert np.min(np.linalg.norm(verts[:, :2] - half, axis=1)) > 0.05


@pytest.mark.parametrize("kind", MODIFIERS)
def test_every_allowed_modifier_keeps_tags(kind):
    base = sm.box(1, 1, 1, tag="wood")
    settings = {"BOOLEAN": {"object": sm.box(0.5, 0.5, 0.5, tag="cut").move(0.5, 0.5, 0.5), "solver": "MANIFOLD"},
                "SHRINKWRAP": {"target": sm.box(2, 2, 2)}, "CURVE": {"object": sm.path([(0, 0, 0), (1, 1, 0)])},
                "DISPLACE": {"texture": sm.texture("CLOUDS"), "strength": 0.05}, "SUBSURF": {"levels": 1}}.get(kind, {})
    shape = base.modify(kind, **settings)
    tags = shape.face_tags()
    assert tags and "" not in tags


def test_unknown_modifier_or_setting_fails_with_its_name():
    with pytest.raises(sm.ShapeError, match="REMESH"):
        sm.box(1, 1, 1).modify("REMESH")
    with pytest.raises(sm.ShapeError, match="cuont"):
        sm.box(1, 1, 1).modify("ARRAY", cuont=3).bm
    with pytest.raises(sm.ShapeError, match="fit_type"):
        sm.box(1, 1, 1).modify("ARRAY", fit_type="BAD").bm


def test_stack_is_lazy_and_does_not_change_the_input():
    base = sm.box(1, 1, 1)
    stacked = base.modify("ARRAY", count=4)
    assert stacked.stack and len(stacked._bm.faces) == 6  # nothing applied yet
    assert len(stacked.faces()) == 24 and not stacked.stack
    assert len(base.faces()) == 6


def test_box_bends_and_tapers_into_a_branch_with_a_ramp_group():
    long_box = sm.box(0.1, 1.0, 0.1, tag="bark").move(y=0.5)
    long_box = sm.bevel(long_box, 0.001)  # some vertices to deform
    from slopoly_model.shapes import _selected  # noqa: F401
    branch = sm.group(long_box, "tip", weight=sm.ramp("y", 0, 1))
    bent = branch.rotate(z=40, group="tip").scale(0.4, 1, 0.4, group="tip", about=(0, 1, 0))
    verts = bent.vertices()
    base = verts[verts[:, 1] < 0.01]
    assert np.allclose(np.abs(base[:, 0]).max(), 0.05, atol=0.002)  # base unmoved
    top = verts[np.argsort(verts[:, 1])[-4:]]
    assert np.abs(top[:, 0]).mean() > 0.2  # the tip leans over


def test_modifier_limited_to_a_group_and_group_scale():
    crate = sm.group(sm.box(1, 1, 1, tag="wood"), "top", faces="top")
    scaled = crate.scale(1.2, 1, 1.2, group="top")
    verts = scaled.vertices()
    assert np.abs(verts[verts[:, 1] > 0][:, 0]).max() == pytest.approx(0.6)
    assert np.abs(verts[verts[:, 1] < 0][:, 0]).max() == pytest.approx(0.5)
    tapered = crate.modify("DISPLACE", group="top", strength=0.4, mid_level=0.0, direction="Y")
    assert tapered.vertices()[:, 1].max() == pytest.approx(0.9)
    assert tapered.vertices()[:, 1].min() == pytest.approx(-0.5)


def test_closed_curve_is_a_watertight_ring():
    ring = sm.curve([(0.3, 0, 0), (0, 0, 0.3), (-0.3, 0, 0), (0, 0, -0.3)], sm.ngon(6, r=0.03), resolution=3,
                    closed=True, tag="metal")
    assert all(e.is_manifold for e in ring.bm.edges)
    assert len(ring.faces()) == 6 * 12


def test_lathe_outline_with_screw():
    vase = sm.outline([(0, 0), (0.2, 0), (0.25, 0.3), (0.1, 0.5), (0, 0.5)], tag="clay")
    vase = vase.modify("SCREW", axis="Y", steps=8, use_merge_vertices=True)
    assert all(e.is_manifold for e in vase.bm.edges)
    assert set(vase.face_tags()) == {"clay"}


def test_raw_bmesh_operation_keeps_tags(tmp_path):
    source = "import bmesh as b\ns = box(1, 1, 1, tag='wood')\n" \
             "top = [f for f in s.bm.faces if f.normal.y > 0.5]\n" \
             "r = bmesh.ops.extrude_face_region(s.bm, geom=top)\n" \
             "bmesh.ops.translate(s.bm, verts=[g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)], vec=(0, 0.3, 0))\n" \
             "bmesh.ops.delete(s.bm, geom=top, context='FACES')\n" \
             "part('crate', s)\n"
    model = run_program(source)
    assert set(model.parts["crate"].shape.face_tags()) == {"wood"}
    report = build({"source": source, "palette": PALETTE}, tmp_path)
    assert report["validated"], report["validation"]


def test_bark_grooves_from_shrinkwrapped_strips():
    trunk = sm.prism(8, r=0.15, length=1.0, tag="bark")
    strip = sm.box(0.03, 0.8, 0.03, tag="bark dark").move(0.15, 0, 0)
    strips = strip.modify("ARRAY", count=4, use_relative_offset=False, use_object_offset=True,
                          offset_object=sm.empty(rot=(0, 90, 0)))
    grooves = trunk.modify("BOOLEAN", object=strips, operation="DIFFERENCE", solver="MANIFOLD")
    assert set(grooves.face_tags()) == {"bark", "bark dark"}
    assert grooves.booleans == 1
