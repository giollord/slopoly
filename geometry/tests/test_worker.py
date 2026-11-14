"""The geometry worker's build handler with a fake job (no broker or API)."""
import asyncio
from pathlib import Path

import pytest
from conftest import PALETTE

import geometry_worker
from slopoly_worker import JobFailed


class FakeJob:
    def __init__(self, inputs, files=None):
        self.id, self.inputs, self.uploads, self.progressed = "job1", inputs, {}, []
        self.files = files or {}  # file id -> local path

    async def progress(self, fraction):
        self.progressed.append(fraction)

    async def download(self, file_id, target: Path):
        if file_id not in self.files:
            raise AssertionError(f"unexpected download {file_id}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(self.files[file_id]).read_bytes())
        return target

    async def upload(self, content, name, content_type="application/octet-stream"):
        self.uploads[name] = content.read_bytes() if isinstance(content, Path) else content
        return f"file-{name}"


def run(inputs, files=None):
    job = FakeJob(inputs, files)
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


def test_scene_places_builds_and_reports_overlaps_and_floating(cart_source):
    import json as _json

    from slopoly_model import glb

    build_job, _ = run({"source": cart_source, "polyBudget": 2000, "palette": PALETTE})
    model = build_job.uploads["model.glb"]

    class SceneJob(FakeJob):
        async def download(self, file_id, target: Path):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(model)
            return target

    job = SceneJob({"sceneId": "s1", "placements": [
        {"name": "cart 1", "glbFileId": "g", "at": [0, 0, 0], "rot": [0, 0, 0], "scale": 1},
        {"name": "cart 2", "glbFileId": "g", "at": [0.1, 0, 0], "rot": [0, 90, 0], "scale": 1},
        {"name": "cart 3", "glbFileId": "g", "at": [5, 1, 0], "rot": [0, 0, 0], "scale": 0.5},
    ]})
    outputs = asyncio.run(geometry_worker.scene(job))
    report = outputs["report"]
    assert outputs["glbFileId"] == "file-scene.glb"
    gltf, _ = glb.read(job.uploads["scene.glb"])
    assert {"cart 1", "cart 2", "cart 3"} <= {n.get("name") for n in gltf["nodes"]}
    assert len(gltf.get("materials", [])) == 1
    grounded = {p["name"]: p["grounded"] for p in report["placements"]}
    assert grounded == {"cart 1": True, "cart 2": True, "cart 3": False}, _json.dumps(report)
    assert [(o["a"], o["b"]) for o in report["overlaps"]] == [("cart 1", "cart 2")]
    cart3 = next(p for p in report["placements"] if p["name"] == "cart 3")["bounds"]
    assert cart3[0][0] > 4 and cart3[0][1] >= 1


def test_views_get_render_and_comparison_file_ids(tmp_path, cart_source):
    import numpy as np
    from PIL import Image

    from slopoly_model import assembly, silhouette
    from slopoly_model.runner import run_program

    model = run_program(cart_source)
    files, masks, views = {}, [], []
    for view in ("front", "side"):
        tris = np.concatenate([silhouette._projected(p, silhouette.VIEWS[view]) for p in model.parts.values()])
        lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
        scale = 150 / max(hi - lo)
        mask = silhouette._fill(list(tris * scale + (np.array([128, 128]) - (lo + hi) / 2 * scale)), (256, 256))
        path = tmp_path / f"{view}.png"
        Image.fromarray((mask * 255).astype(np.uint8)).save(path)
        files[f"mask-{view}"], files[f"view-{view}"] = path, path
        masks.append({"part": "object", "view": view, "fileId": f"mask-{view}"})
        views.append({"id": f"concept-{view}", "view": view, "fileId": f"view-{view}", "width": 256, "height": 256})
    assembly.new_model()
    job, outputs = run({"source": cart_source, "polyBudget": 2000, "palette": PALETTE, "masks": masks,
                        "views": views}, files)
    scored = {v["view"]: v for v in outputs["report"]["silhouette"]["views"]}
    for view in ("front", "side"):
        assert scored[view]["compareFileId"] == f"file-compare_{view}.png"
        assert scored[view]["renderFileId"] == f"file-render_{view}.png"
        assert job.uploads[f"compare_{view}.png"][1:4] == b"PNG"
        assert "compare" not in scored[view] and "render" not in scored[view]


def test_build_without_views_has_no_renders(cart_source):
    job, outputs = run({"source": cart_source, "polyBudget": 2000, "palette": PALETTE})
    assert outputs["report"]["silhouette"]["renders"].startswith("missing")
    assert set(job.uploads) == {"model.glb"}
