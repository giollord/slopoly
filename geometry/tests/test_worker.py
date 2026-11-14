"""The geometry worker's build handler with a fake job (no broker or API)."""
import asyncio
from pathlib import Path

import pytest
from conftest import PALETTE

import geometry_worker
from slopoly_worker import JobFailed


class FakeJob:
    def __init__(self, inputs):
        self.id, self.inputs, self.uploads, self.progressed = "job1", inputs, {}, []

    async def progress(self, fraction):
        self.progressed.append(fraction)

    async def download(self, file_id, target: Path):
        raise AssertionError("no masks in these tests")

    async def upload(self, content, name, content_type="application/octet-stream"):
        self.uploads[name] = content.read_bytes() if isinstance(content, Path) else content
        return f"file-{name}"


def run(inputs):
    job = FakeJob(inputs)
    return job, asyncio.run(geometry_worker.build(job))


def test_noop_build_completes():
    job, outputs = run({"source": "", "polyBudget": 2000})
    assert outputs["glbFileId"] == "file-model.glb" and job.uploads["model.glb"][:4] == b"glTF"
    assert outputs["validated"] is False  # an empty model is reported, not crashed
    assert outputs["report"]["validation"]["issues"][0]["issue"] == "empty"


def test_cart_build_lists_used_palette_entries(cart_source):
    _, outputs = run({"source": cart_source, "polyBudget": 2000, "palette": PALETTE})
    assert outputs["validated"]
    assert sorted(outputs["paletteEntryIds"]) == sorted(e["id"] for e in PALETTE)


def test_program_error_fails_with_line():
    with pytest.raises(JobFailed, match="line 2: NameError") as failure:
        run({"source": "x = 1\nundefined_thing()\n"})
    assert failure.value.code == "program_error"


def test_timeout_kills_the_program(monkeypatch):
    monkeypatch.setattr(geometry_worker, "BUILD_TIMEOUT", 3)
    with pytest.raises(JobFailed) as failure:
        run({"source": "while True:\n    pass\n"})
    assert failure.value.code == "timeout"


def test_palette_render_recolours_the_glb_but_keeps_its_mesh_bytes(cart_source):
    from io import BytesIO

    from PIL import Image

    from slopoly_model import glb

    job, outputs = run({"source": cart_source, "polyBudget": 2000, "palette": PALETTE})
    original = job.uploads["model.glb"]
    recoloured_palette = [dict(e, color="#00ff00") if e["role"] == "wood" else e for e in PALETTE]
    files = {"glb-1": original}

    class RenderJob(FakeJob):
        async def read(self, file_id):
            return files[file_id]

    render = RenderJob({"main": recoloured_palette, "variants": [{"id": "v1", "name": "winter", "entries": PALETTE}],
                        "builds": [{"buildId": "b1", "glbFileId": "glb-1"}]})
    result = asyncio.run(geometry_worker.palette_render(render))
    assert result == {"textureFileId": "file-palette.png", "variants": {"v1": "file-palette_winter.png"},
                      "builds": {"b1": "file-model.glb"}}
    updated = render.uploads["model.glb"]
    new_image = Image.open(BytesIO(glb.image(updated)))
    assert new_image.getpixel((4, 4))[:3] == (0, 255, 0)
    assert Image.open(BytesIO(render.uploads["palette_winter.png"])).size == new_image.size
    old_json, old_bin = glb.read(original)
    new_json, new_bin = glb.read(updated)
    image_view = old_json["images"][0]["bufferView"]
    for i, (a, b) in enumerate(zip(old_json["bufferViews"], new_json["bufferViews"])):
        if i != image_view:
            assert old_bin[a.get("byteOffset", 0):][:a["byteLength"]] == new_bin[b.get("byteOffset", 0):][:b["byteLength"]]
    assert old_json["meshes"] == new_json["meshes"] and old_json["accessors"] == new_json["accessors"]


def test_palette_render_keeps_an_empty_build_as_is():
    from slopoly_model import glb

    job, _ = run({"source": "pass", "polyBudget": 2000, "palette": PALETTE})
    empty = job.uploads["model.glb"]
    assert glb.replace_image(empty, b"png") == empty
