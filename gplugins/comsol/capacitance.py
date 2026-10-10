r"""Add an electrostatic capacitance study to a COMSOL model that uses metal sheets.

The model comes from
:func:`~gplugins.comsol.sheet.build_comsol_sheet_model`, where the metal
is a set of faces on the silicon/air interface. This module picks those faces out
with points inside them, drives one of them with a voltage terminal, grounds the
others, and adds a mesh sequence and a stationary study. Nothing is solved here,
and nothing here is specific to a device: the caller names the conductors, which
one is driven, and which are grounded.

A solve gives electrostatic capacitance: ``es.C11`` is the capacitance of the
driven conductor to the grounded rest of the chip, and the stored energy agrees
with it, since :math:`2 W_\text{e} / V^2` equals ``es.C11``. It is not an RF Josephson
eigenmode, and turning it into a qubit frequency needs an :math:`L_\text{J}` picked
outside COMSOL: that LC estimate is not an eigensolve.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from gplugins.comsol._util import _format_number
from gplugins.comsol.sheet import SILICON_SELECTION

if TYPE_CHECKING:
    import mph

    from gplugins.comsol.layout import ComsolLayout, Point

#: Half-size in µm of the boxes that pick one metal face out of the plane. The
#: metal lives on a single plane, so the box straddles ``z = 0``.
_FACE_HALF_SIZE_UM = 0.01


def _require_point(point: Point, name: str) -> None:
    """Raise unless ``point`` is a finite (x, y) pair in µm.

    Raises:
        ValueError: If the point is not a finite (x, y) pair.
    """
    if len(point) != 2 or not all(math.isfinite(value) for value in point):
        raise ValueError(f"{name} must be a finite (x, y) pair in µm, got {point!r}")


def _require_conductor_tags(
    conductors: tuple[tuple[str, Point], ...],
    terminal: str,
    grounds: tuple[str, ...],
) -> None:
    """Raise unless the tags name every conductor exactly once.

    A tag that repeats, a terminal or ground that names no conductor, and a
    conductor that is neither driven nor grounded are all refused: the first two
    would point a terminal or a ground at a selection that does not exist, and
    the third would leave that face as a dielectric interface, so the
    capacitance would be for a geometry other than the one drawn.

    Raises:
        ValueError: If a conductor tag repeats, if the terminal or a ground is
            not one of the conductors, if the terminal is also grounded, if two
            grounds are the same tag, or if a conductor is neither driven nor
            grounded.
    """
    tags = [tag for tag, _ in conductors]
    if not grounds:
        raise ValueError("at least one grounded conductor is required")
    if len(set(tags)) != len(tags):
        raise ValueError(f"the conductor tags must be unique, got {tags}")
    if terminal not in tags:
        raise ValueError(
            f"the terminal {terminal!r} is not one of the conductors {tags}"
        )
    if len(set(grounds)) != len(grounds):
        raise ValueError(f"the ground tags must be unique, got {grounds}")
    for ground in grounds:
        if ground not in tags:
            raise ValueError(
                f"the ground {ground!r} is not one of the conductors {tags}"
            )
    if terminal in grounds:
        raise ValueError(f"the terminal {terminal!r} must not also be grounded")
    unnamed = [tag for tag in tags if tag != terminal and tag not in grounds]
    if unnamed:
        raise ValueError(
            f"the conductors {unnamed} are neither the terminal nor a ground"
        )


def _add_face_selection(component: Any, tag: str, point: Point) -> tuple[int, ...]:
    """Add a Box selection over the metal face around ``point`` and read it back.

    Returns:
        The entities the selection resolved to, as COMSOL reports them.
    """
    component.selection().create(tag, "Box")
    selection = component.selection(tag)
    selection.set("entitydim", "2")
    selection.set("condition", "intersects")
    selection.set("zmin", _format_number(-_FACE_HALF_SIZE_UM))
    selection.set("zmax", _format_number(_FACE_HALF_SIZE_UM))
    for axis, value in zip("xy", point):
        selection.set(f"{axis}min", _format_number(value - _FACE_HALF_SIZE_UM))
        selection.set(f"{axis}max", _format_number(value + _FACE_HALF_SIZE_UM))
    return tuple(selection.entities())


def _select_metal_faces(
    component: Any, layout: ComsolLayout, conductors: tuple[tuple[str, Point], ...]
) -> None:
    """Add one face selection per conductor and check what they resolved to.

    The layout has to hold exactly one metal polygon per conductor, and each
    point has to land in a different one. A polygon left over would keep its
    metal boundary condition nowhere and be solved as a dielectric interface,
    so the capacitance would be for a geometry other than the one drawn. Every
    box also has to hold exactly one face, and no two conductors the same one,
    or a point that misses the metal would put a terminal or a ground on the
    wrong face.

    Raises:
        ValueError: If the layout does not hold one metal polygon per
            conductor, if a point does not lie inside exactly one of them, if
            two points lie in the same polygon, if a selection holds a number
            of faces other than one, or if two selections hold the same face.
    """
    metal_regions = [
        Polygon(polygon.outline, polygon.holes) for polygon in layout.polygons
    ]
    if len(metal_regions) != len(conductors):
        raise ValueError(
            f"the layout must hold one metal polygon per conductor, expected "
            f"{len(conductors)}, got {len(metal_regions)}"
        )
    assigned: set[int] = set()
    for tag, point in conductors:
        inside = [
            index
            for index, region in enumerate(metal_regions)
            if region.contains(ShapelyPoint(point))
        ]
        if len(inside) != 1:
            raise ValueError(
                f"the {tag} point must lie inside exactly one metal polygon"
            )
        if inside[0] in assigned:
            raise ValueError(
                f"the conductor points must lie in {len(conductors)} different "
                "metal polygons"
            )
        assigned.add(inside[0])

    faces = {
        tag: _add_face_selection(component, tag, point) for tag, point in conductors
    }
    for tag, entities in faces.items():
        if len(entities) != 1:
            raise ValueError(
                f"the {tag} point selects {len(entities)} faces, expected one: "
                "pass a point well inside the metal face it names"
            )
    if len(set(faces.values())) != len(faces):
        raise ValueError(
            f"the conductor points must select {len(conductors)} different faces, "
            f"got {faces}"
        )


def add_electrostatics(
    component: Any,
    *,
    terminal: str,
    grounds: tuple[str, ...],
    voltage_v: float,
) -> None:
    """Add Electrostatics with one voltage terminal and a ground per selection.

    The interface covers every domain, so the default Free Space feature keeps
    the air, and a Charge Conservation feature on silicon uses that domain's
    material permittivity through the default ``epsilonr_mat``.

    Args:
        component: The Java component to add the physics to, usually ``comp1``.
        terminal: Name of the face selection to drive with the voltage source.
        grounds: Names of the face selections to ground, one Ground feature each.
            The features are tagged ``gnd1``, ``gnd2``, and so on, in this order.
        voltage_v: Terminal voltage in V, positive.
    """
    physics = component.physics().create("es", "Electrostatics", "geom1")
    physics.create("ccSi", "ChargeConservation", 3)
    physics.feature("ccSi").selection().named(SILICON_SELECTION)

    physics.create("term1", "Terminal", 2)
    terminal_feature = physics.feature("term1")
    terminal_feature.selection().named(terminal)
    # The default TerminalType is Charge, which would leave the face floating.
    terminal_feature.set("TerminalType", "Voltage")
    terminal_feature.set("V0", f"{_format_number(voltage_v)}[V]")

    for index, selection in enumerate(grounds, start=1):
        tag = f"gnd{index}"
        physics.create(tag, "Ground", 2)
        physics.feature(tag).selection().named(selection)


def add_capacitance_study(
    model: mph.Model,
    layout: ComsolLayout,
    *,
    conductors: tuple[tuple[str, Point], ...],
    terminal: str,
    grounds: tuple[str, ...],
    voltage_v: float = 1.0,
    mesh_size: int = 7,
) -> mph.Model:
    """Add an unsolved electrostatic capacitance study to a sheet model.

    Args:
        model: The MPh model from
            :func:`~gplugins.comsol.sheet.build_comsol_sheet_model`.
        layout: The metal polygons used to build that model. It must hold
            exactly one polygon per conductor; a metal polygon that no point
            names is refused rather than left as a dielectric interface.
        conductors: One ``(tag, point)`` pair per metal face. The tag names the
            face selection created on ``comp1``, and the point in µm on the sheet
            plane has to sit inside that face. It centres a small box, so it has
            to sit clear of the face's edges.
        terminal: Tag of the conductor to drive with the voltage terminal.
        grounds: Tags of the conductors to ground, in the order their Ground
            features are tagged. Together with ``terminal`` they have to name
            every conductor exactly once.
        voltage_v: Terminal voltage in V, positive.
        mesh_size: COMSOL mesh size, an integer from 1 (finest) to 9 (coarsest).

    Returns:
        The same model, with the selections, physics, mesh, and study added and
        nothing solved. Once the caller runs them, ``es.C11`` agrees with
        ``2*es.intWe/voltage_v**2``.

    Raises:
        ValueError: If the voltage is not positive and finite, if the mesh size
            is not an integer in 1 to 9, if a point is not a finite (x, y) pair,
            if the conductor tags do not name a terminal and a ground each, or
            if the layout, the polygons, or the points do not assign exactly one
            distinct metal face to each conductor.
    """
    if not math.isfinite(voltage_v) or voltage_v <= 0.0:
        raise ValueError(f"voltage_v must be positive and finite, got {voltage_v!r}")
    if (
        isinstance(mesh_size, bool)
        or not isinstance(mesh_size, int)
        or not 1 <= mesh_size <= 9
    ):
        raise ValueError(
            "mesh_size must be an integer from 1 (finest) to 9 (coarsest), "
            f"got {mesh_size!r}"
        )
    _require_conductor_tags(conductors, terminal, grounds)
    for tag, point in conductors:
        _require_point(point, tag)

    component = model.java.component("comp1")
    _select_metal_faces(component, layout, conductors)
    add_electrostatics(
        component, terminal=terminal, grounds=grounds, voltage_v=voltage_v
    )

    mesh = component.mesh().create("mesh1", "geom1")
    mesh.autoMeshSize(mesh_size)
    study = model.java.study().create("std1")
    study.create("stat", "Stationary")

    return model
