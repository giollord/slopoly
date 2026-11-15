"""Runs inside Blender: ``blender -b --factory-startup --python launcher.py -- <libs> <mode> [args]``.

Modes:
- ``build <dir>``: runs ``slopoly_model.runner`` on ``<dir>/job.json``.
- ``scene <dir>``: runs ``slopoly_model.scene`` on ``<dir>/scene.json``.
- ``pytest [args]``: runs pytest (the Blender test suite).
"""

import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:]
libs, mode, args = argv[0], argv[1], argv[2:]
# slopoly_model first; the managed libraries after Blender's own, so Blender keeps its numpy.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(libs)

if mode == "build":
    from slopoly_model import runner

    status = runner.main(args[0])
elif mode == "scene":
    from slopoly_model import scene

    status = scene.main(args[0])
elif mode == "pytest":
    import pytest

    status = pytest.main(args)
else:
    print(f"unknown mode {mode}", file=sys.stderr)
    status = 1
sys.stdout.flush()
os._exit(int(status))
