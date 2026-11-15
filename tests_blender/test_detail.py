"""Detail regions: what a matching silhouette hides (a thin missing handle, a dark band, a frame's lines)."""
import numpy as np

from slopoly_model import detail

WOOD, DARK = (170, 105, 60), (30, 20, 15)


def images():
    view = np.full((200, 200, 3), 255, np.uint8)
    view[50:150, 40:160] = WOOD
    view[95:105, 40:160] = DARK  # a dark band across the body
    view[60:68, 160:195] = WOOD  # a thin handle (thinner than 5 px is outline noise)
    view[60:140, 60:62] = (90, 50, 30)  # a frame line
    silhouette = (view != 255).any(2)
    render = np.zeros((200, 200, 4), np.uint8)
    render[50:150, 40:160] = (*WOOD, 255)
    return view, render, silhouette


def test_finds_missing_handle_colour_band_and_frame_line():
    view, render, silhouette = images()
    result, masks = detail.compare(view, render, silhouette, {"handle": np.pad(np.ones((8, 35), bool), ((60, 132), (160, 5)))})
    kinds = {r["kind"]: r for r in result["regions"]}
    assert kinds["missing"]["masks"] == ["handle"] and kinds["missing"]["box"][0] > 0.75
    assert kinds["colour"]["view_color"] == "#1e140f" and 0.35 < kinds["colour"]["box"][1] < 0.5
    assert any(r["kind"] == "edge" and r["box"][0] < 0.2 for r in result["regions"])
    assert len(masks) == len(result["regions"]) and result["colour_match"] < 1


def test_matching_render_has_no_regions():
    view, _, silhouette = images()
    render = np.dstack([view, np.where(silhouette, 255, 0).astype(np.uint8)])
    result, _ = detail.compare(view, render, silhouette)
    assert result["regions"] == [] and result["colour_match"] == 1.0
