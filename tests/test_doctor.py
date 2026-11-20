"""doctor and doctor --fetch against a fake ComfyUI, a fake Blender and a fake model host."""

import httpx
import pytest
import respx
from test_blender_find import fake_blender

from slopoly import blender, config, doctor

URL = "http://comfy.test"


@pytest.fixture
def comfy(tmp_path):
    """A ComfyUI with every node and the given models installed."""
    config.set_("comfyui.url", URL)
    config.set_("blender.path", str(fake_blender(tmp_path / "b", "5.3.0")))
    blender.find.cache_clear()
    installed = {m["subfolder"]: [] for m in doctor.required_models()}
    nodes = {cls: {} for cls in doctor.required_nodes()}
    with respx.mock(base_url=URL, assert_all_called=False) as mock:
        mock.get("/system_stats").respond(200, json={"system": {"comfyui_version": "0.45.3"}})
        mock.get("/object_info").mock(side_effect=lambda r: httpx.Response(200, json=nodes))
        mock.get(path__regex=r"/models/(?P<folder>\w+)").mock(
            side_effect=lambda r, folder: httpx.Response(200, json=installed.get(folder, [])))
        yield {"installed": installed, "nodes": nodes, "mock": mock}
    blender.find.cache_clear()


def by_name(result):
    return {c["check"]: c for c in result["checks"]}


def install_all(comfy):
    for m in doctor.required_models():
        comfy["installed"][m["subfolder"]].append(m["file"])


def test_all_good_except_libs(comfy):
    install_all(comfy)
    checks = by_name(doctor.doctor())
    assert checks["comfyui"]["ok"] and checks["comfyui nodes"]["ok"] and checks["comfyui models"]["ok"]
    assert checks["blender"]["ok"] and "5.3.0" in checks["blender"]["detail"]
    assert not checks["blender libraries"]["ok"] and checks["blender libraries"]["fix"] == "run slopoly doctor --fetch"


def test_missing_node_names_workflow(comfy):
    install_all(comfy)
    cls = next(c for c, w in doctor.required_nodes().items() if "idol-mesh" in w)
    del comfy["nodes"][cls]
    check = by_name(doctor.doctor())["comfyui nodes"]
    assert not check["ok"] and cls in check["missing"] and "idol-mesh" in check["detail"] and check["fix"]


def test_missing_models_without_folder(comfy):
    result = doctor.doctor()
    check = by_name(result)["comfyui models"]
    assert not check["ok"] and "comfyui.models_dir" in check["fix"]
    assert any({"file": "sam3.1_multiplex_fp16.safetensors", "subfolder": "checkpoints"}.items() <= missing.items()
               for missing in check["missing"])


def test_fetch_without_folder_downloads_nothing(comfy, monkeypatch):
    monkeypatch.setattr(blender, "install_libs", lambda b, extra=None: "libs")
    fetched = doctor.doctor(fetch_missing=True)["fetched"]
    assert fetched["models"]["downloaded"] == [] and fetched["models"]["missing"][0]["url"].startswith("https://")
    assert "config set comfyui.models_dir" in fetched["models"]["fix"]


def test_blender_missing(comfy, tmp_path):
    config.set_("blender.path", str(tmp_path / "nope" / "blender.exe"))
    install_all(comfy)
    check = by_name(doctor.doctor())["blender"]
    assert not check["ok"] and "blender.org" in check["fix"]


def test_fetch_resumes_and_installs(comfy, tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    config.set_("comfyui.models_dir", str(models_dir))
    install_all(comfy)
    sam = next(m for m in doctor.required_models() if m["subfolder"] == "checkpoints")
    comfy["installed"]["checkpoints"].remove(sam["file"])
    content = b"0123456789" * 1000
    part = models_dir / "checkpoints" / (sam["file"] + ".part")
    part.parent.mkdir()
    part.write_bytes(content[:4000])
    ranges = []

    def serve(request):
        ranges.append(request.headers.get("range"))
        start = int(request.headers["range"].split("=")[1].rstrip("-")) if "range" in request.headers else 0
        return httpx.Response(206 if start else 200, content=content[start:])
    comfy["mock"].get(sam["url"]).mock(side_effect=serve)
    monkeypatch.setattr(blender, "install_libs", lambda b, extra=None: "installed")
    result = doctor.doctor(fetch_missing=True)
    assert ranges == ["bytes=4000-"]
    assert (models_dir / "checkpoints" / sam["file"]).read_bytes() == content and not part.exists()
    assert result["fetched"]["blender_libraries"] == "installed"


def test_window_files_are_checked(monkeypatch, tmp_path):
    assert doctor.window_check()["ok"]
    monkeypatch.setattr(doctor, "WINDOW_FILES", doctor.WINDOW_FILES + ("missing.js",))
    failed = doctor.window_check()
    assert not failed["ok"] and "missing.js" in failed["detail"] and "reinstall" in failed["fix"]


def test_image_model_selects_its_models_and_names_the_licence(comfy):
    files = {m["file"] for m in doctor.required_models()}
    assert "krea2_turbo_int8_convrot.safetensors" in files and "z_image_turbo_int8_convrot.safetensors" not in files
    check = by_name(doctor.doctor())["image model"]
    assert check["images_model"] == "krea2" and "$1M" in check["detail"] and "z-image-turbo" in check["note"]
    config.set_("images.model", "z-image-turbo")
    files = {m["file"] for m in doctor.required_models()}
    assert "z_image_turbo_int8_convrot.safetensors" in files and "krea2_turbo_int8_convrot.safetensors" not in files
    assert "TextEncodeQwenImageEditPlus" not in doctor.required_nodes()
    assert "note" not in by_name(doctor.doctor())["image model"]
