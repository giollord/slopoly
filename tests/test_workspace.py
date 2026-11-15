import os
import subprocess
from pathlib import Path

import yaml
from conftest import make_image

from slopoly import config, workspace


def test_init_and_discovery_from_subfolder(run, pack):
    Path("src/game").mkdir(parents=True)
    os.chdir("src/game")
    assert run("status").json["packs"][0]["name"] == "gnome-village"


def test_workspace_env(run, pack, tmp_path, monkeypatch):
    monkeypatch.setenv("SLOPOLY_WORKSPACE", str(Path("slopoly").resolve()))
    monkeypatch.chdir(tmp_path)
    assert run("status").json["packs"]


def test_pack_layout(run, pack):
    for name in ("pack.yaml", "style.md", "palette.yaml", ".gitignore"):
        assert (pack / name).is_file()
    for name in ("anchors", "assets", "scenes", "jobs", "style"):
        assert (pack / name).is_dir()


def test_pack_exists(run, pack):
    before = (pack / "pack.yaml").read_text()
    assert run("pack", "new", "gnome-village", ok=False).json["code"] == "exists"
    assert (pack / "pack.yaml").read_text() == before


def test_asset_layout(run, pack):
    variant = pack / "assets/cart/variants/default"
    assert (pack / "assets/cart/asset.yaml").is_file()
    assert (variant / "variant.yaml").is_file() and (variant / "program.py").is_file()
    assert (pack / "assets/cart/heroes").is_dir()
    status = run("status", "gnome-village/cart").json
    assert status["status"] == "concept" and status["description"] == "wooden hand cart"


def test_unknown_target(run, pack):
    result = run("status", "gnome-village/well", ok=False).json
    assert result["code"] == "not_found" and result["assets"] == ["cart"]


def test_variant_copy(run, pack):
    default = pack / "assets/cart/variants/default"
    (default / "manifest.yaml").write_text("parts: [{name: bed}]\n")
    run("variant", "new", "gnome-village/cart", "loaded", "--from", "default")
    loaded = pack / "assets/cart/variants/loaded"
    assert (loaded / "manifest.yaml").read_text() == "parts: [{name: bed}]\n"
    (loaded / "manifest.yaml").write_text("parts: [{name: crate}]\n")
    assert "bed" in (default / "manifest.yaml").read_text()


def hero(pack, name="hero_001", state="undecided"):
    return make_image(pack / f"assets/cart/heroes/{name}.png", {"kind": "hero", "state": state})


def test_variant_from_hero(run, pack):
    path = hero(pack)
    run("variant", "new", "gnome-village/cart", "rustic", "--hero", path.as_posix())
    rustic = pack / "assets/cart/variants/rustic"
    assert path.exists()  # heroes stay in the asset's heroes/; the variant names its reference
    assert yaml.safe_load((rustic / "variant.yaml").read_text())["reference"] == "hero_001.png"
    assert yaml.safe_load(path.with_suffix(".yaml").read_text())["state"] == "picked"


def test_rm_hero_with_views(run, pack):
    path = hero(pack)
    views = pack / "assets/cart/views/hero_001"
    views.mkdir(parents=True)
    (views / "front.png").write_bytes(b"x")
    run("rm", path.as_posix(), "--views-only")
    assert path.exists() and not views.exists()
    run("rm", path.as_posix())
    assert not path.exists() and not path.with_suffix(".yaml").exists()


def test_failed_builds_and_rejected_images_are_ignored(run, pack):
    subprocess.run(["git", "init", "-q"], check=True)
    for f in (pack / "assets/cart/heroes/rejected/hero_002.png",
              pack / "assets/cart/variants/default/builds/rejected/0003/program.py"):
        f.parent.mkdir(parents=True)
        f.write_text("x")
    listed = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True,
                            check=True).stdout.split()
    assert not any("rejected" in p for p in listed)


def test_rm_variant_used_by_scene(run, pack):
    run("variant", "new", "gnome-village/cart", "loaded")
    run("scene", "new", "gnome-village/market-square")
    (pack / "scenes/market-square.yaml").write_text("placements: [{name: c1, asset: cart, variant: loaded}]\n")
    result = run("rm", "gnome-village/cart:loaded", ok=False).json
    assert result["code"] == "in_use" and result["scenes"] == ["market-square"]
    assert run("rm", "gnome-village/cart:default", ok=False).json["code"] == "default_variant"


def test_variant_rename_follows(run, pack):
    run("variant", "new", "gnome-village/cart", "loaded")
    (pack / "scenes/sq.yaml").write_text("placements: [{name: c1, asset: cart, variant: loaded}]\n")
    run("variant", "rename", "gnome-village/cart:loaded", "full")
    assert "variant: full" in (pack / "scenes/sq.yaml").read_text()


def test_gitignore_keeps_current_build(run, pack):
    subprocess.run(["git", "init", "-q"], check=True)
    variant = pack / "assets/cart/variants/default"
    for n in (1, 2):
        build = variant / f"builds/{n:04d}"
        build.mkdir(parents=True)
        for f in ("program.py", "report.json", "model.glb", "render_front.png", "job.json"):
            (build / f).write_text("x")
    with open(pack / ".gitignore", "a") as out:
        out.write("*.psd\n")
    v = workspace.find().pack("gnome-village").asset("cart").variant()
    v.save(v.meta.model_copy(update={"current": 2}))
    listed = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True,
                            check=True).stdout.split()
    base = "slopoly/gnome-village/assets/cart/variants/default/builds"
    assert f"{base}/0002/model.glb" in listed and f"{base}/0002/render_front.png" in listed
    assert f"{base}/0001/model.glb" not in listed and f"{base}/0001/program.py" in listed
    assert f"{base}/0001/report.json" in listed and f"{base}/0002/job.json" not in listed
    assert "*.psd" in (pack / ".gitignore").read_text()
    assert not any("jobs/" in p for p in listed)


def test_check_reports_manifest(run, pack):
    (pack / "assets/cart/variants/default/manifest.yaml").write_text(
        "parts: [{name: bed}, {name: wheel, parent: axle}]\n")
    result = run("check", "gnome-village", ok=False).json
    assert result["code"] == "check_failed"
    assert any(p["file"].endswith("manifest.yaml") and "axle" in p["message"] for p in result["problems"])


def test_check_notes(run, pack):
    notes = Path("slopoly/knowledge/techniques")
    (notes / "Cracks.md").write_text("---\ntitle: Cracks\nsummary: s\n---\nbody\n")
    (notes / "dents.md").write_text("---\nsummary: s\n---\n")
    problems = run("check", ok=False).json["problems"]
    assert any(p["file"].endswith("Cracks.md") for p in problems)
    assert any(p["file"].endswith("dents.md") and p["field"] == "title" for p in problems)


def test_check_shading_range(run, pack):
    (pack / "pack.yaml").write_text("name: gnome-village\nshading: {hard_edge_angle: 200}\n")
    problems = run("check", ok=False).json["problems"]
    assert any(p["field"] == "shading.hard_edge_angle" for p in problems)


def test_check_ok(run, pack):
    assert run("check").json == {"ok": True}


def test_config_outside_workspace(run, pack):
    run("config", "set", "comfyui.url", "http://gpu-box:8188")
    assert config.get("comfyui.url") == "http://gpu-box:8188"
    assert "gpu-box" not in "".join(p.read_text(errors="ignore") for p in Path("slopoly").rglob("*") if p.is_file())
    assert run("config", "set", "nope", "x", ok=False).json["code"] == "unknown_setting"
