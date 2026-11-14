"""Picks orthographic views from the splat turntables of a hero image (design section 3).

The ``views`` workflow renders two turntables of N frames each, one at eye level (``ring``) and one from above
(``above``), starting at yaw 0 and turning a full circle. Frame k of ``above`` looks down with the same yaw as frame k
of ``ring``.

The front is the object's mirror plane. Under an orthographic camera the turntable axis is the image's centre column,
so if the plane faces direction t, the frame at t + d is the mirror image of the frame at t - d. Each candidate t (in
half-frame steps) is scored by that mirror IoU averaged over several d, which is far less noisy than the symmetry of a
single frame. The plane shows twice, as the front and the back; the one nearer the hero's direction is the front.

The hero's direction is the ring frame that best matches the hero image. Silhouettes alone can't settle it: with a
mirror plane, the silhouette d degrees off the front equals the one d degrees off the back. So the match also compares
colours inside the silhouettes, because the splat's visible side is copied from the hero.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

PAIRS = 10  # frame pairs (d = 0..PAIRS-1 frames) averaged per candidate mirror plane
PROMINENCE = 0.08  # how far the best plane's score must stand above the median candidate (the cart: 0.78 vs 0.61)
MATCH_SIZE = 96  # silhouettes are compared with the hero at this size

# Frame offsets in quarter turns from the front. The turn direction of the turntable was calibrated on the cart
# (task 3.3): the side view looks from +X, with the object's front on the image's left.
QUARTER_SIGN = -1


def crop(mask: np.ndarray) -> np.ndarray | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def symmetry(mask: np.ndarray) -> float:
    """IoU of the silhouette with its left-right mirror about the silhouette's own centre."""
    shape = crop(mask)
    return 0.0 if shape is None else iou(shape, shape[:, ::-1])


def plane_scores(ring: list[np.ndarray]) -> list[float]:
    """Mirror-plane score per candidate direction t = i / 2 frames (i = 0 .. 2N-1)."""
    n = len(ring)
    scores = []
    for twice in range(2 * n):
        pairs = []
        for d in range(min(PAIRS, n // 2)):
            a = (twice + 1) // 2 + d  # frames a and twice - a lie d (and a half, for half steps) either side of t
            pairs.append(iou(ring[a % n], ring[(twice - a) % n][:, ::-1]))
        scores.append(float(np.mean(pairs)))
    return scores


def _normalised(mask: np.ndarray, rgb: np.ndarray | None = None) -> tuple[np.ndarray, float, np.ndarray | None] | None:
    """The silhouette's box resized to MATCH_SIZE (and the colours in it), plus the box's aspect."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    shape = Image.fromarray(mask[box].astype(np.uint8) * 255).resize((MATCH_SIZE, MATCH_SIZE), Image.BILINEAR)
    colours = None if rgb is None else np.asarray(Image.fromarray(rgb[box]).resize((MATCH_SIZE, MATCH_SIZE), Image.BILINEAR), float)
    return np.asarray(shape) >= 128, (xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1), colours


def match(hero: np.ndarray, frame: np.ndarray, hero_rgb: np.ndarray | None = None,
          frame_rgb: np.ndarray | None = None) -> float:
    """How well a frame matches the hero: silhouette IoU after normalising the box, times aspect agreement, times
    colour agreement inside both silhouettes when colours are given."""
    a, b = _normalised(hero, hero_rgb), _normalised(frame, frame_rgb)
    if a is None or b is None:
        return 0.0
    score = iou(a[0], b[0]) * min(a[1], b[1]) / max(a[1], b[1])
    if a[2] is not None and b[2] is not None:
        inside = a[0] & b[0]
        if inside.any():
            score *= 1 - float(np.abs(a[2][inside] - b[2][inside]).mean()) / 255
    return score


def _distance(a: int, b: int, n: int) -> int:
    return min((a - b) % n, (b - a) % n)


def pick_front(ring: list[np.ndarray], hero: np.ndarray, ring_rgb: list[np.ndarray] | None = None,
               hero_rgb: np.ndarray | None = None) -> dict:
    """Front frame index of the ring, how it was found ("detected" or "assumed") and the scores behind it. ``ring`` and
    ``hero`` are silhouettes; the optional RGB arrays let colours tell the front from the back."""
    n = len(ring)
    fit = [match(hero, m, hero_rgb, None if ring_rgb is None else ring_rgb[k]) for k, m in enumerate(ring)]
    hero_frame = int(np.argmax(fit))
    scores = plane_scores(ring)
    best = max(scores)
    if best - float(np.median(scores)) >= PROMINENCE:
        # The front and back planes score alike; take the one nearer the hero, rounded to a whole frame.
        planes = [t for t in range(2 * n) if scores[t] >= best - 0.05]
        twice = min(planes, key=lambda t: (_distance(round(t / 2) % n, hero_frame, n), -scores[t]))
        front, how = round(twice / 2) % n, "detected"
    else:
        front, how = hero_frame, "assumed"
    return {"front": front, "how": how, "heroFrame": hero_frame, "plane": round(best, 3)}


def frames(front: int, n: int) -> dict[str, tuple[str, int]]:
    """(turntable, frame) of each view."""
    quarter = n // 4
    return {
        "front": ("ring", front % n),
        "side": ("ring", (front + QUARTER_SIGN * quarter) % n),
        "back": ("ring", (front + 2 * quarter) % n),
        "top": ("above", front % n),
    }


def yaw_of(frame: int, n: int) -> float:
    return round(360.0 * frame / n, 2)


def frame_of(yaw: float, n: int) -> int:
    return round(yaw / 360.0 * n) % n
