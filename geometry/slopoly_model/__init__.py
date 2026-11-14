"""slopoly_model: a small part library for low-poly game assets, on Blender's bmesh.

Programs use the names in ``__all__`` (the build runner provides them as globals). See agent/docs/slopoly_model.md.
"""

import bpy  # noqa: F401  (loads Blender's modules, including bmesh)

from .assembly import (Joint, Model, ModelError, Part, Socket, gradient, instance, mirror_name, new_model, part,
                       rotate, slide, socket)
from .shapes import (Shape, ShapeError, bevel, boolean, box, cone, extrude, inset, join, ngon, paint, prism, select,
                     sweep)

# The program API (documented in agent/docs/slopoly_model.md).
__all__ = [
    "box", "prism", "cone", "ngon", "sweep",
    "extrude", "inset", "bevel", "boolean", "join", "paint", "select",
    "part", "instance", "socket", "rotate", "slide", "gradient",
    "Shape", "ShapeError", "ModelError",
]
