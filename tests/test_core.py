import pytest

from slopoly import models as m
from slopoly.core import SlopolyError, load, write_yaml


def test_error_is_json(run):
    result = run("status", ok=False)
    assert result.code == 1
    assert result.json["code"] == "no_workspace"
    assert "slopoly init" in result.json["hint"]


def test_usage_error_is_json(run):
    assert run("pack", "new", ok=False).json["code"] == "usage"


def test_yaml_round_trip(tmp_path):
    palette = m.Palette(entries=[m.PaletteEntry(role="wood", slot=0, color="#a0703c")],
                        variants={"autumn": {"wood": m.Colours(color="#884422")}})
    write_yaml(tmp_path / "p.yaml", palette)
    assert load(m.Palette, tmp_path / "p.yaml") == palette


def test_validation_errors_list_fields(tmp_path):
    (tmp_path / "pack.yaml").write_text("name: x\nshading: {mode: round, hard_edge_angle: 200}\n")
    with pytest.raises(SlopolyError) as error:
        load(m.Pack, tmp_path / "pack.yaml")
    fields = {p["field"] for p in error.value.details["problems"]}
    assert {"shading.mode", "shading.hard_edge_angle"} <= fields


def test_manifest_problems():
    manifest = m.Manifest(parts=[m.ManifestPart(name="bed"), m.ManifestPart(name="wheel", parent="axle")])
    assert any("unknown parent 'axle'" in p["message"] for p in manifest.problems())


def test_palette_problems():
    palette = m.Palette(entries=[m.PaletteEntry(role="a", slot=1, color="#000000"),
                                 m.PaletteEntry(role="b", slot=1, color="#ffffff")])
    assert any("used by both 'a' and 'b'" in p["message"] for p in palette.problems())
