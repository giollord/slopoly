"""Schemas of the workspace files. ``slopoly check`` and every command that reads a file validate through these."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def check_hex(value: str | None) -> str | None:
    if value is not None and not HEX.match(value):
        raise ValueError(f"{value!r} is not a #rrggbb colour")
    return value


class Workspace(Model):
    format: int = 1


class Shading(Model):
    mode: Literal["flat", "smooth"] = "flat"
    hard_edge_angle: float = Field(60.0, ge=0, le=180)
    shade_strength: float = Field(0.5, ge=0, le=1)

    def for_build(self) -> dict:
        return {"mode": self.mode, "hardEdgeAngle": self.hard_edge_angle, "shadeStrength": self.shade_strength}


class Pack(Model):
    name: str
    budget: int = Field(2000, gt=0, description="triangle budget of every asset without its own")
    shading: Shading = Shading()


class Asset(Model):
    description: str = ""
    budget: int | None = Field(None, gt=0)
    default_variant: str = "default"


class Variant(Model):
    reference: str | None = Field(None, description="file name of the reference hero in the asset's heroes/")
    current: int | None = Field(None, description="number of the current build")


class Connection(Model):
    to: str
    type: Literal["fixed", "rotate", "slide"] = "fixed"
    axis: str | None = None


class ManifestPart(Model):
    name: str
    parent: str | None = None
    primitive: str | None = None
    mirror: str | None = None
    connections: list[Connection] = []


class Manifest(Model):
    symmetry: list[str] = []
    parts: list[ManifestPart]

    def problems(self) -> list[dict]:
        out, names = [], [p.name for p in self.parts]
        for i, part in enumerate(self.parts):
            if names.count(part.name) > 1:
                out.append({"field": f"parts.{i}.name", "message": f"part {part.name!r} appears twice"})
            if part.parent is not None and part.parent not in names:
                out.append({"field": f"parts.{i}.parent", "message": f"part {part.name!r} has unknown parent {part.parent!r}"})
            for j, c in enumerate(part.connections):
                if c.to not in names:
                    out.append({"field": f"parts.{i}.connections.{j}.to",
                                "message": f"part {part.name!r} connects to unknown part {c.to!r}"})
        roots = [p.name for p in self.parts if p.parent is None]
        if self.parts and len(roots) != 1:
            out.append({"field": "parts", "message": f"needs exactly one root part (without parent), found {len(roots)}"})
        if not self.parts:
            out.append({"field": "parts", "message": "needs at least one part"})
        return out


SOLID_SLOTS, GRADIENT_SLOTS = 256, 32  # see slopoly_model.palette


class PaletteEntry(Model):
    role: str
    kind: Literal["solid", "gradient"] = "solid"
    slot: int = Field(ge=0)
    color: str
    color2: str | None = None

    _hex = field_validator("color", "color2")(check_hex)

    def for_build(self) -> dict:
        return {"role": self.role, "kind": self.kind.capitalize(), "slot": self.slot, "color": self.color,
                "color2": self.color2}


class Colours(Model):
    color: str
    color2: str | None = None

    _hex = field_validator("color", "color2")(check_hex)


class Palette(Model):
    entries: list[PaletteEntry] = []
    variants: dict[str, dict[str, Colours]] = {}

    def problems(self) -> list[dict]:
        out, seen, slots = [], set(), {}
        for i, e in enumerate(self.entries):
            if e.role in seen:
                out.append({"field": f"entries.{i}.role", "message": f"role {e.role!r} appears twice"})
            seen.add(e.role)
            limit = SOLID_SLOTS if e.kind == "solid" else GRADIENT_SLOTS
            if e.slot >= limit:
                out.append({"field": f"entries.{i}.slot", "message": f"{e.kind} slot {e.slot} is out of range 0..{limit - 1}"})
            if (e.kind, e.slot) in slots:
                out.append({"field": f"entries.{i}.slot",
                            "message": f"{e.kind} slot {e.slot} is used by both {slots[(e.kind, e.slot)]!r} and {e.role!r}"})
            slots[(e.kind, e.slot)] = e.role
            if e.kind == "gradient" and not e.color2:
                out.append({"field": f"entries.{i}.color2", "message": f"gradient {e.role!r} needs color2"})
        for name, colours in self.variants.items():
            for role in colours:
                if role not in seen:
                    out.append({"field": f"variants.{name}.{role}", "message": f"variant {name!r} names unknown role {role!r}"})
        return out

    def variant_entries(self, name: str) -> list[PaletteEntry]:
        """The main entries recoloured by a variant; roles it doesn't set keep the main colours."""
        colours = self.variants.get(name, {})
        return [e.model_copy(update=colours[e.role].model_dump()) if e.role in colours else e for e in self.entries]


ImageKind = Literal["reference", "anchor", "hero"]
State = Literal["undecided", "picked", "rejected"]


class Image(Model):
    kind: ImageKind
    state: State = "undecided"
    prompt: str | None = None
    change: str | None = None
    seed: int | None = None
    references: list[str] = []
    source: str | None = Field(None, description="the concept this one revises")
    job: str | None = None
    width: int | None = None
    height: int | None = None


Bounds = dict  # {x, y, width, height} in pixels


class View(Model):
    view: Literal["front", "side", "top", "back"]
    image: str
    mask: str
    width: int
    height: int
    bounds: Bounds | None = None


class Views(Model):
    hero: str
    seed: int | None = None
    front_yaw: float | None = None
    front: Literal["detected", "assumed", "given"] | None = None
    job: str | None = None
    views: list[View]


class Mask(Model):
    part: str
    view: str
    path: str
    bounds: Bounds | None = None
    area: int | None = None
    colors: list[dict] = []


class Masks(Model):
    hero: str
    parts: list[str]
    job: str | None = None
    masks: list[Mask] = []
    missing: list[dict] = []


class Placement(Model):
    name: str
    asset: str
    variant: str | None = None
    at: tuple[float, float, float] = (0, 0, 0)
    rot: tuple[float, float, float] = (0, 0, 0)
    scale: float = Field(1.0, gt=0)


class Scene(Model):
    description: str = ""
    placements: list[Placement] = []
    builds: dict[str, Literal["current"] | int] = Field(
        {}, description="build per 'asset' or 'asset:variant'; a missing key means current")


JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class JobError(Model):
    code: str
    message: str
    hint: str | None = None


class Job(Model):
    model_config = ConfigDict(extra="ignore")
    id: str
    kind: str
    target: str
    inputs: dict = {}
    state: JobState = "queued"
    progress: float = 0.0
    message: str | None = None
    pid: int | None = None
    process_started: float | None = None
    created: str
    finished: str | None = None
    cancel_requested: bool = False
    result: dict | None = None
    error: JobError | None = None
    retry_of: str | None = None
    prompts: list[str] = Field([], description="ComfyUI prompt ids, dropped from its queue on cancel")


class Note(BaseModel):
    title: str
    tags: list[str] = []
    summary: str
