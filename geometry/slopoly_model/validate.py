"""Fit validation (design section 7): pairwise intersection volume, contact of every declared connection,
connectivity from the root, and the triangle budget. Uses manifold3d on the parts' world-space meshes."""

from __future__ import annotations

from collections import deque
from itertools import combinations

import numpy as np

from .assembly import Model, Part
from .shapes import Shape, ShapeError


def to_manifold(shape: Shape):
    """manifold3d solid of the shape (for volumes, overlaps and gaps)."""
    import manifold3d

    mesh = manifold3d.Mesh(vert_properties=np.asarray(shape.vertices(), dtype=np.float32),
                           tri_verts=np.asarray(shape.triangles(), dtype=np.uint32).reshape(-1, 3))
    mesh.merge()
    solid = manifold3d.Manifold(mesh)
    if solid.status() != manifold3d.Error.NoError:
        raise ShapeError(f"shape is not a closed solid ({solid.status().name})")
    return solid

INTERSECTION_TOLERANCE = 0.01  # allowed overlap, as a fraction of the smaller part's volume
CONTACT_TOLERANCE = 0.005  # metres: a connection touches when the gap is at most this


def world_solids(model: Model) -> tuple[dict[str, object], list[dict]]:
    """manifold3d solid per part in world space, plus issues for parts that aren't closed solids."""
    solids, issues = {}, []
    for p in model.parts.values():
        try:
            solids[p.name] = to_manifold(p.shape.transformed(p.matrix))
        except ShapeError as error:
            issues.append({"part": p.name, "issue": "not_closed", "message": str(error)})
    return solids, issues


def _boxes_touch(a, b, margin: float) -> bool:
    ba, bb = a.bounding_box(), b.bounding_box()  # (minx, miny, minz, maxx, maxy, maxz)
    return all(ba[i] - margin <= bb[i + 3] and bb[i] - margin <= ba[i + 3] for i in range(3))


def _allowed(a: Part, b: Part) -> bool:
    return b.name in a.overlaps or a.name in b.overlaps


def validate(model: Model, budget: int, contact_tolerance: float = CONTACT_TOLERANCE,
             intersection_tolerance: float = INTERSECTION_TOLERANCE) -> dict:
    """The validator report: {"validated", "intersections", "contacts", "disconnected", "triangles", "issues"}.
    Lists hold only notable entries (intersecting pairs, every declared connection)."""
    solids, issues = world_solids(model)
    parts = model.parts
    if not parts:
        issues.append({"issue": "empty", "message": "the program defined no parts"})

    intersections, touching = [], {name: set() for name in parts}
    for a, b in combinations(solids, 2):
        sa, sb = solids[a], solids[b]
        if not _boxes_touch(sa, sb, contact_tolerance):
            continue
        volume = (sa ^ sb).volume()
        if volume > 0 or sa.min_gap(sb, contact_tolerance * 2) <= contact_tolerance:
            touching[a].add(b)
            touching[b].add(a)
        if volume <= 0:
            continue
        fraction = volume / max(min(sa.volume(), sb.volume()), 1e-12)
        allowed = _allowed(parts[a], parts[b])
        intersections.append({"a": a, "b": b, "volume": round(volume, 9), "fraction": round(fraction, 4),
                              "allowed": allowed, "ok": allowed or fraction <= intersection_tolerance})

    contacts = []
    for p in parts.values():
        if p.parent is None or p.name not in solids or p.parent not in solids:
            continue
        gap = 0.0 if p.parent in touching[p.name] else solids[p.name].min_gap(solids[p.parent], 100.0)
        contacts.append({"part": p.name, "parent": p.parent, "gap": round(float(gap), 6),
                         "ok": gap <= contact_tolerance})

    roots = model.roots()
    reached: set[str] = set()
    if roots:
        queue = deque([roots[0].name])
        reached.add(roots[0].name)
        while queue:
            for other in touching.get(queue.popleft(), ()):
                if other not in reached:
                    reached.add(other)
                    queue.append(other)
    disconnected = [name for name in parts if name not in reached]

    count = sum(p.shape.triangle_count() for p in parts.values())
    triangles = {"count": count, "budget": budget, "ok": count <= budget}
    validated = (not issues and not disconnected and triangles["ok"]
                 and all(i["ok"] for i in intersections) and all(c["ok"] for c in contacts))
    return {"validated": validated, "intersections": intersections, "contacts": contacts,
            "disconnected": disconnected, "triangles": triangles, "issues": issues}


def summary(model: Model) -> list[dict]:
    """Per part: parent, mesh, triangles, booleans, joint, world bounds."""
    rows = []
    for p in model.parts.values():
        verts = p.world_vertices()
        rows.append({"name": p.name, "parent": p.parent, "mesh": p.mesh, "triangles": p.shape.triangle_count(),
                     "booleans": p.shape.booleans, "joint": p.joint.as_dict() if p.joint else None,
                     "origin": np.round(p.origin, 6).tolist(),
                     "bounds": [np.round(verts.min(0), 6).tolist(), np.round(verts.max(0), 6).tolist()],
                     "line": p.line})
    return rows
