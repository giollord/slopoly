"""Shapes: low-poly meshes built from primitives, Blender modifiers and bmesh operations.

Coordinates are metres, Y up. A shape is a closed mesh around its own origin; ``part()`` places it. Every face carries a
tag (a palette role, see ``palette``) in an integer face attribute, which Blender's modifiers and bmesh operations
copy onto the faces they create. Operations return new shapes and never change their input, so one shape can be
reused for several parts.

Modelling is Blender's: ``shape.modify(type, **settings)`` adds a modifier (settings are the Blender modifier's own
properties), vertex groups limit modifiers and transforms to part of a shape, ``curve`` builds Blender curves, and
programs may run ``bmesh.ops`` on ``shape.bm`` directly. The library adds no modelling operations of its own beyond
thin conveniences (``extrude``, ``inset``, ``bevel``, ``jitter``) over ``bmesh.ops``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

Vec3 = Sequence[float]
FaceSelector = str | Callable[[tuple[float, float, float], tuple[float, float, float]], bool] | None

TAG_LAYER = "slopoly_tag"
EDGE_LAYER = "slopoly_edge"  # shading override per edge: 0 = pack rule, 1 = hard, 2 = smooth
HARD, SMOOTH = 1, 2
AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
DIRECTIONS = {
    "+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1),
    "right": (1, 0, 0), "left": (-1, 0, 0), "top": (0, 1, 0), "bottom": (0, -1, 0), "front": (0, 0, 1), "back": (0, 0, -1),
}
# bmesh primitives are built along local Z; this turns Z onto the requested axis.
_FROM_Z = {"x": Matrix.Rotation(math.pi / 2, 4, "Y"), "y": Matrix.Rotation(-math.pi / 2, 4, "X"), "z": Matrix.Identity(4)}

# Modifiers suited to static low-poly assets. Others (simulation, rigging, Remesh, which drops face attributes) are
# refused. Settings are the modifier's Blender properties; axes are program axes (Y up).
MODIFIERS = ("ARRAY", "BEVEL", "BOOLEAN", "CAST", "CURVE", "DECIMATE", "DISPLACE", "EDGE_SPLIT", "MIRROR", "SCREW",
             "SHRINKWRAP", "SIMPLE_DEFORM", "SMOOTH", "SOLIDIFY", "SUBSURF", "TRIANGULATE", "WAVE", "WELD", "WIREFRAME")

# Tag names <-> attribute values; 0 is "no tag". Global to the process: values are only ever compared within one build.
_TAG_NAMES: list[str] = [""]


def tag_id(name: str | None) -> int:
    if not name:
        return 0
    if name not in _TAG_NAMES:
        _TAG_NAMES.append(name)
    return _TAG_NAMES.index(name)


def tag_name(value: int) -> str:
    return _TAG_NAMES[value] if 0 <= value < len(_TAG_NAMES) else ""


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


# --- values for modifier settings that Blender needs as datablocks ---

@dataclass(frozen=True)
class Empty:
    """An empty object for modifier settings such as an Array's ``offset_object`` or a deform ``origin``."""
    at: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rot: tuple[float, float, float] | None = None
    scale: tuple[float, float, float] | None = None


def empty(at: Vec3 = (0, 0, 0), rot: Vec3 | None = None, scale: Vec3 | None = None) -> Empty:
    """An empty at ``at`` with Euler rotation ``rot`` (degrees) and ``scale``, for modifier settings."""
    return Empty(tuple(at), tuple(rot) if rot else None, tuple(scale) if scale else None)


@dataclass(frozen=True)
class Path:
    """Control points of a Blender curve: smooth (auto Bezier handles, passing through the points) or straight."""
    points: tuple[tuple[float, float, float], ...]
    smooth: bool = True
    closed: bool = False


def path(points: Sequence[Vec3], smooth: bool = True, closed: bool = False) -> Path:
    """A path through ``points`` for ``curve`` or a CURVE modifier's ``object``."""
    pts = tuple(tuple(float(c) for c in p) for p in points)
    if len(pts) < 2 or any(len(p) != 3 for p in pts):
        raise ShapeError("a path needs at least 2 points of (x, y, z)")
    return Path(pts, smooth, closed)


@dataclass(frozen=True)
class Texture:
    """A Blender texture for DISPLACE/WAVE ``texture``: ``kind`` is its type (CLOUDS, VORONOI, MUSGRAVE...)."""
    kind: str
    settings: tuple = ()


def texture(kind: str = "CLOUDS", **settings) -> Texture:
    """A procedural texture (Blender texture type ``kind`` with its properties, e.g. noise_scale=0.3)."""
    return Texture(kind.upper(), tuple(sorted(settings.items())))


@dataclass(frozen=True)
class Ramp:
    """Weights along an axis: ``start`` at ``lo``, ``end`` at ``hi`` (default: the selection's extent)."""
    axis: str
    start: float = 0.0
    end: float = 1.0
    lo: float | None = None
    hi: float | None = None


def ramp(axis: str = "y", start: float = 0.0, end: float = 1.0, lo: float | None = None,
         hi: float | None = None) -> Ramp:
    """Vertex-group weights that go from ``start`` to ``end`` along ``axis`` (between ``lo`` and ``hi``, by default
    the grouped vertices' extent): a falloff for bending, tapering or moving one end of a shape."""
    axis_vector(axis)
    return Ramp(axis, start, end, lo, hi)


@dataclass
class _Modifier:
    type: str
    group: str | None
    settings: dict = field(default_factory=dict)


class Shape:
    """A mesh (bmesh) with a tag per face, named vertex groups and a stack of pending Blender modifiers.

    The stack is applied when the mesh is needed (``shape.bm``, a part, an operation), so programs stay
    non-destructive: change a setting and rebuild."""

    def __init__(self, bm: bmesh.types.BMesh, profile: list[tuple[float, float]] | None = None):
        self._bm = bm
        self.tags = bm.faces.layers.int.get(TAG_LAYER) or bm.faces.layers.int.new(TAG_LAYER)
        self.profile = profile  # set on flat profiles (ngon) for curve
        self.booleans = 0  # boolean operations applied; they degrade topology and are reported
        self.groups: list[str] = []  # vertex group names, by deform-layer index
        self.stack: list[_Modifier] = []
        self.fill_tag = 0  # tag for faces a modifier creates without a source face (SCREW of an outline)

    @property
    def bm(self) -> bmesh.types.BMesh:
        if self.stack:
            self._apply()
        return self._bm

    def copy(self) -> Shape:
        shape = Shape(self._bm.copy(), self.profile)
        shape.booleans, shape.groups, shape.fill_tag = self.booleans, list(self.groups), self.fill_tag
        shape.stack = [_Modifier(m.type, m.group, dict(m.settings)) for m in self.stack]
        return shape

    # --- modifiers ---
    def modify(self, type: str, group: str | None = None, **settings) -> Shape:
        """Adds a Blender modifier (``type`` as in Blender: "ARRAY", "SOLIDIFY", ...) with its settings. ``group``
        limits it to a vertex group. Settings that need an object take a shape, ``empty()`` or ``path()``."""
        kind = type.upper()
        if kind not in MODIFIERS:
            raise ShapeError(f"modifier {type!r} is not available; use one of {', '.join(MODIFIERS)}")
        if group is not None and group not in self.groups:
            raise ShapeError(f"no vertex group {group!r} (groups: {', '.join(self.groups) or 'none'}; make one with group())")
        result = self.copy()
        result.stack.append(_Modifier(kind, group, dict(settings)))
        if kind == "BOOLEAN":
            other = settings.get("object")
            result.booleans += 1 + (other.booleans if isinstance(other, Shape) else 0)
        return result

    def _apply(self) -> None:
        stack, self.stack = self.stack, []
        made: list = []
        try:
            obj = _object(self._bm, self.groups, made)
            for i, m in enumerate(stack):
                try:
                    mod = obj.modifiers.new(f"m{i}", m.type)
                except TypeError as error:
                    raise ShapeError(f"modifier {m.type}: {error}") from None
                for key, value in m.settings.items():
                    if not hasattr(mod, key):
                        valid = sorted(p.identifier for p in mod.bl_rna.properties
                                       if not p.is_readonly and p.identifier not in ("name", "show_expanded"))
                        raise ShapeError(f"{m.type} has no setting {key!r}; settings: {', '.join(valid)}")
                    try:
                        setattr(mod, key, _datablock(value, made))
                    except (TypeError, ValueError, AttributeError) as error:
                        raise ShapeError(f"{m.type}.{key}: {error}") from None
                if m.group is not None:
                    if not hasattr(mod, "vertex_group"):
                        raise ShapeError(f"{m.type} can't be limited to a vertex group")
                    mod.vertex_group = m.group
            graph = bpy.context.evaluated_depsgraph_get()
            graph.update()
            bm = bmesh.new()
            bm.from_object(obj.evaluated_get(graph), graph)
        finally:
            _remove(made)
        tags = bm.faces.layers.int.get(TAG_LAYER) or bm.faces.layers.int.new(TAG_LAYER)
        if self.fill_tag:
            for f in bm.faces:
                if f[tags] == 0:
                    f[tags] = self.fill_tag
        if bm.faces:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self._bm, self.tags = bm, tags

    # --- transforms (return new shapes) ---
    def transformed(self, matrix: Matrix, group: str | None = None) -> Shape:
        """The shape transformed by ``matrix``; with ``group``, each vertex moves by its weight in that group."""
        shape = self.copy()
        bm = shape.bm
        if group is None:
            bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
            if matrix.determinant() < 0:
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
            return shape
        index = shape._group_index(group)
        layer = bm.verts.layers.deform.verify()
        for v in bm.verts:
            weight = v[layer].get(index, 0.0)
            if weight:
                v.co = v.co.lerp(matrix @ v.co, weight)
        bm.normal_update()
        return shape

    def _group_index(self, group: str) -> int:
        if group not in self.groups:
            raise ShapeError(f"no vertex group {group!r} (groups: {', '.join(self.groups) or 'none'})")
        return self.groups.index(group)

    def move(self, x: float = 0, y: float = 0, z: float = 0, group: str | None = None) -> Shape:
        return self.transformed(Matrix.Translation((x, y, z)), group)

    def rotate(self, x: float = 0, y: float = 0, z: float = 0, group: str | None = None,
               about: Vec3 = (0, 0, 0)) -> Shape:
        """Rotates by Euler angles in degrees (applied X, then Y, then Z) around ``about``."""
        return self.transformed(_about(rotation_matrix((x, y, z)), about), group)

    def scale(self, x: float = 1, y: float | None = None, z: float | None = None, group: str | None = None,
              about: Vec3 = (0, 0, 0)) -> Shape:
        y = x if y is None else y
        z = x if z is None else z
        return self.transformed(_about(Matrix.Diagonal((x, y, z, 1)), about), group)

    # --- queries ---
    def vertices(self) -> np.ndarray:
        return np.array([v.co[:] for v in self.bm.verts], dtype=float).reshape(-1, 3)

    def faces(self) -> list[list[int]]:
        self.bm.verts.index_update()
        return [[v.index for v in f.verts] for f in self.bm.faces]

    def face_tags(self) -> list[str]:
        bm = self.bm
        return [tag_name(f[self.tags]) for f in bm.faces]

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
        return f"Shape({len(self._bm.verts)} verts, {len(self._bm.faces)} faces, {len(self.stack)} modifiers pending)"


def _about(matrix: Matrix, about: Vec3) -> Matrix:
    pivot = Matrix.Translation(Vector(about))
    return pivot @ matrix @ pivot.inverted()


def _object(bm: bmesh.types.BMesh, groups: list[str], made: list):
    mesh = bpy.data.meshes.new("slopoly_tmp")
    bm.to_mesh(mesh)
    obj = bpy.data.objects.new("slopoly_tmp", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for name in groups:
        obj.vertex_groups.new(name=name)
    made.extend([obj, mesh])
    return obj


def _datablock(value, made: list):
    """Blender datablocks for shape-like setting values; other values pass through."""
    if isinstance(value, Shape):
        return _object(value.bm, value.groups, made)
    if isinstance(value, Empty):
        obj = bpy.data.objects.new("slopoly_empty", None)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = value.at
        if value.rot:
            obj.rotation_euler = [math.radians(a) for a in value.rot]
        if value.scale:
            obj.scale = value.scale
        made.append(obj)
        return obj
    if isinstance(value, Path):
        return _curve_object(value, None, 12, made)
    if isinstance(value, Texture):
        tex = bpy.data.textures.new("slopoly_tex", value.kind)
        for key, setting in value.settings:
            setattr(tex, key, setting)
        made.append(tex)
        return tex
    return value


def _remove(made: list) -> None:
    for block in reversed(made):
        collection = {bpy.types.Object: bpy.data.objects, bpy.types.Mesh: bpy.data.meshes,
                      bpy.types.Curve: bpy.data.curves, bpy.types.Texture: bpy.data.textures}
        for kind, blocks in collection.items():
            if isinstance(block, kind):
                try:
                    blocks.remove(block)
                except ReferenceError:  # already removed with a datablock it used
                    pass
                break


def rotation_matrix(rot: Vec3 | None) -> Matrix:
    if not rot:
        return Matrix.Identity(4)
    return Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()


def _finish(bm: bmesh.types.BMesh, tag: str | None = None, profile=None) -> Shape:
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    shape = Shape(bm, profile)
    if tag:
        value = tag_id(tag)
        for f in bm.faces:
            f[shape.tags] = value
        shape.fill_tag = value
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
    """Flat regular n-gon facing ``axis``: a profile for ``curve``, or a base to ``extrude`` or SOLIDIFY."""
    _segments(n)
    _positive("r", r)
    points = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(int(n))]
    bm = bmesh.new()
    bm.faces.new([bm.verts.new((x, y, 0.0)) for x, y in points])
    _along(bm, axis)
    return _finish(bm, tag, points)


def outline(points: Sequence[Sequence[float]], closed: bool = False, tag: str | None = None) -> Shape:
    """Connected edges through ``points`` ((x, y) in the XY plane, or (x, y, z)), with no faces: a profile to turn
    with SCREW (lathe around Y: x is the radius, y the height), or to thicken with SOLIDIFY after filling. Faces
    that modifiers make from it get ``tag``."""
    pts = [tuple(float(c) for c in p) + (0.0,) * (3 - len(p)) for p in points]
    if len(pts) < 2:
        raise ShapeError("an outline needs at least 2 points")
    bm = bmesh.new()
    verts = [bm.verts.new(p) for p in pts]
    for a, b in zip(verts, verts[1:] + (verts[:1] if closed else [])):
        bm.edges.new((a, b))
    return _finish(bm, tag)


def _curve_object(spec: Path, profile: list[tuple[float, float]] | None, resolution: int, made: list):
    data = bpy.data.curves.new("slopoly_curve", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = int(resolution)
    data.twist_mode = "MINIMUM"
    spline = data.splines.new("BEZIER" if spec.smooth else "POLY")
    if spec.smooth:
        spline.bezier_points.add(len(spec.points) - 1)
        for point, co in zip(spline.bezier_points, spec.points):
            point.co = co
            point.handle_left_type = point.handle_right_type = "AUTO"
    else:
        spline.points.add(len(spec.points) - 1)
        for point, co in zip(spline.points, spec.points):
            point.co = (*co, 1.0)
    spline.use_cyclic_u = spec.closed
    made.append(data)
    if profile is not None:
        shape = bpy.data.curves.new("slopoly_profile", "CURVE")
        ring = shape.splines.new("POLY")
        ring.points.add(len(profile) - 1)
        for point, (u, v) in zip(ring.points, profile):
            point.co = (u, v, 0.0, 1.0)
        ring.use_cyclic_u = True
        bevel = bpy.data.objects.new("slopoly_profile", shape)
        bpy.context.scene.collection.objects.link(bevel)
        made.extend([shape, bevel])
        data.bevel_mode = "OBJECT"
        data.bevel_object = bevel
        data.use_fill_caps = False
    obj = bpy.data.objects.new("slopoly_curve", data)
    bpy.context.scene.collection.objects.link(obj)
    made.append(obj)
    return obj


def curve(points: Sequence[Vec3] | Path, profile: Shape | Sequence[tuple[float, float]], resolution: int = 4,
          smooth: bool = True, closed: bool = False, tag: str | None = None) -> Shape:
    """A tube along a Blender curve through ``points`` (or a ``path()``), with cross-section ``profile`` (an ``ngon``
    or a list of (u, v) points). ``resolution`` is the number of segments between two control points; ``smooth``
    False makes straight segments with sharp corners. Open curves get flat n-gon caps; ``closed`` makes a ring."""
    spec = points if isinstance(points, Path) else path(points, smooth, closed)
    section = profile.profile if isinstance(profile, Shape) else [tuple(p) for p in profile]
    if not section or len(section) < 3:
        raise ShapeError("curve needs a profile with at least 3 points (use ngon)")
    if int(resolution) != resolution or resolution < 1:
        raise ShapeError(f"resolution must be a whole number >= 1, got {resolution}")
    made: list = []
    try:
        obj = _curve_object(spec, section, resolution, made)
        graph = bpy.context.evaluated_depsgraph_get()
        graph.update()
        evaluated = obj.evaluated_get(graph)
        bm = bmesh.new()
        bm.from_mesh(evaluated.to_mesh())
        evaluated.to_mesh_clear()
    finally:
        _remove(made)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    if not spec.closed:
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
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
    tagged = [f for f in all_faces if tag_name(f[shape.tags]) == faces]
    if not tagged:
        raise ShapeError(f"no faces match {faces!r} (directions: {', '.join(DIRECTIONS)}; or a tag in use: "
                         f"{', '.join(sorted(set(shape.face_tags()) - {''})) or 'none'})")
    return tagged


def _selected(shape: Shape, faces: FaceSelector) -> list[bmesh.types.BMFace]:
    found = select(shape, faces)
    if not found:
        raise ShapeError(f"no faces match {faces!r}")
    return found


def group(shape: Shape, name: str, faces: FaceSelector = None,
          where: Callable[[float, float, float], bool] | None = None,
          weight: float | Ramp | Callable[[float, float, float], float] = 1.0) -> Shape:
    """Adds (or extends) vertex group ``name``: the vertices of the selected faces (all when no selection) for
    which ``where(x, y, z)`` holds, with ``weight`` (a number, a ``ramp()``, or a function of the position).
    Groups limit modifiers (``modify(..., group=)``) and transforms (``move/rotate/scale(..., group=)``)."""
    result = shape.copy()
    bm = result.bm
    layer = bm.verts.layers.deform.verify()  # before taking vertex references: adding a layer invalidates them
    verts = {v for f in _selected(result, faces) for v in f.verts} if faces not in (None, "all") else set(bm.verts)
    if where is not None:
        verts = {v for v in verts if where(*v.co)}
    if not verts:
        raise ShapeError(f"group {name!r}: no vertices selected")
    if name not in result.groups:
        result.groups.append(name)
    index = result.groups.index(name)
    if isinstance(weight, Ramp):
        axis = "xyz".index(weight.axis.lstrip("+-"))
        coords = [v.co[axis] for v in verts]
        lo = min(coords) if weight.lo is None else weight.lo
        hi = max(coords) if weight.hi is None else weight.hi
        span = (hi - lo) or 1.0

        def weigh(v):
            t = min(max((v.co[axis] - lo) / span, 0.0), 1.0)
            return weight.start + (weight.end - weight.start) * t
    elif callable(weight):
        def weigh(v):
            return float(weight(*v.co))
    else:
        def weigh(v):
            return float(weight)
    for v in verts:
        v[layer][index] = min(max(weigh(v), 0.0), 1.0)
    return result


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
        value = tag_id(tag)
        for f in set(result.bm.faces) - before:
            f[result.tags] = value
    bmesh.ops.recalc_face_normals(result.bm, faces=result.bm.faces)
    return result


def inset(shape: Shape, faces: FaceSelector, thickness: float, depth: float = 0.0, tag: str | None = None) -> Shape:
    """Insets the selected faces as one region by ``thickness`` (a rim of quads), optionally raising them by
    ``depth``. ``tag`` tags the inner faces."""
    result = shape.copy()
    selected = _selected(result, faces)
    bmesh.ops.inset_region(result.bm, faces=selected, thickness=thickness, depth=depth, use_even_offset=True)
    if tag:
        value = tag_id(tag)
        for f in selected:
            f[result.tags] = value
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


def _mark(shape: Shape, faces: FaceSelector, value: int, border: bool) -> Shape:
    result = shape.copy()
    bm = result.bm
    layer = bm.edges.layers.int.get(EDGE_LAYER) or bm.edges.layers.int.new(EDGE_LAYER)
    selected = set(_selected(result, faces))
    for f in selected:
        for e in f.edges:
            if not border or any(other not in selected for other in e.link_faces):
                e[layer] = value
    return result


def sharp(shape: Shape, faces: FaceSelector = None, border: bool = True) -> Shape:
    """Keeps edges hard in smooth shading: the outline of the selected faces (``border=False``: all their edges),
    whatever the pack's hard-edge angle says. No effect in flat shading, where every edge is hard."""
    return _mark(shape, faces, HARD, border)


def smooth(shape: Shape, faces: FaceSelector = None) -> Shape:
    """Shades every edge of the selected faces smooth in smooth shading, even past the pack's hard-edge angle
    (a rounded box, a soft cushion)."""
    return _mark(shape, faces, SMOOTH, False)


def paint(shape: Shape, tag: str, faces: FaceSelector = None) -> Shape:
    """Tags the selected faces (all when no selection) with a palette role."""
    result = shape.copy()
    value = tag_id(tag)
    for f in select(result, faces):
        f[result.tags] = value
    return result


def join(*shapes: Shape) -> Shape:
    """One shape holding all the given shapes' faces (they may overlap; nothing is merged). Vertex groups with the
    same name are merged."""
    if not shapes:
        raise ShapeError("join needs at least one shape")
    bm = bmesh.new()
    tags = bm.faces.layers.int.new(TAG_LAYER)
    groups: list[str] = []
    layer = bm.verts.layers.deform.verify()
    for shape in shapes:
        source = shape.bm
        source_layer = source.verts.layers.deform.active
        index = {}
        for i, name in enumerate(shape.groups):
            if name not in groups:
                groups.append(name)
            index[i] = groups.index(name)
        vert_map = {}
        for v in source.verts:
            new = bm.verts.new(v.co)
            if source_layer is not None:
                for i, w in v[source_layer].items():
                    new[layer][index[i]] = w
            vert_map[v] = new
        for e in source.edges:
            if not e.link_faces:
                bm.edges.new([vert_map[v] for v in e.verts])
        for f in source.faces:
            face = bm.faces.new([vert_map[v] for v in f.verts])
            face[tags] = f[shape.tags]
        source_edges = source.edges.layers.int.get(EDGE_LAYER)
        if source_edges is not None:
            flags = bm.edges.layers.int.get(EDGE_LAYER) or bm.edges.layers.int.new(EDGE_LAYER)
            for e in source.edges:
                if e[source_edges]:
                    bm.edges.get([vert_map[v] for v in e.verts])[flags] = e[source_edges]
    result = Shape(bm)
    result.groups = groups
    result.booleans = sum(s.booleans for s in shapes)
    return result


BOOLEAN_OPS = {"union": "UNION", "difference": "DIFFERENCE", "intersection": "INTERSECT"}


def boolean(a: Shape, b: Shape, op: str = "difference") -> Shape:
    """Boolean of two closed shapes: "union", "difference" (a minus b) or "intersection". A shortcut for
    ``a.modify("BOOLEAN", object=b, operation=..., solver="MANIFOLD")``; faces keep their tags (cut faces take the
    cutter's). Reported in the build because booleans degrade topology; prefer extrude/inset where they can do."""
    if op not in BOOLEAN_OPS:
        raise ShapeError(f"op must be one of {', '.join(BOOLEAN_OPS)}")
    if not isinstance(b, Shape):
        raise ShapeError("boolean needs two shapes")
    return a.modify("BOOLEAN", object=b, operation=BOOLEAN_OPS[op], solver="MANIFOLD")
