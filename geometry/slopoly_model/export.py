"""GLB export through Blender's glTF exporter: Y up, metres, one node per part with the hierarchy and pivots,
shared meshes for instances, socket empties, palette UVs and the palette material. Each mesh is repaired first (see
normals.py), smooth meshes get area-weighted normals, and the same scene is saved as a Blender file whose palette
image is linked as //palette.png."""

from __future__ import annotations

import json
import math
import struct
import time
from pathlib import Path

import bpy
from mathutils import Matrix

from . import normals
from . import palette as pal
from . import shade
from .assembly import Model
from .shapes import EDGE_LAYER, HARD, SMOOTH

# Program space (Y up) -> Blender space (Z up): (x, y, z) -> (x, -z, y). The exporter's export_yup undoes it.
TO_BLENDER = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
FROM_BLENDER = TO_BLENDER.inverted()


def _material(texture: Path | None) -> bpy.types.Material:
    material = bpy.data.materials.new("palette")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    shader = nodes["Principled BSDF"]
    shader.inputs["Roughness"].default_value = 1.0
    if texture is not None:
        image = bpy.data.images.load(str(texture))
        image.pack()
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        node.interpolation = "Closest"  # exported as a nearest sampler: cells stay solid
        material.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
    return material


def _shade(mesh: bpy.types.Mesh, mode: str, hard_edge_angle: float) -> None:
    """Flat: every face flat (the exporter splits vertices per face). Smooth: shared normals, hard where faces meet
    at more than the angle, then the program's sharp()/smooth() edge overrides."""
    if mode != "smooth":
        mesh.shade_flat()
        return
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=math.radians(hard_edge_angle))
    flags = mesh.attributes.get(EDGE_LAYER)
    if flags is None:
        return
    values = [0] * len(mesh.edges)
    flags.data.foreach_get("value", values)
    sharp = mesh.attributes.get("sharp_edge") or mesh.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    current = [False] * len(mesh.edges)
    sharp.data.foreach_get("value", current)
    sharp.data.foreach_set("value", [v == HARD or (c and v != SMOOTH) for v, c in zip(values, current)])


def _weighted_normals(mesh: bpy.types.Mesh) -> bpy.types.Mesh:
    """The mesh with area-weighted custom normals (Weighted Normal modifier, keeping sharp edges), so small bevel and
    cap faces don't tilt the normals of large faces. Replaces (and removes) the given mesh."""
    obj = bpy.data.objects.new("_weighted", mesh)
    bpy.context.scene.collection.objects.link(obj)
    modifier = obj.modifiers.new("weighted", "WEIGHTED_NORMAL")
    modifier.mode = "FACE_AREA"
    modifier.keep_sharp = True
    modifier.weight = 100  # strongest bias to large faces: bevel and cap faces barely tilt them
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
    bpy.data.objects.remove(obj)
    name = mesh.name
    bpy.data.meshes.remove(mesh)
    result.name = name
    return result


def save_blend(path: Path) -> None:
    """Saves the current scene as a compressed Blender file: metric units, the palette image linked (not packed) as
    //palette.png next to it."""
    units = bpy.context.scene.unit_settings
    units.system, units.scale_length = "METRIC", 1.0
    for image in bpy.data.images:
        if image.packed_file:
            image.unpack(method="REMOVE")
        image.filepath_raw = "//palette.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=False, copy=True)


def export(model: Model, path: Path, entries: list[pal.Entry], texture: Path | None = None,
           shading: dict | None = None, blend: Path | None = None) -> tuple[list[str], dict]:
    """Writes the GLB (and, with ``blend``, the Blender file). Returns the palette roles the model uses that the
    palette lacks, and export stats {vertices, shadeSeconds, repair}. ``repair`` is {merged, removed, flipped, parts:
    [{part, openEdges, inward, bent}]}. ``shading`` is the pack's {mode, hardEdgeAngle, shadeStrength}; parts can
    override the mode, and a shade strength above 0 bakes the vertex shade."""
    shading = shading or {}
    strength = float(shading.get("shadeStrength", 0) or 0)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    material = _material(texture)
    if strength > 0:
        shade.multiply_in(material)
    shade_seconds = 0.0
    by_role = {e.role: e for e in entries}
    missing: set[str] = set()

    meshes = {}
    repair = {"merged": 0, "removed": 0, "flipped": 0, "parts": []}
    for mesh_name, parts in model.meshes().items():
        shape = parts[0].shape
        for key, count in normals.repair(shape.bm).items():
            repair[key] += count * len(parts)
        found = normals.defects(shape.bm)
        repair["parts"] += [{"part": p.name, **found} for p in parts]
        vertices, faces = shape.vertices(), shape.faces()
        uvs, lacking = pal.face_uvs(vertices, faces, parts[0].face_tags(), by_role)
        missing.update(lacking)
        mesh = bpy.data.meshes.new(mesh_name)
        shape.bm.to_mesh(mesh)  # same vertex and face order as vertices()/faces(); keeps the edge flags
        mesh.transform(TO_BLENDER)
        mode = parts[0].shading or shading.get("mode", "flat")
        _shade(mesh, mode, float(shading.get("hardEdgeAngle", 60)))
        while mesh.uv_layers:  # e.g. a curve's own UV map: the palette map must be the only one (TEXCOORD_0)
            mesh.uv_layers.remove(mesh.uv_layers[0])
        layer = mesh.uv_layers.new(name="palette")
        for polygon, face_uv in zip(mesh.polygons, uvs):
            for loop, (u, v) in zip(polygon.loop_indices, face_uv):
                layer.data[loop].uv = (u, 1.0 - v)  # Blender UVs have v up
        mesh.materials.append(material)
        mesh.update()
        if mode == "smooth":
            mesh = _weighted_normals(mesh)
        if strength > 0:
            started = time.perf_counter()
            shade.bake(mesh, strength)
            shade_seconds += time.perf_counter() - started
        meshes[mesh_name] = mesh

    objects, world = {}, {}
    for p in model.parts.values():
        obj = bpy.data.objects.new(p.name, meshes[p.mesh])
        scene.collection.objects.link(obj)
        world[p.name] = TO_BLENDER @ p.matrix @ FROM_BLENDER
        _place(obj, world[p.name], objects.get(p.parent), world.get(p.parent))
        if p.joint:
            obj["joint"] = p.joint.as_dict()  # glTF node extras; axis in glTF (Y up) space
        objects[p.name] = obj

    for s in model.sockets:
        empty = bpy.data.objects.new(f"socket_{s.name}", None)
        scene.collection.objects.link(empty)
        _place(empty, TO_BLENDER @ Matrix.Translation(s.at) @ FROM_BLENDER, objects.get(s.parent), world.get(s.parent))

    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_extras=True,
                              export_apply=False, export_animations=False, export_cameras=False, export_lights=False)
    if blend is not None:
        save_blend(blend)  # after the GLB: the GLB embeds the palette, the Blender file links it
    repair["parts"].sort(key=lambda p: p["part"])
    return sorted(missing), {"vertices": _vertex_count(path), "shadeSeconds": round(shade_seconds, 3), "repair": repair}


def _vertex_count(path: Path) -> int:
    """Vertices in the GLB (after the exporter's splits for flat faces, hard edges and UV seams)."""
    data = path.read_bytes()
    gltf = json.loads(data[20:20 + struct.unpack_from("<I", data, 12)[0]])
    return sum(gltf["accessors"][p["attributes"]["POSITION"]]["count"]
               for m in gltf.get("meshes", []) for p in m["primitives"])


def _place(obj, world_matrix: Matrix, parent, parent_world: Matrix | None) -> None:
    if parent is None:
        obj.matrix_basis = world_matrix
        return
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = parent_world.inverted() @ world_matrix
