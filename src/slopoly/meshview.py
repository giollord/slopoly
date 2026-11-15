"""Pure numpy/Pillow mesh rendering for reference meshes and build close-ups (no Blender, no GPU).

Program space as everywhere in slopoly: metres, Y up, the object's front towards +Z, its left (``_L``) on +X.
A camera is a direction (``yaw`` around Y from the front, towards +X; ``pitch`` up from the horizon) and a framing.
Its image axes match the build scorer's projections: front looks from +Z (right = +X), side from +X (right = -Z,
front on the left), top from +Y (right = +X, front at the bottom), back from -Z (right = -X).

Triangles are drawn far to near (painter's order) with Pillow, flat-lit from the upper front-left; that is plenty for
silhouettes, colour regions and close-ups of a rough reference mesh.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from .blender.slopoly_model import glb

NAMED = {  # yaw, pitch of the named directions
    "front": (0.0, 0.0), "side": (90.0, 0.0), "left": (90.0, 0.0), "right": (-90.0, 0.0), "back": (180.0, 0.0),
    "top": (0.0, 90.0), "bottom": (0.0, -90.0),
    "hero": (45.0, 20.0),  # the hero image: three-quarter from the front-left, slightly from above
}
LIGHT = (-0.4, 0.8, 0.45)  # towards the light, in the camera's (right, up, back): from the upper left, so every
# view is lit alike whichever way the object turns
GREY = np.array([0.7, 0.7, 0.7])


@dataclass
class Mesh:
    verts: np.ndarray  # (n, 3) float, program space
    tris: np.ndarray  # (m, 3) int
    colors: np.ndarray | None = None  # (n, 3) float 0..1 per vertex
    face_colors: np.ndarray | None = None  # (m, 3) float 0..1 per face (builds: palette texture samples)
    face_parts: np.ndarray | None = None  # (m,) node name per face (builds: the part)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return self.verts.min(0), self.verts.max(0)

    def transformed(self, matrix: np.ndarray) -> Mesh:
        verts = self.verts @ matrix[:3, :3].T + matrix[:3, 3]
        tris = self.tris if np.linalg.det(matrix[:3, :3]) > 0 else self.tris[:, ::-1]  # keep winding when mirrored
        return Mesh(verts, tris.copy(), self.colors, self.face_colors, self.face_parts)

    def face_rgb(self) -> np.ndarray:
        if self.face_colors is not None:
            return self.face_colors
        if self.colors is not None:
            return self.colors[self.tris].mean(1)
        return np.tile(GREY, (len(self.tris), 1))


def to_srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.clip(linear, 0, 1)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


def to_linear(srgb: np.ndarray) -> np.ndarray:
    srgb = np.clip(srgb, 0, 1)
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


# --- GLB ---

COMPONENTS = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
SIZES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _accessor(gltf: dict, binary: bytes, index: int) -> np.ndarray:
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    dtype, n = np.dtype(COMPONENTS[acc["componentType"]]), SIZES[acc["type"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or dtype.itemsize * n
    raw = np.frombuffer(binary, dtype=np.uint8, count=stride * (acc["count"] - 1) + dtype.itemsize * n, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, (acc["count"], dtype.itemsize * n), (stride, 1))
    out = np.ascontiguousarray(rows).view(dtype).reshape(acc["count"], n).astype(np.float64)
    if acc.get("normalized"):
        out /= np.iinfo(dtype).max
    return out


def _node_matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    t = np.eye(4)
    t[:3, 3] = node.get("translation", (0, 0, 0))
    x, y, z, w = node.get("rotation", (0, 0, 0, 1))
    r = np.eye(4)
    r[:3, :3] = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                 [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                 [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    s = np.diag([*node.get("scale", (1, 1, 1)), 1.0])
    return t @ r @ s


def _texture(gltf: dict, binary: bytes, material: int | None) -> np.ndarray | None:
    """The base colour texture of a material as an (h, w, 3) float array, or None."""
    if material is None:
        return None
    pbr = gltf["materials"][material].get("pbrMetallicRoughness", {})
    if "baseColorTexture" not in pbr:
        return None
    from io import BytesIO
    image = gltf["images"][gltf["textures"][pbr["baseColorTexture"]["index"]]["source"]]
    view = gltf["bufferViews"][image["bufferView"]]
    data = binary[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
    return np.asarray(Image.open(BytesIO(data)).convert("RGB"), dtype=np.float64) / 255


def load_glb(data: bytes) -> Mesh:
    """Every mesh primitive of the GLB's default scene, in world space, with vertex colours (COLOR_0, as sRGB) and, where a
    material has a base colour texture, per-face colours sampled from it (times the vertex colour)."""
    gltf, binary = glb.read(data)
    verts, tris, colors, faces, names, count = [], [], [], [], [], 0

    def visit(index: int, parent: np.ndarray) -> None:
        nonlocal count
        node = gltf["nodes"][index]
        matrix = parent @ _node_matrix(node)
        for prim in gltf["meshes"][node["mesh"]]["primitives"] if "mesh" in node else []:
            if prim.get("mode", 4) != 4:
                continue
            pos = _accessor(gltf, binary, prim["attributes"]["POSITION"])
            idx = (_accessor(gltf, binary, prim["indices"]).astype(int).reshape(-1, 3) if "indices" in prim
                   else np.arange(len(pos)).reshape(-1, 3))
            col = (to_srgb(_accessor(gltf, binary, prim["attributes"]["COLOR_0"])[:, :3])  # glTF stores it linear
                   if "COLOR_0" in prim["attributes"] else np.ones((len(pos), 3)))
            texture = _texture(gltf, binary, prim.get("material"))
            if texture is not None and "TEXCOORD_0" in prim["attributes"]:
                uv = _accessor(gltf, binary, prim["attributes"]["TEXCOORD_0"])[idx].mean(1)
                h, w = texture.shape[:2]
                px = np.clip((uv[:, 0] % 1) * w, 0, w - 1).astype(int)
                py = np.clip((uv[:, 1] % 1) * h, 0, h - 1).astype(int)
                faces.append(texture[py, px] * col[idx].mean(1))
            else:
                faces.append(col[idx].mean(1))
            world = pos @ matrix[:3, :3].T + matrix[:3, 3]
            flip = np.linalg.det(matrix[:3, :3]) < 0
            verts.append(world)
            tris.append((idx[:, ::-1] if flip else idx) + count)
            names.append(np.full(len(idx), node.get("name", ""), dtype=object))
            colors.append(col)
            count += len(pos)
        for child in node.get("children", []):
            visit(child, matrix)

    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visit(root, np.eye(4))
    if not verts:
        raise ValueError("the GLB has no triangles")
    return Mesh(np.concatenate(verts), np.concatenate(tris), np.concatenate(colors), np.concatenate(faces),
                np.concatenate(names))


def write_glb(mesh: Mesh) -> bytes:
    """A GLB of the mesh with its vertex colours (no materials): what the review window's reference pane loads. With
    ``face_parts``, each part is its own node, named after it."""
    verts = mesh.verts.astype(np.float32)
    colors = to_linear(mesh.colors if mesh.colors is not None else np.tile(GREY, (len(verts), 1))).astype(np.float32)
    parts = np.asarray(mesh.face_parts if mesh.face_parts is not None else ["reference"] * len(mesh.tris), dtype=object)
    names = list(dict.fromkeys(parts.tolist()))
    blobs = [verts.tobytes(), colors.tobytes()] + [mesh.tris[parts == n].astype(np.uint32).tobytes() for n in names]
    offsets = np.cumsum([0] + [len(b) for b in blobs])
    gltf = {
        "asset": {"version": "2.0", "generator": "slopoly"},
        "scene": 0, "scenes": [{"nodes": list(range(len(names)))}],
        "nodes": [{"mesh": i, "name": str(n)} for i, n in enumerate(names)],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "COLOR_0": 1}, "indices": 2 + i}]}
                   for i in range(len(names))],
        "buffers": [{"byteLength": int(offsets[-1])}],
        "bufferViews": [{"buffer": 0, "byteOffset": int(offsets[i]), "byteLength": len(blobs[i]),
                         "target": 34962 if i < 2 else 34963} for i in range(len(blobs))],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(verts), "type": "VEC3",
             "min": verts.min(0).tolist(), "max": verts.max(0).tolist()},
            {"bufferView": 1, "componentType": 5126, "count": len(verts), "type": "VEC3"},
        ] + [{"bufferView": 2 + i, "componentType": 5125, "count": len(blobs[2 + i]) // 4, "type": "SCALAR"}
             for i in range(len(names))],
    }
    return glb.write(gltf, b"".join(blobs))


# --- cameras and rendering ---

@dataclass
class Camera:
    """A view direction with a framing: ``scale`` pixels per metre and ``centre`` (the image centre in the camera's
    (right, up) coordinates). ``perspective`` uses a 35 degree field of view from ``distance`` metres."""
    yaw: float = 0.0
    pitch: float = 0.0
    scale: float = 1.0
    centre: tuple[float, float] = (0.0, 0.0)
    size: tuple[int, int] = (768, 768)
    perspective: bool = False
    distance: float = 0.0
    target: tuple[float, float, float] = (0.0, 0.0, 0.0)
    fov: float | None = None  # vertical field of view in degrees (as three.js cameras); None: 35 across the width

    def axes(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(right, up, towards the camera) unit vectors in program space."""
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        back = np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])
        right = np.array([math.cos(y), 0.0, -math.sin(y)])
        return right, np.cross(back, right), back

    def as_dict(self) -> dict:
        return {"yaw": round(self.yaw, 2), "pitch": round(self.pitch, 2), "px_per_m": round(self.scale, 3),
                "centre": [round(c, 4) for c in self.centre], "size": list(self.size),
                "perspective": self.perspective,
                **({"distance": round(self.distance, 3), "target": [round(c, 4) for c in self.target]}
                   if self.perspective else {})}

    def project(self, verts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Pixel coordinates (n, 2) and depth (larger is nearer the camera)."""
        right, up, back = self.axes()
        w, h = self.size
        if self.perspective:
            rel = verts - np.asarray(self.target)
            depth = rel @ back - self.distance  # negative in front of the camera
            focal = ((h / 2) / math.tan(math.radians(self.fov) / 2) if self.fov
                     else (w / 2) / math.tan(math.radians(35) / 2))
            z = np.maximum(-depth, 1e-3)
            u, v = rel @ right * focal / z, rel @ up * focal / z
            return np.stack([u + w / 2, h / 2 - v], 1), depth
        u, v = verts @ right, verts @ up
        return (np.stack([(u - self.centre[0]) * self.scale + w / 2, h / 2 - (v - self.centre[1]) * self.scale], 1),
                verts @ back)

    def fit(self) -> dict:
        """The build scorer's fit (pixel = projection * scale + offset) for orthographic named views."""
        w, h = self.size
        return {"scale": self.scale, "offset": [w / 2 - self.centre[0] * self.scale, h / 2 + self.centre[1] * self.scale],
                "image": [w, h]}


def look_at(position, target, fov: float, size: tuple[int, int]) -> Camera:
    """A perspective camera at ``position`` looking at ``target`` with a vertical ``fov`` (a three.js orbit camera)."""
    offset = np.asarray(position, float) - np.asarray(target, float)
    distance = float(np.linalg.norm(offset))
    yaw = math.degrees(math.atan2(offset[0], offset[2]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, offset[1] / max(distance, 1e-9)))))
    return Camera(yaw, pitch, size=size, perspective=True, distance=distance, fov=fov,
                  target=tuple(float(c) for c in target))


def direction(name_or_angles: str | tuple[float, float]) -> tuple[float, float]:
    if isinstance(name_or_angles, tuple):
        return name_or_angles
    if name_or_angles in NAMED:
        return NAMED[name_or_angles]
    yaw, pitch = (float(x) for x in name_or_angles.split(","))
    return yaw, pitch


def framed(verts: np.ndarray, yaw: float, pitch: float, size: tuple[int, int], margin: float = 0.05,
           scale: float | None = None) -> Camera:
    """An orthographic camera that frames ``verts`` with ``margin`` (a share of the image) on every side, or at a
    given ``scale`` (pixels per metre) centred on them."""
    camera = Camera(yaw, pitch, size=size)
    right, up, _ = camera.axes()
    u, v = verts @ right, verts @ up
    extent = np.array([u.max() - u.min(), v.max() - v.min()])
    camera.centre = (float(u.max() + u.min()) / 2, float(v.max() + v.min()) / 2)
    if scale is None:
        room = np.array(size, dtype=float) * (1 - 2 * margin)
        scale = float(np.min(room / np.maximum(extent, 1e-9)))
    camera.scale = scale
    return camera


MAX_FRAGMENT_PX = 16  # triangles longer than this on screen are split, so far-to-near sorting holds locally
MAX_FRAGMENTS = 400_000


def fragments(mesh: Mesh, camera: Camera) -> tuple[np.ndarray, np.ndarray]:
    """The mesh's triangles as world-space corners, those longer than MAX_FRAGMENT_PX on screen split into four
    (edge midpoints) until short enough, with each fragment's original face index. Large low-poly faces drawn whole
    sort wrongly against small ones in front of them (spokes showing through a cart's bed)."""
    corners = mesh.verts[mesh.tris]
    parent = np.arange(len(mesh.tris))
    while True:
        pts = camera.project(corners.reshape(-1, 3))[0].reshape(-1, 3, 2)
        longest = np.linalg.norm(pts - np.roll(pts, 1, axis=1), axis=2).max(1)
        big = longest > MAX_FRAGMENT_PX
        if not big.any() or len(corners) + 3 * big.sum() > MAX_FRAGMENTS:
            return corners, parent
        a, b, c = corners[big, 0], corners[big, 1], corners[big, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        split = np.concatenate([np.stack(t, 1) for t in ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))])
        corners = np.concatenate([corners[~big], split])
        parent = np.concatenate([parent[~big], np.tile(parent[big], 4)])


def render(mesh: Mesh, camera: Camera, ids: bool = False, background: tuple[int, int, int] = (255, 255, 255)
           ) -> tuple[np.ndarray, np.ndarray]:
    """(RGB image (h, w, 3) uint8, coverage mask (h, w) bool). With ``ids`` the image holds face index + 1 as a
    24-bit number in RGB (0 = background) and no lighting."""
    w, h = camera.size
    corners, parent = fragments(mesh, camera)  # (n, 3, 3) world corners, and the face each fragment comes from
    pts, depth = camera.project(corners.reshape(-1, 3))
    tri_pts, depth = pts.reshape(-1, 3, 2), depth.reshape(-1, 3)
    tri_depth = depth.mean(1)
    keep = np.ones(len(corners), dtype=bool)
    if camera.perspective:
        keep &= (depth < 0).all(1)
    lo, hi = tri_pts.min(1), tri_pts.max(1)
    keep &= (hi[:, 0] >= 0) & (lo[:, 0] < w) & (hi[:, 1] >= 0) & (lo[:, 1] < h)
    order = np.nonzero(keep)[0]
    order = order[np.argsort(tri_depth[order], kind="stable")]  # far first
    if ids:
        n = parent[order] + 1
        fills = np.stack([(n >> 16) & 255, (n >> 8) & 255, n & 255], 1)
    else:
        a, b, c = (corners[order, k] for k in range(3))
        normal = np.cross(b - a, c - a)
        normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
        right, up, back = camera.axes()
        normal *= np.sign(normal @ back)[:, None] + (normal @ back == 0)[:, None]  # light the side we see
        light = LIGHT[0] * right + LIGHT[1] * up + LIGHT[2] * back
        shade = 0.6 + 0.4 * np.clip(normal @ (light / np.linalg.norm(light)), 0, 1)
        fills = np.clip(mesh.face_rgb()[parent[order]] * shade[:, None] * 255, 0, 255)
    image = Image.new("RGB", (w, h), (0, 0, 0) if ids else background)
    cover = Image.new("L", (w, h), 0)
    draw, mask = ImageDraw.Draw(image), ImageDraw.Draw(cover)
    for poly, fill in zip(tri_pts[order].tolist(), fills.astype(int).tolist()):
        flat = [tuple(p) for p in poly]
        draw.polygon(flat, fill=tuple(fill))
        mask.polygon(flat, fill=255)
    return np.asarray(image), np.asarray(cover) > 0


def face_ids(image: np.ndarray) -> np.ndarray:
    """Face index per pixel from an ``ids`` render (-1 = background)."""
    rgb = image.astype(np.int64)
    return (rgb[..., 0] << 16 | rgb[..., 1] << 8 | rgb[..., 2]) - 1


def mirror_x(mesh: Mesh) -> Mesh:
    return mesh.transformed(np.diag([-1.0, 1.0, 1.0, 1.0]))


def rotation_y(degrees: float) -> np.ndarray:
    a = math.radians(degrees)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return m


__all__ = ["Mesh", "Camera", "NAMED", "load_glb", "write_glb", "framed", "render", "face_ids", "direction", "look_at",
           "mirror_x", "rotation_y"]
