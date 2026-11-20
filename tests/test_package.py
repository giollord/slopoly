"""The built wheel holds the window pages and three.js (a stray .gitignore rule once left out three/build/)."""
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(subprocess.run(["uv", "--version"], capture_output=True).returncode != 0, reason="needs uv")
def test_wheel_contains_the_window_files(tmp_path):
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path), str(ROOT)], check=True, capture_output=True)
    names = set(zipfile.ZipFile(next(tmp_path.glob("*.whl"))).namelist())
    from slopoly.doctor import WINDOW_FILES
    missing = [f for f in WINDOW_FILES if f"slopoly/windows/static/{f}" not in names]
    assert not missing
    assert "slopoly/comfy/workflows/hero.json" in names and "slopoly/comfy/models.yaml" in names
