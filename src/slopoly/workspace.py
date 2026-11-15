"""The workspace: a ``slopoly/`` folder in the user's repository holding packs as plain files (see pack-workspace)."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import models as m
from .core import SlopolyError, load, write_atomic, write_yaml

FOLDER = "slopoly"
MARKER = "slopoly.yaml"
BUILD_BINARIES = ["model.glb", "scene.glb", "model.blend", "palette.png", "render_*.png", "compare_*.png"]
GITIGNORE_START = "# >>> slopoly (managed section, rewritten by slopoly; add your own lines outside it)"
GITIGNORE_END = "# <<< slopoly"
REJECTED = "rejected"  # images, their views and masks, and failed builds that were set aside


def check_name(name: str, what: str) -> str:
    if not m.NAME.match(name):
        raise SlopolyError("invalid_name", f"{what} name {name!r} must be lower-case letters, digits, '-' or '_'")
    return name


def find(start: Path | None = None) -> Workspace:
    if env := os.environ.get("SLOPOLY_WORKSPACE"):
        root = Path(env).resolve()
        if not (root / MARKER).exists():
            raise SlopolyError("no_workspace", f"SLOPOLY_WORKSPACE points to {root.as_posix()}, which has no {MARKER}")
        return Workspace(root)
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / MARKER).exists() and folder.name == FOLDER:
            return Workspace(folder)
        if (folder / FOLDER / MARKER).exists():
            return Workspace(folder / FOLDER)
    raise SlopolyError("no_workspace", f"no {FOLDER}/{MARKER} found in {here.as_posix()} or its parents",
                       "run slopoly init in your repository's root")


def init(where: Path | None = None) -> Workspace:
    root = (where or Path.cwd()).resolve() / FOLDER
    if (root / MARKER).exists():
        raise SlopolyError("exists", f"{root.as_posix()} is already a workspace")
    write_yaml(root / MARKER, m.Workspace())
    for sub in ("techniques", "objects"):
        (root / "knowledge" / sub).mkdir(parents=True, exist_ok=True)
    return Workspace(root)


def build_dirs(builds: Path) -> list[tuple[int, Path]]:
    if not builds.is_dir():
        return []
    return sorted((int(p.name), p) for p in builds.iterdir() if p.is_dir() and p.name.isdigit())


class Workspace:
    def __init__(self, root: Path):
        self.root = root

    def rel(self, path: Path) -> str:
        """Paths in results are relative to the folder that holds the workspace (usually the repository root)."""
        try:
            return path.resolve().relative_to(self.root.parent).as_posix()
        except ValueError:
            return path.as_posix()

    def packs(self) -> list[Pack]:
        return [Pack(self, p.name) for p in sorted(self.root.iterdir()) if (p / "pack.yaml").exists()]

    def pack(self, name: str) -> Pack:
        pack = Pack(self, name)
        if not pack.file.exists():
            raise SlopolyError("not_found", f"pack {name!r} does not exist", "run slopoly status to list the packs",
                               packs=[p.name for p in self.packs()])
        return pack

    def path(self, value: str) -> Path:
        """An image or file given relative to the current folder, the repository root or the workspace."""
        candidates = [Path(value), self.root.parent / value, self.root / value]
        for candidate in candidates:
            if candidate.exists():
                resolved = candidate.resolve()
                if self.root not in (resolved, *resolved.parents):
                    raise SlopolyError("outside_workspace", f"{value} is not inside the workspace")
                return resolved
        raise SlopolyError("not_found", f"{value} does not exist")

    def target(self, value: str) -> Target:
        """``pack``, ``pack/asset``, ``pack/asset:variant`` or ``pack/scenes/scene``."""
        head, _, variant = value.partition(":")
        parts = head.strip("/").split("/")
        pack = self.pack(parts[0])
        if len(parts) == 1 and not variant:
            return Target(pack)
        if len(parts) == 3 and parts[1] == "scenes" and not variant:
            return Target(pack, scene=pack.scene(parts[2]))
        if len(parts) == 2:
            asset = pack.asset(parts[1])
            return Target(pack, asset, asset.variant(variant or None))
        raise SlopolyError("bad_target", f"{value!r} is not <pack>, <pack>/<asset>[:<variant>] or <pack>/scenes/<scene>")

    def image(self, value: str) -> ImageRef:
        path = self.path(value)
        parts = path.relative_to(self.root).parts
        pack = self.pack(parts[0])
        inner = [p for p in parts[:-1] if p != REJECTED] + [parts[-1]]  # rejected images live in a rejected/ subfolder
        if len(inner) == 3 and inner[1] in ("anchors", "style"):
            return ImageRef(path, pack)
        if len(inner) == 5 and inner[1] == "assets" and inner[3] == "heroes":
            return ImageRef(path, pack, pack.asset(inner[2]))
        raise SlopolyError("not_a_concept", f"{value} is not a style reference, anchor or hero image")


@dataclass
class Target:
    pack: Pack
    asset: Asset | None = None
    variant: Variant | None = None
    scene: Scene | None = None

    def need_variant(self) -> Variant:
        if not self.variant:
            raise SlopolyError("bad_target", "this command needs an asset target: <pack>/<asset>[:<variant>]")
        return self.variant


@dataclass
class ImageRef:
    path: Path
    pack: Pack
    asset: Asset | None = None  # set for heroes

    @property
    def rejected(self) -> bool:
        return self.path.parent.name == REJECTED

    @property
    def variants(self) -> list[Variant]:
        """The variants whose reference this hero is."""
        if self.asset is None or self.rejected:
            return []
        return [v for v in self.asset.variants() if v.meta.reference == self.path.name]

    @property
    def meta_path(self) -> Path:
        return self.path.with_suffix(".yaml")

    @property
    def meta(self) -> m.Image:
        return load(m.Image, self.meta_path)

    def save(self, meta: m.Image) -> None:
        write_yaml(self.meta_path, meta)

    def _moved(self, folder: Path, state: str) -> ImageRef:
        """Moves the image with its metadata (and a hero's views and masks) into ``folder`` (its own folder or the
        rejected/ subfolder) and sets its state."""
        meta = self.meta if self.meta_path.exists() else m.Image(kind="reference")
        target = folder / self.path.name
        if target.exists() and target != self.path:
            raise SlopolyError("exists", f"{self.pack.ws.rel(target)} already exists")
        folder.mkdir(parents=True, exist_ok=True)
        if self.asset is not None:
            stem, rejecting = self.path.stem, state == "rejected"
            for kind in ("views", "masks"):
                here = self.asset.root / kind / (REJECTED if self.rejected else "") / stem
                there = self.asset.root / kind / (REJECTED if rejecting else "") / stem
                if here.exists() and here != there:
                    there.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(here, there)
        moved = ImageRef(target, self.pack, self.asset)
        if target != self.path:
            shutil.move(self.path, target)
            if self.meta_path.exists():
                self.meta_path.unlink()
        moved.save(meta.model_copy(update={"state": state}))
        return moved

    def reject(self) -> ImageRef:
        """Sets the image aside in the rejected/ folder next to it (git-ignored). Variants that referenced the hero
        are left without a reference."""
        for variant in self.variants:
            variant.save(variant.meta.model_copy(update={"reference": None}))
        return self._moved(self.path.parent if self.rejected else self.path.parent / REJECTED, "rejected")

    def restore(self, state: str = "undecided") -> ImageRef:
        """Moves a rejected image back (undecided or picked), or sets the state of one that isn't rejected."""
        return self._moved(self.path.parent.parent if self.rejected else self.path.parent, state)


def images(folder: Path, states: tuple[str, ...] = ("undecided", "picked", "rejected")) -> list[tuple[Path, m.Image]]:
    """Images of a folder in the given states; rejected ones are read from its rejected/ subfolder."""
    out = []
    pngs = sorted(folder.glob("*.png")) if folder.is_dir() else []
    if "rejected" in states and (folder / REJECTED).is_dir():
        pngs += sorted((folder / REJECTED).glob("*.png"))
    for png in pngs:
        meta = png.with_suffix(".yaml")
        image = load(m.Image, meta) if meta.exists() else m.Image(kind="reference")
        if image.state in states:
            out.append((png, image))
    return out


def next_name(folder: Path, prefix: str) -> Path:
    pngs = [*folder.glob(f"{prefix}_*.png"), *(folder / REJECTED).glob(f"{prefix}_*.png")]  # never reuse a name
    numbers = [int(x.group(1)) for p in pngs if (x := re.match(rf"{prefix}_(\d+)$", p.stem))]
    return folder / f"{prefix}_{max(numbers, default=0) + 1:03d}.png"


class Pack:
    def __init__(self, ws: Workspace, name: str):
        self.ws, self.name, self.root = ws, name, ws.root / name

    file = property(lambda self: self.root / "pack.yaml")
    style_file = property(lambda self: self.root / "style.md")
    palette_file = property(lambda self: self.root / "palette.yaml")
    palette_dir = property(lambda self: self.root / "palette")
    style_dir = property(lambda self: self.root / "style")
    anchors_dir = property(lambda self: self.root / "anchors")
    jobs_dir = property(lambda self: self.root / "jobs")
    scenes_dir = property(lambda self: self.root / "scenes")

    @property
    def meta(self) -> m.Pack:
        return load(m.Pack, self.file)

    @property
    def palette(self) -> m.Palette:
        return load(m.Palette, self.palette_file, m.Palette())

    def save_palette(self, palette: m.Palette) -> None:
        write_yaml(self.palette_file, palette)

    def assets(self) -> list[Asset]:
        folder = self.root / "assets"
        return [Asset(self, p.name) for p in sorted(folder.iterdir()) if (p / "asset.yaml").exists()] if folder.is_dir() else []

    def asset(self, name: str) -> Asset:
        asset = Asset(self, name)
        if not asset.file.exists():
            raise SlopolyError("not_found", f"asset {name!r} does not exist in pack {self.name!r}",
                               assets=[a.name for a in self.assets()])
        return asset

    def scenes(self) -> list[Scene]:
        return [Scene(self, p.stem) for p in sorted(self.scenes_dir.glob("*.yaml"))]

    def scene(self, name: str) -> Scene:
        scene = Scene(self, name)
        if not scene.file.exists():
            raise SlopolyError("not_found", f"scene {name!r} does not exist in pack {self.name!r}",
                               scenes=[s.name for s in self.scenes()])
        return scene

    def style(self) -> str:
        return self.style_file.read_text(encoding="utf-8") if self.style_file.exists() else ""

    def update_gitignore(self) -> None:
        """Rewrites the managed section: ignore job scratch and old builds' binaries, keep current builds."""
        lines = [GITIGNORE_START, "jobs/", f"**/{REJECTED}/", "**/builds/*/job.json", "**/variants/*/looks/"]
        lines += [f"**/builds/*/{name}" for name in BUILD_BINARIES]
        for asset in self.assets():
            for variant in asset.variants():
                if (current := variant.meta.current) is not None:
                    rel = variant.build_dir(current).relative_to(self.root).as_posix()
                    lines += [f"!{rel}/{name}" for name in BUILD_BINARIES]
        for scene in self.scenes():
            if (latest := build_dirs(scene.builds_dir)):
                rel = latest[-1][1].relative_to(self.root).as_posix()
                lines += [f"!{rel}/{name}" for name in BUILD_BINARIES]
        lines.append(GITIGNORE_END)
        path = self.root / ".gitignore"
        before, after = [], []
        if path.exists():
            text = path.read_text(encoding="utf-8").splitlines()
            if GITIGNORE_START in text and GITIGNORE_END in text:
                before, after = text[:text.index(GITIGNORE_START)], text[text.index(GITIGNORE_END) + 1:]
            else:
                before = text
        write_atomic(path, "\n".join(before + lines + after) + "\n")


class Asset:
    def __init__(self, pack: Pack, name: str):
        self.pack, self.name, self.root = pack, name, pack.root / "assets" / name

    file = property(lambda self: self.root / "asset.yaml")

    @property
    def meta(self) -> m.Asset:
        return load(m.Asset, self.file)

    @property
    def budget(self) -> int:
        return self.meta.budget or self.pack.meta.budget

    def variants(self) -> list[Variant]:
        folder = self.root / "variants"
        return [Variant(self, p.name) for p in sorted(folder.iterdir()) if (p / "variant.yaml").exists()] if folder.is_dir() else []

    def variant(self, name: str | None = None) -> Variant:
        variant = Variant(self, name or self.meta.default_variant)
        if not variant.file.exists():
            raise SlopolyError("not_found", f"variant {variant.name!r} does not exist in asset {self.name!r}",
                               variants=[v.name for v in self.variants()])
        return variant

    @property
    def address(self) -> str:
        return f"{self.pack.name}/{self.name}"

    heroes_dir = property(lambda self: self.root / "heroes")

    def hero(self, name: str) -> ImageRef:
        return ImageRef(self.heroes_dir / name, self.pack, self)

    def views_dir(self, hero: str) -> Path:
        return self.root / "views" / Path(hero).stem

    def masks_dir(self, hero: str) -> Path:
        return self.root / "masks" / Path(hero).stem

    def views(self, hero: str) -> m.Views | None:
        path = self.views_dir(hero) / "views.yaml"
        return load(m.Views, path) if path.exists() else None

    def masks(self, hero: str) -> m.Masks | None:
        path = self.masks_dir(hero) / "masks.yaml"
        return load(m.Masks, path) if path.exists() else None


class Variant:
    def __init__(self, asset: Asset, name: str):
        self.asset, self.name, self.root = asset, name, asset.root / "variants" / name

    file = property(lambda self: self.root / "variant.yaml")
    manifest_file = property(lambda self: self.root / "manifest.yaml")
    program_file = property(lambda self: self.root / "program.py")
    builds_dir = property(lambda self: self.root / "builds")
    pack = property(lambda self: self.asset.pack)

    @property
    def address(self) -> str:
        return f"{self.asset.address}:{self.name}"

    @property
    def meta(self) -> m.Variant:
        return load(m.Variant, self.file)

    def save(self, meta: m.Variant) -> None:
        changed = meta.current != self.meta.current
        write_yaml(self.file, meta)
        if changed:
            self.pack.update_gitignore()

    @property
    def reference(self) -> ImageRef | None:
        """The variant's reference hero (in the asset's heroes/), if it has one."""
        name = self.meta.reference
        return self.asset.hero(name) if name else None

    def builds(self) -> list[tuple[int, Path]]:
        return build_dirs(self.builds_dir)

    def build_dir(self, number: int) -> Path:
        return self.builds_dir / f"{number:04d}"

    def next_build(self) -> int:
        """The next build number, counting failed builds set aside in builds/rejected/ too."""
        numbers = [n for n, _ in self.builds()] + [n for n, _ in build_dirs(self.builds_dir / REJECTED)]
        return max(numbers, default=0) + 1

    def report(self, number: int) -> dict | None:
        path = self.build_dir(number) / "report.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def status(self) -> str:
        meta = self.meta
        if meta.current is not None and (report := self.report(meta.current)) and report.get("validated"):
            return "validated"
        if any((d / "model.glb").exists() for _, d in self.builds()):
            return "built"
        if self.manifest_file.exists():
            return "manifest"
        return "concept"


STATUS_ORDER = ["concept", "manifest", "built", "validated"]


class Scene:
    def __init__(self, pack: Pack, name: str):
        self.pack, self.name = pack, name

    file = property(lambda self: self.pack.scenes_dir / f"{self.name}.yaml")
    builds_dir = property(lambda self: self.pack.scenes_dir / self.name / "builds")

    @property
    def meta(self) -> m.Scene:
        return load(m.Scene, self.file)

    @property
    def address(self) -> str:
        return f"{self.pack.name}/scenes/{self.name}"


# --- scaffolding -------------------------------------------------------------------------------------------------

STYLE_TEMPLATE = """# Instructions

General instructions for the whole pack: what it is for, the game's camera, scale and anything every asset shares.

# Style

Look, shapes, palette mood and level of detail, short and concrete. Style reference images go in style/.
"""

PROGRAM_TEMPLATE = """# Part program (see the skill's modelling reference). Units are metres, Y up, the front faces +Z.
"""


def new_pack(ws: Workspace, name: str) -> Pack:
    pack = Pack(ws, check_name(name, "pack"))
    if pack.root.exists():
        raise SlopolyError("exists", f"pack folder {ws.rel(pack.root)} already exists")
    write_yaml(pack.file, m.Pack(name=name))
    write_atomic(pack.style_file, STYLE_TEMPLATE)
    pack.save_palette(m.Palette())
    for folder in (pack.style_dir, pack.anchors_dir, pack.root / "assets", pack.scenes_dir, pack.jobs_dir, pack.palette_dir):
        folder.mkdir(parents=True, exist_ok=True)
    pack.update_gitignore()
    return pack


def new_asset(pack: Pack, name: str, description: str = "", budget: int | None = None,
              size: m.Size | None = None) -> Asset:
    asset = Asset(pack, check_name(name, "asset"))
    if asset.root.exists():
        raise SlopolyError("exists", f"asset folder {pack.ws.rel(asset.root)} already exists")
    write_yaml(asset.file, m.Asset(description=description, budget=budget, size=size))
    asset.heroes_dir.mkdir()
    new_variant(asset, "default")
    return asset


def new_variant(asset: Asset, name: str, source: Variant | None = None, hero: ImageRef | None = None) -> Variant:
    variant = Variant(asset, check_name(name, "variant"))
    if variant.root.exists():
        raise SlopolyError("exists", f"variant {name!r} already exists in asset {asset.name!r}")
    variant.root.mkdir(parents=True)
    meta = m.Variant()
    if source:
        for f in (source.manifest_file, source.program_file):
            if f.exists():
                shutil.copy2(f, variant.root / f.name)
    else:
        write_atomic(variant.program_file, PROGRAM_TEMPLATE)
    if hero:
        if hero.asset is None or hero.asset.root != asset.root:
            raise SlopolyError("bad_hero", "a variant can only start from a hero of the same asset")
        hero = hero.restore("picked")
        meta.reference = hero.path.name
    write_yaml(variant.file, meta)
    return variant


def set_reference(variant: Variant, hero: ImageRef) -> dict:
    """Makes ``hero`` the variant's reference. The previous reference is rejected when no other variant uses it."""
    out: dict = {"variant": variant.address, "reference": hero.path.name}
    old = variant.reference
    hero = hero.restore("picked")
    variant.save(variant.meta.model_copy(update={"reference": hero.path.name}))
    if old and old.path.name != hero.path.name and old.path.exists() and not old.variants:
        out["rejected"] = variant.pack.ws.rel(old.reject().path)
    return out


def new_scene(pack: Pack, name: str, description: str = "") -> Scene:
    scene = Scene(pack, check_name(name, "scene"))
    if scene.file.exists():
        raise SlopolyError("exists", f"scene {name!r} already exists in pack {pack.name!r}")
    write_yaml(scene.file, m.Scene(description=description))
    return scene


def scenes_using(variant: Variant) -> list[str]:
    asset = variant.asset
    default = asset.meta.default_variant
    return [s.name for s in asset.pack.scenes()
            if any(p.asset == asset.name and (p.variant or default) == variant.name for p in s.meta.placements)]
