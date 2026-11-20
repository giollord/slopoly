"""Image generation on the user's ComfyUI: style anchors, heroes, revisions, views and part segmentation.

The ``start_*`` functions check the request and start a detached job; the job kinds below run the workflows and write
images with their metadata only when everything succeeded (a cancelled or failed job attaches nothing).
"""

from __future__ import annotations

import io
import json
import random
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from . import jobs
from . import meshview as mv
from . import reference
from . import segmentation as seg
from . import models as m
from .comfy import colors
from .comfy import workflow
from .comfy.client import ComfyClient
from .core import SlopolyError, write_yaml
from .workspace import Asset, ImageRef, Pack, images, next_name

MAX_REFERENCES = 3
MIN_MASK_SHARE = 0.002  # a "found" part covers at least 0.2 % of its view
WHOLE_OBJECT_IOU = 0.9
# SAM 3 keeps only the best object per text prompt unless the prompt says "name:N"; a view can show several of a part
# (both wheels, both handles), so every part asks for up to this many and gets their union.
MAX_INSTANCES = 8
HERO_IMAGE = ("ONE object only, whole and centred: {0}. Three-quarter front view from the front-left, slightly from "
              "above, with the whole object in frame. No smoke, steam, fire, sparks, dust or other particles. Plain "
              "light grey background, nothing else in the image.")


def style_text(pack: Pack) -> str:
    """The '# Style' section of style.md (the whole file when it has no such heading)."""
    text = pack.style()
    match = re.search(r"^#\s*Style\s*$(.*?)(?=^#\s|\Z)", text, re.M | re.S | re.I)
    return (match.group(1) if match else text).strip()


def rel(pack: Pack, path: Path) -> str:
    return path.resolve().relative_to(pack.ws.root).as_posix()


def count_of(count: int) -> int:
    if not 1 <= count <= 4:
        raise SlopolyError("bad_count", "count must be 1 to 4")
    return count


# --- starting jobs -----------------------------------------------------------------------------------------------

def start_anchor(pack: Pack, description: str, count: int = 2, seed: int | None = None) -> dict:
    refs = [rel(pack, p) for p, _ in images(pack.style_dir, ("undecided", "picked"))][:MAX_REFERENCES]
    prompt = "\n\n".join(t for t in (style_text(pack), description.strip()) if t)
    inputs = {"workflow": "style-anchor", "kind": "anchor", "prompt": prompt, "references": refs,
              "count": count_of(count), "seed": seed, "folder": rel(pack, pack.anchors_dir), "prefix": "anchor"}
    return jobs.start(pack, "generate", pack.name, inputs)


def picked_anchors(pack: Pack) -> list[str]:
    picked = [p for p, _ in images(pack.anchors_dir, ("picked",))]
    return [rel(pack, p) for p in sorted(picked, reverse=True)][:MAX_REFERENCES]


def start_hero(asset: Asset, description: str | None = None, count: int = 2, seed: int | None = None) -> dict:
    pack = asset.pack
    anchors = picked_anchors(pack)
    if not anchors:
        raise SlopolyError("no_picked_anchor", f"pack {pack.name!r} has no picked style anchor",
                           f"pick one: slopoly pick {pack.name} --anchors")
    style = style_text(pack)
    prompt = HERO_IMAGE.format(description or f"{asset.name}, {asset.meta.description}".strip(", ")) + (
        f" Style notes for colours and materials only: {style}" if style else "")
    asset.heroes_dir.mkdir(parents=True, exist_ok=True)
    inputs = {"workflow": "hero", "kind": "hero", "prompt": prompt, "references": anchors, "count": count_of(count),
              "seed": seed, "folder": rel(pack, asset.heroes_dir), "prefix": "hero"}
    return jobs.start(pack, "generate", asset.address, inputs)


def start_revise(image: ImageRef, change: str | None, count: int = 2) -> dict:
    meta = image.meta
    if meta.kind not in ("anchor", "hero") or not meta.prompt:
        raise SlopolyError("not_revisable", "only generated anchors and heroes can be revised")
    prompt, refs = meta.prompt, list(meta.references)
    own = rel(image.pack, image.path)
    if change and change.strip():
        prompt = f"{prompt}\n\nChange: {change.strip()}"
        refs = [own, *[r for r in refs if r != own]][:MAX_REFERENCES]
    inputs = {"workflow": "style-anchor" if meta.kind == "anchor" else "hero", "kind": meta.kind, "prompt": prompt,
              "references": refs, "count": count_of(count), "seed": None,
              "folder": rel(image.pack, image.path.parent.parent if image.rejected else image.path.parent),
              "prefix": meta.kind, "source": own, "change": change.strip() if change else None}
    target = image.asset.address if image.asset else image.pack.name
    return jobs.start(image.pack, "generate", target, inputs)


def hero_of(image: ImageRef) -> tuple[ImageRef, m.Image]:
    meta = image.meta
    if meta.kind != "hero" or image.asset is None:
        raise SlopolyError("not_a_hero", "views and segmentation work on hero images")
    if image.rejected:
        raise SlopolyError("hero_rejected", "this hero was rejected by the user")
    return image, meta


# Image-to-3D generators for the reference mesh: workflow and the values that select the generator in it.
GENERATORS = {"trellis2": ("reference-mesh", {"trellis2": True}), "pixal3d": ("reference-mesh", {"trellis2": False}),
              "idol": ("idol-mesh", {})}
DEFAULT_GENERATOR = "idol"
GENERATED, HERO_MASK, MESH = "generated.glb", "hero_mask.png", "reference.glb"


def start_views(image: ImageRef, front_yaw: float | None = None, generator: str | None = None) -> dict:
    image, meta = hero_of(image)
    if not image.variants:
        raise SlopolyError("hero_not_picked", "the hero must be picked (a variant's reference) before making its views",
                           f"pick it: slopoly pick {image.asset.address} --heroes")
    if generator is not None and generator not in GENERATORS:
        raise SlopolyError("unknown_generator", f"no generator {generator!r}", f"use one of {', '.join(GENERATORS)}")
    old = image.asset.views(image.path.name)
    folder = image.asset.views_dir(image.path.name)
    # a new front or a new size only re-places the mesh already generated
    reuse = (front_yaw is not None and old is not None and old.generated is not None
             and (folder / old.generated).exists() and generator in (None, old.generator))
    seed = old.seed if reuse and old.seed is not None else random.randrange(1, 2**48)
    inputs = {"hero": rel(image.pack, image.path), "seed": seed, "reuse": reuse,
              "generator": (old.generator if reuse else None) or generator or DEFAULT_GENERATOR,
              "front_yaw": None if front_yaw is None else (front_yaw + 180) % 360 - 180}
    return jobs.start(image.pack, "views", image.asset.address, inputs)


def start_segment(image: ImageRef, parts: list[str], within: str | None = None, vote: bool = True) -> dict:
    image, meta = hero_of(image)
    views = image.asset.views(image.path.name)
    if not views:
        raise SlopolyError("no_views", "make the hero's views before segmenting it",
                           f"slopoly gen views {image.pack.ws.rel(image.path)}")
    specs = [seg.parse(p) for p in parts if p.strip() and p.strip() != "object"]
    if not specs:
        raise SlopolyError("no_parts", "name at least one part to segment")
    if within is not None:
        old = image.asset.masks(image.path.name)
        boxes = {k.view: k.bounds for k in (old.masks if old else []) if k.part == within and k.bounds}
        if not boxes:
            raise SlopolyError("no_mask", f"no mask of {within!r} to segment within",
                               f"segment it first: slopoly segment {image.asset.address} --parts {within}")
        specs = [seg.PartSpec(s.part, view, (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]))
                 for s in specs for view, b in boxes.items() if s.view in (None, view)]
    return jobs.start(image.pack, "segment", image.asset.address,
                      {"hero": rel(image.pack, image.path), "parts": [s.as_dict() for s in specs],
                       "vote": bool(vote and views.mesh)})


# --- running jobs ------------------------------------------------------------------------------------------------

def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def mask_png(mask: np.ndarray) -> bytes:
    return png_bytes(Image.fromarray((mask * 255).astype("uint8"), "L"))


def mask_of(data: bytes) -> np.ndarray:
    return colors.mask_array(Image.open(io.BytesIO(data)))


def box(mask: np.ndarray) -> dict[str, int] | None:
    found = colors.bounds(mask)
    return None if found is None else {"x": found[0], "y": found[1], "width": found[2], "height": found[3]}


class Runner:
    """Runs workflows for one job: uploads inputs, records prompt ids for cancelling, reports progress."""

    def __init__(self, context: jobs.JobContext, client: ComfyClient | None = None):
        self.context, self.client = context, client or ComfyClient.from_config()
        self.client.system_stats()

    def upload(self, path: Path) -> str:
        return self.client.upload(path.read_bytes(), f"{self.context.job.id}_{path.name}")

    def placeholder(self) -> str:
        return self.client.upload(png_bytes(Image.new("RGB", (64, 64))), "placeholder.png")

    def run(self, name: str, values: dict[str, Any], share: tuple[float, float] = (0.0, 1.0)) -> dict[str, list[bytes]]:
        """Runs a workflow; returns file bytes (images, or GLB meshes) per output name. ``share`` is this run's
        (start, span) of progress."""
        prompt = workflow.load(name)
        start, span = share
        self.context.progress(start)
        outputs = self.client.run(workflow.fill(prompt, values), lambda p: self.context.progress(start + span * p),
                                  self.context.remember_prompt)
        named = workflow.outputs(prompt)
        return {named[node]: [self.client.image(item) for item in out.get("images", []) + out.get("3d", [])]
                for node, out in outputs.items() if node in named}


def write_outputs(context: jobs.JobContext, files: dict[Path, bytes | Any]) -> None:
    """Writes all outputs only after a last cancellation check; YAML values are models or dicts."""
    context.check()
    for path, value in files.items():
        if isinstance(value, bytes):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        else:
            write_yaml(path, value)


@jobs.kind("generate")
def generate(context: jobs.JobContext, client: ComfyClient | None = None) -> dict:
    inputs, ws = context.inputs, context.ws
    runner = Runner(context, client)
    name = workflow.image_workflow(inputs["workflow"])
    slots = workflow.reference_slots(workflow.load(name))
    refs = list(inputs.get("references") or [])[:len(slots)]  # an image model without references uses none
    values: dict[str, Any] = {"prompt": inputs["prompt"], "use_references": bool(refs)}
    for i, slot in enumerate(slots):
        if i < len(refs):
            values[f"reference_{slot}"] = runner.upload(ws.root / refs[i])
            values[f"use_reference_{slot}"] = True
        else:
            values[f"reference_{slot}"] = runner.placeholder()
            values[f"use_reference_{slot}"] = False
    count = int(inputs.get("count") or 1)
    seed = inputs.get("seed")
    seed = int(seed) if seed is not None else random.randrange(2**48)
    produced = []
    for i in range(count):
        out = runner.run(name, {**values, "seed": seed + i}, (i / count, 1 / count))
        produced += [(data, seed + i) for data in out.get("image", [])]
    if not produced:
        raise SlopolyError("bad_workflow", f"the {name} workflow produced no image (it needs out:image)")
    folder = ws.root / inputs["folder"]
    context.check()
    first = int(next_name(folder, inputs["prefix"]).stem.rsplit("_", 1)[1])
    files, results = {}, []
    for i, (data, image_seed) in enumerate(produced):
        path = folder / f"{inputs['prefix']}_{first + i:03d}.png"
        size = Image.open(io.BytesIO(data)).size
        files[path] = data
        files[path.with_suffix(".yaml")] = m.Image(
            kind=inputs["kind"], prompt=inputs["prompt"], change=inputs.get("change"), seed=image_seed,
            references=refs, source=inputs.get("source"), job=context.job.id, width=size[0], height=size[1])
        results.append({"path": ws.rel(path), "seed": image_seed, "width": size[0], "height": size[1]})
    write_outputs(context, files)
    return {"images": results}


def view_files(asset: Asset, hero: str, generated: bytes, hero_mask: np.ndarray, hero_rgb: np.ndarray,
               front_yaw: float | None, base: dict) -> tuple[dict[Path, Any], m.Views]:
    """The reference mesh placed in the asset's frame (oriented against the hero unless ``front_yaw`` is given, and
    scaled to the asset's size) and its four metric views with silhouettes, as files for the hero's views folder."""
    mesh = mv.load_glb(generated)
    if front_yaw is None:
        found = reference.orient(mesh, hero_rgb, hero_mask)
        yaw, mirrored, how = found["yaw"], found["mirrored"], found["how"]
    else:
        old = asset.views(hero)
        yaw, mirrored, how = front_yaw, bool(old and old.placement and old.placement.mirrored), "given"
    size = asset.meta.size
    placement, scale_how = reference.place(mesh, yaw, mirrored, size.model_dump() if size else None)
    placed = mesh.transformed(placement.matrix())
    folder = asset.views_dir(hero)
    files: dict[Path, Any] = {folder / GENERATED: generated, folder / HERO_MASK: mask_png(hero_mask),
                              folder / MESH: mv.write_glb(placed)}
    out = []
    for view, (rgb, mask, info) in reference.render_views(placed).items():
        files[folder / f"{view}.png"] = png_bytes(Image.fromarray(rgb))
        files[folder / f"{view}_mask.png"] = mask_png(mask)
        out.append(m.View(view=view, image=f"{view}.png", mask=f"{view}_mask.png", width=rgb.shape[1],
                          height=rgb.shape[0], bounds=box(mask), **info))
    meta = m.Views(hero=hero, front_yaw=yaw, front=how, views=out, mesh=MESH, generated=GENERATED,
                   placement=m.MeshPlacement(yaw=placement.yaw, mirrored=placement.mirrored, scale=placement.scale,
                                         offset=list(placement.offset)),
                   mirrored=mirrored, scale=scale_how, size=size, **base)
    files[folder / "views.yaml"] = meta
    return files, meta


def resize(asset: Asset, size: m.Size) -> dict:
    """Sets the asset's size and rescales every hero's reference mesh and views to it. The views are framed to the
    object, so their images and masks stay the same; their metres per pixel and fits change."""
    meta = asset.meta
    meta.size = size
    write_yaml(asset.file, meta)
    rescaled = []
    for hero in sorted(p.name for p in asset.heroes_dir.glob("*.png")):
        views, folder = asset.views(hero), asset.views_dir(hero)
        if views is None or views.generated is None or not (folder / views.generated).exists():
            continue
        files, new = view_files(asset, hero, (folder / views.generated).read_bytes(),
                                colors.mask_array(Image.open(folder / HERO_MASK)),
                                np.asarray(Image.open(asset.heroes_dir / hero).convert("RGB")), views.front_yaw,
                                {"seed": views.seed, "job": views.job, "generator": views.generator})
        new.front = views.front  # the front is unchanged by a new size
        files[folder / "views.yaml"] = new
        for path, value in files.items():
            if isinstance(value, bytes):
                path.write_bytes(value)
            else:
                write_yaml(path, value)
        rescaled.append(views_result(asset.pack.ws, asset, asset.heroes_dir / hero, new))
    return {"asset": asset.address, "size": size.model_dump(), "rescaled": rescaled}


def views_result(ws, asset: Asset, hero_path: Path, meta: m.Views) -> dict:
    folder = asset.views_dir(hero_path.name)
    return {"hero": ws.rel(hero_path), "generator": meta.generator, "front_yaw": meta.front_yaw, "front": meta.front,
            "mirrored": meta.mirrored, "scale": meta.scale,
            "size": meta.size.model_dump() if meta.size else None, "mesh": ws.rel(folder / meta.mesh),
            "views": [{"view": v.view, "image": ws.rel(folder / v.image), "mask": ws.rel(folder / v.mask),
                       "width": v.width, "height": v.height, "bounds": v.bounds, "m_per_px": v.m_per_px,
                       "axes": v.axes, "ground_row": v.ground_row} for v in meta.views],
            **({} if meta.size else {"hint": f"no size stated: the mesh is {reference.DEFAULT_SIZE:g} m long. State "
                                             f"the real size: slopoly asset size {asset.address} <metres>"})}


@jobs.kind("views")
def make_views(context: jobs.JobContext, client: ComfyClient | None = None) -> dict:
    inputs, ws = context.inputs, context.ws
    hero = ws.image(inputs["hero"])
    folder = hero.asset.views_dir(hero.path.name)
    generator = inputs.get("generator") or DEFAULT_GENERATOR
    if inputs.get("reuse"):
        generated = (folder / GENERATED).read_bytes()
        hero_mask = colors.mask_array(Image.open(folder / HERO_MASK))
    else:
        runner = Runner(context, client)
        name, values = GENERATORS[generator]
        produced = runner.run(name, {"image": runner.upload(hero.path), "seed": int(inputs["seed"]), **values},
                              (0.0, 0.85))
        if not produced.get("mesh") or not produced.get("hero_mask"):
            raise SlopolyError("bad_workflow", f"the {name} workflow produced no mesh (it needs out:mesh and "
                               "out:hero_mask)")
        generated, hero_mask = produced["mesh"][0], mask_of(produced["hero_mask"][0])
    context.progress(0.9)
    hero_rgb = np.asarray(Image.open(hero.path).convert("RGB"))
    files, meta = view_files(hero.asset, hero.path.name, generated, hero_mask, hero_rgb, inputs.get("front_yaw"),
                             {"seed": int(inputs["seed"]), "job": context.job.id, "generator": generator})
    context.check()
    for stale in (folder, hero.asset.masks_dir(hero.path.name)):  # new views replace the old ones and their masks
        if stale.exists():
            shutil.rmtree(stale)
    write_outputs(context, files)
    return views_result(ws, hero.asset, hero.path, meta)


@jobs.kind("segment")
def segment(context: jobs.JobContext, client: ComfyClient | None = None) -> dict:
    inputs, ws = context.inputs, context.ws
    hero = ws.image(inputs["hero"])
    asset = hero.asset
    views = asset.views(hero.path.name)
    specs = [seg.PartSpec(p["part"], p.get("view"), tuple(p["box"]) if p.get("box") else None)
             if isinstance(p, dict) else seg.PartSpec(p) for p in inputs["parts"]]
    names = list(dict.fromkeys(s.part for s in specs))
    runner = Runner(context, client)
    views_folder, folder = asset.views_dir(hero.path.name), asset.masks_dir(hero.path.name)
    mesh = mv.load_glb((views_folder / views.mesh).read_bytes()) if inputs.get("vote") and views.mesh else None
    votes = seg.Votes(mesh) if mesh is not None else None
    runs = max(len(views.views) * len(specs) + (len(seg.VOTE_DIRECTIONS) * len(names) if votes else 0), 1)
    done = 0
    files: dict[Path, Any] = {}
    masks, missing = [], []

    def detect(image: Image.Image, part: str, region=None) -> np.ndarray | None:
        """The part's mask in the image (within ``region``, on an enlarged crop), or None when not found."""
        nonlocal done
        target = image if region is None else seg.crop(image, region)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"segment_{done}.png"
            target.save(path)
            produced = runner.run("segment-parts", {"image": runner.upload(path), "prompt": f"{part}:{MAX_INSTANCES}"},
                                  (done / runs, 1 / runs))
        done += 1
        data = (produced.get("mask") or [None])[0]
        if not data:
            return None
        mask = colors.mask_array(Image.open(io.BytesIO(data)).resize(target.size))
        if region is not None:
            mask = seg.paste(mask, region, image.size)
        least = MIN_MASK_SHARE * (0.1 if region is not None else 1)  # parts found within a box may be small
        return None if colors.bounds(mask) is None or mask.mean() < least else mask

    for render, v in enumerate(views.views):
        image = Image.open(views_folder / v.image).convert("RGB")
        whole = colors.mask_array(Image.open(views_folder / v.mask))
        found: dict[str, tuple[np.ndarray, list[int] | None]] = {}
        for spec in specs:
            if spec.view not in (None, v.view):
                continue
            region = seg.padded(seg.pixel_box(spec.box, image.size), image.size) if spec.box else None
            mask = detect(image, spec.part, region)
            if mask is None:
                missing.append({"part": spec.part, "view": v.view, "reason": "not_found"})
                continue
            if region is None and len(names) > 1 and colors.iou(mask, whole) >= WHOLE_OBJECT_IOU:
                missing.append({"part": spec.part, "view": v.view, "reason": "whole_object"})
                continue
            if whole.any():
                mask = mask & whole  # the detector's masks bleed past the silhouette
            if colors.bounds(mask) is None:
                missing.append({"part": spec.part, "view": v.view, "reason": "not_found"})
                continue
            if spec.part in found:  # several boxes of one part in a view: their union
                mask = mask | found[spec.part][0]
            found[spec.part] = (mask, list(region) if region else None)
        if votes is not None and v.fit is not None:
            ids = mv.face_ids(mv.render(mesh, reference.view_camera(v.view, v.fit.model_dump()), ids=True)[0])
            for part in names:
                votes.add(ids, render, part, found[part][0] if part in found else None)
        flags = seg.implausible({k: x[0] for k, x in found.items()}, whole)
        for part, (mask, region) in found.items():
            name = f"{part}_{v.view}.png"
            files[folder / name] = mask_png(mask)
            masks.append(m.Mask(part=part, view=v.view, path=name, bounds=box(mask), area=int(mask.sum()),
                                colors=colors.dominant_colors(image, mask), region=region,
                                implausible=flags.get(part)))
    regions = []
    if votes is not None:
        for k, camera in enumerate(seg.vote_cameras(mesh)):
            rgb, whole = mv.render(mesh, camera)
            ids = mv.face_ids(mv.render(mesh, camera, ids=True)[0])
            for part in names:
                mask = detect(Image.fromarray(rgb), part)
                if mask is not None and len(names) > 1 and colors.iou(mask, whole) >= WHOLE_OBJECT_IOU:
                    mask = None  # the detector returned the whole object: no vote, as in the views
                votes.add(ids, len(views.views) + k, part, mask)
        for part, found3d in votes.regions().items():
            faces = f"{part}_faces.json"
            files[folder / faces] = json.dumps(found3d["faces"]).encode()
            regions.append(m.Region(part=part, faces=faces, bounds=found3d["bounds"],
                                    agreement=found3d["agreement"], uncertain=found3d["uncertain"],
                                    implausible=found3d.get("implausible")))
    old = asset.masks(hero.path.name)
    kept = [k for k in (old.masks if old else []) if k.part not in names and k.part != "object"]
    for k in kept:  # parts not named this time keep their masks
        if (folder / k.path).exists():
            files.setdefault(folder / k.path, (folder / k.path).read_bytes())
    for r in (old.regions if old else []):
        if r.part not in names and r.faces and (folder / r.faces).exists():
            files[folder / r.faces] = (folder / r.faces).read_bytes()
            regions.append(r)
    objects = []
    for v in views.views:
        whole = colors.mask_array(Image.open(views_folder / v.mask))
        objects.append(m.Mask(part="object", view=v.view, path=Path("..", "..", "views", views_folder.name, v.mask).as_posix(),
                              bounds=box(whole), area=int(whole.sum()),
                              colors=colors.dominant_colors(Image.open(views_folder / v.image).convert("RGB"), whole)))
    meta = m.Masks(hero=hero.path.name, parts=list(dict.fromkeys([*(old.parts if old else []), *names])),
                   job=context.job.id, masks=objects + kept + masks,
                   missing=[x for x in (old.missing if old else []) if x["part"] not in names] + missing,
                   regions=regions)
    files[folder / "masks.yaml"] = meta
    context.check()
    if folder.exists():
        shutil.rmtree(folder)
    write_outputs(context, files)
    return {"hero": ws.rel(hero.path),
            "views": [{"view": v.view, "width": v.width, "height": v.height, "bounds": v.bounds,
                       "m_per_px": v.m_per_px} for v in views.views],
            "masks": [{"part": k.part, "view": k.view, "path": ws.rel(folder / k.path), "bounds": k.bounds,
                       "area": k.area, "colors": k.colors,
                       **({"region": k.region} if k.region else {}),
                       **({"implausible": k.implausible} if k.implausible else {})} for k in meta.masks],
            "missing": meta.missing,
            "regions": [{"part": r.part, "bounds": r.bounds, "agreement": r.agreement, "uncertain": r.uncertain,
                         **({"implausible": r.implausible} if r.implausible else {})} for r in regions]}
