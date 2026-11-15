"""Mask bounds and dominant colours (design §13): k-means in Lab over a mask's pixels, k <= 4, clusters under 5 % dropped."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageCms

_SRGB_TO_LAB = ImageCms.buildTransform(ImageCms.createProfile("sRGB"), ImageCms.createProfile("LAB"), "RGB", "LAB")


def mask_array(mask: Image.Image, threshold: int = 128) -> np.ndarray:
    """Boolean mask from a mask image (white = inside)."""
    return np.asarray(mask.convert("L")) >= threshold


def bounds(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x, y, width, height) of the mask's pixels, or None when empty."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def dominant_colors(image: Image.Image, mask: np.ndarray, k: int = 4, min_share: float = 0.05,
                    max_pixels: int = 20000, seed: int = 0) -> list[dict]:
    """Main colours inside the mask as [{hex, coverage}], largest first; coverage sums to <= 1."""
    rgb = np.asarray(image.convert("RGB"))
    if mask.shape != rgb.shape[:2]:
        raise ValueError("mask and image sizes differ")
    pixels_rgb = rgb[mask]
    if len(pixels_rgb) == 0:
        return []
    rng = np.random.default_rng(seed)
    if len(pixels_rgb) > max_pixels:
        pixels_rgb = pixels_rgb[rng.choice(len(pixels_rgb), max_pixels, replace=False)]
    lab_image = ImageCms.applyTransform(Image.fromarray(pixels_rgb.reshape(1, -1, 3), "RGB"), _SRGB_TO_LAB)
    lab = np.asarray(lab_image, dtype=np.float64).reshape(-1, 3)

    k = min(k, len(np.unique(lab, axis=0)))
    centers = lab[rng.choice(len(lab), k, replace=False)]
    for _ in range(20):
        labels = np.argmin(((lab[:, None, :] - centers[None]) ** 2).sum(-1), axis=1)
        moved = np.array([lab[labels == i].mean(0) if np.any(labels == i) else centers[i] for i in range(k)])
        if np.allclose(moved, centers):
            break
        centers = moved
    labels = np.argmin(((lab[:, None, :] - centers[None]) ** 2).sum(-1), axis=1)

    result = []
    for i in range(k):
        members = labels == i
        share = members.mean()
        if share < min_share:
            continue
        mean_rgb = pixels_rgb[members].mean(0).round().astype(int)
        result.append({"hex": "#{:02x}{:02x}{:02x}".format(*mean_rgb), "coverage": round(float(share), 4)})
    return sorted(result, key=lambda c: -c["coverage"])
