"""slopoly_model: a small part library for low-poly game assets, on Blender's bmesh.

Programs use the names in ``__all__`` (the build runner provides them as globals). See the skill's modelling reference.
Outside Blender only the pure modules (``palette``, ``glb``) can be imported; the CLI uses them for palette refreshes.
"""

try:
    import bpy  # noqa: F401  (loads Blender's modules, including bmesh)
except ImportError:  # imported by the CLI outside Blender
    bpy = None

if bpy is not None:
    from .assembly import (Joint, Model, ModelError, Part, Socket, gradient, instance, mirror_name, new_model, part,
                           rotate, slide, socket)
    from .shapes import (MODIFIERS, Shape, ShapeError, bevel, boolean, box, cone, curve, empty, extrude, group, inset,
                         jitter, join, ngon, outline, paint, path, prism, ramp, select, sharp, smooth, surface_point,
                         texture)

# The program API (documented in the skill's references/modelling-api.md).
__all__ = [
    "box", "prism", "cone", "ngon", "outline", "curve", "path",
    "extrude", "inset", "bevel", "jitter", "boolean", "join", "paint", "select",
    "group", "ramp", "empty", "texture", "MODIFIERS", "sharp", "smooth", "surface_point",
    "part", "instance", "socket", "rotate", "slide", "gradient",
    "Shape", "ShapeError", "ModelError",
]
