"""COMSOL models built on MPh.

:mod:`gplugins.comsol.layout` extracts metal polygons and feed ports from
a gdsfactory component. :func:`~gplugins.comsol.metal.build_comsol_metal_model`
extrudes that metal, and
:func:`~gplugins.comsol.sheet.build_comsol_sheet_model` places it as faces
on an air/silicon interface. Studies are added on top with
:func:`~gplugins.comsol.rf.add_cpw_rf_study` or
:func:`~gplugins.comsol.capacitance.add_capacitance_study`, and
:mod:`gplugins.comsol.mesh` holds the mesh helpers.

The pieces are also available as one chainable class:
:class:`COMSOL` builds a model through its ``create_sheet`` or ``create_metal``
method, holds the layout, and offers a method per study and mesh helper, so
neither the model nor the layout has to be passed again. Solving, saving, and
evaluating are MPh's own methods.

Note:
    The builders need the optional ``comsol`` extra and a local COMSOL
    installation. Only :class:`COMSOL` imports MPh, and lazily, so importing
    this package or the layout and helper modules stays possible without it.

See the `MPh repository <https://github.com/MPh-py/MPh>`_ and
`MPh documentation <https://mph.readthedocs.io/en/stable/>`_.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from gplugins.comsol.capacitance import add_capacitance_study
from gplugins.comsol.layout import (
    ComsolBoundingBox,
    ComsolFeedPort,
    ComsolLayout,
    ComsolPolygon,
    CropPlanes,
    crop_planes,
    feed_port,
    prepare_comsol_layout,
    validate_crop_containment,
)
from gplugins.comsol.mesh import (
    pin_absolute_edge_mesh_sizes,
    pin_absolute_mesh_sizes,
    refine_metal_plane_mesh,
)
from gplugins.comsol.metal import build_comsol_metal_model
from gplugins.comsol.rf import add_cpw_rf_study
from gplugins.comsol.sheet import build_comsol_sheet_model

if TYPE_CHECKING:
    from gplugins.comsol.model import COMSOL

__all__ = [
    "COMSOL",
    "ComsolBoundingBox",
    "ComsolFeedPort",
    "ComsolLayout",
    "ComsolPolygon",
    "CropPlanes",
    "add_capacitance_study",
    "add_cpw_rf_study",
    "build_comsol_metal_model",
    "build_comsol_sheet_model",
    "crop_planes",
    "feed_port",
    "pin_absolute_edge_mesh_sizes",
    "pin_absolute_mesh_sizes",
    "prepare_comsol_layout",
    "refine_metal_plane_mesh",
    "validate_crop_containment",
]


# TODO(Python 3.15): lazy from-import of COMSOL (PEP 810) replaces this hook.
def __getattr__(name: str) -> Any:
    """Import a public name that needs MPh only when it is asked for.

    Returns:
        The requested attribute.

    Raises:
        AttributeError: If ``name`` is not part of the public API.
    """
    if name == "COMSOL":
        return importlib.import_module("gplugins.comsol.model").COMSOL
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List the public names, including the lazily imported one.

    Returns:
        Sorted public attribute names.
    """
    return sorted(__all__)
