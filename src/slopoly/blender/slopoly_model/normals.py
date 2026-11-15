"""Normal repair before export, and the shading defects left after it.

``repair`` merges duplicate vertices, removes zero-area faces and turns every closed piece's normals outward, in place
on a shape's bmesh (face tags and edge flags are layers, so they survive). ``defects`` lists what the repair cannot
fix: open edges, non-manifold edges and vertices, closed pieces that are still inside out, and faces of four or more corners bent out of plane, which
show a crease in flat shading.
"""

from __future__ import annotations

import math

import bmesh
from mathutils.bvhtree import BVHTree

MERGE_DISTANCE = 1e-4  # metres: 0.1 mm
DEGENERATE_DISTANCE = 1e-6
BENT_DEGREES = 5.0


def repair(bm: bmesh.types.BMesh) -> dict:
    """Repairs the mesh in place; returns {merged, removed, flipped} counts."""
    vertices, faces = len(bm.verts), len(bm.faces)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=MERGE_DISTANCE)
    merged = vertices - len(bm.verts)
    bmesh.ops.dissolve_degenerate(bm, dist=DEGENERATE_DISTANCE, edges=list(bm.edges))
    loose = [f for f in bm.faces if f.calc_area() <= DEGENERATE_DISTANCE ** 2]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="FACES_ONLY")
    removed = faces - len(bm.faces)
    bm.normal_update()
    before = {f: f.normal.copy() for f in bm.faces}
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    flipped = sum(1 for f in bm.faces if f in before and f.normal.dot(before[f]) < 0)
    return {"merged": merged, "removed": removed, "flipped": flipped}


def _islands(bm: bmesh.types.BMesh) -> list[list[bmesh.types.BMFace]]:
    """Connected pieces (faces sharing edges)."""
    seen: set = set()
    islands = []
    for start in bm.faces:
        if start in seen:
            continue
        seen.add(start)
        stack, island = [start], []
        while stack:
            face = stack.pop()
            island.append(face)
            for edge in face.edges:
                for other in edge.link_faces:
                    if other not in seen:
                        seen.add(other)
                        stack.append(other)
        islands.append(island)
    return islands


def _signed_volume(faces) -> float:
    volume = 0.0
    for face in faces:
        corners = [v.co for v in face.verts]
        for i in range(1, len(corners) - 1):
            volume += corners[0].dot(corners[i].cross(corners[i + 1])) / 6.0
    return volume


def bend_degrees(face) -> float:
    """Largest angle between the face normal and the normals of its fan triangles."""
    corners = [v.co for v in face.verts]
    worst = 0.0
    for i in range(1, len(corners) - 1):
        normal = (corners[i] - corners[0]).cross(corners[i + 1] - corners[0])
        if normal.length < 1e-12 or face.normal.length < 1e-12:
            continue
        worst = max(worst, math.degrees(normal.angle(face.normal)))
    return worst


def defects(bm: bmesh.types.BMesh) -> dict:
    """{openEdges, nonManifold, selfIntersecting, inward, bent}: boundary edges; edges shared by three or more faces
    or by none, and vertices where pieces touch only at a point; faces that cut through other faces of the same mesh
    (overlapping solids joined into one mesh); closed pieces with negative volume; faces bent over 5 degrees."""
    bm.normal_update()
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    non_manifold = (sum(1 for e in bm.edges if len(e.link_faces) != 1 and len(e.link_faces) != 2)
                    + sum(1 for v in bm.verts if not v.is_manifold and not v.is_boundary))
    tree = BVHTree.FromBMesh(bm, epsilon=1e-6)
    bm.faces.ensure_lookup_table()
    crossing = len({i for a, b in tree.overlap(tree)  # faces sharing a corner only touch (rounding can say overlap)
                    if a != b and not set(bm.faces[a].verts) & set(bm.faces[b].verts) for i in (a, b)})
    inward = 0
    for island in _islands(bm):
        closed = all(len(e.link_faces) == 2 for f in island for e in f.edges)
        if closed and _signed_volume(island) < 0:
            inward += 1
    bent = sum(1 for f in bm.faces if len(f.verts) >= 4 and bend_degrees(f) > BENT_DEGREES)
    return {"openEdges": open_edges, "nonManifold": non_manifold, "selfIntersecting": crossing, "inward": inward,
            "bent": bent}
