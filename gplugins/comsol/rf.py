r"""Add an unsolved CPW full-wave study to a COMSOL model that uses metal sheets.

The model comes from
:func:`~gplugins.comsol.sheet.build_comsol_sheet_model`: air and silicon
meeting at ``z = 0`` with the layout's metal imprinted on that plane as faces.
This module makes those faces perfect electric conductors, turns the two feed
cross sections into numeric ports, and adds a mesh sequence and a frequency
study. Nothing is meshed or solved here.

The port faces and the integration line are found from the feed ports and the
bounding box of the :class:`~gplugins.comsol.layout.ComsolLayout`, never
from hard-coded entity IDs, so a layout whose feeds do not sit on opposite
bounding-box faces is refused instead of quietly porting the wrong plane.

What a solve gives is the S-parameters of the CPW section between the two
planes: ``emw.S21dB`` is the through response at ``frequency_ghz``,
``emw.S11dB`` the reflection. It is not an eigenmode solve, so it says nothing
about a qubit hanging off the feedline.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from gplugins.comsol._util import (
    MESH_TAG,
    STUDY_TAG,
    _format_number,
    _require_no_study,
)

if TYPE_CHECKING:
    import mph

    from gplugins.comsol.layout import ComsolFeedPort, ComsolLayout, Point

#: Named selection holding every metal sheet face, for the PEC boundary.
METAL_FACES_SELECTION = "metal_faces"

#: Named selections for the two port cross sections, low side first.
INPUT_FACES_SELECTION = "input_faces"
OUTPUT_FACES_SELECTION = "output_faces"

#: Named selections for the integration line of each port, low side first.
INPUT_GAP_SELECTION = "input_gap"
OUTPUT_GAP_SELECTION = "output_gap"

#: Half-size in µm of the boxes that pick one metal face out of the plane. The
#: metal lives on a single plane, so the box straddles ``z = 0``.
_METAL_BOX_HALF_SIZE_UM = 0.01

#: Half-thickness in µm of the boxes that lie on a port plane.
_PLANE_HALF_THICKNESS_UM = 0.001

#: Half-thickness in µm of the boxes that pick one gap edge out.
_EDGE_HALF_THICKNESS_UM = 0.001

#: Tolerance in µm for a feed port sitting on a bounding-box face, and for two
#: orientations pointing the same way. A cropped layout snaps its planes
#: outwards to the database grid, so the port centre can miss the box by up to
#: one database unit.
_PLANE_ALIGNMENT_TOLERANCE_UM = 0.01
_ANGLE_TOLERANCE_DEG = 1.0e-6


def _axis_of_orientation(orientation: float) -> int:
    """Return the axis a cardinal port faces along, 0 for x and 1 for y.

    Returns:
        ``0`` when the port faces along ±x, ``1`` along ±y.
    """
    remainder = orientation % 180.0
    return 0 if min(remainder, 180.0 - remainder) <= _ANGLE_TOLERANCE_DEG else 1


def _same_angle(first: float, second: float) -> bool:
    """Return whether two orientations point the same way modulo 360°.

    Returns:
        ``True`` when the orientations differ by less than the angle tolerance.
    """
    return abs((first - second + 180.0) % 360.0 - 180.0) <= _ANGLE_TOLERANCE_DEG


def _feed_pair(
    layout: ComsolLayout,
) -> tuple[int, ComsolFeedPort, ComsolFeedPort]:
    """Validate the two feed ports and order them along their axis.

    Returns:
        The axis to port along and the low and high feed port on that axis.

    Raises:
        ValueError: If the layout does not carry exactly two opposite,
            outward-facing cardinal feeds that each sit on a bounding-box face.
    """
    ports = layout.feed_ports
    if len(ports) != 2:
        raise ValueError(
            "a CPW full-wave study needs exactly two feed ports bounding the "
            f"layout, got {len(ports)}"
        )
    axes = {_axis_of_orientation(port.orientation) for port in ports}
    if len(axes) != 1:
        raise ValueError(
            "the two feed ports must face along the same axis, got orientations "
            f"{[port.orientation for port in ports]}"
        )
    axis = axes.pop()
    low_port, high_port = sorted(ports, key=lambda port: port.center[axis])
    expected = (180.0, 0.0) if axis == 0 else (270.0, 90.0)
    if not (
        _same_angle(low_port.orientation, expected[0])
        and _same_angle(high_port.orientation, expected[1])
    ):
        raise ValueError(
            "the feed ports must face outwards, "
            f"{expected[0]} on the low side and {expected[1]} on the high side, "
            f"got {low_port.orientation} and {high_port.orientation}"
        )
    bbox_low, bbox_high = (
        (layout.bbox.xmin, layout.bbox.xmax)
        if axis == 0
        else (layout.bbox.ymin, layout.bbox.ymax)
    )
    if (
        abs(low_port.center[axis] - bbox_low) > _PLANE_ALIGNMENT_TOLERANCE_UM
        or abs(high_port.center[axis] - bbox_high) > _PLANE_ALIGNMENT_TOLERANCE_UM
    ):
        raise ValueError(
            "the feed ports must sit on opposite bounding-box faces, got "
            f"{low_port.center[axis]} and {high_port.center[axis]} µm against "
            f"[{bbox_low}, {bbox_high}] µm: extract the layout with "
            "crop_to_feed_ports=True so both cross sections are open"
        )
    return axis, low_port, high_port


def _box_selection(
    component: Any,
    tag: str,
    *,
    entitydim: int,
    condition: str,
    spans: dict[str, tuple[float, float]],
) -> tuple[int, ...]:
    """Add one Box selection and read back the entities it resolved to.

    An axis left out of ``spans`` keeps COMSOL's default bound, which is
    unbounded in both directions.

    Returns:
        The entities the selection resolved to, as COMSOL reports them.
    """
    component.selection().create(tag, "Box")
    selection = component.selection(tag)
    # entitydim is a string: an int makes JPype pick the numeric set() overload.
    selection.set("entitydim", str(entitydim))
    selection.set("condition", condition)
    for axis, (low, high) in spans.items():
        selection.set(f"{axis}min", _format_number(low))
        selection.set(f"{axis}max", _format_number(high))
    return tuple(selection.entities())


def _point_box(point: Point, half_size: float) -> dict[str, tuple[float, float]]:
    """Return the spans of a small box centred on a point on the sheet plane.

    Returns:
        The ``(low, high)`` span of the box on each axis.
    """
    return {
        "x": (point[0] - half_size, point[0] + half_size),
        "y": (point[1] - half_size, point[1] + half_size),
        "z": (-half_size, half_size),
    }


def _add_metal_faces(component: Any, layout: ComsolLayout) -> None:
    """Select the metal sheet face of every polygon and union them.

    Each polygon contributes one tiny box around a point strictly inside it, so
    no face ID is hard-coded. A box that finds no face, or two polygons that
    find the same face, means the built geometry is not what the layout
    describes and is refused rather than grounding the wrong area.

    Raises:
        ValueError: If a polygon probe does not select exactly one face, or if
            two polygons select the same face.
    """
    tags: list[str] = []
    faces: list[tuple[int, ...]] = []
    for index, polygon in enumerate(layout.polygons):
        # representative_point is guaranteed inside the outline, holes included.
        point = Polygon(polygon.outline, polygon.holes).representative_point()
        tag = f"metal{index}"
        entities = _box_selection(
            component,
            tag,
            entitydim=2,
            condition="intersects",
            spans=_point_box((point.x, point.y), _METAL_BOX_HALF_SIZE_UM),
        )
        if len(entities) != 1:
            raise ValueError(
                f"metal polygon {index} selects {len(entities)} faces, expected "
                "one: it is degenerate, or it overlaps another polygon"
            )
        tags.append(tag)
        faces.append(entities)
    if len(set(faces)) != len(faces):
        raise ValueError(f"the metal polygons must select different faces, got {faces}")

    component.selection().create(METAL_FACES_SELECTION, "Union")
    union = component.selection(METAL_FACES_SELECTION)
    union.set("entitydim", "2")
    union.set("input", tags)


def _add_port_faces(component: Any, tag: str, axis: int, plane: float) -> None:
    """Select the air and silicon faces of one port cross section.

    The box is a thin slab on the port plane, unbounded in the other two axes, so
    it holds both dielectric halves of the cross section and nothing else. The
    transverse and z extents are left unbounded rather than given finite spans:
    the blocks can reach any distance sideways and in height, and a capped box
    would then report a partial face, a half port.

    The port plane is where the feed metal ends, the layout's bounding-box face.
    It is only an outer face of the model when the sheet model was built with no
    lateral margin; with a margin the plane runs through the inside of each block
    and carries no face at all.

    Raises:
        ValueError: If the plane does not carry exactly two faces, one air and
            one silicon, which means the model was built with a nonzero
            ``lateral_margin_um``, was not built from this layout, or its two
            dielectric blocks are not both cut by the port plane.
    """
    axial = "x" if axis == 0 else "y"
    thickness = _PLANE_HALF_THICKNESS_UM
    entities = _box_selection(
        component,
        tag,
        entitydim=2,
        condition="inside",
        spans={axial: (plane - thickness, plane + thickness)},
    )
    if not entities:
        raise ValueError(
            f"the {tag} box selects no face on the port plane at {axial} = "
            f"{plane} µm, so the model's outer face is not where the feed metal "
            "ends: build the sheet model with lateral_margin_um=0 for an RF "
            "study, or from the layout passed here"
        )
    if len(entities) != 2:
        raise ValueError(
            f"the {tag} box selects {len(entities)} faces on the port plane at "
            f"{axial} = {plane} µm, expected two, one air and one silicon: the "
            "model has to hold the sheet geometry this layout was extracted from"
        )


def _add_gap_edge(
    component: Any,
    name: str,
    axis: int,
    plane: float,
    feed: ComsolFeedPort,
    gap_um: float,
) -> None:
    """Select the CPW gap edge one port's voltage integrates across.

    The edge leaves the centre conductor at half its width and runs the gap
    length into the ground, so the box spans exactly that strip on the port
    plane.

    Raises:
        ValueError: If the strip does not hold exactly one edge, which means the
            cross section is not a single open CPW gap.
    """
    axial, transverse = ("x", "y") if axis == 0 else ("y", "x")
    inner = feed.center[1 - axis] + 0.5 * feed.width
    thickness = _EDGE_HALF_THICKNESS_UM
    entities = _box_selection(
        component,
        f"{name}_gap",
        entitydim=1,
        condition="inside",
        spans={
            axial: (plane - thickness, plane + thickness),
            transverse: (inner - thickness, inner + gap_um + thickness),
            "z": (-thickness, thickness),
        },
    )
    if len(entities) != 1:
        raise ValueError(
            f"the {name} port gap selects {len(entities)} edges, expected one: "
            f"the {gap_um} µm from {inner} µm off the centre conductor must be a "
            "single unmasked CPW gap"
        )


def _check_cpw_cross_sections(
    layout: ComsolLayout, axis: int, feeds: tuple[ComsolFeedPort, ...], gap_um: float
) -> None:
    """Require a separate centre conductor and open gaps on both sides."""
    metal = [Polygon(polygon.outline, polygon.holes) for polygon in layout.polygons]
    inward = min(1.0, gap_um / 2.0)
    for index, feed in enumerate(feeds):
        axial = feed.center[axis] + (inward if index == 0 else -inward)
        transverse = feed.center[1 - axis]

        def owners(
            offset: float, *, axial: float = axial, transverse: float = transverse
        ) -> set[int]:
            point = [0.0, 0.0]
            point[axis] = axial
            point[1 - axis] = transverse + offset
            return {
                index
                for index, region in enumerate(metal)
                if region.contains(ShapelyPoint(point))
            }

        centre = owners(0.0)
        if len(centre) != 1:
            raise ValueError(
                f"{feed.name} centre conductor must occupy one metal polygon"
            )
        for direction in (-1, 1):
            if owners(direction * (feed.width / 2.0 + gap_um / 2.0)):
                raise ValueError(f"{feed.name} CPW gap is shorted on one side")
            ground = owners(direction * (feed.width / 2.0 + gap_um + inward))
            if len(ground) != 1 or ground == centre:
                raise ValueError(
                    f"{feed.name} centre and ground must be separate metal"
                )


def _add_electromagnetic_waves(component: Any) -> None:
    """Add EMW with a PEC on every metal face and one numeric port per plane."""
    physics = component.physics().create("emw", "ElectromagneticWaves", "geom1")
    physics.create("pecMetal", "PerfectElectricConductor", 2)
    physics.feature("pecMetal").selection().named(METAL_FACES_SELECTION)

    for index, (faces, gap) in enumerate(
        (
            (INPUT_FACES_SELECTION, INPUT_GAP_SELECTION),
            (OUTPUT_FACES_SELECTION, OUTPUT_GAP_SELECTION),
        ),
        start=1,
    ):
        tag = f"port{index}"
        physics.create(tag, "Port", 2)
        port = physics.feature(tag)
        port.selection().named(faces)
        port.set("PortType", "Numeric")
        # Numeric TEM ports need the flag set to the string "1"; "on" is not a
        # value this property accepts.
        port.set("numericTEM", "1")
        port.set("PortName", str(index))
        if index > 1:
            # The first port drives the model, the rest are matched loads.
            port.set("PortExcitation", "off")
        port.create("ivl", "IntegrationLineforVoltage")
        port.feature("ivl").selection().named(gap)


def _add_mesh_and_study(
    component: Any,
    model: mph.Model,
    frequency_ghz: float,
    mesh_size: int,
    effective_index_shift: float,
) -> None:
    """Add an automatic mesh and a frequency study with one BMA step per port."""
    mesh = component.mesh().create(MESH_TAG, "geom1")
    mesh.autoMeshSize(mesh_size)

    frequency = f"{_format_number(frequency_ghz)}[GHz]"
    study = model.java.study().create(STUDY_TAG)
    for index in (1, 2):
        tag = f"bma{index}"
        study.create(tag, "BoundaryModeAnalysis")
        feature = study.feature(tag)
        feature.set("PortName", str(index))
        feature.set("modeFreq", frequency)
        feature.set("shift", _format_number(effective_index_shift))
        feature.set("shiftactive", "on")
    study.create("freq", "Frequency")
    study.feature("freq").set("plist", frequency)


def add_cpw_rf_study(
    model: mph.Model,
    layout: ComsolLayout,
    *,
    cpw_gap_um: float,
    frequency_ghz: float = 7.5,
    mesh_size: int = 8,
    effective_index_shift: float = 2.5,
) -> mph.Model:
    """Add an unsolved CPW full-wave study to a sheet model.

    Args:
        model: The MPh model from
            :func:`~gplugins.comsol.sheet.build_comsol_sheet_model`, built with
            ``lateral_margin_um=0``: the ports sit on the model's outer faces,
            and those have to be where the feed metal ends.
        layout: The same layout the model was built from, extracted with
            ``crop_to_feed_ports=True`` so both feed planes are open CPW cross
            sections on the bounding box.
        cpw_gap_um: Width of the etch gap between the centre conductor and the
            ground at the ports, in µm. The voltage integration line spans it.
        frequency_ghz: Boundary mode analysis reference and initial frequency
            in GHz.
        mesh_size: COMSOL mesh size, an integer from 1 (finest) to 9
            (coarsest).
        effective_index_shift: Effective-index shift both boundary mode
            analyses search around, positive and finite. The default 2.5 suits
            the silicon/air CPW section and reproduces the saved examples.

    Returns:
        The same model, with the metal and port selections, the EMW interface,
        the mesh sequence, and the frequency study added. It has not been meshed
        or solved and has not been saved.

    Raises:
        ValueError: If the gap is not positive and finite, if the frequency is
            not positive and finite, if the mesh size is not an integer in 1 to
            9, if the effective-index shift is not positive and finite, if the
            layout does not carry two opposite outward-facing feeds on the
            bounding box, if the feed cross sections are not open CPW gaps, or
            if a selection does not resolve to the faces or edges the layout
            implies, which includes a model built with a nonzero
            ``lateral_margin_um``, or if the model already holds a study.
    """
    if not math.isfinite(cpw_gap_um) or cpw_gap_um <= 0.0:
        raise ValueError(f"cpw_gap_um must be positive and finite, got {cpw_gap_um!r}")
    if not math.isfinite(frequency_ghz) or frequency_ghz <= 0.0:
        raise ValueError(
            f"frequency_ghz must be positive and finite, got {frequency_ghz!r}"
        )
    # bool is an int subclass, so isinstance alone would let True through as 1.
    if (
        isinstance(mesh_size, bool)
        or not isinstance(mesh_size, int)
        or not 1 <= mesh_size <= 9
    ):
        raise ValueError(
            "mesh_size must be an integer from 1 (finest) to 9 (coarsest), "
            f"got {mesh_size!r}"
        )
    if not math.isfinite(effective_index_shift) or effective_index_shift <= 0.0:
        raise ValueError(
            "effective_index_shift must be positive and finite, "
            f"got {effective_index_shift!r}"
        )

    axis, low_feed, high_feed = _feed_pair(layout)
    # Pure layout checks go before the first create, so a refused layout leaves
    # the model untouched.
    _check_cpw_cross_sections(layout, axis, (low_feed, high_feed), cpw_gap_um)
    planes = (
        (layout.bbox.xmin, layout.bbox.xmax)
        if axis == 0
        else (layout.bbox.ymin, layout.bbox.ymax)
    )

    component = model.java.component("comp1")
    _require_no_study(model, component)
    # The port planes are probed first: they are what a model built with a
    # lateral margin gets wrong, and they fail before any physics selection.
    for name, plane in (("input", planes[0]), ("output", planes[1])):
        _add_port_faces(component, f"{name}_faces", axis, plane)
    _add_metal_faces(component, layout)
    for name, plane, feed in (
        ("input", planes[0], low_feed),
        ("output", planes[1], high_feed),
    ):
        _add_gap_edge(component, name, axis, plane, feed, cpw_gap_um)
    _add_electromagnetic_waves(component)
    _add_mesh_and_study(
        component, model, frequency_ghz, mesh_size, effective_index_shift
    )

    return model
