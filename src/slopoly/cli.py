"""The ``slopoly`` command. Every command prints one JSON document; errors are JSON with a non-zero exit status."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from . import __version__, config
from . import build as builds
from . import jobs as job_runner
from . import check as checks
from . import models as m
from . import workspace as wsp
from .core import SlopolyError, emit, write_yaml

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False,
                  help="Low-poly asset packs from ComfyUI concepts and Blender part programs.")
pack_app = typer.Typer(no_args_is_help=True, help="Create and delete packs.")
asset_app = typer.Typer(no_args_is_help=True, help="Create assets.")
variant_app = typer.Typer(no_args_is_help=True, help="Create, rename and choose asset variants.")
scene_app = typer.Typer(no_args_is_help=True, help="Create and build scenes.")
config_app = typer.Typer(no_args_is_help=True, help="Machine settings (stored outside the workspace).")
dev_app = typer.Typer(no_args_is_help=True, help="Development commands (run in a checkout of the slopoly repository).")
gen_app = typer.Typer(no_args_is_help=True, help="Generate images on ComfyUI (detached jobs: slopoly wait <id>).")
palette_app = typer.Typer(no_args_is_help=True, help="Edit the pack palette (slots stay stable) and render its textures.")
for sub, name in ((pack_app, "pack"), (asset_app, "asset"), (variant_app, "variant"), (scene_app, "scene"),
                  (config_app, "config"), (palette_app, "palette"), (dev_app, "dev"), (gen_app, "gen")):
    app.add_typer(sub, name=name)


def _version(value: bool) -> None:
    if value:
        print(__version__)
        raise typer.Exit()


@app.callback()
def root(version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Print the version.")):
    """Low-poly asset packs from ComfyUI concepts and Blender part programs."""


def ws() -> wsp.Workspace:
    return wsp.find()


def asset_target(value: str) -> tuple[wsp.Pack, str]:
    pack, sep, name = value.partition("/")
    if not sep or not name or "/" in name or ":" in name:
        raise SlopolyError("bad_target", f"{value!r} is not <pack>/<asset>")
    return ws().pack(pack), name


# --- workspace ---------------------------------------------------------------------------------------------------

@app.command()
def init():
    """Create a slopoly/ workspace in the current folder."""
    w = wsp.init()
    emit({"workspace": w.root.as_posix()})


@app.command()
def status(target: Optional[str] = typer.Argument(None, help="<pack> or <pack>/<asset>[:<variant>]")):
    """Packs, assets and variants with their statuses, references, current builds and open jobs."""
    w = ws()
    emit(checks.status(w, w.target(target) if target else None))


@app.command()
def check(target: Optional[str] = typer.Argument(None, help="<pack> (default: the whole workspace)")):
    """Validate workspace files and their cross-references."""
    w = ws()
    emit(checks.check(w, w.target(target) if target else None))


@pack_app.command("new")
def pack_new(name: str):
    """Create a pack folder with pack.yaml, style.md, palette.yaml and a .gitignore."""
    pack = wsp.new_pack(ws(), name)
    emit({"pack": name, "path": pack.ws.rel(pack.root),
          "files": [pack.ws.rel(p) for p in (pack.file, pack.style_file, pack.palette_file)]})


@pack_app.command("rm")
def pack_rm(name: str, yes: bool = typer.Option(False, "--yes", help="confirm the deletion")):
    """Delete a pack folder, after cancelling its running jobs."""
    w = ws()
    try:
        pack = w.pack(name)
    except SlopolyError as error:
        raise SlopolyError("not_found", error.message, packs=[p.name for p in w.packs()]) from None
    if not yes:
        raise SlopolyError("confirm_required", f"deleting {w.rel(pack.root)} cannot be undone",
                           f"run slopoly pack rm {name} --yes")
    cancelled = job_runner.cancel_all(pack)
    shutil.rmtree(pack.root)
    emit({"removed": name, "cancelled_jobs": cancelled})


SIZE_HELP = "real size in metres: 9 (longest dimension) or <axis>=<metres>, e.g. z=9 from back to front"


def parse_size(text: str) -> m.Size:
    try:
        return m.Size.parse(text)
    except (ValueError, ValidationError) as error:
        raise SlopolyError("bad_size", f"can't read the size {text!r}", SIZE_HELP) from error


@asset_app.command("size")
def asset_size(target: str = typer.Argument(..., help="<pack>/<asset>"),
               size: str = typer.Argument(..., help=SIZE_HELP)):
    """Set an asset's real size; its heroes' reference meshes and views are rescaled at once (no new generation)."""
    from . import generate
    pack, name = asset_target(target)
    emit(generate.resize(pack.asset(name), parse_size(size)))


@asset_app.command("new")
def asset_new(target: str = typer.Argument(..., help="<pack>/<asset>"),
              description: str = typer.Option("", help="short description of the asset"),
              budget: Optional[int] = typer.Option(None, help="triangle budget (default: the pack's)"),
              size: Optional[str] = typer.Option(None, help=SIZE_HELP)):
    """Create an asset with its default variant."""
    pack, name = asset_target(target)
    asset = wsp.new_asset(pack, name, description, budget, parse_size(size) if size else None)
    variant = asset.variant()
    emit({"asset": asset.address, "variant": variant.name, "path": pack.ws.rel(asset.root),
          "files": [pack.ws.rel(p) for p in (asset.file, variant.file, variant.program_file)]})


@variant_app.command("reference")
def variant_reference(target: str = typer.Argument(..., help="<pack>/<asset>:<variant>"),
                      hero: str = typer.Argument(..., help="a hero of the asset (its path or file name)")):
    """Make a hero the variant's reference, keeping the variant's manifest, program and builds. The old reference
    is rejected unless another variant uses it."""
    variant = ws().target(target).need_variant()
    found = variant.asset.hero(Path(hero).name)
    if not found.path.exists():
        raise SlopolyError("not_found", f"{variant.asset.address} has no hero {Path(hero).name!r}",
                           f"list them: slopoly status {variant.asset.address}")
    if found.meta.kind != "hero":
        raise SlopolyError("not_a_hero", f"{Path(hero).name} is not a hero image")
    out = wsp.set_reference(variant, found)
    if not variant.asset.views(found.path.name):
        out["hint"] = f"make its views: slopoly gen views {variant.address}"
    emit(out)


@variant_app.command("new")
def variant_new(target: str = typer.Argument(..., help="<pack>/<asset>"), name: str = typer.Argument(...),
                source: Optional[str] = typer.Option(None, "--from", help="copy manifest and program of this variant"),
                hero: Optional[str] = typer.Option(None, help="start from this hero of the asset (it becomes the reference)")):
    """Create a variant: empty, a copy of another variant, or from a hero."""
    pack, asset_name = asset_target(target)
    asset = pack.asset(asset_name)
    variant = wsp.new_variant(asset, name, asset.variant(source) if source else None,
                              pack.ws.image(hero) if hero else None)
    emit({"variant": variant.address, "path": pack.ws.rel(variant.root), "reference": variant.meta.reference})


@variant_app.command("rename")
def variant_rename(target: str = typer.Argument(..., help="<pack>/<asset>:<variant>"), new_name: str = typer.Argument(...)):
    """Rename a variant (scenes and the asset's default follow)."""
    variant = ws().target(target).need_variant()
    asset = variant.asset
    wsp.check_name(new_name, "variant")
    if (asset.root / "variants" / new_name).exists():
        raise SlopolyError("exists", f"variant {new_name!r} already exists in asset {asset.name!r}")
    users = wsp.scenes_using(variant)
    variant.root.rename(asset.root / "variants" / new_name)
    meta = asset.meta
    if meta.default_variant == variant.name:
        write_yaml(asset.file, meta.model_copy(update={"default_variant": new_name}))
    for scene in asset.pack.scenes():
        if scene.name in users:
            s = scene.meta
            for p in s.placements:
                if p.asset == asset.name and p.variant == variant.name:
                    p.variant = new_name
            s.builds = {(f"{asset.name}:{new_name}" if k == f"{asset.name}:{variant.name}" else k): v
                        for k, v in s.builds.items()}
            write_yaml(scene.file, s)
    asset.pack.update_gitignore()
    emit({"variant": f"{asset.address}:{new_name}"})


@variant_app.command("default")
def variant_default(target: str = typer.Argument(..., help="<pack>/<asset>:<variant>")):
    """Make a variant the asset's default."""
    variant = ws().target(target).need_variant()
    write_yaml(variant.asset.file, variant.asset.meta.model_copy(update={"default_variant": variant.name}))
    emit({"asset": variant.asset.address, "default_variant": variant.name})


@scene_app.command("new")
def scene_new(target: str = typer.Argument(..., help="<pack>/<scene>"), description: str = ""):
    """Create an empty scene file."""
    pack, name = asset_target(target)
    scene = wsp.new_scene(pack, name, description)
    emit({"scene": scene.address, "file": pack.ws.rel(scene.file)})


@app.command()
def rm(target: str = typer.Argument(..., help="an image path, <pack>/<asset> or <pack>/<asset>:<variant>"),
       views_only: bool = typer.Option(False, "--views-only", help="for a hero: delete only its views and masks")):
    """Delete an image (a hero with its views and masks), a variant or an asset."""
    w = ws()
    if target.endswith(".png"):
        image = w.image(target)
        removed = []
        if image.asset:
            for kind in ("views", "masks"):
                folder = image.asset.root / kind / (wsp.REJECTED if image.rejected else "") / image.path.stem
                if folder.exists():
                    shutil.rmtree(folder)
                    removed.append(w.rel(folder))
        if not views_only:
            for variant in image.variants:
                variant.save(variant.meta.model_copy(update={"reference": None}))
            for f in (image.path, image.meta_path):
                if f.exists():
                    f.unlink()
                    removed.append(w.rel(f))
        emit({"removed": removed})
        return
    t = w.target(target)
    if not t.asset:
        raise SlopolyError("bad_target", "use slopoly pack rm to delete a pack")
    if ":" in target:
        variant = t.variant
        if len(t.asset.variants()) == 1:
            raise SlopolyError("only_variant", f"{variant.address} is the asset's only variant; delete the asset instead")
        if t.asset.meta.default_variant == variant.name:
            raise SlopolyError("default_variant", f"{variant.address} is the default variant",
                               "make another variant the default first (slopoly variant default)")
        if users := wsp.scenes_using(variant):
            raise SlopolyError("in_use", f"{variant.address} is placed in scenes: {', '.join(users)}", scenes=users)
        shutil.rmtree(variant.root)
        removed = variant.address
    else:
        users = sorted({s for v in t.asset.variants() for s in wsp.scenes_using(v)})
        if users:
            raise SlopolyError("in_use", f"{t.asset.address} is placed in scenes: {', '.join(users)}", scenes=users)
        shutil.rmtree(t.asset.root)
        removed = t.asset.address
    t.pack.update_gitignore()
    emit({"removed": removed})


# --- builds ------------------------------------------------------------------------------------------------------

@app.command()
def build(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>], or 'use' to make an earlier build current"),
          use_target: Optional[str] = typer.Argument(None, metavar="[TARGET]", help="with 'use': the variant"),
          number: Optional[int] = typer.Argument(None, metavar="[N]", help="with 'use': the build number"),
          timeout: int = typer.Option(builds.DEFAULT_TIMEOUT, help="seconds before Blender is stopped")):
    """Build a variant's program.py in Blender: validate, score against the views, export. Or: build use <target> <n>."""
    if target == "use":
        if not use_target or number is None:
            raise SlopolyError("usage", "usage: slopoly build use <pack>/<asset>[:<variant>] <n>")
        emit(builds.use(ws().target(use_target).need_variant(), number))
        return
    emit(builds.build(ws().target(target).need_variant(), timeout))


@scene_app.command("build")
def scene_build(target: str = typer.Argument(..., help="<pack>/scenes/<scene>"),
                current: bool = typer.Option(False, "--current", help="set every build choice back to current first"),
                timeout: int = typer.Option(builds.DEFAULT_TIMEOUT)):
    """Combine the scene's placements into one model, with bounds, grounding and overlaps."""
    t = ws().target(target)
    if not t.scene:
        raise SlopolyError("bad_target", f"{target!r} is not <pack>/scenes/<scene>")
    emit(builds.build_scene(t.scene, current, timeout))


@app.command()
def export(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>]"),
           to: Path = typer.Option(..., "--to", help="folder to write into"),
           number: Optional[int] = typer.Option(None, "--build", help="build number (default: current)"),
           blend: bool = typer.Option(False, "--blend", help="also the Blender file")):
    """Write a build's GLB (current palette embedded), the palette variant textures and optionally the .blend."""
    emit(builds.export(ws().target(target).need_variant(), to, number, blend))


@palette_app.command("show")
def palette_show(pack: str):
    p = ws().pack(pack)
    emit({"palette": p.palette, "used": builds.roles_in_builds(p)})


@palette_app.command("add")
def palette_add(pack: str, role: str, color: str = typer.Argument(..., help="#rrggbb"),
                to: Optional[str] = typer.Option(None, "--to", help="second colour: makes a gradient")):
    """Add a role (named by usage, e.g. 'cart wood') in the next free slot."""
    emit(builds.palette_add(ws().pack(pack), role, color, to))


@palette_app.command("set")
def palette_set(pack: str, role: str, color: str, to: Optional[str] = typer.Option(None, "--to"),
                variant: Optional[str] = typer.Option(None, help="recolour in this palette variant only")):
    """Recolour a role; current builds are refreshed without rebuilding."""
    emit(builds.palette_set(ws().pack(pack), role, color, to, variant))


@palette_app.command("rm")
def palette_rm(pack: str, role: str):
    """Delete a role that no build uses."""
    emit(builds.palette_rm(ws().pack(pack), role))


@palette_app.command("variant")
def palette_variant(pack: str, name: str, remove: bool = typer.Option(False, "--rm", help="delete the variant")):
    """Create (or --rm) a palette variant; set its colours with palette set --variant."""
    emit(builds.palette_variant(ws().pack(pack), name, remove))


@palette_app.command("render")
def palette_render(pack: str):
    """Render the palette textures and refresh the current builds' models."""
    emit(builds.render_palette(ws().pack(pack)))


# --- generation --------------------------------------------------------------------------------------------------

@gen_app.command("anchor")
def gen_anchor(pack: str, prompt: str = typer.Option(..., help="scene description: several typical objects of the pack"),
               count: int = typer.Option(2, min=1, max=4), seed: Optional[int] = None):
    """Style anchor scene images from the pack's style text and style references."""
    from . import generate
    emit(generate.start_anchor(ws().pack(pack), prompt, count, seed))


@gen_app.command("hero")
def gen_hero(target: str = typer.Argument(..., help="<pack>/<asset>"),
             prompt: Optional[str] = typer.Option(None, help="object description (default: the asset's)"),
             count: int = typer.Option(2, min=1, max=4), seed: Optional[int] = None):
    """Hero images of an asset (one object, three-quarter front view) referencing the picked style anchors."""
    from . import generate
    emit(generate.start_hero(ws().target(target).need_variant().asset, prompt, count, seed))


@gen_app.command("revise")
def gen_revise(image: str, change: Optional[str] = typer.Option(None, help="what to change (empty: more of the same)"),
               count: int = typer.Option(2, min=1, max=4)):
    """New images from an anchor's or hero's generation, with a fresh seed and an optional change."""
    from . import generate
    emit(generate.start_revise(ws().image(image), change, count))


@gen_app.command("views")
def gen_views(hero: str = typer.Argument(..., help="a picked hero image, or <pack>/<asset>[:<variant>] for its reference"),
              front_yaw: Optional[float] = typer.Option(None, help="turn the front (degrees) and remake the views"),
              generator: Optional[str] = typer.Option(None, help="image-to-3D model: idol (default), trellis2 or pixal3d")):
    """A rough 3D reference mesh of the hero, scaled to the asset's size, and its metric front, side, top and back
    views with silhouettes."""
    from . import generate
    emit(generate.start_views(hero_ref(hero), front_yaw, generator))


@app.command()
def look(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>]"),
         from_: str = typer.Option("hero", "--from", help="front, back, left, right, side, top, bottom, hero, or "
                                                          "<yaw>,<pitch> in degrees (yaw from the front towards +X)"),
         region: Optional[str] = typer.Option(None, help="frame this part's 3D region (from slopoly segment)"),
         box: Optional[str] = typer.Option(None, help="frame this box: x0,y0,z0,x1,y1,z1 in metres"),
         zoom: float = typer.Option(1.0, help="move closer by this factor"),
         perspective: bool = typer.Option(False, help="perspective instead of orthographic"),
         with_build: bool = typer.Option(False, "--with-build", help="also render the current build, same camera"),
         build: Optional[int] = typer.Option(None, help="render this build number beside the reference")):
    """Close-up of the reference mesh from any direction, optionally beside the build: image paths, the camera and
    the framed bounds in metres."""
    from . import look as looks
    emit(looks.look(ws().target(target).need_variant(), from_, region, box, zoom, perspective, with_build, build))


@app.command()
def segment(hero: str = typer.Argument(..., help="a hero image, or <pack>/<asset>[:<variant>] for its reference"),
            parts: str = typer.Option(..., help="comma-separated parts: name, name@view, or name@view:x0,y0,x1,y1 "
                                                "to look only within a box (pixels, or fractions of the image)"),
            within: Optional[str] = typer.Option(None, help="look for the parts only within this part's masks"),
            no_3d: bool = typer.Option(False, "--no-3d", help="skip the 3D regions on the reference mesh")):
    """Part masks (bounds, areas, colours) in each view of a hero, and part regions on its reference mesh. Parts
    segmented before and not named again keep their masks."""
    from . import generate
    emit(generate.start_segment(hero_ref(hero), split_parts(parts), within, not no_3d))


def split_parts(text: str) -> list[str]:
    """Commas separate parts, except inside a box (name@view:x0,y0,x1,y1)."""
    out: list[str] = []
    for piece in text.split(","):
        if out and "@" in out[-1] and ":" in out[-1] and out[-1].count(",") < 3:
            out[-1] += "," + piece
        else:
            out.append(piece)
    return out


def hero_ref(value: str) -> wsp.ImageRef:
    w = ws()
    if value.endswith(".png"):
        return w.image(value)
    variant = w.target(value).need_variant()
    if not variant.reference:
        raise SlopolyError("no_reference", f"{variant.address} has no reference hero",
                           f"slopoly pick {variant.asset.address} --heroes")
    return variant.reference


# --- windows -----------------------------------------------------------------------------------------------------

@app.command()
def pick(target: Optional[str] = typer.Argument(None, help="<pack> (anchors) or <pack>/<asset> (heroes)"),
         anchors: bool = typer.Option(False, "--anchors", help="the pack's style anchors"),
         heroes: bool = typer.Option(False, "--heroes", help="the asset's heroes"),
         image: Optional[list[str]] = typer.Option(None, help="pick among these images instead (repeatable)"),
         question: Optional[str] = typer.Option(None, help="a question to ask the user"),
         option: Optional[list[str]] = typer.Option(None, help="an answer option for the question (repeatable)"),
         limit: Optional[int] = typer.Option(None, help="the most images the user may pick"),
         show_rejected: bool = typer.Option(False, help="also show rejected images"),
         set_: Optional[str] = typer.Option(None, "--set", metavar="IMAGE", help="no window: set this image's state"),
         state: Optional[str] = typer.Option(None, help="with --set: picked, rejected or undecided"),
         variant: Optional[str] = typer.Option(None, help="with --set on a hero: the variant it becomes the reference "
                                                          "of (created if new; default: the default variant)"),
         for_: Optional[str] = typer.Option(None, "--for", help="with --heroes: the variant whose reference the pick "
                                                                 "replaces (keeping its program and builds)")):
    """Open a window where the user picks images (or answers a question); images not picked are rejected. Each
    picked hero becomes the reference of its own variant. Returns a job id at once: slopoly wait <id> returns the
    choice. With --set, sets one image's state without a window."""
    from . import windows
    w = ws()
    if set_:
        ref = w.image(set_)
        if state == "rejected":
            emit({"rejected": [w.rel(ref.reject().path)]})
        elif state == "undecided":
            for v in ref.variants:
                v.save(v.meta.model_copy(update={"reference": None}))
            emit({"undecided": [w.rel(ref.restore("undecided").path)]})
        elif state == "picked":
            emit(windows.choose(w, [], [(ref, variant or (ref.asset.meta.default_variant if ref.asset else None))]))
        else:
            raise SlopolyError("usage", "--set needs --state picked, rejected or undecided")
        return
    if not target:
        raise SlopolyError("usage", "name a target: slopoly pick <pack> --anchors or slopoly pick <pack>/<asset> --heroes")
    t = w.target(target.partition(":")[0])
    kind = "anchors" if anchors or (not heroes and not t.asset) else "heroes"
    if kind == "heroes":
        t.need_variant()
        if for_ is not None and for_ not in [v.name for v in t.asset.variants()]:
            raise SlopolyError("not_found", f"{t.asset.address} has no variant {for_!r}",
                               variants=[v.name for v in t.asset.variants()])
    spec = {"pack": t.pack.name, "target": t.asset.address if t.asset else t.pack.name, "set": kind,
            "for": for_ if kind == "heroes" else None,
            "paths": image or None, "question": question, "options": option or None, "limit": limit,
            "show_rejected": show_rejected,
            "title": question or (f"Pick style anchors of {t.pack.name}" if kind == "anchors" else
                                  f"Pick heroes of {t.asset.address}")}
    emit(windows.start_pick(w, spec))


@app.command()
def view(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>] or <pack>/scenes/<scene>"),
         number: Optional[int] = typer.Option(None, "--build", help="a build number (default: the current build)")):
    """Open the 3D viewer with the build's comparison images and report. Returns at once."""
    from . import windows
    emit(windows.start_view(ws(), target, number))


@app.command()
def review(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>]"),
           number: Optional[int] = typer.Option(None, "--build", help="a build number (default: the current build)")):
    """Open the review window: the reference (hero image or reference mesh) beside the build, where the user paints
    on both and comments, as many notes as they like. Returns a job id and the window's address at once; slopoly wait
    <id> returns the notes with the parts their strokes hit."""
    from . import windows
    emit(windows.start_review(ws(), target, number))


@app.command()
def note(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>]"),
         number: int = typer.Argument(..., help="the note's number"),
         status: str = typer.Argument(..., help="addressed, wontfix or open"),
         by: Optional[int] = typer.Option(None, "--by", help="the build that addressed it"),
         reason: Optional[str] = typer.Option(None, help="what you changed, or why it won't be fixed")):
    """Set a review note's status. The next review shows addressed notes for the user to confirm or reopen."""
    from . import review as reviews
    emit(reviews.set_status(ws().target(target).need_variant(), number, status, by, reason))


@app.command()
def notes(target: str = typer.Argument(..., help="<pack>/<asset>[:<variant>]"),
          all_: bool = typer.Option(False, "--all", help="also closed and wontfix notes"),
          brief: bool = typer.Option(False, "--brief", help="only each note's number, status and comment")):
    """List a variant's review notes (open and addressed ones by default)."""
    from . import review as reviews
    variant = ws().target(target).need_variant()
    found = [{"number": n.number, "status": n.status, "comment": n.comment} if brief else reviews.summary(variant, n)
             for n in reviews.load_notes(variant).notes if all_ or n.status in ("open", "addressed")]
    emit({"variant": variant.address, "notes": found, "open": reviews.open_count(variant)})


# --- environment -------------------------------------------------------------------------------------------------

@app.command()
def doctor(fetch: bool = typer.Option(False, "--fetch", help="download missing models into comfyui.models_dir and "
                                                             "install the build libraries for Blender")):
    """Check ComfyUI (reachable, nodes, models), Blender (version, libraries) and settings, with a fix for each failure."""
    from . import doctor as checks_env
    result = checks_env.doctor(fetch)
    emit(result)
    if not result["ok"]:
        raise typer.Exit(1)


# --- jobs --------------------------------------------------------------------------------------------------------

@app.command()
def jobs(pack: Optional[str] = typer.Argument(None, help="<pack> (default: all packs)"),
         all_: bool = typer.Option(False, "--all", help="include finished jobs")):
    """List jobs with their states and progress (open ones only, unless --all)."""
    w = ws()
    out = []
    for p in [w.pack(pack)] if pack else w.packs():
        out += [job_runner.result_of(j) if all_ else job_runner.summary(j) for _, j in job_runner.jobs_of(p)
                if all_ or j.state not in job_runner.TERMINAL]
    emit({"jobs": out})


@app.command()
def wait(job: str, timeout: float = typer.Option(job_runner.DEFAULT_WAIT, help="seconds to wait before returning 'pending'")):
    """Wait for a job; returns its result, or state 'pending' on timeout (call again). Has no side effects."""
    emit(job_runner.wait(ws(), job, timeout))


@app.command()
def cancel(job: str):
    """Cancel a queued or running job (its ComfyUI prompts are dropped; nothing is written)."""
    emit(job_runner.cancel(ws(), job))


@app.command()
def retry(job: str):
    """Start a failed or cancelled job again with the same inputs."""
    emit(job_runner.retry(ws(), job))


@app.command("_job", hidden=True)
def job_process(path: Path):
    raise typer.Exit(job_runner.run(path))


@app.command("_sleep", hidden=True)
def sleep_cmd(pack: str, seconds: float = 1.0, fail: bool = False):
    """Start a job that only waits (checks that detached jobs work)."""
    emit(job_runner.start(ws().pack(pack), "sleep", pack, {"seconds": seconds, "fail": fail}))


# --- development -------------------------------------------------------------------------------------------------

@dev_app.command("test-blender", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def dev_test_blender(ctx: typer.Context):
    """Run tests_blender/ with pytest inside Blender (extra arguments go to pytest)."""
    import subprocess

    from . import blender
    tests = Path.cwd() / "tests_blender"
    if not tests.is_dir():
        raise SlopolyError("not_a_checkout", "run this from the root of a slopoly repository checkout")
    found = blender.find()
    if blender.missing_libs(found) or not (found.libs / "pytest").exists():
        blender.install_libs(found, ["pytest>=8.4"])
    status = subprocess.run(found.command("pytest", str(tests), "-p", "no:cacheprovider", *ctx.args)).returncode
    raise typer.Exit(status)


# --- settings ----------------------------------------------------------------------------------------------------

@config_app.command("show")
def config_show():
    """Show every setting with its value and where it comes from."""
    emit(config.describe())


@config_app.command("get")
def config_get(key: str):
    emit({key: config.get(key)})


@config_app.command("set")
def config_set(key: str, value: str = typer.Argument("", help="empty to unset")):
    config.set_(key, value or None)
    emit({key: config.get(key)})


def split_target_hint(args: list[str]) -> str | None:
    """For "<pack>/<asset> <variant>" given as two arguments: the command with them joined by ":"."""
    for i, (a, b) in enumerate(zip(args, args[1:])):
        target = a.count("/") == 1 and ":" not in a and not a.startswith("-")
        if target and m.NAME.fullmatch(b):
            joined = [*args[:i], f"{a}:{b}", *args[i + 2:]]
            return f"did you mean <pack>/<asset>:<variant>? slopoly {' '.join(joined)}"
    return None


def main() -> None:
    try:
        app(standalone_mode=False)
    except SlopolyError as error:
        emit(error.as_dict())
        sys.exit(error.status)
    except typer.TyperException as error:  # usage errors (typer's own click)
        if type(error).__name__ == "NoArgsIsHelpError":
            print(error.ctx.get_help() if getattr(error, "ctx", None) else str(error))
            sys.exit(0)
        message = error.format_message() if hasattr(error, "format_message") else str(error)
        emit({"error": message, "code": "usage", "hint": split_target_hint(sys.argv[1:]) or "run the command with --help"})
        sys.exit(1)
    except typer.Exit as done:
        sys.exit(done.exit_code)
    except typer.Abort:
        sys.exit(1)
