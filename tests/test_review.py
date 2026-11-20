"""Review notes: strokes on the panes, the build parts they hit, the note lifecycle and the review window's state."""
import base64
import io

import numpy as np
import pytest
import yaml
from PIL import Image
from test_reference import box, merge

from slopoly import meshview as mv
from slopoly import review, windows, workspace


def build_mesh():
    """A body with a chimney on top (front at +Z)."""
    body = box((-0.5, 0.0, -1.0), (0.5, 0.6, 1.0), (0.5, 0.4, 0.2))
    chimney = box((-0.1, 0.6, 0.5), (0.1, 1.2, 0.7), (0.2, 0.2, 0.2))
    mesh = merge(body, chimney)
    mesh.face_parts = np.array(["body"] * 12 + ["chimney"] * 12, dtype=object)
    return mesh


@pytest.fixture
def built(run, pack):
    """The cart's default variant with build 1 (the mesh above) and a reference mesh whose chimney is taller."""
    variant_dir = pack / "assets/cart/variants/default"
    (variant_dir / "builds/0001").mkdir(parents=True)
    (variant_dir / "builds/0001/model.glb").write_bytes(mv.write_glb(build_mesh()))
    (variant_dir / "builds/0001/report.json").write_text("{}")
    meta = yaml.safe_load((variant_dir / "variant.yaml").read_text()) or {}
    (variant_dir / "variant.yaml").write_text(yaml.safe_dump({**meta, "current": 1}))
    return workspace.find().target("gnome-village/cart:default").need_variant()


def front_camera():
    return {"position": [0.0, 0.6, 6.0], "target": [0.0, 0.6, 0.0], "fov": 35}


def project(point, camera, size=(512, 512)):
    cam = review.camera_of(camera, size)
    (u, v), = cam.project(np.array([point], float))[0]
    return [u / size[0], v / size[1]]


def png_url():
    out = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def test_glb_keeps_part_names():
    loaded = mv.load_glb(mv.write_glb(build_mesh()))
    assert sorted(set(loaded.face_parts.tolist())) == ["body", "chimney"]


def test_strokes_on_the_chimney_hit_the_chimney():
    camera = front_camera()
    stroke = {"points": [project((0, 0.8, 0.7), camera), project((0, 1.1, 0.7), camera)], "width": 0.02}
    found = review.hits(build_mesh(), review.camera_of(camera, (512, 512)),
                        review.stroke_weights([stroke], (512, 512)))
    assert found["parts"][0]["part"] == "chimney" and found["parts"][0]["share"] > 0.8
    assert abs(found["parts"][0]["centre"][1] - 0.9) < 0.3
    assert found["empty"] < 0.2


def test_strokes_over_empty_space_find_the_region_on_the_reference():
    tall = merge(box((-0.5, 0.0, -1.0), (0.5, 0.6, 1.0), (0.5, 0.4, 0.2)),
                 box((-0.1, 0.6, 0.5), (0.1, 1.6, 0.7), (0.2, 0.2, 0.2)))
    camera = front_camera()
    stroke = {"points": [project((0, 1.3, 0.7), camera), project((0, 1.5, 0.7), camera)], "width": 0.02}
    out = review.evaluate({"camera": camera, "aspect": 1.0, "model_strokes": [stroke], "left": "mesh"},
                          build_mesh(), tall)
    assert out["empty"] > 0.8 and not out["hits"]
    assert out["region"] is not None and out["region"][1][1] > 1.4


def test_note_lifecycle(built):
    camera = front_camera()
    stroke = {"points": [project((0, 0.9, 0.7), camera)], "width": 0.03}
    added = review.add_notes(built, 1, [
        {"comment": "chimney too short", "camera": camera, "aspect": 1.0, "left": "hero", "model_strokes": [stroke],
         "images": {"model": png_url(), "reference": png_url()}},
        {"comment": "", "model_strokes": [], "reference_strokes": []},  # empty: skipped
    ], build_mesh(), None)
    assert [n.number for n in added] == [1] and added[0].hits[0]["part"] == "chimney"
    assert (review.notes_dir(built) / "001_model.png").exists()
    assert review.open_count(built) == 1
    with pytest.raises(Exception, match="--by"):
        review.set_status(built, 1, "addressed", None, "taller")
    assert review.set_status(built, 1, "addressed", 2, "made it 0.6 m taller")["open"] == 0
    state = windows.review_state(workspace.find(), {"target": built.address})
    assert [p["number"] for p in state["pins"]] == [1] and state["pins"][0]["reason"] == "made it 0.6 m taller"
    assert state["mesh"] is None and state["mesh_reason"]
    assert review.confirm(built, [{"number": 1, "fixed": False, "comment": "still short"}], 2) == \
        {"closed": [], "reopened": [1]}
    assert review.open_count(built) == 1
    review.set_status(built, 1, "addressed", 3, "taller again")
    assert review.confirm(built, [{"number": 1, "fixed": True}], 3)["closed"] == [1]
    assert [e.status for e in review.load_notes(built).notes[0].history] == \
        ["open", "addressed", "open", "addressed", "closed"]


def test_note_commands_and_status(run, built):
    review.add_notes(built, 1, [{"comment": "wheels too small"}], build_mesh(), None)
    assert run("notes", built.address).json["open"] == 1
    assert run("status", built.address).json["notes"] == {"open": 1, "unconfirmed": 0}
    assert run("notes", built.address, "--brief").json["notes"] == [
        {"number": 1, "status": "open", "comment": "wheels too small"}]
    review.set_status(built, 1, "addressed", 1, "bigger wheels")
    status = run("status", built.address).json["notes"]
    assert status["unconfirmed"] == 1 and "slopoly review" in status["hint"]
    review.set_status(built, 1, "open", None, None)
    assert run("note", built.address, "1", "wontfix", ok=False).json["code"] == "reason_required"
    assert run("note", built.address, "1", "wontfix", "--reason", "matches the hero").json["open"] == 0
    assert run("notes", built.address).json["notes"] == []
    assert len(run("notes", built.address, "--all").json["notes"]) == 1


def test_review_job_stores_sent_notes(run, built, monkeypatch):
    sent = {}

    def fake_show(server, title, done, context, size=None, guard=None):
        import httpx
        state = httpx.get(server.url + "api/state").json()
        sent["state"] = state
        assert httpx.post(server.url + "api/dirty", json={"dirty": True}).json() == {"dirty": True}
        assert guard.dirty
        camera = front_camera()
        body = {"notes": [{"comment": "chimney", "camera": camera, "aspect": 1.0, "left": "hero",
                           "model_strokes": [{"points": [project((0, 0.9, 0.7), camera)], "width": 0.03}]}]}
        sent["response"] = httpx.post(server.url + "api/choice", json=body).json()
        return "window"
    monkeypatch.setattr(windows, "show", fake_show)

    class Context:
        ws = workspace.find()
        inputs = {"target": built.address, "build": None}
    result = windows.review_job(Context())
    assert sent["state"]["model"].startswith("files/") and sent["state"]["build"] == 1
    assert result["notes"][0]["hits"][0]["part"] == "chimney" and result["open"] == 1


def test_review_closed_without_sending_is_cancelled(run, built, monkeypatch):
    def fake_show(server, title, done, context, size=None, guard=None):
        import httpx
        httpx.post(server.url + "api/dirty", json={"dirty": True})
        assert httpx.post(server.url + "api/close", json={}).json() == {"closing": True}
        assert guard.discard.is_set() and not done.is_set()
        return "window"
    monkeypatch.setattr(windows, "show", fake_show)

    class Context:
        ws = workspace.find()
        inputs = {"target": built.address, "build": None}
    with pytest.raises(windows.jobs.Cancelled):
        windows.review_job(Context())
    assert review.load_notes(built).notes == []


def test_note_image_highlights_the_painted_area():
    image = Image.new("RGB", (200, 100), (200, 200, 200))
    raw = io.BytesIO()
    image.save(raw, "PNG")
    assert review.highlight(raw.getvalue(), []) == raw.getvalue()  # no strokes: unchanged
    stroke = {"points": [[0.25, 0.5], [0.35, 0.5]], "width": 0.05}  # 10 px wide, x 50..70
    out = np.asarray(Image.open(io.BytesIO(review.highlight(raw.getvalue(), [stroke]))).convert("RGB")).astype(int)
    assert out[50, 60].tolist() == [200, 200, 200]  # painted: as it was, no paint colour
    assert out[50, 150].tolist() == [80, 80, 80]  # far away: dimmed
    inner, outer = out[50, 76], out[50, 78]  # just outside the stroke's end (painted to x 74): the border
    assert inner[0] > 200 and inner[2] < 100 and outer.max() < 60
    assert out[10, 10].tolist() == out[90, 190].tolist()  # nothing blurred: the dimmed area is flat
