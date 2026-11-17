"""Builds through the user's Blender (skipped when no supported Blender with the build libraries is found)."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from slopoly import blender
from slopoly.blender.slopoly_model import glb
from slopoly.core import SlopolyError

CART = Path(__file__).parent.parent / "tests_blender" / "samples" / "cart.py"
REAL_DATA = None


def blender_ready() -> bool:
    try:
        blender.find.cache_clear()
        blender.require_ready()
        return True
    except SlopolyError:
        return False


@pytest.fixture
def ready(monkeypatch):
    """The developer's real libraries folder, so the managed Blender libraries are found."""
    import os
    import platformdirs
    monkeypatch.setenv("SLOPOLY_DATA_DIR", platformdirs.user_data_dir("slopoly", appauthor=False))
    if not blender_ready():
        pytest.skip("no supported Blender with the build libraries (run slopoly doctor --fetch)")
    yield
    blender.find.cache_clear()


@pytest.fixture
def cart(run, pack, ready):
    run("palette", "add", "gnome-village", "wood", "#a0703c")
    run("palette", "add", "gnome-village", "wood dark", "#6b4423")
    run("palette", "add", "gnome-village", "metal", "#555555", "--to", "#999999")
    variant = pack / "assets/cart/variants/default"
    shutil.copy(CART, variant / "program.py")
    return variant


def test_build_cart(run, cart):
    result = run("build", "gnome-village/cart").json
    assert result["build"] == 1 and result["validated"] and result["current"]
    assert result["triangles"] == result["validation"]["triangles"]["count"] ==         sum(p["triangles"] for p in result["parts"])
    assert {p["name"] for p in result["parts"]} >= {"bed", "axle"} and set(result["parts"][0]) <=         {"name", "triangles", "booleans", "warnings"}
    assert "no reference hero" in result["silhouette"]["renders"]
    for key in ("model", "blend", "report", "program"):
        assert Path(result["files"][key]).exists(), key
    assert yaml.safe_load((cart / "variant.yaml").read_text()).get("current") == 1
    assert run("status", "gnome-village/cart").json["status"] == "validated"


def test_program_error(run, cart):
    (cart / "program.py").write_text("part('bed', box(1, 1, 1))\n\npart('wheel', prism(2, r=1, length=1))\n")
    result = run("build", "gnome-village/cart", ok=False)
    assert result.code == 2 and result.json["code"] == "program_error" and result.json["line"] == 3
    assert yaml.safe_load((cart / "variant.yaml").read_text()).get("current") is None
    assert (cart / "builds/rejected/0001/program.py").exists()  # failed builds are set aside (git-ignored)
    assert result.json["program"].endswith("builds/rejected/0001/program.py")
    shutil.copy(CART, cart / "program.py")
    assert run("build", "gnome-village/cart").json["build"] == 2  # the failed build's number stays used


def test_use_restores_program(run, cart):
    run("build", "gnome-village/cart")
    original = (cart / "program.py").read_text()
    (cart / "program.py").write_text(original.replace("0.8, 0.3, 0.7", "0.9, 0.3, 0.7"))
    run("build", "gnome-village/cart")
    run("build", "use", "gnome-village/cart", "1")
    assert (cart / "program.py").read_text() == original
    assert yaml.safe_load((cart / "variant.yaml").read_text()).get("current") == 1


def test_palette_refresh_and_rm(run, cart, pack):
    run("build", "gnome-village/cart")
    model = cart / "builds/0001/model.glb"
    before = model.read_bytes()
    slots = {e["role"]: e["slot"] for e in yaml.safe_load((pack / "palette.yaml").read_text())["entries"]}
    run("palette", "add", "gnome-village", "roof", "#aa2222")
    run("palette", "set", "gnome-village", "wood", "#ff0000")
    after = {e["role"]: e["slot"] for e in yaml.safe_load((pack / "palette.yaml").read_text())["entries"]}
    assert all(after[r] == s for r, s in slots.items())
    assert model.read_bytes() != before and glb.read(model.read_bytes())[0]["meshes"] == glb.read(before)[0]["meshes"]
    result = run("palette", "rm", "gnome-village", "wood", ok=False).json
    assert result["code"] == "in_use" and result["assets"] == ["gnome-village/cart:default"]
    run("palette", "rm", "gnome-village", "roof")


def test_export(run, cart, tmp_path):
    run("build", "gnome-village/cart")
    run("palette", "variant", "gnome-village", "autumn")
    run("palette", "set", "gnome-village", "wood", "#884422", "--variant", "autumn")
    files = run("export", "gnome-village/cart", "--to", tmp_path / "out", "--blend").json["files"]
    names = sorted(Path(f).name for f in files)
    assert names == ["cart.blend", "cart.glb", "palette.png", "palette_autumn.png"]


def test_scene_build(run, cart, pack):
    run("build", "gnome-village/cart")
    run("scene", "new", "gnome-village/market")
    (pack / "scenes/market.yaml").write_text(yaml.safe_dump({"placements": [
        {"name": "cart_1", "asset": "cart", "at": [0, 0, 0]}, {"name": "cart_2", "asset": "cart", "at": [0, 0, 0]}],
        "builds": {"cart": 1}}))
    result = run("scene", "build", "gnome-village/scenes/market", "--current").json
    assert Path(result["model"]).exists() and result["report"]["overlaps"]
    assert yaml.safe_load((pack / "scenes/market.yaml").read_text())["builds"] == {}
    (pack / "scenes/market.yaml").write_text(yaml.safe_dump({"placements": [{"name": "c", "asset": "cart"}],
                                                             "builds": {"cart": 7}}))
    assert run("scene", "build", "gnome-village/scenes/market", ok=False).json["code"] == "version_without_build"
