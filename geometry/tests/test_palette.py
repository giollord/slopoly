import json

import numpy as np
import pytest
from conftest import PALETTE, glb_accessor, glb_json

from slopoly_model import palette as pal
from slopoly_model import runner

ENTRIES = [pal.Entry.parse(e) for e in PALETTE]


def pixel(image, uv):
    return image.getpixel((int(uv[0] * pal.SIZE), int(uv[1] * pal.SIZE)))


def test_slot_rectangles_are_fixed_by_slot_index():
    before = pal.cell_centre(5)
    many = [pal.Entry(f"role {i}", "Solid", i, "#000000") for i in range(200)]
    pal.render(many)
    assert pal.cell_centre(5) == before == ((5 * 8 + 4) / 256, 4 / 256)
    assert pal.cell_centre(33) == ((1 * 8 + 4) / 256, (1 * 8 + 4) / 256)  # second row
    assert pal.strip_uv(2, 0.5)[1] == (128 + 2 * 4 + 2) / 256


def test_sampled_uvs_land_in_the_right_cell_and_strip():
    image = pal.render(ENTRIES)
    assert image.size == (256, 256)
    assert pixel(image, pal.cell_centre(0)) == pal.rgb("#a0703c")
    assert pixel(image, pal.cell_centre(1)) == pal.rgb("#6b4423")
    assert pixel(image, pal.strip_uv(0, 0.0)) == pal.rgb("#555555")
    assert pixel(image, pal.strip_uv(0, 1.0)) == pal.rgb("#999999")
    u0, _ = pal.strip_uv(0, 0.0)
    u1, _ = pal.strip_uv(0, 1.0)
    assert u0 * 256 == 0.5 and u1 * 256 == 255.5  # half-pixel inset


def test_variant_overrides_only_change_colours():
    main = np.asarray(pal.render(ENTRIES))
    variant = np.asarray(pal.render(ENTRIES, {"wood": ("#00ff00", None)}))
    changed = np.argwhere((main != variant).any(-1))
    assert changed[:, 0].max() < 8 and changed[:, 1].max() < 8  # only slot 0's cell


def build_cart(tmp_path, source):
    (tmp_path / "job.json").write_text(json.dumps({"source": source, "polyBudget": 2000, "palette": PALETTE}))
    assert runner.main(str(tmp_path)) == 0
    gltf = glb_json(tmp_path / "model.glb")
    return gltf, {m["name"]: m for m in gltf["meshes"]}


def mesh_uvs(tmp_path, gltf, mesh):
    prim = mesh["primitives"][0]
    path = tmp_path / "model.glb"
    return glb_accessor(path, gltf, prim["attributes"]["TEXCOORD_0"]), glb_accessor(path, gltf, prim["attributes"]["POSITION"])


def test_cart_bed_samples_only_the_wood_cell(tmp_path, cart_source):
    gltf, meshes = build_cart(tmp_path, cart_source)
    uvs, _ = mesh_uvs(tmp_path, gltf, meshes["bed"])
    np.testing.assert_allclose(uvs, np.tile(pal.cell_centre(0), (len(uvs), 1)), atol=1e-6)


def test_gradient_part_spans_its_strip(tmp_path, cart_source):
    source = cart_source.replace('joint=rotate("x"), color="metal"', 'joint=rotate("x"), color=gradient("metal", "x")')
    gltf, meshes = build_cart(tmp_path, source)
    uvs, positions = mesh_uvs(tmp_path, gltf, meshes["axle"])
    lowest, highest = positions[:, 0].argmin(), positions[:, 0].argmax()
    assert uvs[lowest] == pytest.approx(pal.strip_uv(0, 0.0), abs=1e-6)
    assert uvs[highest] == pytest.approx(pal.strip_uv(0, 1.0), abs=1e-6)
    assert np.all(np.abs(uvs[:, 1] - pal.strip_uv(0, 0)[1]) < 1e-6)  # stays inside the strip


def test_colour_likeness_flags_a_green_wheel_over_a_brown_mask(cart_source):
    from slopoly_model.likeness import _area, likeness

    assert _area(np.array([[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]], float)) == pytest.approx(2.0)
    entries = ENTRIES + [pal.Entry("leaf green", "Solid", 2, "#3c8a2e")]
    masks = [{"part": "wheel", "view": "side", "colors": [{"hex": "#6e4524", "coverage": 0.8}]},
             {"part": "bed", "view": "side", "colors": [{"hex": "#a3733f", "coverage": 0.9}]}]
    rows = {r["mask"]: r for r in likeness(runner.run_program(cart_source.replace('color="wood dark", overlaps',
                                                                                  'color="leaf green", overlaps')),
                                           masks, entries)}
    assert rows["wheel"]["role"] == "leaf green" and not rows["wheel"]["ok"] and rows["wheel"]["delta_e"] > 20
    assert rows["bed"]["role"] == "wood" and rows["bed"]["ok"]
