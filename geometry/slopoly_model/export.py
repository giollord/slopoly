"""GLB export through Blender's glTF exporter: Y up, metres, one node per part with the hierarchy and pivots,
shared meshes for instances, socket empties, palette UVs and the palette material."""

from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Matrix

from . import palette as pal
from .assembly import Model

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


def export(model: Model, path: Path, entries: list[pal.Entry], texture: Path | None = None) -> list[str]:
    """Writes the GLB; returns palette roles the model uses that the palette lacks."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    material = _material(texture)
    by_role = {e.role: e for e in entries}
    missing: set[str] = set()

    meshes = {}
    for mesh_name, parts in model.meshes().items():
        shape = parts[0].shape
        vertices, faces = shape.vertices(), shape.faces()
        uvs, lacking = pal.face_uvs(vertices, faces, parts[0].face_tags(), by_role)
        missing.update(lacking)
        mesh = bpy.data.meshes.new(mesh_name)
        mesh.from_pydata([(x, -z, y) for x, y, z in vertices.tolist()], [], faces)  # TO_BLENDER applied
        layer = mesh.uv_layers.new(name="palette")
        for polygon, face_uv in zip(mesh.polygons, uvs):
            for loop, (u, v) in zip(polygon.loop_indices, face_uv):
                layer.data[loop].uv = (u, 1.0 - v)  # Blender UVs have v up
        mesh.materials.append(material)
        mesh.update()
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
    return sorted(missing)


def _place(obj, world_matrix: Matrix, parent, parent_world: Matrix | None) -> None:
    if parent is None:
        obj.matrix_basis = world_matrix
        return
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = parent_world.inverted() @ world_matrix
