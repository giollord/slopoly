"""Safe bevels: only real corners, no bent faces, no non-manifold edges, nothing pushed outside the shape."""
import numpy as np
import pytest

import slopoly_model as sm
from slopoly_model import normals


def check(shape) -> dict:
    co = np.array([v.co[:] for v in shape.bm.verts])
    return {**normals.defects(shape.bm), "lo": co.min(0), "hi": co.max(0)}


def seamed_box():
    ring = sm.boolean(sm.box(0.94, 0.014, 1.24), sm.box(0.88, 0.03, 1.18))
    return sm.boolean(sm.box(0.9, 0.5, 1.2), ring)


@pytest.mark.parametrize("make", [
    lambda: sm.box(1, 1, 1),
    lambda: sm.prism(8, r=0.3, length=0.1, axis="x"),
    lambda: sm.boolean(sm.box(1, 1, 1), sm.box(0.4, 2, 0.4), op="union"),
    seamed_box,
    lambda: sm.extrude(sm.inset(sm.box(0.9, 0.5, 1.2, tag="w"), "top", 0.05, tag="i"), "i", -0.43),
], ids=["box", "prism8", "union", "seamed", "open bed"])
@pytest.mark.parametrize("width", [0.01, 0.05])
def test_bevel_stays_a_clean_solid_inside_the_shape(make, width):
    shape = make()
    before, after = check(shape), check(sm.bevel(shape, width))
    assert (after["openEdges"], after["nonManifold"], after["inward"], after["bent"]) == (0, 0, 0, 0)
    assert (after["lo"] >= before["lo"] - 1e-4).all() and (after["hi"] <= before["hi"] + 1e-4).all()


def test_bevel_leaves_soft_edges_of_round_parts_alone():
    cylinder = sm.prism(16, r=0.3, length=0.5, axis="y")
    assert len(sm.bevel(cylinder, 0.01).bm.faces) == len(cylinder.bm.faces) + 32  # only the two caps' rims


def test_inset_after_bevel_does_not_raise_the_top():
    shape = sm.inset(sm.bevel(sm.box(0.9, 0.5, 1.2, tag="w"), 0.02), "top", 0.05, tag="i")
    assert check(shape)["hi"][1] <= 0.25 + 1e-6
