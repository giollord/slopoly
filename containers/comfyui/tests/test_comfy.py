"""Comfy worker pieces against a recorded ComfyUI run (fixtures/segment_run.json) and the repo's workflow files."""

import io
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
from PIL import Image

import colors
import comfy_worker
import comfy_client
import workflow
from comfy_client import ComfyClient, prompt_error
import views
from slopoly_worker import JobFailed

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "segment_run.json").read_text())
WORKFLOWS = Path(__file__).resolve().parents[3] / "comfyui" / "workflows"


def test_repo_workflows_have_named_inputs_and_outputs():
    for name, expected_in, expected_out in [
        ("style-anchor", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("hero", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("views", {"image", "seed"}, {"ring", "ring_mask", "above", "above_mask", "hero_mask"}),
        ("segment-parts", {"image", "prompt"}, {"mask"}),
    ]:
        prompt = workflow.load(WORKFLOWS, name)
        assert expected_in <= set(workflow.inputs(prompt))
        assert set(workflow.outputs(prompt).values()) == expected_out
    assert workflow.reference_slots(workflow.load(WORKFLOWS, "style-anchor")) == [1, 2, 3]


def test_fill_sets_primary_widgets_and_keeps_defaults():
    prompt = workflow.load(WORKFLOWS, "style-anchor")
    filled = workflow.fill(prompt, {"prompt": "a well", "seed": 5, "use_reference_1": True, "unknown": 1})
    by_name = {name: filled[node_id] for name, node_id in workflow.inputs(filled).items()}
    assert by_name["prompt"]["inputs"]["prompt"] == "a well"
    assert by_name["seed"]["inputs"]["seed"] == 5
    assert by_name["use_reference_1"]["inputs"]["value"] is True
    assert by_name["use_reference_2"]["inputs"]["value"] is False  # default kept
    assert prompt != filled  # the loaded workflow isn't modified


def test_unknown_workflow_fails_readably():
    with pytest.raises(JobFailed, match="No workflow file nope.json"):
        workflow.load(WORKFLOWS, "nope")


class ReplayWebSocket:
    """Plays back the recorded websocket messages."""

    def __init__(self, messages):
        self.messages = [json.dumps(m) for m in messages]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)


async def test_run_follows_recorded_session(monkeypatch):
    monkeypatch.setattr(comfy_client.websockets, "connect", lambda *a, **k: ReplayWebSocket(FIXTURE["messages"]))
    prompt_id = FIXTURE["queued"]["prompt_id"]
    progress = []

    async def on_progress(value):
        progress.append(value)

    with respx.mock(base_url="http://comfy.test") as mock:
        mock.post("/prompt").respond(200, json=FIXTURE["queued"])
        mock.get(f"/history/{prompt_id}").respond(200, json=FIXTURE["history"])
        outputs = await ComfyClient("http://comfy.test").run(FIXTURE["prompt"], on_progress)
    assert outputs == FIXTURE["history"][prompt_id]["outputs"]
    assert progress and progress == sorted(progress) and progress[-1] <= 0.99


async def test_execution_error_is_reported(monkeypatch):
    messages = [{"type": "execution_error", "data": {"prompt_id": "p1", "node_type": "SAM3_Detect", "exception_message": "CUDA out of memory"}}]
    monkeypatch.setattr(comfy_client.websockets, "connect", lambda *a, **k: ReplayWebSocket(messages))
    with respx.mock(base_url="http://comfy.test") as mock:
        mock.post("/prompt").respond(200, json={"prompt_id": "p1"})
        with pytest.raises(JobFailed, match="SAM3_Detect: CUDA out of memory"):
            await ComfyClient("http://comfy.test").run({})


def test_missing_model_gets_its_own_code():
    response = httpx.Response(400, json={"error": {"message": "Prompt outputs failed validation"}, "node_errors": {"5": {
        "class_type": "UNETLoader", "errors": [{"type": "value_not_in_list", "message": "Value not in list",
                                                 "details": "unet_name: 'flux-2-klein-4b-fp8.safetensors' not in []"}]}}})
    error = prompt_error(response)
    assert error.code == "missing_model"
    assert "flux-2-klein-4b-fp8.safetensors" in str(error)


def shape(width: int, notch: int = 0) -> np.ndarray:
    """A centred block, optionally with a bump on its right (an asymmetric silhouette)."""
    mask = np.zeros((64, 64), bool)
    mask[20:44, 32 - width // 2:32 + width // 2] = True
    if notch:
        mask[0:20, 32 + width // 2 - notch:32 + width // 2] = True
    return mask


def turntable(points: np.ndarray, n: int = 24, size: int = 64) -> list[np.ndarray]:
    """Orthographic silhouettes of a point cloud turning about Y: frame k at yaw 360 k / n, axis at the centre column."""
    frames = []
    for k in range(n):
        yaw = np.radians(360 * k / n)
        u = points[:, 0] * np.cos(yaw) + points[:, 2] * np.sin(yaw)
        mask = np.zeros((size, size), bool)
        mask[np.floor(size / 2 - points[:, 1] * 20).astype(int), np.floor(size / 2 + u * 20).astype(int)] = True
        frames.append(mask)
    return frames


def box(x0, x1, y0, y1, z0, z1, step=0.02) -> np.ndarray:
    grid = np.mgrid[x0:x1:step, y0:y1:step, z0:z1:step]
    return grid.reshape(3, -1).T


# A cart-like body, mirror-symmetric about x = 0, with a handle at the back (-z): its front faces yaw 0.
CART = np.concatenate([box(-0.5, 0.5, -0.3, 0.3, -1.0, 1.0), box(-0.4, -0.3, 0.0, 0.5, -1.4, -1.0),
                       box(0.3, 0.4, 0.0, 0.5, -1.4, -1.0)])


def painted(ring: list[np.ndarray]) -> list[np.ndarray]:
    """Colour frames: the front is painted red and the back blue, blending as the cart turns."""
    n = len(ring)
    return [(m[..., None] * [128 + 127 * np.cos(2 * np.pi * k / n), 60, 128 - 127 * np.cos(2 * np.pi * k / n)]).astype(np.uint8)
            for k, m in enumerate(ring)]


def test_front_is_the_mirror_plane_nearest_the_hero():
    ring = turntable(CART)
    colours = painted(ring)
    picked = views.pick_front(ring, ring[2], colours, colours[2])  # the hero seen 30 degrees off the front
    assert (picked["front"], picked["how"], picked["heroFrame"]) == (0, "detected", 2)
    # Seen 30 degrees off the back, the silhouette is the same; only the colours show it's the back.
    assert np.array_equal(ring[10], ring[2])
    assert views.pick_front(ring, ring[10], colours, colours[10])["front"] == 12


def test_asymmetric_object_falls_back_to_the_hero_direction():
    lopsided = np.concatenate([CART, box(0.5, 1.0, -0.3, 0.5, 0.2, 0.9), box(-0.9, -0.5, 0.3, 0.6, -0.9, -0.2)])
    ring = turntable(lopsided)
    picked = views.pick_front(ring, hero=ring[5])
    assert (picked["front"], picked["how"]) == (5, "assumed")


def test_view_frames_follow_the_calibrated_turn():
    assert views.frames(35, 72) == {"front": ("ring", 35), "side": ("ring", 17), "back": ("ring", 71),
                                    "top": ("above", 35)}
    assert views.frame_of(views.yaw_of(35, 72), 72) == 35


def png_of(mask: np.ndarray) -> bytes:
    return comfy_worker.png(mask)


def rgb_png(rgb: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, "PNG")
    return buffer.getvalue()


class FakeJob:
    def __init__(self, inputs, files=None):
        self.inputs = inputs
        self.files = files or {}
        self.uploads = []

    async def read(self, file_id):
        return self.files[file_id]

    async def upload(self, data, name, content_type):
        self.uploads.append(name)
        return f"file-{len(self.uploads)}"


class FakeStaging:
    async def fetch(self, file_id, name):
        return name

    def save(self, image, name):
        return name


def fake_views_run(n: int):
    ring = turntable(CART, n)

    async def run(job, prompt, values, share=(0.0, 1.0)):
        masks = [png_of(m) for m in ring]
        return {"ring": colour_pngs, "ring_mask": masks, "above": colour_pngs, "above_mask": masks, "hero_mask": [masks[1]]}

    colour_pngs = [rgb_png(c) for c in painted(ring)]
    return run


async def test_views_job_returns_four_views_with_masks(monkeypatch):
    monkeypatch.setattr(comfy_worker, "run_prompt", fake_views_run(8))
    hero = rgb_png(painted(turntable(CART, 8))[1])  # seen 45 degrees off the front
    job = FakeJob({"image": "hero", "seed": 7}, {"hero": hero})
    result = await comfy_worker.make_views(job, {}, FakeStaging())
    assert (result["front"], result["frontYaw"]) == ("detected", 0.0)
    assert [v["view"] for v in result["views"]] == ["front", "side", "back", "top"]
    front = result["views"][0]
    assert (front["width"], front["height"]) == (64, 64)
    assert front["bounds"] == comfy_worker.box(turntable(CART, 8)[0])
    assert len(job.uploads) == 8


async def test_given_front_yaw_skips_the_symmetry_search(monkeypatch):
    monkeypatch.setattr(comfy_worker, "run_prompt", fake_views_run(8))

    def no_search(*_):
        raise AssertionError("the symmetry search ran")
    monkeypatch.setattr(views, "pick_front", no_search)
    result = await comfy_worker.make_views(FakeJob({"image": "hero", "seed": 7, "frontYaw": 90}), {}, FakeStaging())
    assert (result["front"], result["frontYaw"]) == ("given", 90.0)


async def test_segmentation_runs_per_view_with_the_render_silhouette(monkeypatch):
    whole = shape(40)
    wheel = np.zeros((64, 64), bool)
    wheel[36:44, 14:22] = True
    found = {"wheel": wheel, "cart": whole, "rope": None}
    calls = []

    async def run(job, prompt, values, share=(0.0, 1.0)):
        calls.append((values["image"], values["prompt"]))
        mask = found[values["prompt"].split(":")[0]]
        return {"mask": [png_of(mask)] if mask is not None else []}
    monkeypatch.setattr(comfy_worker, "run_prompt", run)
    image = io.BytesIO()
    Image.new("RGB", (64, 64), (139, 90, 43)).save(image, "PNG")
    files = {"front-img": image.getvalue(), "front-mask": png_of(whole)}
    job = FakeJob({"parts": ["wheel", "cart", "rope"], "object": "cart",
                   "views": [{"conceptImageId": "c1", "view": "front", "image": "front-img", "mask": "front-mask"}]},
                  files)
    result = await comfy_worker.segment(job, {}, FakeStaging())
    assert calls == [("front.png", "wheel:8"), ("front.png", "cart:8"), ("front.png", "rope:8")]  # every instance
    assert [(m["part"], m["view"], m["conceptImageId"]) for m in result["masks"]] == [
        ("object", "front", "c1"), ("wheel", "front", "c1")]
    assert result["masks"][0]["fileId"] == "front-mask"
    assert result["masks"][1]["bounds"] == {"x": 14, "y": 36, "width": 8, "height": 8}
    assert result["missing"] == [{"part": "cart", "view": "front", "reason": "whole_object"},
                                 {"part": "rope", "view": "front", "reason": "not_found"}]


def test_mask_bounds_iou_and_colours():
    pixels = np.zeros((40, 60, 3), dtype=np.uint8)
    pixels[10:30, 10:40] = (139, 90, 43)  # wood
    pixels[10:30, 40:50] = (40, 40, 40)   # iron
    mask = np.zeros((40, 60), dtype=bool)
    mask[10:30, 10:50] = True
    assert colors.bounds(mask) == (10, 10, 40, 20)
    assert colors.bounds(np.zeros((4, 4), bool)) is None
    assert colors.iou(mask, mask) == 1.0
    found = colors.dominant_colors(Image.fromarray(pixels), mask)
    assert [c["hex"] for c in found] == ["#8b5a2b", "#282828"]
    assert found[0]["coverage"] == pytest.approx(0.75, abs=0.01)
