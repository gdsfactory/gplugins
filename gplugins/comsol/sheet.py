r"""Build air and silicon domains with metal sheets at their interface.

The metal polygons are faces at ``z = 0``. Layouts without holes use a work
plane and Form Union. Layouts with holes use the Design Module's
``ProjectToFaces`` to imprint each outline and hole onto the interface; the
builder checks that those faces survived. Air and silicon get named selections
and materials. Physics and studies are added separately by
:func:`~gplugins.comsol.rf.add_cpw_rf_study` or
:func:`~gplugins.comsol.capacitance.add_capacitance_study`.
"""

from __future__ import annotations

import contextlib
import math
from typing import TYPE_CHECKING, Any

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from gplugins.comsol._util import _add_polygon, _format_number

if TYPE_CHECKING:
    import mph

    from gplugins.comsol.layout import ComsolLayout, Point

#: Domain selection tags, reused by the physics added on top of this model.
AIR_SELECTION = "air"
SILICON_SELECTION = "si"

#: Default relative permittivity of the silicon substrate (room temperature) and
#: of the air above it. PDKs with a characterised substrate pass their own value,
#: e.g. the cryogenic permittivity of high-resistivity silicon.
SILICON_RELATIVE_PERMITTIVITY = 11.7
AIR_RELATIVE_PERMITTIVITY = 1.0

#: Half-size in µm of the small boxes that pick one dielectric domain out.
_BOX_HALF_SIZE_UM = 0.01

#: Largest half-width in µm of a face probe box, and the share of the room around
#: a probe point it may take up. A probe stays inside one region however narrow
#: that region is, so it never reaches across a face boundary.
_PROBE_MAX_HALF_WIDTH_UM = 0.01
_PROBE_BOUNDARY_FRACTION = 0.25

#: Tag of the union that keeps the interface between the air and silicon blocks.
_UNION_TAG = "uni1"

#: Tag of the geometry selection holding the z = 0 interface face.
_INTERFACE_SELECTION = "interface"

#: Tag of the work plane carrying the metal polygons.
_WORK_PLANE_TAG = "wp1"

#: Tag of the feature that imprints the work plane on the interface.
_PROJECTION_TAG = "proj1"

#: Tag prefix of the Box probes left behind by the imprint check.
_PROBE_PREFIX = "imprint"

#: How far the interface selection reaches sideways past the blocks, as a
#: fraction of the larger block side, and how far it, and a face probe, span into
#: each block in z. A quarter of each thickness keeps the side faces, which run
#: the full thickness from z = 0, and the exterior faces out of a selection that
#: has to hold only the flat interface.
_SELECTION_MARGIN_FRACTION = 0.01
_SELECTION_Z_FRACTION = 0.25


def _add_block(
    geometry: Any,
    tag: str,
    origin: tuple[float, float, float],
    size: tuple[float, float, float],
) -> None:
    """Add one axis-aligned ``Block`` solid anchored at its lower corner."""
    geometry.create(tag, "Block")
    block = geometry.feature(tag)
    block.set("size", [_format_number(value) for value in size])
    block.set("pos", [_format_number(value) for value in origin])


def _add_domain_selection(
    component: Any, tag: str, point: tuple[float, float, float], thickness_um: float
) -> tuple[int, ...]:
    """Add a Box selection that holds the one domain around ``point``."""
    component.selection().create(tag, "Box")
    selection = component.selection(tag)
    # entitydim is a string: an int makes JPype pick the numeric set() overload.
    selection.set("entitydim", "3")
    selection.set("condition", "intersects")
    half_size = min(_BOX_HALF_SIZE_UM, thickness_um / 4.0)
    for axis, value in zip("xyz", point):
        selection.set(f"{axis}min", _format_number(value - half_size))
        selection.set(f"{axis}max", _format_number(value + half_size))
    return tuple(selection.entities())


def _add_material(
    component: Any, tag: str, selection: str, relative_permittivity: float
) -> None:
    """Add a Common material on a named domain selection.

    The permittivity goes into ``propertyGroup("def").set("relpermittivity")``;
    a material has no ``epsilonr`` property for COMSOL to read.
    """
    component.material().create(tag, "Common")
    material = component.material(tag)
    material.selection().named(selection)
    material.propertyGroup("def").set(
        "relpermittivity", _format_number(relative_permittivity)
    )
    material.propertyGroup("def").set("relpermeability", "1")
    material.propertyGroup("def").set("electricconductivity", "0")


def _union_blocks(geometry: Any) -> None:
    """Union the air and silicon blocks, keeping the interface between them.

    Without ``intbnd`` the union would dissolve the shared face, leaving one
    domain with nothing to imprint the metal on.
    """
    geometry.create(_UNION_TAG, "Union")
    union = geometry.feature(_UNION_TAG)
    union.selection("input").set("air", "si")
    union.set("intbnd", "on")


def _add_interface_selection(
    geometry: Any,
    west: float,
    south: float,
    width: float,
    depth: float,
    substrate_thickness_um: float,
    air_height_um: float,
) -> None:
    """Add a geometry Box selection holding only the z = 0 interface face.

    The box reaches past the blocks sideways and spans part of each thickness,
    so the flat interior face at z = 0 lies well inside it while the side faces,
    which start at z = 0 and run a whole thickness, do not.

    JPype cannot choose between COMSOL's int and boolean setters for a Python
    integer, so the dimension is set as a string.
    """
    geometry.create(_INTERFACE_SELECTION, "BoxSelection")
    selection = geometry.feature(_INTERFACE_SELECTION)
    selection.set("entitydim", "2")
    selection.set("condition", "inside")
    margin = _SELECTION_MARGIN_FRACTION * max(width, depth)
    for axis, low, span in (("x", west, width), ("y", south, depth)):
        selection.set(f"{axis}min", _format_number(low - margin))
        selection.set(f"{axis}max", _format_number(low + span + margin))
    into_silicon = _SELECTION_Z_FRACTION * substrate_thickness_um
    into_air = _SELECTION_Z_FRACTION * air_height_um
    selection.set("zmin", _format_number(-into_silicon))
    selection.set("zmax", _format_number(into_air))


def _add_metal_sheets(
    geometry: Any, layout: ComsolLayout, *, construction: bool
) -> tuple[str, ...]:
    """Draw the layout's metal polygons on a work plane at the z = 0 interface.

    Each outline becomes a polygon on ``wp1`` and each hole a second polygon
    subtracted by its own ``Difference`` feature. Nothing is extruded.

    With ``construction`` the plane is marked as construction geometry, so its
    faces are a projection tool rather than an object Form Union has to take
    apart, which is what a layout with holes needs.

    Returns:
        The tag of the last feature of each polygon, which is what COMSOL names
        that object after the plane: ``wp1.<tag>``.
    """
    geometry.create(_WORK_PLANE_TAG, "WorkPlane")
    if construction:
        geometry.feature(_WORK_PLANE_TAG).setAttribute("construction", "on")
    work_plane = geometry.feature(_WORK_PLANE_TAG).geom()
    objects: list[str] = []
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
        objects.append(target)
    return tuple(objects)


def _project_interface(geometry: Any, objects: tuple[str, ...]) -> None:
    """Imprint the work plane's metal outlines onto the z = 0 interface.

    The tool is every face of every metal object, taken by object name so each
    outline brings its holes along; the target is the interface Box selection,
    named rather than listed because the face it holds does not exist until the
    sequence runs. Imprinting the projected outlines is what splits the
    interface into metal, hole, and ground faces.
    """
    geometry.create(_PROJECTION_TAG, "ProjectToFaces")
    projection = geometry.feature(_PROJECTION_TAG)
    projection.selection("target").named(_INTERFACE_SELECTION)
    tool = projection.selection("tool")
    tool.init(2)
    for tag in objects:
        tool.all(f"{_WORK_PLANE_TAG}.{tag}")
    projection.set("imprint", "on")


def _face_probe(
    component: Any,
    tag: str,
    point: Point,
    region: BaseGeometry,
    z_half_extent_um: float,
) -> tuple[int, ...]:
    """Add a Box probe that fits inside ``region`` around ``point`` and read it back.

    The box stops a quarter of the way to the region's nearest boundary and no
    further than ``z_half_extent_um`` in z, so it holds the one face that region
    became and no exterior face, however narrow the region is. ``region`` may be
    several pieces, as a hole cut by an island is, as long as ``point`` is in it.

    Returns:
        The entities the selection resolved to, as COMSOL reports them.
    """
    room = region.boundary.distance(ShapelyPoint(point))
    half_width = min(_PROBE_MAX_HALF_WIDTH_UM, _PROBE_BOUNDARY_FRACTION * room)
    half_height = min(half_width, z_half_extent_um)
    component.selection().create(tag, "Box")
    selection = component.selection(tag)
    # entitydim is a string: an int makes JPype pick the numeric set() overload.
    selection.set("entitydim", "2")
    selection.set("condition", "intersects")
    for axis, value in zip("xy", point):
        selection.set(f"{axis}min", _format_number(value - half_width))
        selection.set(f"{axis}max", _format_number(value + half_width))
    selection.set("zmin", _format_number(-half_height))
    selection.set("zmax", _format_number(half_height))
    return tuple(selection.entities())


def _check_imprint(
    component: Any,
    layout: ComsolLayout,
    *,
    substrate_thickness_um: float,
    air_height_um: float,
) -> None:
    """Prove the metal polygons and their holes survived the union as faces.

    A point inside a polygon has to pick exactly one face, otherwise the polygon
    is degenerate or the imprint left the interface whole. A hole is probed where
    it is dielectric, past any island sitting in it, and that point has to pick
    exactly one face too, a face other than the metal one: a hole that imprints
    nothing leaves the metal solid there, and a hole that imprints as part of the
    metal is not a hole at all.

    Raises:
        ValueError: If a polygon or hole probe does not select exactly one face,
            if a hole probe selects the metal face, which means the holes were
            imprinted nowhere and the metal sheet is solid, or if a hole holds no
            dielectric to probe because other metal polygons cover it.
    """
    z_half_extent_um = _SELECTION_Z_FRACTION * min(
        substrate_thickness_um, air_height_um
    )
    for index, polygon in enumerate(layout.polygons):
        metal_region = Polygon(polygon.outline, polygon.holes)
        metal_point = metal_region.representative_point()
        metal = _face_probe(
            component,
            f"{_PROBE_PREFIX}_metal{index}",
            (metal_point.x, metal_point.y),
            metal_region,
            z_half_extent_um,
        )
        if len(metal) != 1:
            raise ValueError(
                f"metal polygon {index} selects {len(metal)} faces on the z = 0 "
                "interface, expected one: the work plane imprint did not turn it "
                "into a single sheet face"
            )
        for hole, points in enumerate(polygon.holes):
            hole_region = Polygon(points)
            # Another island can sit inside the hole, so the probe has to aim at
            # what is dielectric there, not at the hole's own middle.
            for other, other_polygon in enumerate(layout.polygons):
                if other != index:
                    hole_region = hole_region.difference(
                        Polygon(other_polygon.outline, other_polygon.holes)
                    )
            if hole_region.is_empty:
                raise ValueError(
                    f"hole {hole} of metal polygon {index} leaves no dielectric to "
                    "probe: other metal polygons cover it completely"
                )
            hole_point = hole_region.representative_point()
            hole_faces = _face_probe(
                component,
                f"{_PROBE_PREFIX}_hole{index}_{hole}",
                (hole_point.x, hole_point.y),
                hole_region,
                z_half_extent_um,
            )
            if len(hole_faces) != 1:
                raise ValueError(
                    f"hole {hole} of metal polygon {index} selects "
                    f"{len(hole_faces)} faces on the z = 0 interface, expected "
                    "one: the hole did not become a face of its own"
                )
            if set(hole_faces) & set(metal):
                raise ValueError(
                    f"hole {hole} of metal polygon {index} did not survive the "
                    f"imprint: a point inside it resolves to faces {hole_faces}, "
                    f"the same as the metal face {metal}, so the metal is solid "
                    "there"
                )


def build_comsol_sheet_model(
    client: mph.Client,
    layout: ComsolLayout,
    name: str,
    *,
    substrate_thickness_um: float = 200.0,
    air_height_um: float = 200.0,
    lateral_margin_um: float = 0.0,
    silicon_relative_permittivity: float = SILICON_RELATIVE_PERMITTIVITY,
    air_relative_permittivity: float = AIR_RELATIVE_PERMITTIVITY,
) -> mph.Model:
    """Create a COMSOL 3D model holding the layout's metal as interface sheets.

    The air and silicon blocks touch at ``z = 0`` and span the layout bounding
    box grown by ``lateral_margin_um``. A layout without holes puts the metal
    polygons on a work plane and lets Form Union leave one face per polygon. A
    layout with holes keeps the interface between the blocks and projects a
    construction work plane's faces onto it, so the model ends up with two
    dielectric domains and one face per metal and per hole region.

    A layout with holes is built with the Design Module's ``ProjectToFaces``
    feature and the CAD kernel geometry representation, so it needs the Design
    Module license; a layout without holes needs neither.

    Args:
        client: A connected :class:`mph.Client`.
        layout: Extracted metal polygons and bounding box in µm.
        name: Name of the COMSOL model.
        substrate_thickness_um: Silicon thickness below the interface, in µm.
        air_height_um: Air height above the interface, in µm.
        lateral_margin_um: Margin around the layout bounding box for both
            blocks, in µm. Leave it at 0 for
            :func:`~gplugins.comsol.rf.add_cpw_rf_study`, whose ports have to
            sit on the outer faces where the feed metal ends.
        silicon_relative_permittivity: Relative permittivity of the silicon
            block, positive and finite. Defaults to
            :data:`SILICON_RELATIVE_PERMITTIVITY`.
        air_relative_permittivity: Relative permittivity of the air block,
            positive and finite. Defaults to :data:`AIR_RELATIVE_PERMITTIVITY`.

    Returns:
        The MPh model, with geometry, selections, and materials only.

    Raises:
        ValueError: If a thickness is not positive and finite, if the margin is
            negative or not finite, if the permittivity is not positive and
            finite, if the layout has no polygons, or, for a layout with holes,
            if the built geometry does not carry one face per metal polygon with
            the holes still cut out of the metal.
    """
    for label, thickness in (
        ("substrate_thickness_um", substrate_thickness_um),
        ("air_height_um", air_height_um),
    ):
        if not math.isfinite(thickness) or thickness <= 0.0:
            raise ValueError(f"{label} must be positive and finite, got {thickness!r}")
    if not math.isfinite(lateral_margin_um) or lateral_margin_um < 0.0:
        raise ValueError(
            "lateral_margin_um must be finite and non-negative, "
            f"got {lateral_margin_um!r}"
        )
    for label, permittivity in (
        ("silicon_relative_permittivity", silicon_relative_permittivity),
        ("air_relative_permittivity", air_relative_permittivity),
    ):
        if not math.isfinite(permittivity) or permittivity <= 0.0:
            raise ValueError(
                f"{label} must be positive and finite, got {permittivity!r}"
            )
    if not layout.polygons:
        raise ValueError("layout has no metal polygons to imprint")

    model = client.create(name)
    try:
        model.java.component().create("comp1")
        component = model.java.component("comp1")
        geometry = component.geom().create("geom1", 3)
        geometry.lengthUnit("um")
        has_holes = any(polygon.holes for polygon in layout.polygons)
        if has_holes:
            # ProjectToFaces is a Design Module feature and needs the CAD kernel.
            geometry.geomRep("cadps")

        west, south = (
            layout.bbox.xmin - lateral_margin_um,
            layout.bbox.ymin - lateral_margin_um,
        )
        width = layout.bbox.width + 2.0 * lateral_margin_um
        depth = layout.bbox.height + 2.0 * lateral_margin_um
        _add_block(geometry, "air", (west, south, 0.0), (width, depth, air_height_um))
        _add_block(
            geometry,
            "si",
            (west, south, -substrate_thickness_um),
            (width, depth, substrate_thickness_um),
        )
        if has_holes:
            _union_blocks(geometry)
            _add_interface_selection(
                geometry,
                west,
                south,
                width,
                depth,
                substrate_thickness_um,
                air_height_um,
            )
            metal_objects = _add_metal_sheets(geometry, layout, construction=True)
            _project_interface(geometry, metal_objects)
        else:
            _add_metal_sheets(geometry, layout, construction=False)

        geometry.feature("fin").set("action", "union")
        geometry.run()

        if has_holes:
            _check_imprint(
                component,
                layout,
                substrate_thickness_um=substrate_thickness_um,
                air_height_um=air_height_um,
            )

        centre = (
            (layout.bbox.xmin + layout.bbox.xmax) / 2.0,
            (layout.bbox.ymin + layout.bbox.ymax) / 2.0,
        )
        air_domains = _add_domain_selection(
            component,
            AIR_SELECTION,
            (centre[0], centre[1], 0.5 * air_height_um),
            air_height_um,
        )
        silicon_domains = _add_domain_selection(
            component,
            SILICON_SELECTION,
            (centre[0], centre[1], -0.5 * substrate_thickness_um),
            substrate_thickness_um,
        )
        if (
            len(air_domains) != 1
            or len(silicon_domains) != 1
            or air_domains == silicon_domains
        ):
            raise ValueError(
                "air and silicon selections must resolve to one distinct domain "
                f"each, got air={air_domains} and silicon={silicon_domains}"
            )

        _add_material(component, "matAir", AIR_SELECTION, air_relative_permittivity)
        _add_material(
            component, "matSi", SILICON_SELECTION, silicon_relative_permittivity
        )
    except BaseException:
        # A half-built native model would otherwise pile up in the COMSOL
        # process on every retry; the build failure is what matters, so a
        # failing cleanup must not mask it.
        with contextlib.suppress(Exception):
            client.remove(model)
        raise

    return model
