"""3D comparison of a build with its reference mesh (both in metres, the asset's frame): volume overlap, surface
distances, and the regions where one has surface the other lacks, with their bounds and the build parts near them.
Works on surface samples, so a rough reference mesh with small holes is fine."""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import meshview as mv

CELLS = 128  # voxels along the longest axis
SAMPLES = 60000  # surface points per mesh
REGION_SHARE = 0.01  # a region holds at least this share of its mesh's samples
NEAR = 0.05  # metres: build parts this close to a region are named with it
MAX_REGIONS = 8


def sample(mesh: mv.Mesh, n: int = SAMPLES, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """``n`` points spread over the surface by area, and the face each lies on."""
    a, b, c = (mesh.verts[mesh.tris[:, k]] for k in range(3))
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    if area.sum() <= 0:
        return np.zeros((0, 3)), np.zeros(0, int)
    rng = np.random.default_rng(seed)
    faces = rng.choice(len(area), n, p=area / area.sum())
    u, v = rng.random(n), rng.random(n)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    points = a[faces] + (b[faces] - a[faces]) * u[:, None] + (c[faces] - a[faces]) * v[:, None]
    return points, faces


def _grid(lo: np.ndarray, hi: np.ndarray) -> tuple[float, np.ndarray, tuple[int, int, int]]:
    cell = float((hi - lo).max()) / CELLS
    origin = lo - 2 * cell
    shape = tuple(int(x) for x in np.ceil((hi - lo) / cell) + 5)
    return cell, origin, shape


def _solid(points: np.ndarray, cell: float, origin: np.ndarray, shape) -> np.ndarray:
    grid = np.zeros(shape, bool)
    idx = np.clip(((points - origin) / cell).astype(int), 0, np.array(shape) - 1)
    grid[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    grid = ndimage.binary_closing(ndimage.binary_dilation(grid), iterations=1)
    return ndimage.binary_fill_holes(grid)


def _regions(points: np.ndarray, far: np.ndarray, cell: float, origin: np.ndarray, shape, total: int,
             near_parts: cKDTree | None, part_names: np.ndarray | None, build_points: np.ndarray | None) -> list[dict]:
    if not far.any():
        return []
    grid = np.zeros(shape, np.int32)
    idx = np.clip(((points[far] - origin) / cell).astype(int), 0, np.array(shape) - 1)
    grid[idx[:, 0], idx[:, 1], idx[:, 2]] = 1
    labels, count = ndimage.label(ndimage.binary_dilation(grid), structure=np.ones((3, 3, 3)))
    point_labels = labels[idx[:, 0], idx[:, 1], idx[:, 2]]
    out = []
    for label in range(1, count + 1):
        members = points[far][point_labels == label]
        if len(members) < REGION_SHARE * total:
            continue
        region = {"bounds": [np.round(members.min(0), 3).tolist(), np.round(members.max(0), 3).tolist()],
                  "share": round(len(members) / total, 4)}
        if near_parts is not None and part_names is not None and build_points is not None:
            dist, nearest = near_parts.query(members, distance_upper_bound=NEAR + cell)
            names = Counter(part_names[nearest[np.isfinite(dist)]].tolist())
            region["parts"] = [n for n, _ in names.most_common(3) if n]
        out.append(region)
    return sorted(out, key=lambda r: -r["share"])[:MAX_REGIONS]


def compare(build: mv.Mesh, ref: mv.Mesh) -> dict:
    """{"volume_iou", "distance": {"mean", "p90"} in metres (both ways), "missing": regions where the reference has
    surface the build lacks, "extra": the reverse}. Each region: bounds in metres, its share of the samples, and the
    build parts nearby."""
    ref_points, _ = sample(ref)
    build_points, build_faces = sample(build, seed=1)
    if not len(ref_points) or not len(build_points):
        return {"skipped": "an empty mesh"}
    lo = np.minimum(ref_points.min(0), build_points.min(0))
    hi = np.maximum(ref_points.max(0), build_points.max(0))
    cell, origin, shape = _grid(lo, hi)
    a, b = _solid(ref_points, cell, origin, shape), _solid(build_points, cell, origin, shape)
    union = np.logical_or(a, b).sum()
    build_tree, ref_tree = cKDTree(build_points), cKDTree(ref_points)
    to_build, _ = build_tree.query(ref_points)
    to_ref, _ = ref_tree.query(build_points)
    threshold = max(3 * cell, 0.02 * float(np.linalg.norm(hi - lo)))
    names = build.face_parts[build_faces] if build.face_parts is not None else None
    both = np.concatenate([to_build, to_ref])
    return {
        "volume_iou": round(float(np.logical_and(a, b).sum() / union), 4) if union else None,
        "distance": {"mean": round(float(both.mean()), 4), "p90": round(float(np.percentile(both, 90)), 4)},
        "threshold": round(threshold, 4),
        "missing": _regions(ref_points, to_build > threshold, cell, origin, shape, len(ref_points), build_tree, names,
                            build_points),
        "extra": _regions(build_points, to_ref > threshold, cell, origin, shape, len(build_points), build_tree,
                          names, build_points),
    }
