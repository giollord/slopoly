"""The window server, picks and the view state, without opening a window."""

import json
import threading
from pathlib import Path

import httpx
import pytest
import yaml
from conftest import make_image

from slopoly import jobs, windows, workspace
from slopoly import models as m
from slopoly.core import write_yaml
from slopoly.windows.server import PageServer


HEROES = "assets/cart/heroes"


def hero(pack, name, state="undecided"):
    folder = f"{HEROES}/rejected" if state == "rejected" else HEROES
    return make_image(pack / f"{folder}/{name}.png", {"kind": "hero", "state": state, "prompt": "a cart", "seed": 3})


def reference(pack, variant="default"):
    path = pack / f"assets/cart/variants/{variant}/variant.yaml"
    return yaml.safe_load(path.read_text()).get("reference") if path.exists() else None


def test_server_api_and_path_safety(run, pack):
    secret = pack.parent.parent / "secret.txt"
    secret.write_text("no")
    chosen = []
    with PageServer(Path("slopoly"), "pick.html", lambda: {"hello": 1}, lambda b: chosen.append(b) or {"ok": 1}) as s:
        base = s.url
        assert httpx.get(base + "api/state").json() == {"hello": 1}
        assert httpx.get(base).text.startswith("<!doctype html>")
        assert httpx.get(base + "static/three/build/three.module.min.js").status_code == 200
        assert httpx.get(base + "files/gnome-village/pack.yaml").status_code == 200
        assert httpx.get(base + "files/../secret.txt").status_code == 404
        assert httpx.get(base + "files/%2E%2E/secret.txt").status_code == 404
        assert httpx.get(base.replace(s.token, "wrong") + "api/state").status_code == 404
        assert httpx.post(base + "api/choice", json={"picked": []}).json() == {"ok": 1}
        assert httpx.post(base + "api/prefs", json={"overlays": {"grid": True}}).json() == {"ok": True}
        assert httpx.get(base + "api/prefs").json() == {"overlays": {"grid": True}}
    assert chosen == [{"picked": []}]


def ws():
    return workspace.find()


def test_set_picked_hero_becomes_a_variants_reference(run, pack):
    a, c = hero(pack, "hero_001"), hero(pack, "hero_003")
    run("pick", "--set", a.as_posix(), "--state", "picked")
    assert reference(pack) == "hero_001.png"
    run("pick", "--set", c.as_posix(), "--state", "picked", "--variant", "rustic")
    assert reference(pack, "rustic") == "hero_003.png" and reference(pack) == "hero_001.png"
    b = hero(pack, "hero_004")
    run("pick", "--set", b.as_posix(), "--state", "picked")  # replaces default's reference; hero_001 is set aside
    assert reference(pack) == "hero_004.png"
    assert not a.exists() and (pack / HEROES / "rejected/hero_001.png").exists()


def test_rejected_hero_moves_with_its_views_and_leaves_its_variant(run, pack):
    a = hero(pack, "hero_001")
    run("pick", "--set", a.as_posix(), "--state", "picked")
    views = pack / "assets/cart/views/hero_001"
    views.mkdir(parents=True)
    (views / "views.yaml").write_text("x: 1\n")
    moved = run("pick", "--set", a.as_posix(), "--state", "rejected").json["rejected"][0]
    assert moved.endswith("assets/cart/heroes/rejected/hero_001.png") and Path(moved).exists()
    assert (pack / "assets/cart/views/rejected/hero_001/views.yaml").exists() and not views.exists()
    assert reference(pack) is None
    assert "**/rejected/" in (pack / ".gitignore").read_text()
    back = run("pick", "--set", moved, "--state", "undecided").json["undecided"][0]
    assert back.endswith("assets/cart/heroes/hero_001.png") and (pack / "assets/cart/views/hero_001").exists()


def pick_context(pack, spec):
    job = m.Job(id="p1", kind="pick", target=spec["target"], inputs=spec, created=jobs.now(), state="running")
    path = pack / "jobs/p1.yaml"
    write_yaml(path, job)
    return jobs.JobContext(ws().pack(pack.name), path, job)


@pytest.fixture
def clicking(monkeypatch):
    """Replaces the window with a 'user' that reads the state and posts a choice."""
    seen = {}

    def install(choice):
        def show(server, title, done, context, size=None):
            seen["state"] = httpx.get(server.url + "api/state").json()
            if choice is not None:
                seen["response"] = httpx.post(server.url + "api/choice", json=choice(seen["state"]))
            return "test"
        monkeypatch.setattr(windows, "show", show)
        return seen
    return install


def test_pick_rejects_what_is_not_picked(run, pack, clicking):
    h1, h2 = hero(pack, "hero_001"), hero(pack, "hero_002")
    hero(pack, "hero_009", state="rejected")
    seen = clicking(lambda s: {"picked": [{"path": s["images"][1]["path"], "variant": s["suggested"][0]}],
                               "note": "make the wheels bigger"})
    spec = {"pack": "gnome-village", "target": "gnome-village/cart", "set": "heroes"}
    result = windows.pick(pick_context(pack, spec))
    assert [i["name"] for i in seen["state"]["images"]] == ["hero_001.png", "hero_002.png"]  # rejected hidden
    assert seen["state"]["suggested"][0] == "default"
    assert result["note"] == "make the wheels bigger" and result["picked"][0].endswith("hero_002.png")
    assert reference(pack) == "hero_002.png"
    assert not h1.exists() and result["rejected"][0].endswith("heroes/rejected/hero_001.png")


def test_pick_several_heroes_makes_a_variant_each(run, pack, clicking):
    for n in (1, 2, 3):
        hero(pack, f"hero_00{n}")
    seen = clicking(lambda s: {"picked": [{"path": i["path"], "variant": name}
                                          for i, name in zip(s["images"][:2], ["default", "rustic"])]})
    spec = {"pack": "gnome-village", "target": "gnome-village/cart", "set": "heroes"}
    result = windows.pick(pick_context(pack, spec))
    assert seen["state"]["suggested"] == ["default", "variant_2", "variant_3"]
    assert (reference(pack), reference(pack, "rustic")) == ("hero_001.png", "hero_002.png")
    assert [v["variant"] for v in result["variants"]] == ["gnome-village/cart:default", "gnome-village/cart:rustic"]
    assert len(result["rejected"]) == 1


def test_pick_window_closed_is_cancelled(run, pack, clicking):
    hero(pack, "hero_001")
    clicking(None)
    spec = {"pack": "gnome-village", "target": "gnome-village/cart", "set": "heroes"}
    with pytest.raises(jobs.Cancelled):
        windows.pick(pick_context(pack, spec))
    assert yaml.safe_load((pack / HEROES / "hero_001.yaml").read_text())["state"] == "undecided"


def test_pick_shows_current_references_apart_and_keeps_them(run, pack, clicking):
    hero(pack, "hero_001", state="picked")
    (pack / "assets/cart/variants/default/variant.yaml").write_text("reference: hero_001.png\n")
    hero(pack, "hero_003")
    seen = clicking(lambda s: {"picked": [{"path": s["images"][0]["path"], "variant": ""}]})
    spec = {"pack": "gnome-village", "target": "gnome-village/cart", "set": "heroes"}
    with pytest.raises(jobs.Cancelled):
        windows.pick(pick_context(pack, spec))
    assert [i["name"] for i in seen["state"]["images"]] == ["hero_003.png"]
    assert [r["variant"] for r in seen["state"]["references"]] == ["default"]
    assert seen["state"]["suggested"] == ["variant_2"]
    assert seen["response"].status_code == 400 and seen["response"].json()["code"] == "variant_name_required"


def test_unpicked_anchors_are_rejected(run, pack, clicking):
    a = make_image(pack / "anchors/anchor_001.png", {"kind": "anchor", "state": "picked"})
    b = make_image(pack / "anchors/anchor_002.png", {"kind": "anchor"})
    clicking(lambda s: {"picked": [s["images"][1]["path"]]})
    spec = {"pack": "gnome-village", "target": "gnome-village", "set": "anchors"}
    windows.pick(pick_context(pack, spec))
    assert yaml.safe_load(b.with_suffix(".yaml").read_text())["state"] == "picked"
    assert not a.exists() and (pack / "anchors/rejected/anchor_001.png").exists()


def test_question_with_options(run, pack, clicking):
    clicking(lambda s: {"option": "smooth", "note": "rounder"})
    spec = {"pack": "gnome-village", "target": "gnome-village", "set": "anchors", "question": "Shading?",
            "options": ["flat", "smooth"]}
    assert windows.pick(pick_context(pack, spec)) | {"shown_in": None} == {
        "note": "rounder", "option": "smooth", "shown_in": None}


def test_pick_command_starts_a_job(run, pack, monkeypatch):
    started = []
    monkeypatch.setattr(jobs, "start", lambda *a, **k: started.append(a) or {"job": "x"})
    assert run("pick", "gnome-village", ok=False).json["code"] == "nothing_to_pick"
    make_image(pack / "anchors/anchor_001.png", {"kind": "anchor"})
    assert run("pick", "gnome-village").json == {"job": "x"}
    assert started[0][1] == "pick" and started[0][3]["set"] == "anchors"


def test_view_state(run, pack):
    assert run("view", "gnome-village/cart", ok=False).json["code"] == "not_built"
    variant = pack / "assets/cart/variants/default"
    build = variant / "builds/0001"
    build.mkdir(parents=True)
    (build / "model.glb").write_bytes(b"glb")
    (build / "compare_front.png").write_bytes(b"png")
    (build / "report.json").write_text(json.dumps({
        "validated": True, "parts": [{"name": "bed", "triangles": 12}],
        "silhouette": {"mean_object_iou": 0.9, "views": [{"view": "front", "object": {"iou": 0.9},
                                                           "compare": "compare_front.png"}]},
        "shading": {"merged": 0, "removed": 0, "flipped": 1, "parts": []}, "validation": {"issues": []}}))
    (variant / "variant.yaml").write_text("current: 1\n")
    state = windows.view_state(ws(), {"target": "gnome-village/cart"})
    assert state["validated"] and state["triangles"] == 12 and state["comparisons"][0]["object_iou"] == 0.9
    assert state["model"].startswith("files/gnome-village/assets/cart/variants/default/builds/0001/model.glb")
    assert state["comparisons"][0]["compare"].startswith("files/")
