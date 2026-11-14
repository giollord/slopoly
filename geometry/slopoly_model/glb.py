"""Minimal GLB container access: swap the embedded palette image without touching mesh data (palette-render)."""

from __future__ import annotations

import json
import struct

JSON_CHUNK, BIN_CHUNK = 0x4E4F534A, 0x004E4942


def read(data: bytes) -> tuple[dict, bytes]:
    magic, version, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError("not a glTF 2.0 binary")
    offset, gltf, binary = 12, None, b""
    while offset < len(data):
        length, kind = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8:offset + 8 + length]
        if kind == JSON_CHUNK:
            gltf = json.loads(chunk)
        elif kind == BIN_CHUNK:
            binary = chunk
        offset += 8 + length
    if gltf is None:
        raise ValueError("GLB has no JSON chunk")
    return gltf, binary


def _pad(data: bytes, filler: bytes) -> bytes:
    return data + filler * (-len(data) % 4)


def write(gltf: dict, binary: bytes) -> bytes:
    text = _pad(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    binary = _pad(binary, b"\0")
    chunks = struct.pack("<II", len(text), JSON_CHUNK) + text + struct.pack("<II", len(binary), BIN_CHUNK) + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def replace_image(data: bytes, png: bytes, index: int = 0) -> bytes:
    """The GLB with image ``index`` replaced by ``png``; all other buffer views keep their bytes.
    A GLB without images (e.g. a build with no parts) has nothing to recolour and is returned as is."""
    gltf, binary = read(data)
    if index >= len(gltf.get("images", [])):
        return data
    target = gltf["images"][index]["bufferView"]
    out = bytearray()
    for i, view in enumerate(gltf["bufferViews"]):
        start = view.get("byteOffset", 0)
        chunk = png if i == target else binary[start:start + view["byteLength"]]
        out += b"\0" * (-len(out) % 4)
        view["byteOffset"], view["byteLength"] = len(out), len(chunk)
        out += chunk
    gltf["buffers"][0]["byteLength"] = len(out)
    return write(gltf, bytes(out))


def image(data: bytes, index: int = 0) -> bytes:
    gltf, binary = read(data)
    view = gltf["bufferViews"][gltf["images"][index]["bufferView"]]
    start = view.get("byteOffset", 0)
    return binary[start:start + view["byteLength"]]
