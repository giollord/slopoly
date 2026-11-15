import json
import sys
from pathlib import Path

import pytest

from slopoly import cli


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Each test runs in an empty repository folder with its own config and data folders."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SLOPOLY_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("SLOPOLY_DATA_DIR", str(tmp_path / "data"))
    for key in ("SLOPOLY_WORKSPACE", "SLOPOLY_COMFYUI_URL", "SLOPOLY_COMFYUI_MODELS_DIR", "SLOPOLY_BLENDER_PATH"):
        monkeypatch.delenv(key, raising=False)
    return repo


class Result:
    def __init__(self, code, out):
        self.code, self.out = code, out
        self.json = json.loads(out) if out.strip() else None


@pytest.fixture
def run(capsys):
    def invoke(*args, ok=True):
        capsys.readouterr()
        code = 0
        old = sys.argv
        sys.argv = ["slopoly", *map(str, args)]
        try:
            cli.main()
        except SystemExit as done:
            code = done.code or 0
        finally:
            sys.argv = old
        result = Result(code, capsys.readouterr().out)
        if ok is not None:
            assert (code == 0) == ok, result.out
        return result
    return invoke


@pytest.fixture
def pack(run):
    run("init")
    run("pack", "new", "gnome-village")
    run("asset", "new", "gnome-village/cart", "--description", "wooden hand cart")
    return Path("slopoly/gnome-village")


def make_image(path: Path, meta: dict, size=(8, 8)) -> Path:
    import yaml
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 180, 160)).save(path)
    path.with_suffix(".yaml").write_text(yaml.safe_dump(meta))
    return path
