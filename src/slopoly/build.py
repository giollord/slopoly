"""Builds (part programs in Blender), scene builds, palette refreshes and exports."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import blender
from . import models as m
from .blender.slopoly_model import glb
from .blender.slopoly_model import palette as pal
from .core import SlopolyError, load, write_atomic, write_yaml
from .workspace import REJECTED, Pack, Scene, Variant, build_dirs

DEFAULT_TIMEOUT = 300


def run_blender(mode: str, folder: Path, timeout: int) -> int:
    runner = blender.require_ready()
    log = folder / "blender.log"
    with log.open("w", encoding="utf-8") as out:
        try:
            process = subprocess.run(runner.command(mode, str(folder)), stdout=out, stderr=subprocess.STDOUT,
                                     timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SlopolyError("build_timeout", f"Blender did not finish within {timeout} s",
                               "simplify the program (lower counts and resolutions) or pass --timeout") from None
    return process.returncode


def log_tail(folder: Path) -> str:
    path = folder / "blender.log"
    return path.read_text(encoding="utf-8", errors="replace")[-3000:] if path.exists() else ""


def palette_entries(pack: Pack, variant: str | None = None) -> list[dict]:
    palette = pack.palette
    entries = palette.variant_entries(variant) if variant else palette.entries
    return [e.for_build() for e in entries]


def reference_inputs(variant: Variant) -> tuple[list[dict], list[dict], str | None]:
    """The reference hero's views and masks (absolute paths) for the runner; part "object" is a view's silhouette."""
    reference = variant.meta.reference
    if not reference:
        return [], [], "the variant has no reference hero (pick one with slopoly pick)"
    asset = variant.asset
    views = asset.views(reference)
    if not views:
        return [], [], f"the reference hero {reference} has no views yet (run slopoly gen views)"
    folder = asset.views_dir(reference)
    view_inputs = [{"view": v.view, "path": str(folder / v.image), **({"fit": v.fit.model_dump()} if v.fit else {})}
                   for v in views.views]
    masks = [{"part": "object", "view": v.view, "path": str(folder / v.mask)} for v in views.views]
    if parts := asset.masks(reference):
        mask_folder = asset.masks_dir(reference)
        masks += [{"part": k.part, "view": k.view, "path": str(mask_folder / k.path), "colors": k.colors}
                  for k in parts.masks if k.part != "object"]
    return view_inputs, masks, None


def build(variant: Variant, timeout: int = DEFAULT_TIMEOUT) -> dict:
    ws = variant.pack.ws
    source = variant.program_file.read_text(encoding="utf-8") if variant.program_file.exists() else ""
    if not source.strip() or all(line.strip().startswith("#") for line in source.splitlines() if line.strip()):
        raise SlopolyError("no_program", f"{ws.rel(variant.program_file)} has no program yet",
                           "write the part program (see the skill's modelling reference)")
    blender.require_ready()
    number = variant.next_build()
    folder = variant.build_dir(number)
    folder.mkdir(parents=True)
    shutil.copy2(variant.program_file, folder / "program.py")
    views, masks, no_views = reference_inputs(variant)
    pack = variant.pack
    job = {"source": source, "polyBudget": variant.asset.budget, "shading": pack.meta.shading.for_build(),
           "palette": palette_entries(pack), "masks": masks, "views": views, "noViewsReason": no_views}
    write_atomic(folder / "job.json", json.dumps(job, indent=1))
    status = run_blender("build", folder, timeout)
    report_file = folder / "report.json"
    if not report_file.exists():
        log = log_tail(folder)
        raise SlopolyError("blender_failed", f"Blender exited with status {status} without a report",
                           "see the log; run slopoly doctor", build=number, log=log, folder=ws.rel(set_aside(folder)))
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if "error" in report:
        where = f"line {report['line']}: " if report.get("line") else ""
        rejected = set_aside(folder)
        raise SlopolyError("program_error", f"program error at {where}{report['error']}",
                           "fix program.py and build again", status=2, build=number, line=report.get("line"),
                           program=ws.rel(rejected / "program.py"))
    if (compared := compare_reference(variant, folder)) is not None:
        report["compare3d"] = compared
        write_atomic(report_file, json.dumps(report))
    meta = variant.meta
    variant.save(meta.model_copy(update={"current": number}))
    return result(variant, number, report)


def compare_reference(variant: Variant, folder: Path) -> dict | None:
    """The build compared in 3D with its reference hero's reference mesh, when both exist."""
    from . import compare3d
    from . import meshview as mv
    hero = variant.meta.reference
    views = variant.asset.views(hero) if hero else None
    mesh = variant.asset.views_dir(hero) / views.mesh if views and views.mesh else None
    if mesh is None or not mesh.exists() or not (folder / "model.glb").exists():
        return None
    return compare3d.compare(mv.load_glb((folder / "model.glb").read_bytes()), mv.load_glb(mesh.read_bytes()))


def set_aside(folder: Path) -> Path:
    """Moves a failed build into builds/rejected/ (git-ignored); its number stays used."""
    target = folder.parent / REJECTED / folder.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(folder, target)
    return target


def result(variant: Variant, number: int, report: dict) -> dict:
    ws = variant.pack.ws
    folder = variant.build_dir(number)
    silhouette = report.get("silhouette") or {}
    for score in silhouette.get("views", []):
        for key in ("render", "compare"):
            if score.get(key):
                score[key] = ws.rel(folder / score[key])
    counted = ((report.get("validation") or {}).get("triangles") or {}).get("count")
    triangles = counted if counted is not None else sum(p.get("triangles", 0) for p in report.get("parts", []))
    parts = [{k: p[k] for k in ("name", "triangles", "booleans", "warnings") if p.get(k)}
             for p in report.get("parts", [])]
    return {"build": number, "variant": variant.address, "current": variant.meta.current == number,
            "validated": report.get("validated"), "triangles": triangles, "budget": variant.asset.budget,
            "parts": parts,
            "bounds": report.get("bounds"), "validation": report.get("validation"), "silhouette": silhouette,
            "compare3d": report.get("compare3d"),
            "colors": report.get("colors"), "palette": report.get("palette"), "shading": report.get("shading"),
            "files": {"model": ws.rel(folder / "model.glb"), "blend": ws.rel(folder / "model.blend"),
                      "report": ws.rel(folder / "report.json"), "program": ws.rel(folder / "program.py")}}


def use(variant: Variant, number: int) -> dict:
    folder = variant.build_dir(number)
    if not (folder / "model.glb").exists():
        raise SlopolyError("not_found", f"build {number} of {variant.address} has no model",
                           builds=[n for n, d in variant.builds() if (d / "model.glb").exists()])
    shutil.copy2(folder / "program.py", variant.program_file)
    variant.save(variant.meta.model_copy(update={"current": number}))
    return {"variant": variant.address, "current": number, "program": variant.pack.ws.rel(variant.program_file)}


def chosen_build(scene: Scene, meta: m.Scene, placement: m.Placement) -> tuple[Variant, int]:
    asset = scene.pack.asset(placement.asset)
    variant = asset.variant(placement.variant)
    choice = meta.builds.get(f"{asset.name}:{variant.name}", meta.builds.get(asset.name, "current")) \
        if variant.name == asset.meta.default_variant else meta.builds.get(f"{asset.name}:{variant.name}", "current")
    number = variant.meta.current if choice == "current" else choice
    if number is None:
        raise SlopolyError("not_built", f"asset {asset.name!r} ({variant.name}) has no build", "build it first",
                           asset=asset.name, variant=variant.name)
    if not (variant.build_dir(number) / "model.glb").exists():
        raise SlopolyError("version_without_build", f"build {number} of asset {asset.name!r} ({variant.name}) has no model",
                           asset=asset.name, variant=variant.name, build=number)
    return variant, number


def build_scene(scene: Scene, current: bool = False, timeout: int = DEFAULT_TIMEOUT) -> dict:
    meta = scene.meta
    if current and meta.builds:
        meta = meta.model_copy(update={"builds": {}})
        write_yaml(scene.file, meta)
    if not meta.placements:
        raise SlopolyError("empty_scene", f"scene {scene.name!r} has no placements", "add placements to its file")
    placements = []
    for p in meta.placements:
        variant, number = chosen_build(scene, meta, p)
        placements.append({"name": p.name, "path": str(variant.build_dir(number) / "model.glb"), "at": list(p.at),
                           "rot": list(p.rot), "scale": p.scale,
                           "asset": variant.asset.name, "variant": variant.name, "build": number})
    dirs = build_dirs(scene.builds_dir)
    number = (dirs[-1][0] + 1) if dirs else 1
    folder = scene.builds_dir / f"{number:04d}"
    folder.mkdir(parents=True)
    write_atomic(folder / "scene.json", json.dumps({"placements": placements}, indent=1))
    status = run_blender("scene", folder, timeout)
    if status != 0 or not (folder / "report.json").exists():
        raise SlopolyError("blender_failed", f"the scene build failed (status {status})", log=log_tail(folder))
    scene.pack.update_gitignore()
    ws = scene.pack.ws
    return {"scene": scene.address, "build": number, "model": ws.rel(folder / "scene.glb"),
            "placements": [{k: p[k] for k in ("name", "asset", "variant", "build")} for p in placements],
            "report": json.loads((folder / "report.json").read_text(encoding="utf-8"))}


# --- palette -----------------------------------------------------------------------------------------------------

def render_palette(pack: Pack) -> dict:
    """Renders the main and variant textures and refreshes every current build's GLB and palette image."""
    palette = pack.palette
    if problems := palette.problems():
        raise SlopolyError("invalid_palette", "the palette is not valid", "fix palette.yaml or use the palette commands",
                           problems=[{"file": pack.ws.rel(pack.palette_file)} | p for p in problems])
    pack.palette_dir.mkdir(parents=True, exist_ok=True)
    main = pal.render([pal.Entry.parse(e) for e in palette_entries(pack)])
    main_path = pack.palette_dir / "main.png"
    main.save(main_path)
    textures = {"main": pack.ws.rel(main_path)}
    for name in palette.variants:
        path = pack.palette_dir / f"{name}.png"
        pal.render([pal.Entry.parse(e) for e in palette_entries(pack, name)]).save(path)
        textures[name] = pack.ws.rel(path)
    for stale in pack.palette_dir.glob("*.png"):
        if stale.stem != "main" and stale.stem not in palette.variants:
            stale.unlink()
    png = main_path.read_bytes()
    refreshed = []
    for asset in pack.assets():
        for variant in asset.variants():
            if (current := variant.meta.current) is None:
                continue
            folder = variant.build_dir(current)
            if (model := folder / "model.glb").exists():
                write_atomic(model, glb.replace_image(model.read_bytes(), png))
                write_atomic(folder / "palette.png", png)
                refreshed.append(variant.address)
    return {"textures": textures, "refreshed": refreshed}


def roles_in_builds(pack: Pack) -> dict[str, list[str]]:
    used: dict[str, list[str]] = {}
    for asset in pack.assets():
        for variant in asset.variants():
            for _, folder in variant.builds():
                report = folder / "report.json"
                if report.exists():
                    for role in (json.loads(report.read_text(encoding="utf-8")).get("palette") or {}).get("roles", []):
                        used.setdefault(role, [])
                        if variant.address not in used[role]:
                            used[role].append(variant.address)
    return used


def free_slot(palette: m.Palette, kind: str) -> int:
    taken = {e.slot for e in palette.entries if e.kind == kind}
    limit = m.SOLID_SLOTS if kind == "solid" else m.GRADIENT_SLOTS
    for slot in range(limit):
        if slot not in taken:
            return slot
    raise SlopolyError("palette_full", f"all {limit} {kind} slots are used")


def palette_add(pack: Pack, role: str, color: str, color2: str | None) -> dict:
    palette = pack.palette
    if any(e.role == role for e in palette.entries):
        raise SlopolyError("exists", f"role {role!r} already exists", "use slopoly palette set to recolour it")
    kind = "gradient" if color2 else "solid"
    entry = m.PaletteEntry(role=role, kind=kind, slot=free_slot(palette, kind), color=color, color2=color2)
    palette.entries.append(entry)
    pack.save_palette(palette)
    return {"added": entry} | render_palette(pack)


def palette_set(pack: Pack, role: str, color: str, color2: str | None, variant: str | None) -> dict:
    palette = pack.palette
    entry = next((e for e in palette.entries if e.role == role), None)
    if entry is None:
        raise SlopolyError("not_found", f"role {role!r} is not in the palette", roles=[e.role for e in palette.entries])
    if variant:
        if variant not in palette.variants:
            raise SlopolyError("not_found", f"palette variant {variant!r} does not exist", variants=list(palette.variants))
        palette.variants[variant][role] = m.Colours(color=color, color2=color2 if entry.kind == "gradient" else None)
    else:
        if entry.kind == "gradient" and not color2:
            color2 = entry.color2
        entry.color, entry.color2 = m.check_hex(color), m.check_hex(color2) if entry.kind == "gradient" else None
    pack.save_palette(m.Palette.model_validate(palette.model_dump()))
    return {"role": role, "variant": variant} | render_palette(pack)


def palette_rm(pack: Pack, role: str) -> dict:
    palette = pack.palette
    if not any(e.role == role for e in palette.entries):
        raise SlopolyError("not_found", f"role {role!r} is not in the palette")
    if users := roles_in_builds(pack).get(role):
        raise SlopolyError("in_use", f"role {role!r} is used by builds of: {', '.join(users)}", assets=users)
    palette.entries = [e for e in palette.entries if e.role != role]
    for colours in palette.variants.values():
        colours.pop(role, None)
    pack.save_palette(palette)
    return {"removed": role} | render_palette(pack)


def palette_variant(pack: Pack, name: str, remove: bool = False) -> dict:
    palette = pack.palette
    if remove:
        if palette.variants.pop(name, None) is None:
            raise SlopolyError("not_found", f"palette variant {name!r} does not exist")
    else:
        if name in palette.variants:
            raise SlopolyError("exists", f"palette variant {name!r} already exists")
        palette.variants[name] = {}
    pack.save_palette(palette)
    return {"variant": name, "removed": remove} | render_palette(pack)


# --- export ------------------------------------------------------------------------------------------------------

def export(variant: Variant, to: Path, number: int | None = None, blend: bool = False) -> dict:
    number = number if number is not None else variant.meta.current
    if number is None:
        raise SlopolyError("not_built", f"{variant.address} has no current build", "build it first")
    folder = variant.build_dir(number)
    if not (folder / "model.glb").exists():
        raise SlopolyError("not_found", f"build {number} of {variant.address} has no model")
    pack = variant.pack
    render_palette(pack)
    to.mkdir(parents=True, exist_ok=True)
    name = variant.asset.name if variant.name == variant.asset.meta.default_variant else f"{variant.asset.name}-{variant.name}"
    main = (pack.palette_dir / "main.png").read_bytes()
    files = [to / f"{name}.glb"]
    write_atomic(files[0], glb.replace_image((folder / "model.glb").read_bytes(), main))
    write_atomic(to / "palette.png", main)
    files.append(to / "palette.png")
    for texture in sorted(pack.palette_dir.glob("*.png")):
        if texture.stem != "main":
            shutil.copy2(texture, to / f"palette_{texture.stem}.png")
            files.append(to / f"palette_{texture.stem}.png")
    if blend:
        if not (folder / "model.blend").exists():
            raise SlopolyError("no_blend", f"build {number} of {variant.address} has no Blender file",
                               "rebuild its program to make one")
        shutil.copy2(folder / "model.blend", to / f"{name}.blend")
        files.append(to / f"{name}.blend")
    return {"variant": variant.address, "build": number, "files": [f.as_posix() for f in files]}
