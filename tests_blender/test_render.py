"""Build renders framed like the views, and comparison images."""
import numpy as np
from PIL import Image

import slopoly_model as sm
from conftest import PALETTE
from slopoly_model import assembly, render, silhouette
from slopoly_model.export import export
from slopoly_model.runner import build, run_program

SIZE = 256
MODEL = ("part('body', box(0.8, 0.5, 0.4, tag='wood'), at=(0, 0.25, 0))\n"
         "part('chimney', prism(6, r=0.08, length=0.4, tag='metal'), parent='body', at=(0.25, 0.6, -0.1),"
         " overlaps=['body'])\n")


def projected_mask(model, view: str, scale=150.0, shift=(0.0, 0.0)) -> np.ndarray:
    """The model's own silhouette in a SIZE x SIZE image, centred (plus ``shift`` pixels)."""
    tris = np.concatenate([silhouette._projected(p, silhouette.VIEWS[view]) for p in model.parts.values()])
    lo, hi = tris.reshape(-1, 2).min(0), tris.reshape(-1, 2).max(0)
    offset = np.array([SIZE / 2, SIZE / 2]) + np.array(shift) - (lo + hi) / 2 * scale
    return silhouette._fill(list(tris * scale + offset), (SIZE, SIZE))


def test_fit_reproduces_the_fitted_bounds():
    model = run_program(MODEL)
    mask = projected_mask(model, "front", shift=(10, -5))
    result = silhouette.score_view(model, "front", {"object": mask})
    fit = result["fit"]
    tris = np.concatenate([silhouette._projected(p, silhouette.VIEWS["front"]) for p in model.parts.values()])
    placed = tris.reshape(-1, 2) * fit["scale"] + np.array(fit["offset"])
    x0, y0, x1, y1 = silhouette.bbox(mask)
    np.testing.assert_allclose([*placed.min(0), *placed.max(0)], [x0, y0, x1, y1], atol=1.5)
    assert fit["image"] == [SIZE, SIZE]


def test_render_overlays_its_own_projection(tmp_path):
    model = run_program(MODEL)
    for view in ("front", "side", "top"):
        mask = projected_mask(model, view)
        fit = silhouette.score_view(model, view, {"object": mask})["fit"]
        export(model, tmp_path / "model.glb", [], None)
        image = render.render_view(view, fit, tmp_path / f"render_{view}.png")
        rendered = render.alpha_mask(image)
        assert image.size == (SIZE, SIZE)
        assert np.logical_xor(rendered, mask).mean() < 0.01, view
        assembly.new_model()
        model = run_program(MODEL)


def test_comparison_shows_model_only_and_view_only_sides():
    projection = np.zeros((SIZE, SIZE), bool)
    projection[60:200, 80:200] = True  # the model sits further right
    view = np.zeros((SIZE, SIZE), bool)
    view[60:200, 50:170] = True
    sheet = render.comparison(Image.new("RGB", (SIZE, SIZE), "white"), Image.new("RGBA", (SIZE, SIZE)), projection, view)
    assert sheet.size == (3 * render.PANEL, render.PANEL)
    diff = np.asarray(render.difference(projection, view))
    red = np.argwhere((diff == render.MODEL_ONLY).all(-1))
    blue = np.argwhere((diff == render.VIEW_ONLY).all(-1))
    assert red[:, 1].mean() > blue[:, 1].mean()  # red on the right, blue on the left


def test_build_with_views_lists_renders_and_comparisons(tmp_path):
    model = run_program(MODEL)
    masks, views = [], []
    for view in ("front", "side", "top", "back"):
        mask = projected_mask(model, view)
        path = tmp_path / f"{view}_mask.png"
        Image.fromarray((mask * 255).astype(np.uint8)).save(path)
        masks.append({"part": "object", "view": view, "path": str(path)})
        views.append({"view": view, "path": str(path)})
    assembly.new_model()
    out = tmp_path / "out"
    out.mkdir()
    report = build({"source": MODEL, "palette": PALETTE, "masks": masks, "views": views}, out)
    scored = {v["view"]: v for v in report["silhouette"]["views"]}
    assert set(scored) == {"front", "side", "top", "back"}
    for view, score in scored.items():
        assert (out / score["render"]).exists() and (out / score["compare"]).exists()
        assert Image.open(out / score["compare"]).size == (3 * render.PANEL, render.PANEL)
        assert "_projection" not in score
    assert score["object"]["iou"] > 0.9


def test_build_without_views_says_why(tmp_path):
    report = build({"source": MODEL, "palette": PALETTE}, tmp_path)
    assert report["silhouette"]["renders"].startswith("missing")
    assert not list(tmp_path.glob("compare_*.png"))
    assert sm  # the program API stays importable alongside the renderer
