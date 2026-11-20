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


class Size(Model):
    """The asset's real size: ``metres`` along ``axis`` (x, y, z or longest), used to scale its reference mesh."""
    axis: Literal["x", "y", "z", "longest"] = "longest"
    metres: float = Field(gt=0)

    @classmethod
    def parse(cls, text: str) -> Size:
        """"9" (the longest dimension) or "<axis>=<metres>", e.g. "z=9" for 9 m from back to front."""
        axis, _, metres = text.rpartition("=")
        return cls(axis=axis.strip().lower() or "longest", metres=float(metres))


class Asset(Model):
    description: str = ""
    budget: int | None = Field(None, gt=0)
    default_variant: str = "default"
    size: Size | None = None


class Variant(Model):
    reference: str | None = Field(None, description="file name of the reference hero in the asset's heroes/")
    current: int | None = Field(None, description="number of the current build")


class Connection(Model):
    to: str
    type: Literal["fixed", "rotate", "slide"] = "fixed"
    axis: str | None = None


VIEW_NAMES = ("front", "side", "top", "back")
# Directions `slopoly look --from` takes by name; "hero" is the hero image's camera (three-quarter front-left).
LOOK_DIRECTIONS = ("front", "back", "left", "right", "side", "top", "bottom", "hero")


def check_problem(check: str) -> str | None:
    """Why a shape plan's check entry is invalid (None when valid): a view name, or look:<direction> where the
    direction is a named one or "<yaw>,<pitch>" in degrees."""
    if check in VIEW_NAMES:
        return None
    kind, _, direction = check.partition(":")
    if kind != "look":
        return f"check {check!r} is neither a view ({', '.join(VIEW_NAMES)}) nor look:<direction>"
    if direction in LOOK_DIRECTIONS:
        return None
    try:
        yaw, pitch = (float(x) for x in direction.split(","))
    except ValueError:
        return (f"check {check!r} has an unknown direction; use {', '.join(LOOK_DIRECTIONS)} "
                "or <yaw>,<pitch> in degrees")
    return None if -90 <= pitch <= 90 else f"check {check!r} has a pitch outside -90..90"


class ManifestPart(Model):
    name: str
    parent: str | None = None
    primitive: str | None = None
    mirror: str | None = None
    connections: list[Connection] = []
    shape: str | None = Field(None, description="the part's shape character: plan, profile, bends, ends, contacts")
    steps: list[str] = Field([], description="how the part is built, in modelling operations")
    checks: list[str] = Field([], description="views or look:<direction> close-ups that show the part is right")


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
            for j, check in enumerate(part.checks):
                if problem := check_problem(check):
                    out.append({"field": f"parts.{i}.checks.{j}", "message": f"part {part.name!r}: {problem}"})
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


class Fit(Model):
    """Image pixel = the scorer's view projection (metres) * scale + offset."""
    scale: float
    offset: list[float]
    image: list[int]


class View(Model):
    view: Literal["front", "side", "top", "back"]
    image: str
    mask: str
    width: int
    height: int
    bounds: Bounds | None = None
    m_per_px: float | None = Field(None, description="metres per pixel (views of a reference mesh)")
    axes: dict[str, str] | None = Field(None, description="model axis along the image's x and y, e.g. {x: -z, y: -y}")
    ground_row: float | None = Field(None, description="image row of the ground (y = 0)")
    fit: Fit | None = None


class MeshPlacement(Model):
    """How the generated mesh becomes the reference: mirrored across X, turned ``yaw`` degrees around Y, scaled and
    moved onto the ground."""
    yaw: float = 0.0
    mirrored: bool = False
    scale: float = 1.0
    offset: list[float] = [0.0, 0.0, 0.0]


class Views(Model):
    hero: str
    seed: int | None = None
    front_yaw: float | None = None
    front: Literal["detected", "assumed", "given"] | None = None
    job: str | None = None
    views: list[View]
    generator: str | None = Field(None, description="the image-to-3D model that made the reference mesh")
    mesh: str | None = Field(None, description="the reference mesh, placed in metres (reference.glb)")
    generated: str | None = Field(None, description="the mesh as generated, before placement")
    placement: MeshPlacement | None = None
    mirrored: bool | None = None
    scale: Literal["given", "assumed"] | None = Field(None, description="whether the size came from the asset")
    size: Size | None = Field(None, description="the asset size the views were made at")


class Mask(Model):
    part: str
    view: str
    path: str
    bounds: Bounds | None = None
    area: int | None = None
    colors: list[dict] = []
    region: list[int] | None = Field(None, description="the box (x0, y0, x1, y1 px) it was segmented within")
    implausible: str | None = Field(None, description="why the mask is suspect (covers most of the object...)")


class Region(Model):
    """A part's faces on the reference mesh, voted from its masks in many renders."""
    part: str
    faces: str | None = Field(None, description="JSON file with the face indices on reference.glb")
    bounds: list[list[float]] | None = Field(None, description="[[x, y, z] min, [x, y, z] max] in metres")
    agreement: float = 0.0
    uncertain: bool = True
    implausible: str | None = Field(None, description="why the region can't be one part (spans most of the object)")


class Masks(Model):
    hero: str
    parts: list[str]
    job: str | None = None
    masks: list[Mask] = []
    missing: list[dict] = []
    regions: list[Region] = []


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


class ReviewEvent(Model):
    at: str
    status: Literal["open", "addressed", "wontfix", "closed"]
    build: int | None = None
    text: str | None = Field(None, description="the agent's reason or the user's comment")


class ReviewNote(Model):
    """A user's review note on a variant: a comment with painted regions on the reference and the build."""
    number: int
    build: int | None = None
    comment: str = ""
    status: Literal["open", "addressed", "wontfix", "closed"] = "open"
    camera: dict = {}
    left: Literal["hero", "mesh"] = "hero"
    images: dict[str, str] = Field({}, description="pane images with the strokes, relative to the variant's notes/")
    hits: list[dict] = Field([], description="build parts under the strokes: part, share, centre (metres)")
    empty: float = Field(0.0, description="share of the strokes over empty space")
    region: list[list[float]] | None = Field(None, description="the painted region on the reference mesh (metres)")
    history: list[ReviewEvent] = []


class ReviewNotes(Model):
    notes: list[ReviewNote] = []
