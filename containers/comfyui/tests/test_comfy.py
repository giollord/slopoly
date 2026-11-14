"""Comfy worker pieces against a recorded ComfyUI run (fixtures/segment_run.json) and the repo's workflow files."""

import json
from pathlib import Path

import httpx
import numpy as np
import pytest
import respx
from PIL import Image

import colors
import comfy_client
import workflow
from comfy_client import ComfyClient, prompt_error
from comfy_worker import thirds
from slopoly_worker import JobFailed

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "segment_run.json").read_text())
WORKFLOWS = Path(__file__).resolve().parents[3] / "comfyui" / "workflows"


def test_repo_workflows_have_named_inputs_and_outputs():
    for name, expected_in, expected_out in [
        ("style-anchor", {"prompt", "seed", "reference_1", "use_reference_3"}, {"image"}),
        ("turnaround", {"prompt", "seed", "reference_2"}, {"image"}),
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
    assert by_name["prompt"]["inputs"]["text"] == "a well"
    assert by_name["seed"]["inputs"]["noise_seed"] == 5
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


def test_turnaround_views_are_thirds():
    assert thirds(1536, 512) == {
        "front": {"x": 0, "y": 0, "width": 512, "height": 512},
        "side": {"x": 512, "y": 0, "width": 512, "height": 512},
        "top": {"x": 1024, "y": 0, "width": 512, "height": 512},
    }


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
