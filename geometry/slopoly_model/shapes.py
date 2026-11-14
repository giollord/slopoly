"""Shapes: low-poly meshes built from primitives and a few bmesh operations.

Coordinates are metres, Y up. A shape is a closed mesh around its own origin; ``part()`` places it. Every face carries a
tag (a palette role, see ``palette``); operations can tag the faces they create, and ``paint`` re-tags a selection.
Operations return new shapes and never change their input, so one shape can be reused for several parts.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector

Vec3 = Sequence[float]
FaceSelector = str | Callable[[tuple[float, float, float], tuple[float, float, float]], bool] | None

TAG_LAYER = "tag"
AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
DIRECTIONS = {
    "+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1),
    "right": (1, 0, 0), "left": (-1, 0, 0), "top": (0, 1, 0), "bottom": (0, -1, 0), "front": (0, 0, 1), "back": (0, 0, -1),
}
# bmesh primitives are built along local Z; this turns Z onto the requested axis.
_FROM_Z = {"x": Matrix.Rotation(math.pi / 2, 4, "Y"), "y": Matrix.Rotation(-math.pi / 2, 4, "X"), "z": Matrix.Identity(4)}


class ShapeError(ValueError):
    """A shape or operation got arguments it can't use."""


def axis_vector(axis: str | Vec3) -> Vector:
    if isinstance(axis, str):
        sign = -1.0 if axis.startswith("-") else 1.0
        name = axis.lstrip("+-")
        if name not in AXES:
            raise ShapeError(f"unknown axis {axis!r}; use x, y, z, -x, ...")
        return Vector(AXES[name]) * sign
    vector = Vector(axis)
    if vector.length == 0:
        raise ShapeError("axis vector is zero")
    return vector.normalized()


class Shape:
    """A closed mesh (bmesh) with a tag per face."""

    def __init__(self, bm: bmesh.types.BMesh, profile: list[tuple[float, float]] | None = None):
        self.bm = bm
        self.tags = bm.faces.layers.string.get(TAG_LAYER) or bm.faces.layers.string.new(TAG_LAYER)
        self.profile = profile  # set on flat profiles (ngon) for sweep
        self.booleans = 0  # boolean operations applied; they degrade topology and are reported

    def copy(self) -> Shape:
        shape = Shape(self.bm.copy(), self.profile)
        shape.booleans = self.booleans
        return shape

    # --- transforms (return new shapes) ---
    def transformed(self, matrix: Matrix) -> Shape:
        shape = self.copy()
        bmesh.ops.transform(shape.bm, matrix=matrix, verts=shape.bm.verts)
        if matrix.determinant() < 0:
            bmesh.ops.reverse_faces(shape.bm, faces=shape.bm.faces)
        return shape

    def move(self, x: float = 0, y: float = 0, z: float = 0) -> Shape:
        return self.transformed(Matrix.Translation((x, y, z)))

    def rotate(self, x: float = 0, y: float = 0, z: float = 0) -> Shape:
        """Rotates by Euler angles in degrees (applied X, then Y, then Z) around the origin."""
        return self.transformed(rotation_matrix((x, y, z)))

    def scale(self, x: float = 1, y: float | None = None, z: float | None = None) -> Shape:
        y = x if y is None else y
        z = x if z is None else z
        return self.transformed(Matrix.Diagonal((x, y, z, 1)))

    # --- queries ---
    def vertices(self) -> np.ndarray:
        return np.array([v.co[:] for v in self.bm.verts], dtype=float).reshape(-1, 3)

    def faces(self) -> list[list[int]]:
        self.bm.verts.index_update()
        return [[v.index for v in f.verts] for f in self.bm.faces]

    def face_tags(self) -> list[str]:
        return [f[self.tags].decode() for f in self.bm.faces]

    def triangles(self) -> np.ndarray:
        """Vertex indices of a fan triangulation of every face (faces are convex or near-convex)."""
        self.bm.verts.index_update()
        tris = [(f.verts[0].index, f.verts[i].index, f.verts[i + 1].index)
                for f in self.bm.faces for i in range(1, len(f.verts) - 1)]
        return np.array(tris, dtype=np.int64).reshape(-1, 3)

    def triangle_count(self) -> int:
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        verts = self.vertices()
        return verts.min(0), verts.max(0)

    def __repr__(self) -> str:
        return f"Shape({len(self.bm.verts)} verts, {len(self.bm.faces)} faces)"


def rotation_matrix(rot: Vec3 | None) -> Matrix:
    if not rot:
        return Matrix.Identity(4)
    return Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()


def _finish(bm: bmesh.types.BMesh, tag: str | None = None, profile=None) -> Shape:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    shape = Shape(bm, profile)
    if tag:
        for f in bm.faces:
            f[shape.tags] = tag.encode()
    return shape


def _along(bm: bmesh.types.BMesh, axis: str) -> None:
    if axis not in _FROM_Z:
        raise ShapeError(f"axis must be x, y or z, not {axis!r}")
    bmesh.ops.transform(bm, matrix=_FROM_Z[axis], verts=bm.verts)


def _positive(name: str, value: float) -> None:
    if not value > 0:
        raise ShapeError(f"{name} must be positive, got {value}")


def _segments(n: int) -> None:
    if int(n) != n or n < 3:
        raise ShapeError(f"segment count must be a whole number >= 3, got {n}")


# --- primitives ---

def box(width: float, height: float, depth: float, tag: str | None = None) -> Shape:
    """Box centred on the origin: width along X, height along Y, depth along Z. 6 quads."""
    for name, value in (("width", width), ("height", height), ("depth", depth)):
        _positive(name, value)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(width, height, depth), verts=bm.verts)
    return _finish(bm, tag)


def prism(n: int, r: float, length: float, axis: str = "y", tag: str | None = None) -> Shape:
    """n-sided prism (low-poly cylinder) centred on the origin along ``axis``: n side quads and two n-gon caps."""
    _segments(n)
    _positive("r", r)
    _positive("length", length)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=int(n), radius1=r, radius2=r, depth=length)
    _along(bm, axis)
    return _finish(bm, tag)


def cone(n: int, r: float, length: float, axis: str = "y", r2: float = 0.0, tag: str | None = None) -> Shape:
    """n-sided cone centred on the origin along ``axis``, base radius ``r`` at the negative end, ``r2`` at the
    positive end (0 = pointed: n triangles)."""
    _segments(n)
    _positive("r", r)
    _positive("length", length)
    if r2 < 0:
        raise ShapeError("r2 must not be negative")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=int(n), radius1=r, radius2=r2, depth=length)
    _along(bm, axis)
    return _finish(bm, tag)


def ngon(n: int, r: float, axis: str = "y", tag: str | None = None) -> Shape:
    """Flat regular n-gon facing ``axis``: a profile for ``sweep`` or a base for ``extrude``."""
    _segments(n)
    _positive("r", r)
    points = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(int(n))]
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0.0)) for x, y in points]
    bm.faces.new(verts)
    _along(bm, axis)
    shape = Shape(bm, points)
    if tag:
        for f in bm.faces:
            f[shape.tags] = tag.encode()
    return shape


def sweep(path: Sequence[Vec3], profile: Shape | Sequence[tuple[float, float]], closed: bool = False,
          tag: str | None = None) -> Shape:
    """Sweeps a 2D profile (an ``ngon`` or a list of (u, v) points) along a polyline. Corners are mitred so the
    thickness stays constant. Open paths get capped ends; ``closed`` joins the last point to the first (a ring)."""
    points = profile.profile if isinstance(profile, Shape) else [tuple(p) for p in profile]
    if not points or len(points) < 3:
        raise ShapeError("sweep needs a profile with at least 3 points (use ngon)")
    path_v = [Vector(p) for p in path]
    if len(path_v) < 2 or any((b - a).length == 0 for a, b in zip(path_v, path_v[1:])):
        raise ShapeError("sweep needs at least 2 distinct consecutive path points")
    count = len(path_v)

    def direction(i: int) -> Vector:
        return (path_v[(i + 1) % count] - path_v[i]).normalized()

    segments = [direction(i) for i in range(count if closed else count - 1)]
    normal = None
    bm = bmesh.new()
    rings = []
    for i, point in enumerate(path_v):
        incoming = segments[i - 1] if (closed or i > 0) else None
        outgoing = segments[i] if (closed or i < count - 1) else None
        tangent = ((incoming or outgoing) + (outgoing or incoming)).normalized()
        if normal is None:
            up = Vector((0, 1, 0)) if abs(tangent.y) < 0.9 else Vector((1, 0, 0))
            normal = (up - tangent * up.dot(tangent)).normalized()
        else:  # parallel transport: keep the frame from twisting
            normal = (normal - tangent * normal.dot(tangent)).normalized()
        binormal = tangent.cross(normal)
        bend, stretch = None, 1.0
        if incoming and outgoing and (outgoing - incoming).length > 1e-9:
            bend = (outgoing - incoming).normalized()
            stretch = 1.0 / max(incoming.dot(tangent), 0.2)
        ring = []
        for u, v in points:
            offset = normal * u + binormal * v
            if bend is not None:
                offset += bend * (offset.dot(bend) * (stretch - 1.0))
            ring.append(bm.verts.new(point + offset))
        rings.append(ring)

    n = len(points)
    for a, b in zip(rings, rings[1:] + (rings[:1] if closed else [])):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1])
    return _finish(bm, tag)


# --- face selection and operations ---

def select(shape: Shape, faces: FaceSelector) -> list[bmesh.types.BMFace]:
    """Faces by selector: None/"all", a direction ("top", "+x", "front", ...: faces whose normal points that way),
    a tag name, or a function (centre, normal) -> bool."""
    all_faces = list(shape.bm.faces)
    if faces is None or faces == "all":
        return all_faces
    if callable(faces):
        return [f for f in all_faces if faces(tuple(f.calc_center_median()), tuple(f.normal))]
    if faces in DIRECTIONS:
        direction = Vector(DIRECTIONS[faces])
        return [f for f in all_faces if f.normal.dot(direction) > 0.7]
    tagged = [f for f in all_faces if f[shape.tags].decode() == faces]
    if not tagged:
        raise ShapeError(f"no faces match {faces!r} (directions: {', '.join(DIRECTIONS)}; or a tag in use: "
                         f"{', '.join(sorted(set(shape.face_tags()) - {''})) or 'none'})")
    return tagged


def _selected(shape: Shape, faces: FaceSelector) -> list[bmesh.types.BMFace]:
    found = select(shape, faces)
    if not found:
        raise ShapeError(f"no faces match {faces!r}")
    return found


def extrude(shape: Shape, faces: FaceSelector, distance: float, tag: str | None = None) -> Shape:
    """Pushes the selected faces out along their average normal by ``distance`` (negative pushes in), adding side
    quads. ``tag`` tags the moved faces and the new sides."""
    result = shape.copy()
    selected = _selected(result, faces)
    normal = sum((f.normal for f in selected), Vector()).normalized()
    before = set(result.bm.faces)
    created = bmesh.ops.extrude_face_region(result.bm, geom=selected)
    bmesh.ops.delete(result.bm, geom=selected, context="FACES")
    moved = [g for g in created["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(result.bm, verts=moved, vec=normal * distance)
    if tag:
        for f in set(result.bm.faces) - before:
            f[result.tags] = tag.encode()
    bmesh.ops.recalc_face_normals(result.bm, faces=result.bm.faces)
    return result


def inset(shape: Shape, faces: FaceSelector, thickness: float, depth: float = 0.0, tag: str | None = None) -> Shape:
    """Insets the selected faces as one region by ``thickness`` (a rim of quads), optionally raising them by
    ``depth``. ``tag`` tags the inner faces."""
    result = shape.copy()
    selected = _selected(result, faces)
    bmesh.ops.inset_region(result.bm, faces=selected, thickness=thickness, depth=depth, use_even_offset=True)
    if tag:
        for f in selected:
            f[result.tags] = tag.encode()
    return result


def bevel(shape: Shape, width: float, segments: int = 1, faces: FaceSelector = None) -> Shape:
    """Bevels the edges of the selected faces (all edges when no selection) by ``width`` with ``segments`` rows."""
    result = shape.copy()
    edges = list({e for f in select(result, faces) for e in f.edges}) if faces not in (None, "all") else list(result.bm.edges)
    bmesh.ops.bevel(result.bm, geom=edges, offset=width, offset_type="OFFSET", segments=int(segments), profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    bmesh.ops.recalc_face_normals(result.bm, faces=result.bm.faces)
    return result


def jitter(shape: Shape, amount: float, seed: int = 0, faces: FaceSelector = None) -> Shape:
    """Moves each vertex of the selected faces (all when no selection) by a seeded random offset of up to ``amount``
    per axis: dents, sag and uneven chips. Shared vertices move once, so the shape stays closed."""
    _positive("amount", amount)
    result = shape.copy()
    result.bm.verts.index_update()
    verts = sorted({v for f in _selected(result, faces) for v in f.verts}, key=lambda v: v.index)
    offsets = np.random.default_rng(seed).uniform(-amount, amount, (len(verts), 3))
    for v, offset in zip(verts, offsets):
        v.co += Vector(offset.tolist())
    result.bm.normal_update()
    return result


def paint(shape: Shape, tag: str, faces: FaceSelector = None) -> Shape:
    """Tags the selected faces (all when no selection) with a palette role."""
    result = shape.copy()
    for f in select(result, faces):
        f[result.tags] = tag.encode()
    return result


def join(*shapes: Shape) -> Shape:
    """One shape holding all the given shapes' faces (they may overlap; nothing is merged)."""
    if not shapes:
        raise ShapeError("join needs at least one shape")
    bm = bmesh.new()
    tags = bm.faces.layers.string.new(TAG_LAYER)
    for shape in shapes:
        vert_map = {v: bm.verts.new(v.co) for v in shape.bm.verts}
        for f in shape.bm.faces:
            face = bm.faces.new([vert_map[v] for v in f.verts])
            face[tags] = f[shape.tags]
    result = Shape(bm)
    result.booleans = sum(s.booleans for s in shapes)
    return result


def boolean(a: Shape, b: Shape, op: str = "difference") -> Shape:
    """Boolean of two closed shapes with manifold3d: "union", "difference" (a minus b) or "intersection".
    The result is re-triangulated and coplanar triangles are merged back into polygons; tags are kept. Reported in
    the build because booleans degrade topology; prefer extrude/inset where they can do the job."""
    import manifold3d

    ops = {"union": manifold3d.OpType.Add, "difference": manifold3d.OpType.Subtract,
           "intersection": manifold3d.OpType.Intersect}
    if op not in ops:
        raise ShapeError(f"op must be one of {', '.join(ops)}")
    names = sorted(set(a.face_tags()) | set(b.face_tags()))
    solids = [to_manifold(shape, names) for shape in (a, b)]
    result = manifold3d.Manifold.batch_boolean(solids, ops[op])
    shape = from_manifold(result, names)
    shape.booleans = a.booleans + b.booleans + 1
    return shape


def to_manifold(shape: Shape, tag_names: list[str] | None = None):
    """manifold3d solid of the shape; each triangle's face_id is its tag's index in ``tag_names``."""
    import manifold3d

    tag_names = tag_names or sorted(set(shape.face_tags()))
    index = {name: i for i, name in enumerate(tag_names)}
    shape.bm.verts.index_update()
    tris, ids = [], []
    for f in shape.bm.faces:
        tag = index[f[shape.tags].decode()]
        for i in range(1, len(f.verts) - 1):
            tris.append((f.verts[0].index, f.verts[i].index, f.verts[i + 1].index))
            ids.append(tag)
    mesh = manifold3d.Mesh(vert_properties=np.asarray(shape.vertices(), dtype=np.float32),
                           tri_verts=np.asarray(tris, dtype=np.uint32).reshape(-1, 3),
                           face_id=np.asarray(ids, dtype=np.uint32))
    mesh.merge()
    solid = manifold3d.Manifold(mesh)
    if solid.status() != manifold3d.Error.NoError:
        raise ShapeError(f"shape is not a closed solid ({solid.status().name})")
    return solid


def from_manifold(solid, tag_names: list[str]) -> Shape:
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    tris = np.asarray(mesh.tri_verts)
    face_ids = np.asarray(mesh.face_id) if len(np.asarray(mesh.face_id)) else np.zeros(len(tris), dtype=np.uint32)
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in verts]
    tags = bm.faces.layers.string.new(TAG_LAYER)
    for tri, face_id in zip(tris, face_ids):
        face = bm.faces.new([bm_verts[i] for i in tri])
        face.material_index = int(face_id)  # dissolve_limit keeps tag borders via the material delimiter
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges, delimit={"MATERIAL"})
    for face in bm.faces:
        if 0 <= face.material_index < len(tag_names):
            face[tags] = tag_names[face.material_index].encode()
        face.material_index = 0
    return _finish(bm)
