"""ComfyUI pieces: workflow files, the client against a recorded run, and the generation jobs on a fake ComfyUI."""

import io
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
import yaml
from conftest import make_image
from PIL import Image

from slopoly import generate, jobs, workspace
from slopoly import models as m
from slopoly.comfy import client as comfy_client
from slopoly.comfy import colors, views, workflow
from slopoly.comfy.client import ComfyClient, prompt_error
from slopoly.core import SlopolyError

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "segment_run.json").read_text())


def test_shipped_workflows_have_named_inputs_and_outputs():
    for name, expected_in, expected_out in [
        ("style-anchor", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("hero", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("views", {"image", "seed"}, {"ring", "ring_mask", "above", "above_mask", "hero_mask"}),
        ("segment-parts", {"image", "prompt"}, {"mask"}),
    ]:
        prompt = workflow.load(name)
        assert expected_in <= set(workflow.inputs(prompt))
        assert set(workflow.outputs(prompt).values()) == expected_out
    assert workflow.reference_slots(workflow.load("style-anchor")) == [1, 2, 3]


def test_fill_sets_primary_widgets_and_keeps_defaults():
    prompt = workflow.load("style-anchor")
    filled = workflow.fill(prompt, {"prompt": "a well", "seed": 5, "use_reference_1": True, "unknown": 1})
    by_name = {name: filled[node_id] for name, node_id in workflow.inputs(filled).items()}
    assert by_name["prompt"]["inputs"]["prompt"] == "a well"
    assert by_name["seed"]["inputs"]["seed"] == 5
    assert by_name["use_reference_1"]["inputs"]["value"] is True
    assert by_name["use_reference_2"]["inputs"]["value"] is False
    assert prompt != filled


def test_unknown_workflow_fails_readably():
    with pytest.raises(SlopolyError, match="no workflow file nope.json"):
        workflow.load("nope")


class ReplayWebSocket:
    def __init__(self, messages):
        self.messages = [json.dumps(x) for x in messages]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return iter(self.messages)


def test_run_follows_recorded_session(monkeypatch):
    monkeypatch.setattr(comfy_client, "connect", lambda *a, **k: ReplayWebSocket(FIXTURE["messages"]))
    prompt_id = FIXTURE["queued"]["prompt_id"]
    progress, queued = [], []
    with respx.mock(base_url="http://comfy.test") as mock:
        mock.post("/prompt").respond(200, json=FIXTURE["queued"])
        mock.get(f"/history/{prompt_id}").respond(200, json=FIXTURE["history"])
        outputs = ComfyClient("http://comfy.test").run(FIXTURE["prompt"], progress.append, queued.append)
    assert outputs == FIXTURE["history"][prompt_id]["outputs"]
    assert progress and progress == sorted(progress) and progress[-1] <= 0.99
    assert queued == [prompt_id]


def test_execution_error_is_reported(monkeypatch):
    messages = [{"type": "execution_error", "data": {"prompt_id": "p1", "node_type": "SAM3_Detect",
                                                     "exception_message": "CUDA out of memory"}}]
    monkeypatch.setattr(comfy_client, "connect", lambda *a, **k: ReplayWebSocket(messages))
    with respx.mock(base_url="http://comfy.test") as mock:
        mock.post("/prompt").respond(200, json={"prompt_id": "p1"})
        with pytest.raises(SlopolyError, match="SAM3_Detect: CUDA out of memory"):
            ComfyClient("http://comfy.test").run({})


def test_missing_model_gets_its_own_code():
    response = httpx.Response(400, json={"error": {"message": "Prompt outputs failed validation"}, "node_errors": {"5": {
        "class_type": "UNETLoader", "errors": [{"type": "value_not_in_list", "message": "Value not in list",
                                                 "details": "unet_name: 'flux-2-klein-4b-fp8.safetensors' not in []"}]}}})
    error = prompt_error(response)
    assert error.code == "missing_model" and "flux-2-klein-4b-fp8.safetensors" in error.message
    assert "doctor --fetch" in error.hint


def test_missing_node_gets_its_own_code():
    response = httpx.Response(400, json={"error": {"type": "invalid_prompt", "message":
                                                   "Cannot execute because node SAM3_Detect does not exist.",
                                                   "details": "Node ID '#7'"}, "node_errors": {}})
    error = prompt_error(response)
    assert error.code == "missing_node" and "SAM3_Detect" in error.message and "doctor" in error.hint


def test_unreachable_comfyui():
    with pytest.raises(SlopolyError) as error:
        ComfyClient("http://127.0.0.1:9").system_stats()
    assert error.value.code == "comfyui_unreachable"


# --- turntable and colours ---------------------------------------------------------------------------------------

def turntable(points: np.ndarray, n: int = 24, size: int = 64) -> list[np.ndarray]:
    frames = []
    for k in range(n):
        yaw = np.radians(360 * k / n)
        u = points[:, 0] * np.cos(yaw) + points[:, 2] * np.sin(yaw)
        mask = np.zeros((size, size), bool)
        mask[np.floor(size / 2 - points[:, 1] * 20).astype(int), np.floor(size / 2 + u * 20).astype(int)] = True
        frames.append(mask)
    return frames


def block(x0, x1, y0, y1, z0, z1, step=0.02) -> np.ndarray:
    return np.mgrid[x0:x1:step, y0:y1:step, z0:z1:step].reshape(3, -1).T


CART = np.concatenate([block(-0.5, 0.5, -0.3, 0.3, -1.0, 1.0), block(-0.4, -0.3, 0.0, 0.5, -1.4, -1.0),
                       block(0.3, 0.4, 0.0, 0.5, -1.4, -1.0)])


def painted(ring):
    n = len(ring)
    return [(x[..., None] * [128 + 127 * np.cos(2 * np.pi * k / n), 60, 128 - 127 * np.cos(2 * np.pi * k / n)]
             ).astype(np.uint8) for k, x in enumerate(ring)]


def test_front_is_the_mirror_plane_nearest_the_hero():
    ring = turntable(CART)
    colours = painted(ring)
    picked = views.pick_front(ring, ring[2], colours, colours[2])
    assert (picked["front"], picked["how"], picked["heroFrame"]) == (0, "detected", 2)
    assert views.pick_front(ring, ring[10], colours, colours[10])["front"] == 12


def test_asymmetric_object_falls_back_to_the_hero_direction():
    lopsided = np.concatenate([CART, block(0.5, 1.0, -0.3, 0.5, 0.2, 0.9), block(-0.9, -0.5, 0.3, 0.6, -0.9, -0.2)])
    ring = turntable(lopsided)
    assert (lambda p: (p["front"], p["how"]))(views.pick_front(ring, hero=ring[5])) == (5, "assumed")


def test_view_frames_follow_the_calibrated_turn():
    assert views.frames(35, 72) == {"front": ("ring", 35), "side": ("ring", 17), "back": ("ring", 71),
                                    "top": ("above", 35)}
    assert views.frame_of(views.yaw_of(35, 72), 72) == 35


def test_mask_bounds_iou_and_colours():
    pixels = np.zeros((40, 60, 3), dtype=np.uint8)
    pixels[10:30, 10:40] = (139, 90, 43)
    pixels[10:30, 40:50] = (40, 40, 40)
    mask = np.zeros((40, 60), dtype=bool)
    mask[10:30, 10:50] = True
    assert colors.bounds(mask) == (10, 10, 40, 20)
    assert colors.iou(mask, mask) == 1.0
    found = colors.dominant_colors(Image.fromarray(pixels), mask)
    assert [c["hex"] for c in found] == ["#8b5a2b", "#282828"]


# --- jobs on a fake ComfyUI --------------------------------------------------------------------------------------

def png(array) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, "PNG")
    return buffer.getvalue()


def mask_bytes(mask):
    return png((mask * 255).astype("uint8"))


class FakeComfy:
    """Stands in for ComfyClient: records uploads and prompts, answers with prepared outputs per workflow."""

    def __init__(self, answer):
        self.answer, self.uploads, self.prompts = answer, [], []

    def system_stats(self):
        return {}

    def upload(self, data, name, subfolder="slopoly"):
        self.uploads.append(name)
        return f"slopoly/{name}"

    def run(self, prompt, on_progress=None, on_queued=None):
        self.prompts.append(prompt)
        on_queued and on_queued(f"p{len(self.prompts)}")
        on_progress and on_progress(0.5)
        produced = self.answer(prompt)
        named = {name: node for node, name in workflow.outputs(prompt).items()}
        self.produced = produced
        return {named[k]: {"images": [{"filename": f"{k}:{i}"} for i in range(len(v))]} for k, v in produced.items()}

    def image(self, item):
        name, i = item["filename"].split(":")
        return self.produced[name][int(i)]


def context(pack_dir: Path, kind: str, target: str, inputs: dict) -> jobs.JobContext:
    pack = workspace.find().pack(pack_dir.name)
    job = m.Job(id="j1", kind=kind, target=target, inputs=inputs, created=jobs.now(), state="running")
    path = pack.jobs_dir / "j1.yaml"
    from slopoly.core import write_yaml
    write_yaml(path, job)
    return jobs.JobContext(pack, path, job)


@pytest.fixture
def started(monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, "start", lambda pack, kind, target, inputs, retry_of=None:
                        calls.append((kind, target, inputs)) or {"job": "j1"})
    return calls


def test_hero_needs_a_picked_anchor(run, pack, started):
    result = run("gen", "hero", "gnome-village/cart", ok=False).json
    assert result["code"] == "no_picked_anchor" and "slopoly pick" in result["hint"]


def test_hero_job_writes_images(run, pack, started):
    make_image(pack / "anchors/anchor_001.png", {"kind": "anchor", "state": "picked"})
    run("gen", "hero", "gnome-village/cart", "--count", "2", "--seed", "10")
    kind, target, inputs = started[0]
    assert (kind, target) == ("generate", "gnome-village/cart")
    assert inputs["references"] == ["gnome-village/anchors/anchor_001.png"]
    assert "wooden hand cart" in inputs["prompt"]
    fake = FakeComfy(lambda prompt: {"image": [png(np.full((32, 32, 3), 200, np.uint8))]})
    result = generate.generate(context(pack, kind, target, inputs), fake)
    heroes = pack / "assets/cart/heroes"
    assert [r["path"] for r in result["images"]] == [
        "slopoly/gnome-village/assets/cart/heroes/hero_001.png",
        "slopoly/gnome-village/assets/cart/heroes/hero_002.png"]
    meta = yaml.safe_load((heroes / "hero_002.yaml").read_text())
    assert meta["seed"] == 11 and meta["state"] == "undecided" and meta["job"] == "j1"
    assert len(fake.prompts) == 2 and fake.uploads[0].endswith("anchor_001.png")


def test_cancelled_job_writes_nothing(run, pack, started):
    make_image(pack / "anchors/anchor_001.png", {"kind": "anchor", "state": "picked"})
    run("gen", "hero", "gnome-village/cart", "--count", "1")
    ctx = context(pack, *started[0])

    def answer(prompt):
        from slopoly.core import write_yaml
        write_yaml(ctx.path, ctx.reload().model_copy(update={"cancel_requested": True}))
        return {"image": [png(np.zeros((8, 8, 3), np.uint8))]}
    with pytest.raises(jobs.Cancelled):
        generate.generate(ctx, FakeComfy(answer))
    assert not list((pack / "assets/cart/heroes").glob("*.png"))


def test_revise_with_change(run, pack, started):
    hero = make_image(pack / "assets/cart/heroes/hero_001.png",
                      {"kind": "hero", "prompt": "a cart", "references": ["gnome-village/anchors/anchor_001.png"]})
    run("gen", "revise", hero.as_posix(), "--change", "add a red roof", "--count", "3")
    inputs = started[0][2]
    assert inputs["prompt"].endswith("Change from image 1: add a red roof") and inputs["count"] == 3
    assert inputs["references"][0] == "gnome-village/assets/cart/heroes/hero_001.png"


def test_views_need_a_picked_hero(run, pack, started):
    hero = make_image(pack / "assets/cart/heroes/hero_001.png", {"kind": "hero"})
    assert run("gen", "views", hero.as_posix(), ok=False).json["code"] == "hero_not_picked"


def views_answer(n=8):
    ring = turntable(CART, n)
    colours = [png(c) for c in painted(ring)]
    masks = [mask_bytes(x) for x in ring]
    return lambda prompt: {"ring": colours, "ring_mask": masks, "above": colours, "above_mask": masks,
                           "hero_mask": [masks[1]]}


def picked_hero(pack):
    hero = pack / "assets/cart/heroes/hero_001.png"
    hero.parent.mkdir(parents=True, exist_ok=True)
    hero.write_bytes(png(painted(turntable(CART, 8))[1]))
    hero.with_suffix(".yaml").write_text(yaml.safe_dump({"kind": "hero", "state": "picked"}))
    (pack / "assets/cart/variants/default/variant.yaml").write_text("reference: hero_001.png\n")
    return hero


def test_views_job(run, pack, started):
    picked_hero(pack)
    run("gen", "views", "gnome-village/cart")
    result = generate.make_views(context(pack, *started[0]), FakeComfy(views_answer()))
    assert (result["front"], result["front_yaw"]) == ("detected", 0.0)
    assert [v["view"] for v in result["views"]] == ["front", "side", "back", "top"]
    folder = pack / "assets/cart/views/hero_001"
    assert (folder / "front.png").exists() and (folder / "top_mask.png").exists()
    assert yaml.safe_load((folder / "views.yaml").read_text())["front"] == "detected"
    seed = yaml.safe_load((folder / "views.yaml").read_text())["seed"]
    run("gen", "views", "gnome-village/cart", "--front-yaw", "450")
    assert started[1][2]["seed"] == seed and started[1][2]["front_yaw"] == 90


def test_segment_job(run, pack, started):
    picked_hero(pack)
    run("gen", "views", "gnome-village/cart")
    generate.make_views(context(pack, *started[0]), FakeComfy(views_answer()))
    wheel = np.zeros((64, 64), bool)
    wheel[36:44, 14:22] = True
    found = {"wheel": wheel, "rope": None}
    run("segment", "gnome-village/cart", "--parts", "wheel,rope")

    def answer(prompt):
        node = prompt[workflow.inputs(prompt)["prompt"]]
        name = node["inputs"][workflow.primary_input(node)]
        mask = found[name.split(":")[0]]
        return {"mask": [mask_bytes(mask)] if mask is not None else []}
    result = generate.segment(context(pack, *started[1]), FakeComfy(answer))
    parts = {(x["part"], x["view"]) for x in result["masks"]}
    assert ("object", "front") in parts and ("wheel", "front") in parts
    assert {"part": "rope", "view": "front", "reason": "not_found"} in result["missing"]
    wheel_front = next(x for x in result["masks"] if (x["part"], x["view"]) == ("wheel", "front"))
    assert wheel_front["bounds"] == {"x": 14, "y": 36, "width": 8, "height": 8} and Path(wheel_front["path"]).exists()
    assert run("check").json == {"ok": True}
