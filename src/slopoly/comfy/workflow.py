"""API-format workflow files with named inputs: nodes titled ``in:<name>`` take job values, save nodes titled
``out:<name>`` are the outputs. The files ship in ``workflows/``; their sources are in the repository's comfyui/."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .. import config
from ..core import SlopolyError

WORKFLOWS = Path(__file__).parent / "workflows"
# Image models for anchors and heroes (the `images.model` setting) and the suffix of their workflow files.
IMAGE_MODELS = {"krea2": "", "z-image-turbo": ".z-image-turbo"}
IMAGE_WORKFLOWS = ("style-anchor", "hero")
# The widget an ``in:`` node's value goes into, when the node has several scalar inputs.
PRIMARY = ("value", "image", "text", "prompt", "noise_seed", "seed", "string", "boolean", "int", "float")


def names() -> list[str]:
    return sorted(p.stem for p in WORKFLOWS.glob("*.json"))


def image_model() -> str:
    model = config.get("images.model")
    if model not in IMAGE_MODELS:
        raise SlopolyError("unknown_image_model", f"no image model {model!r}",
                           f"slopoly config set images.model <{'|'.join(IMAGE_MODELS)}>")
    return model


def image_workflow(name: str) -> str:
    """The selected image model's file of an anchor or hero workflow; other names are returned unchanged."""
    return name + IMAGE_MODELS[image_model()] if name in IMAGE_WORKFLOWS else name


def active_names() -> list[str]:
    """The workflows jobs can run with the current settings (the other image models' files left out)."""
    return sorted({image_workflow(n.split(".")[0]) for n in names()})


def load(name: str, directory: Path = WORKFLOWS) -> dict[str, Any]:
    path = directory / f"{name}.json"
    if not path.is_file():
        raise SlopolyError("unknown_workflow", f"no workflow file {path.name}", workflows=names())
    return json.loads(path.read_text(encoding="utf-8"))


def title(node: dict[str, Any]) -> str:
    return (node.get("_meta") or {}).get("title", "")


def inputs(prompt: dict[str, Any]) -> dict[str, str]:
    """Named inputs: name -> node id."""
    return {title(n)[3:]: node_id for node_id, n in prompt.items() if title(n).startswith("in:")}


def outputs(prompt: dict[str, Any]) -> dict[str, str]:
    """Named outputs: node id -> name."""
    return {node_id: title(n)[4:] for node_id, n in prompt.items() if title(n).startswith("out:")}


def class_types(prompt: dict[str, Any]) -> set[str]:
    return {n["class_type"] for n in prompt.values() if isinstance(n, dict) and "class_type" in n}


def primary_input(node: dict[str, Any]) -> str:
    scalars = [k for k, v in node.get("inputs", {}).items() if not isinstance(v, list)]
    for name in PRIMARY:
        if name in scalars:
            return name
    if len(scalars) == 1:
        return scalars[0]
    raise SlopolyError("bad_workflow", f"input node \"{title(node)}\" ({node.get('class_type')}) has no single value to set")


def fill(prompt: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """A copy of the prompt with the given values set; values without a matching ``in:`` node are ignored, and
    ``in:`` nodes without a value keep the workflow's default."""
    filled = copy.deepcopy(prompt)
    for name, node_id in inputs(filled).items():
        if name in values and values[name] is not None:
            node = filled[node_id]
            node["inputs"][primary_input(node)] = values[name]
    return filled


def reference_slots(prompt: dict[str, Any]) -> list[int]:
    """Slot numbers n of ``in:reference_<n>`` inputs, ascending."""
    return sorted(int(name.split("_")[1]) for name in inputs(prompt)
                  if name.startswith("reference_") and name.split("_")[1].isdigit())
