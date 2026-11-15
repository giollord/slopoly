"""The user's Blender: discovery, version check, the Slopoly-managed libraries for its Python, and running code in it.

Builds run ``blender --background --factory-startup --python launcher.py -- <mode> ...``; the launcher puts the
managed site-packages and this folder (which holds ``slopoly_model``) on ``sys.path`` first.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .. import config
from ..core import SlopolyError

HERE = Path(__file__).parent
LAUNCHER = HERE / "launcher.py"
REQUIREMENTS = HERE / "requirements.txt"
MIN_VERSION = (5, 0)
DOWNLOAD = "https://www.blender.org/download/"


@dataclass(frozen=True)
class Blender:
    path: Path
    version: tuple[int, int, int]

    @property
    def version_text(self) -> str:
        return ".".join(map(str, self.version))

    @property
    def supported(self) -> bool:
        return self.version[:2] >= MIN_VERSION

    @property
    def libs(self) -> Path:
        return config.data_dir() / "blender" / f"{self.version[0]}.{self.version[1]}" / "site-packages"

    def command(self, *args: str) -> list[str]:
        return [str(self.path), "--background", "--factory-startup", "--python-exit-code", "3",
                "--python", str(LAUNCHER), "--", str(self.libs), *args]

    def python(self) -> Path:
        """Blender's bundled Python interpreter."""
        out = subprocess.run([str(self.path), "--background", "--factory-startup", "--python-expr",
                              "import sys; print('SLOPOLY_PY=' + sys.executable)"],
                             capture_output=True, text=True, timeout=120)
        match = re.search(r"SLOPOLY_PY=(.+)", out.stdout)
        if not match:
            raise SlopolyError("blender_failed", "could not ask Blender for its Python", details=out.stderr[-2000:])
        return Path(match.group(1).strip())


def version_of(path: Path) -> tuple[int, int, int] | None:
    try:
        out = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"Blender (\d+)\.(\d+)(?:\.(\d+))?", out)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)) if match else None


def candidates() -> list[Path]:
    """Executables in the usual install locations, newest version folder first."""
    found: list[str] = []
    if on_path := shutil.which("blender"):
        found.append(on_path)
    if sys.platform == "win32":
        for root in {os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")} - {""}:
            found += glob.glob(os.path.join(root, "Blender Foundation", "Blender*", "blender.exe"))
        found += glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender*\blender.exe"))
    elif sys.platform == "darwin":
        found += glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender")
        found += glob.glob(os.path.expanduser("~/Applications/Blender*.app/Contents/MacOS/Blender"))
    else:
        found += ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"]
        found += glob.glob(os.path.expanduser("~/blender*/blender")) + glob.glob("/opt/blender*/blender")

    def key(p: str):
        nums = re.findall(r"(\d+)\.(\d+)", p)
        return tuple(map(int, nums[-1])) if nums else (0, 0)

    first = found[:1] if on_path else []
    rest = sorted(set(found) - set(first), key=key, reverse=True)
    return [Path(p) for p in first + rest if Path(p).is_file()]


@lru_cache(maxsize=1)
def find() -> Blender:
    configured = config.get("blender.path")
    paths = [Path(configured)] if configured else candidates()
    seen = []
    for path in paths:
        version = version_of(path)
        if version is None:
            continue
        blender = Blender(path, version)
        if blender.supported:
            return blender
        seen.append(f"{path.as_posix()} ({blender.version_text})")
    if configured:
        problem = (f"the configured Blender {seen[0]} is older than {'.'.join(map(str, MIN_VERSION))}" if seen
                   else f"the configured Blender path {configured} does not run")
    else:
        problem = (f"no Blender {'.'.join(map(str, MIN_VERSION))} or newer found" +
                   (f"; found only {', '.join(seen)}" if seen else ""))
    raise SlopolyError("no_blender", problem,
                       f"install Blender from {DOWNLOAD}, or run slopoly config set blender.path <path to blender>")


def missing_libs(blender: Blender) -> list[str]:
    """Requirement names (from requirements.txt) not installed in the managed folder."""
    names = [re.split(r"[<>=!~ ;]", line.strip())[0] for line in REQUIREMENTS.read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    have = {p.name.split("-")[0].lower().replace("_", "-") for p in blender.libs.glob("*.dist-info")}
    return [n for n in names if n.lower().replace("_", "-") not in have]


def install_libs(blender: Blender, extra: list[str] | None = None) -> str:
    """Installs the pinned libraries for Blender's Python into the managed folder (Blender itself is untouched)."""
    blender.libs.mkdir(parents=True, exist_ok=True)
    python = blender.python()
    # Pin numpy to Blender's own, so the copy pip puts in the folder matches the one Blender's modules use.
    numpy = subprocess.run([str(python), "-c", "import numpy; print(numpy.__version__)"], capture_output=True, text=True)
    pins = [f"numpy=={numpy.stdout.strip()}"] if numpy.returncode == 0 and numpy.stdout.strip() else []
    cmd = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--upgrade",
           "--target", str(blender.libs), "-r", str(REQUIREMENTS), *pins, *(extra or [])]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        ensure = subprocess.run([str(python), "-m", "ensurepip", "--user"], capture_output=True, text=True)
        out = subprocess.run(cmd, capture_output=True, text=True) if ensure.returncode == 0 else out
    if out.returncode != 0:
        raise SlopolyError("blender_libs_failed", f"pip could not install the build libraries for Blender {blender.version_text}",
                           "see details; the libraries need wheels for Blender's Python version",
                           details=(out.stderr or out.stdout)[-3000:])
    return blender.libs.as_posix()


def require_ready() -> Blender:
    blender = find()
    if missing := missing_libs(blender):
        raise SlopolyError("missing_blender_libs", f"build libraries missing for Blender {blender.version_text}: "
                           f"{', '.join(missing)}", "run slopoly doctor --fetch")
    return blender
