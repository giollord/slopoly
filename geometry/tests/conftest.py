import json
import struct
from pathlib import Path

import pytest

from slopoly_model import assembly

SAMPLES = Path(__file__).parent.parent / "samples"
PALETTE = [
    {"id": "11111111-1111-1111-1111-111111111111", "role": "wood", "kind": "Solid", "slot": 0, "color": "#a0703c"},
    {"id": "22222222-2222-2222-2222-222222222222", "role": "wood dark", "kind": "Solid", "slot": 1, "color": "#6b4423"},
    {"id": "33333333-3333-3333-3333-333333333333", "role": "metal", "kind": "Gradient", "slot": 0,
     "color": "#555555", "color2": "#999999"},
]


@pytest.fixture(autouse=True)
def model():
    return assembly.new_model()


@pytest.fixture
def cart_source() -> str:
    return (SAMPLES / "cart.py").read_text(encoding="utf-8")


def glb_json(path: Path) -> dict:
    """The JSON chunk of a GLB file."""
    data = path.read_bytes()
    length, kind = struct.unpack_from("<I4s", data, 12)
    assert data[:4] == b"glTF" and kind == b"JSON"
    return json.loads(data[20:20 + length])


def glb_accessor(path: Path, gltf: dict, index: int):
    """An accessor's data as a numpy array (float/uint types, tightly packed buffer views)."""
    import numpy as np

    data = path.read_bytes()
    json_length = struct.unpack_from("<I", data, 12)[0]
    binary = data[20 + json_length + 8:]
    accessor = gltf["accessors"][index]
    view = gltf["bufferViews"][accessor["bufferView"]]
    dtype = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[accessor["componentType"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return np.frombuffer(binary, dtype, accessor["count"] * width, start).reshape(-1, width)
