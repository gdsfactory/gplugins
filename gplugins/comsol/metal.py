"""Build unsolved extruded metal geometry from an extracted layout.

:class:`~gplugins.comsol.model.COMSOL` extends MPh's model with
layout, study, and mesh methods and builds a model through this builder; the
sheet builder for RF and electrostatic studies lives in
:mod:`gplugins.comsol.sheet`.
"""

from __future__ import annotations

import contextlib
import math
from typing import TYPE_CHECKING

from gplugins.comsol._util import _add_polygon, _format_number

if TYPE_CHECKING:
    import mph

    from gplugins.comsol.layout import ComsolLayout


def build_comsol_metal_model(
    client: mph.Client,
    layout: ComsolLayout,
    *,
    metal_thickness_um: float = 0.2,
    name: str = "gdsfactory metal",
) -> mph.Model:
    """Create a COMSOL 3D model holding the layout's metal as extruded polygons.

    Works for any extracted layout, fed or not: the feed ports are not used
    here. Each polygon outline becomes a solid polygon on work plane ``wp1``;
    each hole becomes a second polygon subtracted by its own ``Difference``
    feature. The finished work plane is extruded to ``metal_thickness_um`` by
    ``ext1``.

    Args:
        client: A connected :class:`mph.Client`.
        layout: Extracted metal polygons and feed ports in µm.
        metal_thickness_um: Extrusion height in µm, strictly positive.
        name: Name of the COMSOL model.

    Returns:
        The MPh model. Geometry only: no physics, materials, ports, or studies
        have been added, and the model has not been saved.

    Raises:
        ValueError: If ``metal_thickness_um`` is not positive and finite, or
            the layout has no polygons to extrude.
    """
    if not math.isfinite(metal_thickness_um) or metal_thickness_um <= 0.0:
        raise ValueError(
            "metal_thickness_um must be positive and finite, "
            f"got {metal_thickness_um!r}"
        )
    if not layout.polygons:
        raise ValueError("layout has no polygons to extrude")

    model = client.create(name)
    try:  # ruff: ignore[too-many-statements-in-try-clause]
        model.java.component().create("comp1")
        geometry = model.java.component("comp1").geom().create("geom1", 3)
        geometry.lengthUnit("um")
        geometry.create("wp1", "WorkPlane")
        work_plane = geometry.feature("wp1").geom()

        for index, polygon in enumerate(layout.polygons):
            # One Difference per hole: selection().set() takes a single feature name.
            target = f"pol{index}"
            _add_polygon(work_plane, target, polygon.outline)

            for hole, points in enumerate(polygon.holes):
                hole_tag = f"hole{index}_{hole}"
                _add_polygon(work_plane, hole_tag, points)

                difference_tag = f"dif{index}_{hole}"
                work_plane.create(difference_tag, "Difference")
                difference = work_plane.feature(difference_tag)
                difference.selection("input").set(target)
                difference.selection("input2").set(hole_tag)
                target = difference_tag

        geometry.create("ext1", "Extrude")
        extrude = geometry.feature("ext1")
        extrude.set("workplane", "wp1")
        extrude.selection("input").set("wp1")
        extrude.set("distance", _format_number(metal_thickness_um))
        geometry.run()
    except BaseException:
        # A half-built native model would otherwise pile up in the COMSOL
        # process on every retry; the build failure is what matters, so a
        # failing cleanup must not mask it.
        with contextlib.suppress(Exception):
            client.remove(model)
        raise

    return model
