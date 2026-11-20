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
from slopoly.comfy import colors, workflow
from slopoly.comfy.client import ComfyClient, prompt_error
from slopoly.core import SlopolyError

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "segment_run.json").read_text())


def test_shipped_workflows_have_named_inputs_and_outputs():
    for name, expected_in, expected_out in [
        ("style-anchor", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("hero", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("idol-mesh", {"image", "seed", "faces"}, {"mesh", "hero_mask"}),
        ("reference-mesh", {"image", "seed", "trellis2", "resolution", "faces"}, {"mesh", "hero_mask"}),
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
    assert by_name["prompt"]["inputs"]["value"] == "a well"
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


# --- colours ------------------------------------------------------------------------------------------------

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
    assert "No smoke, steam, fire" in inputs["prompt"] and "whole object in frame" in inputs["prompt"]
    fake = FakeComfy(lambda prompt: {"image": [png(np.full((32, 32, 3), 200, np.uint8))]})
    result = generate.generate(context(pack, kind, target, inputs), fake)
    heroes = pack / "assets/cart/heroes"
    assert [r["path"] for r in result["images"]] == [
        "slopoly/gnome-village/assets/cart/heroes/hero_001.png",
        "slopoly/gnome-village/assets/cart/heroes/hero_002.png"]
    meta = yaml.safe_load((heroes / "hero_002.yaml").read_text())
    assert meta["seed"] == 11 and meta["state"] == "undecided" and meta["job"] == "j1"
    assert len(fake.prompts) == 2 and fake.uploads[0].endswith("anchor_001.png")
    sent = {name: fake.prompts[0][node]["inputs"] for name, node in workflow.inputs(fake.prompts[0]).items()}
    assert sent["use_references"]["value"] is True and sent["use_reference_1"]["value"] is True
    assert sent["use_reference_2"]["value"] is False and sent["prompt"]["value"] == meta["prompt"]
    assert meta["references"] == ["gnome-village/anchors/anchor_001.png"]


def test_fallback_image_model_has_no_references(run, pack, started):
    from slopoly import config
    config.set_("images.model", "z-image-turbo")
    assert "hero.z-image-turbo" in workflow.active_names() and "hero" not in workflow.active_names()
    make_image(pack / "anchors/anchor_001.png", {"kind": "anchor", "state": "picked"})
    run("gen", "hero", "gnome-village/cart", "--count", "1")
    kind, target, inputs = started[0]
    fake = FakeComfy(lambda prompt: {"image": [png(np.full((32, 32, 3), 200, np.uint8))]})
    generate.generate(context(pack, kind, target, inputs), fake)
    assert "ModelSamplingAuraFlow" in workflow.class_types(fake.prompts[0]) and not fake.uploads
    sent = {name: fake.prompts[0][node]["inputs"] for name, node in workflow.inputs(fake.prompts[0]).items()}
    assert set(sent) == {"prompt", "seed"} and "wooden hand cart" in sent["prompt"]["text"]
    meta = yaml.safe_load((pack / "assets/cart/heroes/hero_001.yaml").read_text())
    assert meta["references"] == []
    config.set_("images.model", "nope")
    with pytest.raises(SlopolyError, match="no image model 'nope'"):
        workflow.image_workflow("hero")


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
    assert inputs["prompt"].endswith("Change: add a red roof") and inputs["count"] == 3
    assert inputs["references"][0] == "gnome-village/assets/cart/heroes/hero_001.png"


def test_views_need_a_picked_hero(run, pack, started):
    hero = make_image(pack / "assets/cart/heroes/hero_001.png", {"kind": "hero"})
    assert run("gen", "views", hero.as_posix(), ok=False).json["code"] == "hero_not_picked"


def reference_cart():
    from test_reference import box, merge
    return merge(box((-0.5, 0.2, -1.0), (0.5, 0.8, 1.0), (0.8, 0.6, 0.2)),
                 box((0.3, 0.3, 1.0), (0.45, 0.45, 2.0), (0.9, 0.1, 0.1)),
                 box((-0.2, 0.0, -0.2), (0.2, 0.2, 0.2), (0.2, 0.2, 0.2)))


def hero_render(size=128):
    from slopoly import meshview as mv
    cart = reference_cart()
    return mv.render(cart, mv.framed(cart.verts, *mv.NAMED["hero"], (size, size)))


def views_answer(turn=60.0):
    """The generated mesh: the cart turned ``turn`` degrees, as a GLB; the hero mask from the hero render."""
    from slopoly import meshview as mv
    mesh = reference_cart().transformed(mv.rotation_y(turn))
    return lambda prompt: {"mesh": [mv.write_glb(mesh)], "hero_mask": [mask_bytes(hero_render()[1])]}


def picked_hero(pack):
    hero = pack / "assets/cart/heroes/hero_001.png"
    hero.parent.mkdir(parents=True, exist_ok=True)
    hero.write_bytes(png(hero_render()[0]))
    hero.with_suffix(".yaml").write_text(yaml.safe_dump({"kind": "hero", "state": "picked"}))
    (pack / "assets/cart/variants/default/variant.yaml").write_text("reference: hero_001.png\n")
    return hero


class NoComfy(FakeComfy):
    def run(self, prompt, on_progress=None, on_queued=None):
        raise AssertionError("re-placing a generated mesh must not run a workflow")


def test_views_job(run, pack, started):
    picked_hero(pack)
    (pack / "assets/cart/asset.yaml").write_text("description: cart\nsize: {axis: z, metres: 3.0}\n")
    run("gen", "views", "gnome-village/cart")
    assert started[0][2]["generator"] == "idol" and not started[0][2]["reuse"]
    fake = FakeComfy(views_answer())
    result = generate.make_views(context(pack, *started[0]), fake)
    assert "SplatToMesh" in {n["class_type"] for n in fake.prompts[0].values()}
    assert (result["front"], result["front_yaw"], result["mirrored"], result["scale"]) == (
        "detected", -60.0, False, "given")
    assert [v["view"] for v in result["views"]] == ["front", "side", "top", "back"]
    side = next(v for v in result["views"] if v["view"] == "side")
    assert side["axes"] == {"x": "-z", "y": "-y"} and side["width"] * side["m_per_px"] > 3.0
    folder = pack / "assets/cart/views/hero_001"
    for name in ("front.png", "top_mask.png", "reference.glb", "generated.glb", "hero_mask.png"):
        assert (folder / name).exists(), name
    meta = yaml.safe_load((folder / "views.yaml").read_text())
    assert meta["front"] == "detected" and meta["views"][1]["fit"]["scale"] > 0
    seed = meta["seed"]
    run("gen", "views", "gnome-village/cart", "--front-yaw", "450")
    assert started[1][2]["seed"] == seed and started[1][2]["front_yaw"] == 90 and started[1][2]["reuse"]
    turned = generate.make_views(context(pack, *started[1]), NoComfy(None))
    assert (turned["front"], turned["front_yaw"]) == ("given", 90.0)


def test_trellis2_generator_sets_its_switch(run, pack, started):
    picked_hero(pack)
    run("gen", "views", "gnome-village/cart", "--generator", "trellis2")
    fake = FakeComfy(views_answer())
    generate.make_views(context(pack, *started[0]), fake)
    assert fake.prompts[0][workflow.inputs(fake.prompts[0])["trellis2"]]["inputs"]["value"] is True


def test_unknown_generator_is_refused(run, pack, started):
    picked_hero(pack)
    assert run("gen", "views", "gnome-village/cart", "--generator", "nope", ok=False).json["code"] ==         "unknown_generator"


def segmented(pack, run, started, parts, answer, *more):
    """Views of the test cart, then a segment job of ``parts`` answered by ``answer(part, image size)``."""
    picked_hero(pack)
    run("gen", "views", "gnome-village/cart")
    generate.make_views(context(pack, *started[0]), FakeComfy(views_answer()))
    return segment_again(pack, run, started, parts, answer, *more)


def segment_again(pack, run, started, parts, answer, *more):
    run("segment", "gnome-village/cart", "--parts", parts, *more)
    fake = FakeComfy(None)

    def reply(prompt):
        node = prompt[workflow.inputs(prompt)["prompt"]]
        mask = answer(node["inputs"][workflow.primary_input(node)].split(":")[0])
        return {"mask": [mask_bytes(mask)] if mask is not None else []}
    fake.answer = reply
    return generate.segment(context(pack, *started[-1]), fake), fake


def object_mask(pack, view="front"):
    return colors.mask_array(Image.open(pack / f"assets/cart/views/hero_001/{view}_mask.png"))


def lower_part(pack):
    """The bottom fifth of the front silhouette (the cart's stand), as the detector's answer at 768 px."""
    whole = object_mask(pack)
    rows = np.nonzero(whole.any(1))[0]
    out = np.zeros_like(whole)
    out[rows.max() - (rows.max() - rows.min()) // 5:] = True
    return out & whole


def test_segment_job(run, pack, started):
    result, _ = segmented(pack, run, started, "wheel,rope",
                          lambda part: lower_part(pack) if part == "wheel" else None)
    parts = {(x["part"], x["view"]) for x in result["masks"]}
    assert ("object", "front") in parts and ("wheel", "front") in parts
    assert {"part": "rope", "view": "front", "reason": "not_found"} in result["missing"]
    wheel_front = next(x for x in result["masks"] if (x["part"], x["view"]) == ("wheel", "front"))
    x, y, w, h = colors.bounds(lower_part(pack))
    assert wheel_front["bounds"] == {"x": x, "y": y, "width": w, "height": h} and Path(wheel_front["path"]).exists()
    regions = {r["part"]: r for r in result["regions"]}
    assert regions["rope"]["uncertain"] and regions["rope"]["bounds"] is None
    assert regions["wheel"]["bounds"] is not None and regions["wheel"]["bounds"][0][1] == pytest.approx(0, abs=0.2)
    assert run("check").json == {"ok": True}


def test_segment_within_a_box_uses_an_enlarged_crop(run, pack, started):
    seen = []

    def answer(part):
        seen.append(part)
        return np.ones((100, 100), bool)  # everything in the crop it was shown
    result, fake = segmented(pack, run, started, "spike@side:0.5,0.0,1.0,0.5", answer, "--no-3d")
    masks = [x for x in result["masks"] if x["part"] == "spike"]
    assert [x["view"] for x in masks] == ["side"]
    region = masks[0]["region"]
    assert region[0] >= 768 * 0.5 - 768 * 0.05 - 1 and region[3] <= 768 * 0.5 + 768 * 0.05 + 1  # the box, padded
    b = masks[0]["bounds"]
    assert b["x"] >= region[0] and b["y"] + b["height"] <= region[3]
    assert not result["regions"] and len(seen) == 1


def test_implausible_masks_are_flagged_and_parts_merge(run, pack, started):
    def answer(part):
        whole = object_mask(pack)
        cols = np.nonzero(whole.any(0))[0]
        big = whole.copy()
        big[:, cols.min() + int(0.8 * (cols.max() - cols.min())):] = False  # 80 % of the object, not all of it
        return big
    result, _ = segmented(pack, run, started, "horn,spike", answer, "--no-3d")
    flagged = {(x["part"], x["view"]): x.get("implausible") for x in result["masks"] if x["part"] != "object"}
    assert flagged[("horn", "front")] and "of the object" in flagged[("horn", "front")]
    result, _ = segment_again(pack, run, started, "tusk", lambda part: lower_part(pack), "--no-3d")
    assert {"horn", "spike", "tusk"} <= {x["part"] for x in result["masks"]}  # earlier parts are kept


def test_resize_rescales_views_without_generating(run, pack, started):
    picked_hero(pack)
    (pack / "assets/cart/asset.yaml").write_text("description: cart\nsize: {axis: z, metres: 3.0}\n")
    run("gen", "views", "gnome-village/cart")
    generate.make_views(context(pack, *started[0]), FakeComfy(views_answer()))
    folder = pack / "assets/cart/views/hero_001"
    before = yaml.safe_load((folder / "views.yaml").read_text())
    image = (folder / "side.png").read_bytes()
    result = run("asset", "size", "gnome-village/cart", "z=6").json
    after = yaml.safe_load((folder / "views.yaml").read_text())
    assert result["size"] == {"axis": "z", "metres": 6.0} and len(result["rescaled"]) == 1
    assert after["views"][1]["m_per_px"] == pytest.approx(2 * before["views"][1]["m_per_px"], rel=1e-3)
    assert after["front"] == before["front"] and after["placement"]["yaw"] == before["placement"]["yaw"]
    assert (folder / "side.png").read_bytes() == image  # framed to the object: the picture is the same
    from slopoly import meshview as mv
    lo, hi = mv.load_glb((folder / "reference.glb").read_bytes()).bounds()
    assert hi[2] - lo[2] == pytest.approx(6.0, rel=1e-4)


def test_old_splat_views_are_reported_by_check(run, pack, started):
    picked_hero(pack)
    folder = pack / "assets/cart/views/hero_001"
    folder.mkdir(parents=True)
    (folder / "views.yaml").write_text("hero: hero_001.png\nviews: []\n")
    problems = run("check", "gnome-village", ok=False).json["problems"]
    assert any(p["field"] == "mesh" and "gen views" in p["message"] for p in problems)


def test_look_renders_a_region_close_up_beside_the_build(run, pack, started):
    segmented(pack, run, started, "wheel", lambda part: lower_part(pack))
    from slopoly import meshview as mv
    variant = pack / "assets/cart/variants/default"
    (variant / "builds/0001").mkdir(parents=True)
    (variant / "builds/0001/model.glb").write_bytes(mv.write_glb(reference_cart()))
    (variant / "variant.yaml").write_text("reference: hero_001.png\ncurrent: 1\n")
    result = run("look", "gnome-village/cart", "--from", "top", "--region", "wheel", "--with-build").json
    assert result["camera"]["yaw"] == 0 and result["camera"]["pitch"] == 90 and result["build_number"] == 1
    assert Path(result["reference"]).exists() and Path(result["build"]).exists()
    assert result["bounds"][0][1] == pytest.approx(0, abs=0.2)
    whole = run("look", "gnome-village/cart", "--from", "30,20", "--perspective", "--zoom", "2").json
    assert whole["camera"]["perspective"] and "build" not in whole
    assert run("look", "gnome-village/cart", "--region", "rope", ok=False).json["code"] == "no_region"
    assert run("look", "gnome-village/cart", "--from", "sideways", ok=False).json["code"] == "bad_direction"
    assert "**/variants/*/looks/" in (pack / ".gitignore").read_text()


def test_revision_uses_its_source_as_first_reference(run, pack, started):
    make_image(pack / "anchors/anchor_001.png", {"kind": "anchor", "state": "picked"})
    hero = make_image(pack / "assets/cart/heroes/hero_001.png",
                      {"kind": "hero", "prompt": "a cart", "references": ["gnome-village/anchors/anchor_001.png"]})
    run("gen", "revise", hero.as_posix(), "--change", "add a red roof", "--count", "1")
    kind, target, inputs = started[0]
    fake = FakeComfy(lambda prompt: {"image": [png(np.full((32, 32, 3), 200, np.uint8))]})
    generate.generate(context(pack, kind, target, inputs), fake)
    sent = {name: fake.prompts[0][node]["inputs"] for name, node in workflow.inputs(fake.prompts[0]).items()}
    assert sent["use_references"]["value"] is True and sent["prompt"]["value"].startswith("a cart")
    assert fake.uploads[0].endswith("hero_001.png")
