"""Tests for the COMSOL sheet-model builder.

MPh and COMSOL are not installed here, so a small fake of the Java tree stands
in for them. The geometry, selection, and material assertions use real
:class:`~gplugins.comsol.layout.ComsolLayout` input, so the builder's own
arithmetic is checked rather than re-implemented.

Face probes are resolved against a hand-written model of the interface: for a
layout with holes, one face per metal polygon and one per hole once the sequence
projects the work plane's metal onto it, and a single face covering all of it
when it does not. The regions are cut out of one another, so an island drawn
inside a hole takes that part of the hole away from the dielectric face. The fake settles that from the calls the builder made, so the
wiring itself is what the imprint tests exercise: the union that keeps the
interface, the Box selection that holds it, the construction work plane, and the
projection that imprints its metal objects.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from gplugins.comsol._util import _format_number
from gplugins.comsol.layout import (
    ComsolBoundingBox,
    ComsolLayout,
    ComsolPolygon,
)
from gplugins.comsol.sheet import (
    SILICON_RELATIVE_PERMITTIVITY,
    build_comsol_sheet_model,
)

_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((-10.0, -5.0), (10.0, -5.0), (10.0, 5.0), (-10.0, 5.0)),
            holes=(((-2.0, -1.0), (-1.0, -1.0), (-1.0, 1.0), (-2.0, 1.0)),),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=-10.0, ymin=-5.0, xmax=10.0, ymax=5.0),
)
#: A polygon with a hole and one without, so both endings of the per-polygon
#: tag run are covered: a Difference for the first, its own Polygon for the
#: second.
_TWO_POLYGON_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((-10.0, -5.0), (0.0, -5.0), (0.0, 5.0), (-10.0, 5.0)),
            holes=(((-4.0, -1.0), (-3.0, -1.0), (-3.0, 1.0), (-4.0, 1.0)),),
        ),
        ComsolPolygon(
            outline=((2.0, -5.0), (10.0, -5.0), (10.0, 5.0), (2.0, 5.0)),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=-10.0, ymin=-5.0, xmax=10.0, ymax=5.0),
)
#: A layout with no holes at all: the original blocks, work plane, Form Union
#: sequence, with no projection and no Design Module feature.
_NO_HOLE_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((-10.0, -5.0), (10.0, -5.0), (10.0, 5.0), (-10.0, 5.0)),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=-10.0, ymin=-5.0, xmax=10.0, ymax=5.0),
)
#: A hole narrower than the probe cap, so the probe box has to shrink to fit it.
_NARROW_HOLE_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((-10.0, -5.0), (10.0, -5.0), (10.0, 5.0), (-10.0, 5.0)),
            holes=(((-0.005, -1.0), (0.005, -1.0), (0.005, 1.0), (-0.005, 1.0)),),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=-10.0, ymin=-5.0, xmax=10.0, ymax=5.0),
)
#: A hole with a separate island inside it, covering the hole's own middle, (5,
#: 5), which is where the hole probe used to aim.
_ISLAND_IN_HOLE_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
            holes=(((2.0, 2.0), (8.0, 2.0), (8.0, 8.0), (2.0, 8.0)),),
        ),
        ComsolPolygon(
            outline=((4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=0.0, ymin=0.0, xmax=10.0, ymax=10.0),
)
#: The same, with the island's edge through the hole's middle, so the old probe
#: box straddled that edge.
_ISLAND_EDGE_ON_HOLE_MIDDLE_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
            holes=(((2.0, 2.0), (8.0, 2.0), (8.0, 8.0), (2.0, 8.0)),),
        ),
        ComsolPolygon(
            outline=((5.0, 4.0), (6.0, 4.0), (6.0, 6.0), (5.0, 6.0)),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=0.0, ymin=0.0, xmax=10.0, ymax=10.0),
)
#: An island filling a hole exactly, leaving no dielectric in it to probe.
_FILLED_HOLE_LAYOUT = ComsolLayout(
    polygons=(
        ComsolPolygon(
            outline=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
            holes=(((2.0, 2.0), (8.0, 2.0), (8.0, 8.0), (2.0, 8.0)),),
        ),
        ComsolPolygon(
            outline=((2.0, 2.0), (8.0, 2.0), (8.0, 8.0), (2.0, 8.0)),
        ),
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=0.0, ymin=0.0, xmax=10.0, ymax=10.0),
)
_EMPTY_LAYOUT = ComsolLayout(
    polygons=(),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=-10.0, ymin=-5.0, xmax=10.0, ymax=5.0),
)

_UNION_TAG = "uni1"
_INTERFACE_SELECTION = "interface"
_WORK_PLANE_TAG = "wp1"
_PROJECTION_TAG = "proj1"

#: The dielectric interface face: the whole interface when the imprint is lost,
#: and the plain sheet where no metal or hole sits when it is there. The exterior
#: faces are what a probe picks up if it reaches past a block in z.
_INTERFACE_FACE = 1
_AIR_TOP_FACE = 2
_SILICON_BOTTOM_FACE = 3


class _Interface:
    """The z = 0 interface the face probes are resolved against.

    Only the sequence a layout with holes takes is modelled here; the no-hole
    path is checked on the calls it makes, not on faces.

    ``imprint_lost`` models what the live 6.3 build reported for both partition
    attempts: the whole interface stayed one face, so a point in a hole landed
    on the same face as the metal around it.
    """

    def __init__(
        self,
        layout: ComsolLayout,
        *,
        substrate_thickness_um: float = 200.0,
        air_height_um: float = 200.0,
        imprint_lost: bool = False,
    ) -> None:
        self.layout = layout
        self.substrate_thickness_um = substrate_thickness_um
        self.air_height_um = air_height_um
        self.imprint_lost = imprint_lost
        self.imprinted = not imprint_lost

    def faces_at(self, properties: dict[str, Any]) -> list[int]:
        """Return the faces a recorded Box probe resolves to.

        The box picks every interface region it overlaps in x and y, so one that
        reaches across a region boundary picks both sides of it. It picks the
        dielectric interface when it overlaps no metal and no hole, and a block's
        exterior face when it reaches past that block in z.

        Returns:
            The face IDs, or the single face the whole interface collapses to
            when the imprint is lost.
        """
        if not self.imprinted:
            return [_INTERFACE_FACE]
        span = {
            axis: (float(properties[f"{axis}min"]), float(properties[f"{axis}max"]))
            for axis in "xyz"
        }
        faces: list[int] = []
        if span["z"][1] > self.air_height_um:
            faces.append(_AIR_TOP_FACE)
        if span["z"][0] < -self.substrate_thickness_um:
            faces.append(_SILICON_BOTTOM_FACE)
        probe = Polygon.from_bounds(
            span["x"][0], span["y"][0], span["x"][1], span["y"][1]
        )
        regions = [
            face for face, region in self._face_regions() if region.intersects(probe)
        ]
        return faces + (regions or [_INTERFACE_FACE])

    def _face_regions(self) -> list[tuple[int, BaseGeometry]]:
        """Return one region per metal polygon and per hole, cut apart.

        The imprint runs along every outline, so each metal polygon is cut by the
        others and each hole by all of them: an island inside a hole is not part
        of the dielectric that hole leaves behind.

        Returns:
            The face IDs with the region each one covers.
        """
        metal = [
            Polygon(polygon.outline, polygon.holes) for polygon in self.layout.polygons
        ]
        everything = unary_union(metal)
        regions: list[tuple[int, BaseGeometry]] = []
        for index, polygon in enumerate(self.layout.polygons):
            others = unary_union(
                [region for other, region in enumerate(metal) if other != index]
            )
            regions.append((100 + index, metal[index].difference(others)))
            for hole, ring in enumerate(polygon.holes):
                regions.append(
                    (
                        200 + 10 * index + hole,
                        Polygon(ring).difference(everything),
                    )
                )
        return regions


class _Node:
    """Stands in for a feature node, recording properties and selections."""

    def __init__(self, interface: _Interface) -> None:
        self.interface = interface
        self.properties: dict[str, Any] = {}
        self.attributes: dict[str, str] = {}
        self.named_tags: list[str] = []
        self.references: list[str] = []
        self.set_calls: list[tuple[Any, ...]] = []
        self.inits: list[int] = []
        self.all_calls: list[str] = []
        self.children: dict[str, _Node] = {}
        self.planes: dict[str, _Group] = {}

    def child(self, tag: str) -> _Node:
        """Return the child filed under ``tag``, creating it if needed."""
        return self.children.setdefault(tag, _Node(self.interface))

    def selection(self, tag: str | None = None) -> _Node:
        """Return the node's own selection, or a child selection by name."""
        if tag is None:
            return self
        return self.child(f"selection:{tag}")

    def propertyGroup(self, tag: str) -> _Node:  # ruff: ignore[invalid-function-name]
        """Return a material property group by tag."""
        return self.child(f"group:{tag}")

    def geom(self) -> _Group:
        """Return the work plane's own geometry sequence."""
        return self.planes.setdefault("wpgeom", _Group(self.interface))

    def set(self, *args: Any) -> None:
        """Record a ``set`` call, as properties or as named references.

        A one-argument call names an entity, which is how a geometry feature
        takes its input objects; a two-argument call is a property.
        """
        self.set_calls.append(args)
        if len(args) == 1:
            self.references.append(args[0])
        else:
            name, value = args
            self.properties[name] = value

    def setAttribute(self, name: str, value: str) -> None:  # ruff: ignore[invalid-function-name]
        """Record a geometry feature attribute."""
        self.attributes[name] = value

    def named(self, tag: str) -> None:
        """Record an assignment to a named selection."""
        self.named_tags.append(tag)

    def init(self, dim: int) -> None:
        """Record a selection initialised to one entity dimension."""
        self.inits.append(dim)

    def all(self, object_name: str) -> None:
        """Record a selection widened to every entity of one object."""
        self.all_calls.append(object_name)

    def entities(self) -> list[int]:
        """Resolve a probe against the fake geometry."""
        if self.properties.get("entitydim") == "2":
            return self.interface.faces_at(self.properties)
        if "zmin" not in self.properties:
            return []
        zmin, zmax = (float(self.properties[key]) for key in ("zmin", "zmax"))
        if zmin >= 0:
            return [1]
        if zmax <= 0:
            return [2]
        return [1, 2]


class _Group:
    """Stands in for a COMSOL collection: ``create`` makes children."""

    def __init__(self, interface: _Interface, factory: Any = _Node) -> None:
        self.interface = interface
        self.created: list[tuple[Any, ...]] = []
        self.children: dict[str, _Node] = {}
        self._factory = factory

    def __call__(self, tag: str | None = None) -> Any:
        """Return this collection, or the child node filed under ``tag``."""
        if tag is None:
            return self
        return self.children.setdefault(tag, self._factory(self.interface))

    def create(self, tag: str, *args: Any) -> _Node:
        """Record a create call and return the new child node."""
        self.created.append((tag, *args))
        return self(tag)

    def feature(self, tag: str) -> _Node:
        """Return a child feature by tag."""
        return self(tag)


class _Geometry(_Group):
    """Stands in for the geometry sequence."""

    def __init__(self, interface: _Interface) -> None:
        super().__init__(interface)
        self.unit: str | None = None
        self.geom_rep: str | None = None
        self.geom_rep_feature_count = 0
        self.runs = 0

    def lengthUnit(self, unit: str) -> None:  # ruff: ignore[invalid-function-name]
        """Record the length unit."""
        self.unit = unit

    def geomRep(self, representation: str) -> None:  # ruff: ignore[invalid-function-name]
        """Record the geometry representation and the features already made."""
        self.geom_rep = representation
        self.geom_rep_feature_count = len(self.created)

    def run(self) -> None:
        """Record a geometry run and settle what the interface came out as."""
        self.runs += 1
        self.interface.imprinted = (
            not self.interface.imprint_lost and self._imprint_is_wired()
        )

    def _imprint_is_wired(self) -> bool:
        """Return whether the sequence is the one the fake assumes imprints.

        The fake resolves one face per metal and hole region only when the union
        kept the interface, a Box selection holds that one face, the work plane
        is construction geometry, and the projection targets that selection with
        the plane's metal faces as its tool. That is the fake's model of the
        imprint, not live evidence for any of these calls.

        Returns:
            ``True`` when every call the imprint needs was made.
        """
        union = self.children.get(_UNION_TAG)
        selection = self.children.get(_INTERFACE_SELECTION)
        work_plane = self.children.get(_WORK_PLANE_TAG)
        projection = self.children.get(_PROJECTION_TAG)
        if union is None or selection is None or work_plane is None:
            return False
        if projection is None:
            return False
        if union.properties.get("intbnd") != "on":
            return False
        if selection.properties.get("entitydim") != "2":
            return False
        if work_plane.attributes.get("construction") != "on":
            return False
        if projection.properties.get("imprint") != "on":
            return False
        target = projection.children.get("selection:target")
        if target is None or target.named_tags != [_INTERFACE_SELECTION]:
            return False
        tool = projection.children.get("selection:tool")
        return tool is not None and tool.inits == [2] and bool(tool.all_calls)


class _Component:
    """Stands in for ``comp1``: its geometry, selections, and materials."""

    def __init__(self, interface: _Interface) -> None:
        self.geometries = _Group(interface, _Geometry)
        self.selections = _Group(interface)
        self.materials = _Group(interface)

    def geom(self, tag: str | None = None) -> Any:
        """Return the geometry collection, or one geometry by tag."""
        return self.geometries if tag is None else self.geometries(tag)

    def selection(self, tag: str | None = None) -> Any:
        """Return the selection collection, or one selection by tag."""
        return self.selections if tag is None else self.selections(tag)

    def material(self, tag: str | None = None) -> Any:
        """Return the material collection, or one material by tag."""
        return self.materials if tag is None else self.materials(tag)


class _FakeJava:
    """The fake ``model.java`` tree."""

    def __init__(self, interface: _Interface) -> None:
        self.interface = interface
        self.component = _Group(interface, _Component)
        self.mesh = _Group(interface)
        self.study = _Group(interface)


def _client(
    *,
    layout: ComsolLayout = _LAYOUT,
    substrate_thickness_um: float = 200.0,
    air_height_um: float = 200.0,
    imprint_lost: bool = False,
) -> MagicMock:
    """Return a client whose created model carries the fake Java tree.

    The slab thicknesses are what the fake checks a probe's z extent against, so
    they have to match the ones the build is given.

    Returns:
        The client double.
    """
    client = MagicMock()
    client.create.return_value.java = _FakeJava(
        _Interface(
            layout,
            substrate_thickness_um=substrate_thickness_um,
            air_height_um=air_height_um,
            imprint_lost=imprint_lost,
        )
    )
    return client


def _build(
    client: MagicMock, layout: ComsolLayout = _LAYOUT, **overrides: Any
) -> _Component:
    """Build a sheet model with the fake client and return its component.

    Returns:
        The fake ``comp1``.
    """
    build_comsol_sheet_model(client, layout, "qubit", **overrides)
    return client.create.return_value.java.component("comp1")


def _centre(box: dict[str, Any]) -> Point:
    """Return the centre of a recorded box.

    Returns:
        The centre in µm.
    """
    return Point(
        (float(box["xmin"]) + float(box["xmax"])) / 2.0,
        (float(box["ymin"]) + float(box["ymax"])) / 2.0,
    )


def _box(properties: dict[str, Any]) -> Polygon:
    """Return the x-y footprint of a recorded box.

    Returns:
        The box in µm.
    """
    return Polygon.from_bounds(
        float(properties["xmin"]),
        float(properties["ymin"]),
        float(properties["xmax"]),
        float(properties["ymax"]),
    )


def test_blocks_touch_at_the_interface_and_span_the_bbox():
    """Air sits on silicon at z = 0, both exactly the layout's bounding box."""
    component = _build(_client())
    geometry = component.geom("geom1")

    assert geometry.unit == "um"
    assert [args[0] for _, *args in geometry.created] == [
        "Block",
        "Block",
        "Union",
        "BoxSelection",
        "WorkPlane",
        "ProjectToFaces",
    ]
    assert [float(value) for value in geometry.feature("air").properties["size"]] == [
        20.0,
        10.0,
        200.0,
    ]
    assert [float(value) for value in geometry.feature("air").properties["pos"]] == [
        -10.0,
        -5.0,
        0.0,
    ]
    assert [float(value) for value in geometry.feature("si").properties["size"]] == [
        20.0,
        10.0,
        200.0,
    ]
    assert [float(value) for value in geometry.feature("si").properties["pos"]] == [
        -10.0,
        -5.0,
        -200.0,
    ]


def test_thicknesses_and_margin_are_configurable():
    """The blocks follow the requested thicknesses and lateral margin."""
    component = _build(
        _client(),
        substrate_thickness_um=50.0,
        air_height_um=30.0,
        lateral_margin_um=5.0,
    )
    geometry = component.geom("geom1")

    assert [float(value) for value in geometry.feature("air").properties["size"]] == [
        30.0,
        20.0,
        30.0,
    ]
    assert [float(value) for value in geometry.feature("si").properties["pos"]] == [
        -15.0,
        -10.0,
        -50.0,
    ]


def test_thin_slabs_keep_domain_probes_on_opposite_sides_of_interface():
    component = _build(_client(), substrate_thickness_um=0.01, air_height_um=0.01)
    assert float(component.selection("air").properties["zmin"]) > 0
    assert float(component.selection("si").properties["zmax"]) < 0


def test_metal_is_a_work_plane_polygon_with_the_hole_subtracted():
    """The sheet keeps the layout's outline and subtracts its holes."""
    component = _build(_client())
    work_plane = component.geom("geom1").feature("wp1").geom()

    assert work_plane.created == [
        ("pol0", "Polygon"),
        ("hole0_0", "Polygon"),
        ("dif0_0", "Difference"),
    ]
    assert work_plane.feature("pol0").properties["x"] == "-10,10,10,-10"
    assert work_plane.feature("pol0").properties["y"] == "-5,-5,5,5"
    assert work_plane.feature("hole0_0").properties["x"] == "-2,-1,-1,-2"
    difference = work_plane.feature("dif0_0")
    assert difference.selection("input").references == ["pol0"]
    assert difference.selection("input2").references == ["hole0_0"]


def test_geometry_is_unioned_and_run_once():
    """The finalization is a union, the sequence runs once, nothing extrudes."""
    geometry = _build(_client()).geom("geom1")

    assert geometry.feature("fin").properties["action"] == "union"
    assert geometry.runs == 1
    assert "Extrude" not in {args[0] for _, *args in geometry.created if args}


def test_the_blocks_are_unioned_with_the_interface_kept():
    """The union names both blocks and keeps the boundary between them."""
    geometry = _build(_client()).geom("geom1")
    union = geometry.feature(_UNION_TAG)

    assert union.properties["intbnd"] == "on"
    assert union.selection("input").set_calls == [("air", "si")]


def test_the_interface_selection_holds_the_flat_interior_face():
    """One geometry Box selection, reaching past the blocks and past z = 0."""
    geometry = _build(_client()).geom("geom1")
    selection = geometry.feature(_INTERFACE_SELECTION).properties

    assert selection["entitydim"] == "2"
    assert selection["condition"] == "inside"
    # The blocks span x from -10 to 10 and y from -5 to 5, both 200 µm thick.
    assert float(selection["xmin"]) < -10.0
    assert float(selection["xmax"]) > 10.0
    assert float(selection["ymin"]) < -5.0
    assert float(selection["ymax"]) > 5.0
    # The side faces start at z = 0 and run a whole thickness, so a box that
    # stops a quarter of the way into each block leaves them out.
    assert -200.0 < float(selection["zmin"]) < 0.0
    assert 0.0 < float(selection["zmax"]) < 200.0


def test_the_work_plane_is_construction_geometry():
    """The plane is a projection tool, not an object the union takes apart."""
    geometry = _build(_client()).geom("geom1")

    assert geometry.feature(_WORK_PLANE_TAG).attributes == {"construction": "on"}


def test_the_metal_faces_are_projected_onto_the_named_interface():
    """ProjectToFaces targets that one face and takes the metal as its tool."""
    geometry = _build(_client()).geom("geom1")
    projection = geometry.feature(_PROJECTION_TAG)

    assert geometry.created == [
        ("air", "Block"),
        ("si", "Block"),
        (_UNION_TAG, "Union"),
        (_INTERFACE_SELECTION, "BoxSelection"),
        (_WORK_PLANE_TAG, "WorkPlane"),
        (_PROJECTION_TAG, "ProjectToFaces"),
    ]
    assert projection.properties == {"imprint": "on"}
    assert projection.selection("target").named_tags == [_INTERFACE_SELECTION]
    tool = projection.selection("tool")
    assert tool.inits == [2]
    # Polygon 0 has a hole, so its object is the Difference of the two.
    assert tool.all_calls == [f"{_WORK_PLANE_TAG}.dif0_0"]
    # The CAD kernel representation, set before any feature is created.
    assert geometry.geom_rep == "cadps"
    assert geometry.geom_rep_feature_count == 0


def test_every_metal_object_is_projected_by_its_own_name():
    """A polygon without holes keeps its own tag as the object name."""
    layout = _TWO_POLYGON_LAYOUT
    geometry = _build(_client(layout=layout), layout).geom("geom1")

    tool = geometry.feature(_PROJECTION_TAG).selection("tool")
    assert tool.all_calls == [
        f"{_WORK_PLANE_TAG}.dif0_0",
        f"{_WORK_PLANE_TAG}.pol1",
    ]


def test_a_layout_without_holes_keeps_the_original_sequence():
    """No holes means no projection, no guard, and a plain work plane.

    The solved qubit capacitance models were built from this sequence, so it
    stays exactly two blocks, the work plane, and Form Union.
    """
    layout = _NO_HOLE_LAYOUT
    component = _build(_client(layout=layout), layout)
    geometry = component.geom("geom1")

    assert geometry.created == [
        ("air", "Block"),
        ("si", "Block"),
        (_WORK_PLANE_TAG, "WorkPlane"),
    ]
    # No Design Module feature, so this path needs no DESIGN license.
    assert "ProjectToFaces" not in {args[0] for _, *args in geometry.created if args}
    assert geometry.geom_rep is None
    assert geometry.feature(_WORK_PLANE_TAG).attributes == {}
    assert component.selections.created == [("air", "Box"), ("si", "Box")]


def test_metal_and_holes_become_separate_interface_faces():
    """A probe in the metal and a probe in its hole pick different faces."""
    component = _build(_client())
    metal = component.selection("imprint_metal0")
    hole = component.selection("imprint_hole0_0")

    assert metal.entities() == [100]
    assert hole.entities() == [200]
    for probe in (metal, hole):
        span = probe.properties
        assert span["entitydim"] == "2"
        assert span["condition"] == "intersects"
        assert float(span["xmax"]) - float(span["xmin"]) == pytest.approx(0.02)
        assert float(span["ymax"]) - float(span["ymin"]) == pytest.approx(0.02)
        assert float(span["zmin"]) < 0.0 < float(span["zmax"])

    # The metal probe sits in the metal, the hole probe in the cut-out.
    polygon = _LAYOUT.polygons[0]
    assert Polygon(polygon.outline, polygon.holes).contains(_centre(metal.properties))
    assert Polygon(polygon.holes[0]).contains(_centre(hole.properties))


def test_a_hole_probe_avoids_an_island_over_the_hole_middle():
    """An island over the hole's middle does not fail a correct imprint.

    The hole probe used to aim at the hole's own representative point, (5, 5),
    which this island covers; the probe then picked the island's face as well as
    the hole's.
    """
    layout = _ISLAND_IN_HOLE_LAYOUT
    component = _build(_client(layout=layout), layout)
    ring = Polygon(layout.polygons[0].holes[0])
    island = Polygon(layout.polygons[1].outline)

    assert ring.representative_point().within(island)
    assert component.selection("imprint_metal1").entities() == [101]
    probe = _box(component.selection("imprint_hole0_0").properties)
    assert probe.within(ring)
    assert not probe.intersects(island)
    assert component.selection("imprint_hole0_0").entities() == [200]


def test_a_hole_probe_avoids_an_island_edge_through_the_hole_middle():
    """An island edge through the hole's middle is stepped around as well."""
    layout = _ISLAND_EDGE_ON_HOLE_MIDDLE_LAYOUT
    component = _build(_client(layout=layout), layout)
    ring = Polygon(layout.polygons[0].holes[0])
    island = Polygon(layout.polygons[1].outline)

    # The island's edge runs exactly through the hole's representative point.
    point = ring.representative_point()
    assert island.intersects(point)
    assert not point.within(island)
    assert component.selection("imprint_metal1").entities() == [101]
    probe = _box(component.selection("imprint_hole0_0").properties)
    assert probe.within(ring)
    assert not probe.intersects(island)
    assert component.selection("imprint_hole0_0").entities() == [200]


def test_a_hole_covered_by_metal_leaves_no_dielectric_to_probe():
    """A hole with no dielectric left in it is refused, not probed empty."""
    layout = _FILLED_HOLE_LAYOUT
    with pytest.raises(ValueError, match="leaves no dielectric to probe"):
        _build(_client(layout=layout), layout)


def test_a_hole_probe_that_finds_no_face_is_refused(
    monkeypatch: pytest.MonkeyPatch,
):
    """A hole that imprints nothing leaves the metal solid there."""
    client = _client()
    inside_interface = _Interface.faces_at

    def no_face_in_hole(self: _Interface, properties: dict[str, Any]) -> list[int]:
        """Resolve as usual, but leave the hole regions without any face."""
        faces = inside_interface(self, properties)
        return [] if faces and faces[0] >= 200 else faces

    monkeypatch.setattr(_Interface, "faces_at", no_face_in_hole)
    with pytest.raises(ValueError, match="hole 0 of metal polygon 0 selects 0 faces"):
        _build(client)


def test_a_narrow_hole_probe_shrinks_to_fit_the_hole():
    """A hole a hundredth of a micron wide still gets a box of its own."""
    layout = _NARROW_HOLE_LAYOUT
    component = _build(_client(layout=layout), layout)
    hole = component.selection("imprint_hole0_0")

    assert hole.entities() == [200]
    span = hole.properties
    # A quarter of the 0.005 µm from the hole's centre to its nearest edge.
    assert float(span["xmax"]) - float(span["xmin"]) == pytest.approx(0.0025)
    assert float(span["xmin"]) >= -0.005
    assert float(span["xmax"]) <= 0.005


def test_thin_slabs_keep_the_probe_inside_the_blocks():
    """A probe that reached past a slab would pick up that block's outer face."""
    client = _client(substrate_thickness_um=0.01, air_height_um=0.01)
    component = _build(client, substrate_thickness_um=0.01, air_height_um=0.01)

    assert component.selection("imprint_metal0").entities() == [100]
    assert component.selection("imprint_hole0_0").entities() == [200]
    for tag in ("imprint_metal0", "imprint_hole0_0"):
        span = component.selection(tag).properties
        assert float(span["zmax"]) <= 0.01 / 4.0
        assert float(span["zmin"]) >= -0.01 / 4.0


def test_an_imprint_that_leaves_one_interface_face_is_refused():
    """A geometry whose interface stayed whole is refused, holes and all."""
    with pytest.raises(ValueError, match="did not survive the imprint"):
        _build(_client(imprint_lost=True))


def test_a_metal_probe_that_misses_its_own_face_is_refused(
    monkeypatch: pytest.MonkeyPatch,
):
    """A polygon that resolves to no face means the imprint is not there."""
    monkeypatch.setattr(_Interface, "faces_at", lambda _self, _: [])
    with pytest.raises(ValueError, match="selects 0 faces on the z = 0"):
        _build(_client())


def test_dielectric_domains_are_selected_and_materialized():
    """Each domain gets a Box selection and a Common material with epsilon r."""
    component = _build(_client())

    assert component.selections.created == [
        ("imprint_metal0", "Box"),
        ("imprint_hole0_0", "Box"),
        ("air", "Box"),
        ("si", "Box"),
    ]
    air = component.selection("air").properties
    assert air["entitydim"] == "3"
    assert air["condition"] == "intersects"
    assert 0.0 < float(air["zmin"]) < float(air["zmax"])
    for axis in "xy":
        assert float(air[f"{axis}min"]) < 0.0 < float(air[f"{axis}max"])
    silicon = component.selection("si").properties
    assert float(silicon["zmin"]) < float(silicon["zmax"]) < 0.0

    assert component.materials.created == [("matAir", "Common"), ("matSi", "Common")]
    air_material = component.material("matAir")
    silicon_material = component.material("matSi")
    assert air_material.named_tags == ["air"]
    assert silicon_material.named_tags == ["si"]
    assert air_material.propertyGroup("def").properties["relpermittivity"] == "1"
    assert silicon_material.propertyGroup("def").properties[
        "relpermittivity"
    ] == _format_number(SILICON_RELATIVE_PERMITTIVITY)
    for material in (air_material, silicon_material):
        properties = material.propertyGroup("def").properties
        assert properties["relpermeability"] == "1"
        assert properties["electricconductivity"] == "0"
    assert "epsilonr" not in silicon_material.propertyGroup("def").properties


def test_permittivities_default_to_the_module_constants():
    """Without overrides the blocks get the room-temperature defaults."""
    component = _build(_client())

    assert SILICON_RELATIVE_PERMITTIVITY == 11.7
    assert component.material("matSi").propertyGroup("def").properties[
        "relpermittivity"
    ] == _format_number(SILICON_RELATIVE_PERMITTIVITY)
    assert (
        component.material("matAir").propertyGroup("def").properties["relpermittivity"]
        == "1"
    )


def test_air_permittivity_override_reaches_the_material():
    """A PDK can set the air block permittivity, e.g. for a cryostat gas fill."""
    component = _build(_client(), air_relative_permittivity=1.5)

    assert component.material("matAir").propertyGroup("def").properties[
        "relpermittivity"
    ] == _format_number(1.5)


def test_silicon_permittivity_can_be_overridden():
    """An explicit permittivity reaches the silicon material."""
    component = _build(_client(), silicon_relative_permittivity=11.45)

    assert (
        component.material("matSi").propertyGroup("def").properties["relpermittivity"]
        == "11.45"
    )
    assert (
        component.material("matAir").propertyGroup("def").properties["relpermittivity"]
        == "1"
    )


def test_builder_adds_no_physics_mesh_or_study():
    """The returned model is geometry, selections, and materials only."""
    client = _client()
    _build(client)
    java = client.create.return_value.java
    model = client.create.return_value

    assert java.mesh.created == []
    assert java.study.created == []
    assert java.component.created == [("comp1",)]
    model.mesh.assert_not_called()
    model.solve.assert_not_called()


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"substrate_thickness_um": 0.0}, "substrate_thickness_um"),
        ({"substrate_thickness_um": -200.0}, "substrate_thickness_um"),
        ({"substrate_thickness_um": float("nan")}, "substrate_thickness_um"),
        ({"air_height_um": float("inf")}, "air_height_um"),
        ({"lateral_margin_um": -1.0}, "lateral_margin_um"),
        ({"lateral_margin_um": float("nan")}, "lateral_margin_um"),
        ({"silicon_relative_permittivity": 0.0}, "silicon_relative_permittivity"),
        ({"silicon_relative_permittivity": -11.7}, "silicon_relative_permittivity"),
        (
            {"silicon_relative_permittivity": float("nan")},
            "silicon_relative_permittivity",
        ),
        ({"air_relative_permittivity": 0.0}, "air_relative_permittivity"),
        ({"air_relative_permittivity": float("inf")}, "air_relative_permittivity"),
    ],
)
def test_rejects_bad_thicknesses_before_touching_comsol(
    overrides: dict[str, Any], match: str
):
    """Invalid lengths are refused before the client is used."""
    client: Any = None
    with pytest.raises(ValueError, match=match):
        build_comsol_sheet_model(client, _LAYOUT, "qubit", **overrides)


def test_rejects_layout_without_polygons():
    """A layout with no metal cannot make sheets."""
    with pytest.raises(ValueError, match="no metal polygons"):
        build_comsol_sheet_model(None, _EMPTY_LAYOUT, "qubit")


def test_a_successful_build_leaves_the_model_alone():
    """Nothing is removed when the build returns."""
    client = _client()
    _build(client)
    client.remove.assert_not_called()


def test_a_failed_build_removes_the_native_model():
    """A failure after the model exists does not leak it in the COMSOL process."""
    client = _client(imprint_lost=True)
    model = client.create.return_value

    with pytest.raises(ValueError, match="did not survive the imprint"):
        build_comsol_sheet_model(client, _LAYOUT, "qubit")

    client.remove.assert_called_once_with(model)


def test_a_failing_cleanup_keeps_the_original_error():
    """A cleanup that itself fails must not mask the build failure."""
    client = _client(imprint_lost=True)
    model = client.create.return_value
    client.remove.side_effect = RuntimeError("cleanup failed")

    with pytest.raises(ValueError, match="did not survive the imprint"):
        build_comsol_sheet_model(client, _LAYOUT, "qubit")

    client.remove.assert_called_once_with(model)
