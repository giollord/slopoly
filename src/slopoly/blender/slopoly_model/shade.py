"""Baked vertex shade: a grey colour attribute (ambient occlusion plus a little convex-edge wear) that the palette
material multiplies with the atlas, exported as the standard glTF vertex colour (COLOR_0).

Each mesh is baked on its own (self-occlusion only), so instances and mirrors keep sharing one mesh."""

from __future__ import annotations

import math

import bmesh
import bpy

ATTRIBUTE = "shade"
SAMPLES = 16
DARKEST = 0.35  # the shade never goes below this, so palette colours stay recognisable
WEAR = 0.25  # share of the darkening that convex edges add, at full sharpness


def _wear(mesh: bpy.types.Mesh) -> list[float]:
    """0..1 per loop: how sharp the convex edges at the loop's vertex are (90 degrees and more count fully)."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    sharpness = {}
    for v in bm.verts:
        angles = [e.calc_face_angle_signed(0.0) for e in v.link_edges if len(e.link_faces) == 2]
        sharpness[v.index] = min(max([a for a in angles if a > 0] or [0.0]) / (math.pi / 2), 1.0)
    values = [sharpness[loop.vert.index] for face in bm.faces for loop in face.loops]
    bm.free()
    return values


def bake(mesh: bpy.types.Mesh, strength: float) -> None:
    """Adds the ``shade`` colour attribute (corner domain) to ``mesh``: 1 - strength * (occlusion + wear), grey,
    clamped to DARKEST..1. Uses Cycles on the CPU with a temporary object in the current (otherwise empty) scene."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bake")
    size = max(mesh.vertices[i].co.length for i in range(len(mesh.vertices))) if mesh.vertices else 1.0
    scene.world.light_settings.distance = max(size, 0.05)  # occlusion only from nearby geometry of this mesh

    attribute = mesh.color_attributes.new(ATTRIBUTE, "BYTE_COLOR", "CORNER")
    mesh.color_attributes.active_color = attribute
    obj = bpy.data.objects.new("slopoly_bake", mesh)
    scene.collection.objects.link(obj)
    try:
        with bpy.context.temp_override(active_object=obj, object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    finally:
        bpy.data.objects.remove(obj)
    occlusion = [1.0 - d.color[0] for d in attribute.data]
    for d, ao, wear in zip(attribute.data, occlusion, _wear(mesh)):
        value = min(max(1.0 - strength * (ao + WEAR * wear), DARKEST), 1.0)
        d.color = (value, value, value, 1.0)


def multiply_in(material: bpy.types.Material) -> None:
    """Makes the material's base colour the atlas times the ``shade`` attribute (what the exporter writes as
    COLOR_0 times baseColorTexture, and what renders show)."""
    tree = material.node_tree
    shader = tree.nodes["Principled BSDF"]
    base = shader.inputs["Base Color"]
    source = base.links[0].from_socket if base.links else None
    color = tree.nodes.new("ShaderNodeVertexColor")
    color.layer_name = ATTRIBUTE
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    if source is not None:
        tree.links.new(source, mix.inputs[6])
    tree.links.new(color.outputs["Color"], mix.inputs[7])
    tree.links.new(mix.outputs[2], base)
