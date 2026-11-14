"""Assembly: places shapes as named parts with a hierarchy, mirroring, joints, instances and sockets.

A program calls ``part``/``instance``/``socket``; they register into the current ``Model``, which the build runner
collects. Positions (``at``) are world coordinates in metres, Y up; a part's origin is its shape's origin, so a
rotating part (``joint=rotate(...)``) is built around its pivot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from mathutils import Matrix, Vector

from .shapes import Shape, ShapeError, Vec3, axis_vector, rotation_matrix


class ModelError(ValueError):
    """The assembly is inconsistent (unknown parent, duplicate name, ...)."""


@dataclass(frozen=True)
class Joint:
    """How a part moves relative to its parent: "rotate" around or "slide" along ``axis`` through the part's
    origin. ``limits`` are (min, max) in degrees for rotate, metres for slide."""
    kind: str
    axis: tuple[float, float, float]
    limits: tuple[float, float] | None = None

    def as_dict(self) -> dict:
        return {"type": self.kind, "axis": list(self.axis), **({"limits": list(self.limits)} if self.limits else {})}


def rotate(axis: str | Vec3 = "y", limits: tuple[float, float] | None = None) -> Joint:
    return Joint("rotate", tuple(axis_vector(axis)), tuple(limits) if limits else None)


def slide(axis: str | Vec3 = "y", limits: tuple[float, float] | None = None) -> Joint:
    return Joint("slide", tuple(axis_vector(axis)), tuple(limits) if limits else None)


def gradient(role: str, axis: str = "y") -> str:
    """A gradient palette role laid along ``axis`` over the part (or tagged faces): use as a ``color`` or tag."""
    axis_vector(axis)
    return f"{role}@{axis}"


@dataclass
class Part:
    name: str
    shape: Shape
    matrix: Matrix  # local -> world
    parent: str | None = None
    joint: Joint | None = None
    color: str | None = None
    overlaps: tuple[str, ...] = ()
    mesh: str = ""  # parts with the same mesh name share one mesh (instances)
    mirror_of: str | None = None
    line: int | None = None  # program line that defined the part

    @property
    def origin(self) -> np.ndarray:
        return np.array(self.matrix.translation)

    def world_vertices(self) -> np.ndarray:
        verts = self.shape.vertices()
        m = np.array(self.matrix)
        return verts @ m[:3, :3].T + m[:3, 3]

    def face_tags(self) -> list[str]:
        """Each face's palette role: its own tag, else the part's colour ("" when neither)."""
        return [tag or (self.color or "") for tag in self.shape.face_tags()]


@dataclass
class Socket:
    name: str
    at: tuple[float, float, float]
    parent: str | None = None


@dataclass
class Model:
    parts: dict[str, Part] = field(default_factory=dict)
    sockets: list[Socket] = field(default_factory=list)

    def add(self, item: Part) -> Part:
        if item.name in self.parts:
            raise ModelError(f"part {item.name!r} is defined twice")
        if item.parent is not None and item.parent not in self.parts:
            raise ModelError(f"part {item.name!r}: parent {item.parent!r} is not defined (define parents first)")
        self.parts[item.name] = item
        return item

    def roots(self) -> list[Part]:
        return [p for p in self.parts.values() if p.parent is None]

    def children(self, name: str) -> list[Part]:
        return [p for p in self.parts.values() if p.parent == name]

    def meshes(self) -> dict[str, list[Part]]:
        groups: dict[str, list[Part]] = {}
        for p in self.parts.values():
            groups.setdefault(p.mesh, []).append(p)
        return groups


current = Model()


def new_model() -> Model:
    """Starts an empty model (the build runner calls this before running a program)."""
    global current
    current = Model()
    return current


def _caller_line() -> int | None:
    import sys

    frame = sys._getframe(2)
    while frame is not None:
        if frame.f_code.co_filename == "program.py":
            return frame.f_lineno
        frame = frame.f_back
    return None


def _placement(at: Vec3, rot: Vec3 | None) -> Matrix:
    if len(at) != 3:
        raise ModelError(f"at must be (x, y, z), got {at!r}")
    return Matrix.Translation(Vector(at)) @ rotation_matrix(rot)


MIRROR_NAMES = (("_L", "_R"), ("_l", "_r"), ("Left", "Right"), ("left", "right"))


def mirror_name(name: str) -> str:
    for a, b in MIRROR_NAMES:
        if name.endswith(a):
            return name[: -len(a)] + b
        if name.endswith(b):
            return name[: -len(b)] + a
    return name + "_mirror"


def _mirror_matrix(axis: str) -> Matrix:
    scale = [1.0, 1.0, 1.0, 1.0]
    try:
        scale["xyz".index(axis)] = -1.0
    except ValueError:
        raise ModelError(f"mirror must be 'x', 'y' or 'z', not {axis!r}") from None
    return Matrix.Diagonal(scale)


def part(name: str, shape: Shape, parent: str | None = None, at: Vec3 = (0, 0, 0), rot: Vec3 | None = None,
         mirror: str | None = None, joint: Joint | None = None, color: str | None = None,
         overlaps: Sequence[str] = ()) -> Part:
    """Places ``shape`` as part ``name`` with its origin at world position ``at`` and Euler rotation ``rot``
    (degrees). ``mirror="x"`` also creates the mirror image across the X=0 plane, named with _L/_R swapped
    (its parent is the mirrored parent when one exists). ``overlaps`` lists parts it may intersect (e.g. an axle
    through a wheel). ``color`` is the palette role for faces without their own tag. Returns the part."""
    if not isinstance(shape, Shape):
        raise ShapeError(f"part {name!r}: shape must be a Shape (box, prism, ...), got {type(shape).__name__}")
    line = _caller_line()
    created = current.add(Part(name, shape, _placement(at, rot), parent, joint, color, tuple(overlaps), name, line=line))
    if mirror:
        m = _mirror_matrix(mirror)
        other_parent = parent
        if parent is not None and mirror_name(parent) in current.parts:
            other_parent = mirror_name(parent)
        other_joint = None
        if joint is not None:
            axis = m.to_3x3() @ Vector(joint.axis)
            if joint.kind == "rotate":
                axis = -axis  # a rotation axis is a pseudo-vector: mirroring flips it once more
            other_joint = Joint(joint.kind, tuple(axis), joint.limits)
        other = mirror_name(name)
        current.add(Part(other, shape.transformed(m), m @ created.matrix @ m, other_parent, other_joint, color,
                         tuple(mirror_name(o) if mirror_name(o) in current.parts else o for o in overlaps), other,
                         mirror_of=name, line=line))
    return created


def instance(name: str, shape: Shape, transforms: Sequence, parent: str | None = None, color: str | None = None,
             overlaps: Sequence[str] = ()) -> list[Part]:
    """Places one shape many times, sharing one mesh: parts ``name_1``..``name_N``. Each transform is a position
    (x, y, z) or a dict {"at": (x, y, z), "rot": (x, y, z)}."""
    if not transforms:
        raise ModelError(f"instance {name!r} needs at least one transform")
    line = _caller_line()
    placed = []
    for i, t in enumerate(transforms, start=1):
        at, rot = (t.get("at", (0, 0, 0)), t.get("rot")) if isinstance(t, dict) else (t, None)
        placed.append(current.add(Part(f"{name}_{i}", shape, _placement(at, rot), parent, None, color,
                                       tuple(overlaps), name, line=line)))
    return placed


def socket(name: str, at: Vec3, parent: str | None = None) -> Socket:
    """A named connection point (exported as an empty node ``socket_<name>``) at world position ``at``."""
    if parent is not None and parent not in current.parts:
        raise ModelError(f"socket {name!r}: parent {parent!r} is not defined")
    created = Socket(name, tuple(float(c) for c in at), parent)
    current.sockets.append(created)
    return created
