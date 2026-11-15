"""Build renders beside the views: the exported scene rendered orthographically from each view's direction, framed by
the silhouette fit so that render and view overlay pixel for pixel, plus a comparison image per view
(reference view | render | differences) and the detail regions of detail.py.

Cycles on the CPU (the container has no GPU or display), few samples, a soft white world plus one sun so that shading
reads, the Standard view transform so palette colours stay true.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np
from scipy import ndimage
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw

from . import detail

from .export import TO_BLENDER

SAMPLES = 16
PANEL = 384  # comparison panel size (px)
# Per view: image right and image up, in program space (Y up, front faces +Z). Matches silhouette.VIEWS.
AXES = {
    "front": ((1, 0, 0), (0, 1, 0)),
    "side": ((0, 0, -1), (0, 1, 0)),
    "top": ((1, 0, 0), (0, 0, -1)),
    "back": ((-1, 0, 0), (0, 1, 0)),
}
BOTH, MODEL_ONLY, VIEW_ONLY, NEITHER = (150, 150, 150), (220, 40, 40), (40, 90, 230), (255, 255, 255)
COLOUR = (230, 60, 210)  # inside both, colours differ
EDGE = (240, 140, 0)  # a line in the view that the model lacks
LABEL = (0, 0, 0)


def _setup(scene: bpy.types.Scene) -> None:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = False
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    world = scene.world or bpy.data.worlds.new("render")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (1, 1, 1, 1)
    background.inputs["Strength"].default_value = 0.6
    if "slopoly_sun" not in bpy.data.objects:
        sun = bpy.data.objects.new("slopoly_sun", bpy.data.lights.new("slopoly_sun", "SUN"))
        sun.data.energy = 2.5
        # from the upper front-left (program space), so tops are lightest and sides differ
        direction = Vector((0.5, -1.0, -0.6)).normalized()  # light travels this way
        sun.matrix_world = TO_BLENDER @ direction.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        scene.collection.objects.link(sun)


def camera_matrix(view: str, fit: dict) -> tuple[Matrix, float]:
    """The camera's world matrix (program space) and ortho scale for a view's fit (image px = proj * scale + offset)."""
    right, up = Vector(AXES[view][0]), Vector(AXES[view][1])
    back = right.cross(up)  # towards the camera
    width, height = fit["image"]
    scale, offset = fit["scale"], fit["offset"]
    cu, cv = (width / 2 - offset[0]) / scale, (height / 2 - offset[1]) / scale  # image centre in projection units
    centre = right * cu - up * cv
    rotation = Matrix((right, up, back)).transposed().to_4x4()
    return Matrix.Translation(centre + back * 50.0) @ rotation, max(width, height) / scale


def render_view(view: str, fit: dict, path: Path) -> Image.Image:
    """Renders the current scene (the exported model) for one view; saves and returns the RGBA image."""
    scene = bpy.context.scene
    _setup(scene)
    camera = bpy.data.objects.get("slopoly_camera")
    if camera is None:
        camera = bpy.data.objects.new("slopoly_camera", bpy.data.cameras.new("slopoly_camera"))
        scene.collection.objects.link(camera)
    matrix, ortho = camera_matrix(view, fit)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = ortho
    camera.data.clip_end = 200.0
    camera.matrix_world = TO_BLENDER @ matrix
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = fit["image"]
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return Image.open(path).convert("RGBA")


def on_white(image: Image.Image) -> Image.Image:
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, image).convert("RGB")


def difference(projection: np.ndarray, silhouette: np.ndarray) -> Image.Image:
    """Grey where both cover, red where only the model does, blue where only the view does."""
    out = np.full(projection.shape + (3,), NEITHER, dtype=np.uint8)
    out[projection & silhouette] = BOTH
    out[projection & ~silhouette] = MODEL_ONLY
    out[~projection & silhouette] = VIEW_ONLY
    return Image.fromarray(out)


def comparison(view_image: Image.Image, render: Image.Image, projection: np.ndarray, silhouette: np.ndarray,
               regions: list[dict] = (), region_masks: list[np.ndarray] = ()) -> Image.Image:
    """Reference view | model render | differences (magenta: colour regions, orange: lacking lines) with numbered
    region boxes, each scaled to PANEL px high."""
    panels = [view_image.convert("RGB"), on_white(render), difference(projection, silhouette)]
    marks = np.asarray(panels[2]).copy()
    for region, mask in zip(regions, region_masks):
        if region["kind"] in ("colour", "edge"):
            marks[ndimage.binary_dilation(mask) if region["kind"] == "edge" else mask] =                 COLOUR if region["kind"] == "colour" else EDGE
    panels[2] = Image.fromarray(marks)
    width, height = panels[0].size
    panel_w = round(PANEL * width / height)
    sheet = Image.new("RGB", (panel_w * 3, PANEL), NEITHER)
    for i, panel in enumerate(panels):
        sheet.paste(panel.resize((panel_w, PANEL), Image.Resampling.LANCZOS), (i * panel_w, 0))
    draw, k = ImageDraw.Draw(sheet), PANEL / height
    for region, mask in zip(regions, region_masks):
        ys, xs = np.nonzero(mask)
        box = [2 * panel_w + xs.min() * k - 2, ys.min() * k - 2, 2 * panel_w + (xs.max() + 1) * k + 2, (ys.max() + 1) * k + 2]
        draw.rectangle(box, outline=LABEL)
        draw.text((box[0] + 2, box[1] + 1), str(region["id"]), fill=LABEL)
    return sheet


def render_views(silhouette: dict, views: dict[str, Path], masks: dict[str, np.ndarray], out: Path,
                 parts: dict[str, dict[str, np.ndarray]] | None = None) -> None:
    """For each scored view with a fit, an object mask and a view image: writes render_<view>.png and
    compare_<view>.png into ``out``, records their names on the view's score ("render", "compare") and adds the
    detail regions ("detail", from detail.compare with the view's part masks ``parts[view]``)."""
    for score in silhouette.get("views", []):
        name = score["view"]
        projection = score.pop("_projection", None)
        if "fit" not in score or projection is None or name not in views or name not in masks or name not in AXES:
            continue
        render = render_view(name, score["fit"], out / f"render_{name}.png")
        on_white(render).save(out / f"render_{name}.png")
        view_image = Image.open(views[name]).convert("RGB")
        score["detail"], region_masks = detail.compare(np.asarray(view_image), np.asarray(render), masks[name],
                                                       (parts or {}).get(name))
        comparison(view_image, render, projection, masks[name], score["detail"]["regions"], region_masks
                   ).save(out / f"compare_{name}.png")
        score["render"], score["compare"] = f"render_{name}.png", f"compare_{name}.png"


def alpha_mask(image: Image.Image) -> np.ndarray:
    return np.asarray(image)[:, :, 3] >= 128
