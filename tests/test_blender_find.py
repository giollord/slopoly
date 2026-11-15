import sys

import pytest

from slopoly import blender, config
from slopoly.core import SlopolyError


def fake_blender(folder, version):
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        path = folder / "blender.cmd"
        path.write_text(f"@echo Blender {version}\n")
    else:
        path = folder / "blender"
        path.write_text(f"#!/bin/sh\necho 'Blender {version}'\n")
        path.chmod(0o755)
    return path


@pytest.fixture(autouse=True)
def fresh():
    blender.find.cache_clear()
    yield
    blender.find.cache_clear()


def test_configured_blender(tmp_path):
    config.set_("blender.path", str(fake_blender(tmp_path / "b51", "5.1.2")))
    found = blender.find()
    assert found.version == (5, 1, 2) and found.supported
    assert found.libs.as_posix().endswith("blender/5.1/site-packages")


def test_configured_blender_too_old(tmp_path):
    config.set_("blender.path", str(fake_blender(tmp_path / "b42", "4.2.0")))
    with pytest.raises(SlopolyError) as error:
        blender.find()
    assert error.value.code == "no_blender" and "older than 5.0" in error.value.message
    assert "blender.org" in error.value.hint


def test_discovery_skips_old_versions(tmp_path, monkeypatch):
    old, new = fake_blender(tmp_path / "old", "3.6.0"), fake_blender(tmp_path / "new", "5.3.0")
    monkeypatch.setattr(blender, "candidates", lambda: [old, new])
    assert blender.find().path == new


def test_nothing_found(monkeypatch):
    monkeypatch.setattr(blender, "candidates", lambda: [])
    with pytest.raises(SlopolyError, match="no Blender 5.0 or newer found"):
        blender.find()


def test_missing_libs(tmp_path):
    config.set_("blender.path", str(fake_blender(tmp_path / "b", "5.3.0")))
    found = blender.find()
    assert set(blender.missing_libs(found)) == {"pillow", "scikit-image", "manifold3d"}
    (found.libs / "pillow-12.0.0.dist-info").mkdir(parents=True)
    assert "pillow" not in blender.missing_libs(found)
