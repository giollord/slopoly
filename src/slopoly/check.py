"""``slopoly check`` and ``slopoly status``: file validation with cross-references, and the derived overview."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel

from . import models as m
from .core import SlopolyError, load
from .workspace import STATUS_ORDER, Pack, Target, Variant, Workspace, build_dirs, images

NOTE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.md$")


class Checker:
    def __init__(self, ws: Workspace):
        self.ws, self.problems = ws, []

    def add(self, path: Path, field: str, message: str) -> None:
        self.problems.append({"file": self.ws.rel(path), "field": field, "message": message})

    def load(self, model: type[BaseModel], path: Path):
        try:
            return load(model, path)
        except SlopolyError as error:
            for p in error.details.get("problems", [{"field": "", "message": error.message}]):
                self.add(path, p.get("field", ""), p["message"])
            return None

    def pack(self, pack: Pack) -> None:
        self.load(m.Pack, pack.file)
        palette = self.load(m.Palette, pack.palette_file) if pack.palette_file.exists() else m.Palette()
        if palette:
            for p in palette.problems():
                self.add(pack.palette_file, p["field"], p["message"])
        for folder in (pack.style_dir, pack.anchors_dir):
            self.sidecars(folder)
        for asset in pack.assets():
            meta = self.load(m.Asset, asset.file)
            variants = asset.variants()
            if meta and meta.default_variant not in [v.name for v in variants]:
                self.add(asset.file, "default_variant", f"default variant {meta.default_variant!r} does not exist")
            self.sidecars(asset.heroes_dir)
            for variant in variants:
                self.variant(variant, palette)
        for scene in pack.scenes():
            self.scene(pack, scene)

    def sidecars(self, folder: Path) -> None:
        for png in sorted(folder.glob("*.png")) if folder.is_dir() else []:
            if png.with_suffix(".yaml").exists():
                self.load(m.Image, png.with_suffix(".yaml"))

    def variant(self, variant: Variant, palette: m.Palette | None) -> None:
        meta = self.load(m.Variant, variant.file)
        if variant.manifest_file.exists() and (manifest := self.load(m.Manifest, variant.manifest_file)):
            for p in manifest.problems():
                self.add(variant.manifest_file, p["field"], p["message"])
        if not meta:
            return
        asset = variant.asset
        if meta.reference and not (asset.heroes_dir / meta.reference).exists():
            self.add(variant.file, "reference", f"reference {meta.reference!r} is not a hero in {asset.name}/heroes/")
        if meta.current is not None:
            folder = variant.build_dir(meta.current)
            if not (folder / "model.glb").exists():
                self.add(variant.file, "current", f"current build {meta.current} has no model")
        for hero in [meta.reference] if meta.reference else []:
            for model, path in ((m.Views, asset.views_dir(hero) / "views.yaml"),
                                (m.Masks, asset.masks_dir(hero) / "masks.yaml")):
                loaded = self.load(model, path) if path.exists() else None
                if model is m.Views and loaded is not None and not loaded.mesh:
                    self.add(path, "mesh", f"the views of {hero} come from the old splat turntable and have no "
                             f"reference mesh; remake them: slopoly gen views {asset.address}")

    def scene(self, pack: Pack, scene) -> None:
        meta = self.load(m.Scene, scene.file)
        if not meta:
            return
        names = {a.name: a for a in pack.assets()}
        for i, p in enumerate(meta.placements):
            if p.asset not in names:
                self.add(scene.file, f"placements.{i}.asset", f"unknown asset {p.asset!r}")
            elif p.variant and p.variant not in [v.name for v in names[p.asset].variants()]:
                self.add(scene.file, f"placements.{i}.variant", f"asset {p.asset!r} has no variant {p.variant!r}")
        for key in meta.builds:
            if key.partition(":")[0] not in names:
                self.add(scene.file, f"builds.{key}", f"unknown asset {key!r}")

    def notes(self) -> None:
        folder = self.ws.root / "knowledge"
        for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
            rel = path.relative_to(folder)
            if len(rel.parts) != 2 or rel.parts[0] not in ("techniques", "objects") or not NOTE_NAME.match(path.name):
                self.add(path, "", "notes go in knowledge/techniques/ or knowledge/objects/ with a kebab-case file name")
            front = note_front_matter(path)
            if front is None:
                self.add(path, "", "missing --- front matter with title, tags and summary")
                continue
            try:
                m.Note.model_validate(front)
            except Exception as error:  # pydantic ValidationError
                for e in getattr(error, "errors", lambda: [])():
                    self.add(path, ".".join(map(str, e["loc"])), e["msg"])


def note_front_matter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---")
    front, sep, _ = rest.partition("\n---")
    if not sep:
        return None
    try:
        data = yaml.safe_load(front)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def check(ws: Workspace, target: Target | None) -> dict:
    checker = Checker(ws)
    for pack in [target.pack] if target else ws.packs():
        checker.pack(pack)
    if not target:
        checker.notes()
    if checker.problems:
        raise SlopolyError("check_failed", f"{len(checker.problems)} problem(s) found", "fix the listed files",
                           problems=checker.problems)
    return {"ok": True}


def counts(found: list) -> dict:
    return {s: sum(1 for _, i in found if i.state == s) for s in ("undecided", "picked", "rejected")}


def variant_status(variant: Variant) -> dict:
    meta = variant.meta
    out = {"name": variant.name, "status": variant.status(), "reference": meta.reference, "current": meta.current,
           "builds": len(variant.builds())}
    if meta.reference:
        out["views"] = bool(variant.asset.views(meta.reference))
        out["segmented"] = bool(variant.asset.masks(meta.reference))
    from .review import load_notes  # review imports meshview; keep it out of every status call's import time
    notes = load_notes(variant).notes
    if notes:
        out["notes"] = {"open": sum(n.status == "open" for n in notes),
                        "addressed": sum(n.status == "addressed" for n in notes)}
    return out


def pack_status(pack: Pack) -> dict:
    from .jobs import open_jobs  # jobs imports workspace; keep the import local

    meta = pack.meta
    anchors = images(pack.anchors_dir)
    assets = []
    for asset in pack.assets():
        variants = [variant_status(v) for v in asset.variants()]
        status = max((v["status"] for v in variants), key=STATUS_ORDER.index, default="concept")
        assets.append({"name": asset.name, "description": asset.meta.description, "status": status,
                       "budget": asset.budget, "default_variant": asset.meta.default_variant,
                       "heroes": counts(images(asset.heroes_dir)), "variants": variants})
    return {"name": pack.name, "path": pack.ws.rel(pack.root), "budget": meta.budget,
            "shading": meta.shading.model_dump(),
            "anchors": counts(anchors),
            "palette_roles": [e.role for e in pack.palette.entries],
            "assets": assets,
            "scenes": [{"name": s.name, "builds": len(build_dirs(s.builds_dir))} for s in pack.scenes()],
            "open_jobs": open_jobs(pack)}


def status(ws: Workspace, target: Target | None) -> dict:
    if target and target.variant:
        asset = target.variant.asset
        return {"asset": asset.address, "description": asset.meta.description, "budget": asset.budget,
                "heroes": counts(images(asset.heroes_dir)), **variant_status(target.variant)}
    packs = [target.pack] if target else ws.packs()
    return {"workspace": ws.root.as_posix(), "packs": [pack_status(p) for p in packs]}
