"""Tests for the CPW full-wave study.

MPh and COMSOL are not installed here, so a small fake of the Java tree answers
``entities()`` from a hand-written model of the unioned sheet geometry: which
face each polygon became, which faces sit on each port plane, and where the
edges are. The assertions stay on behaviour: that each polygon probe lands on
its own face, that the port faces and gap edges land on the port planes, and
that the physics, mesh, and study are wired but not run.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from shapely.geometry import Point, Polygon

from gplugins.comsol import rf as comsol_rf
from gplugins.comsol.layout import (
    ComsolBoundingBox,
    ComsolFeedPort,
    ComsolLayout,
    ComsolPolygon,
)
from gplugins.comsol.rf import (
    INPUT_FACES_SELECTION,
    INPUT_GAP_SELECTION,
    METAL_FACES_SELECTION,
    OUTPUT_FACES_SELECTION,
    OUTPUT_GAP_SELECTION,
    add_cpw_rf_study,
)
from gplugins.comsol.sheet import AIR_SELECTION, SILICON_SELECTION


class _Sheet:
    """The geometry the boxes are resolved against, written out by hand.

    ``metal_faces`` runs parallel to the layout polygons: the face each polygon
    turned into after the union. ``port_faces`` maps an axis and plane to the
    air and silicon faces on that plane, and ``gap_edges`` lists every edge on
    the sheet plane as ``(axis, plane, low, high, id)`` in the transverse
    direction.
    """

    def __init__(
        self,
        polygons: list[Polygon],
        metal_faces: list[int],
        port_faces: dict[tuple[int, float], list[int]],
        gap_edges: list[tuple[int, float, float, float, int]],
    ) -> None:
        self.polygons = polygons
        self.metal_faces = metal_faces
        self.port_faces = port_faces
        self.gap_edges = gap_edges

    def resolve(self, properties: dict[str, str]) -> list[int]:
        """Return the entities a recorded Box selection resolves to.

        Returns:
            The entity IDs, empty when the box holds nothing.
        """
        # An axis the box does not set is unbounded in COMSOL, so -inf to inf.
        spans = {
            axis: (
                float(properties.get(f"{axis}min", "-inf")),
                float(properties.get(f"{axis}max", "inf")),
            )
            for axis in "xyz"
        }
        if properties["entitydim"] == "2" and properties["condition"] == "intersects":
            point = Point(
                (spans["x"][0] + spans["x"][1]) / 2.0,
                (spans["y"][0] + spans["y"][1]) / 2.0,
            )
            return [
                face
                for face, polygon in zip(self.metal_faces, self.polygons)
                if polygon.area > 0.0 and polygon.contains(point)
            ]
        if properties["entitydim"] == "2":
            return [
                face
                for (axis, plane), faces in self.port_faces.items()
                if _inside(spans["x" if axis == 0 else "y"], plane)
                for face in faces
            ]
        edges = []
        for axis, plane, low, high, edge in self.gap_edges:
            if (
                _inside(spans["x" if axis == 0 else "y"], plane)
                and _inside(spans["y" if axis == 0 else "x"], low, high)
                and _inside(spans["z"], 0.0)
            ):
                edges.append(edge)
        return edges


def _inside(span: tuple[float, float], *values: float) -> bool:
    """Return whether every value sits inside a recorded span.

    Returns:
        ``True`` when all values are inside the span.
    """
    return all(span[0] <= value <= span[1] for value in values)


class _Selection:
    """A fake Box selection resolving against the geometry model."""

    def __init__(self, sheet: _Sheet) -> None:
        self.sheet = sheet
        self.properties: dict[str, str] = {}
        self.named_tags: list[str] = []

    def set(self, name: str, value: str) -> None:
        """Record a property assignment."""
        self.properties[name] = value

    def named(self, tag: str) -> None:
        """Record an assignment to a named selection."""
        self.named_tags.append(tag)

    def entities(self) -> list[int]:
        """Return the entities the recorded box resolves to.

        Returns:
            The entity IDs.
        """
        return self.sheet.resolve(self.properties)


class _Node:
    """Stands in for a feature node, recording properties and selections."""

    def __init__(self) -> None:
        self.created: list[tuple[Any, ...]] = []
        self.properties: dict[str, Any] = {}
        self.named_tags: list[str] = []
        self.children: dict[str, _Node] = {}
        self.auto_mesh_size: int | None = None
        self.runs = 0

    def __call__(self, tag: str | None = None) -> Any:
        """Return this node, or the child node filed under ``tag``."""
        if tag is None:
            return self
        return self.children.setdefault(tag, _Node())

    def create(self, tag: str, *args: Any) -> _Node:
        """Record a create call and return the new child node."""
        self.created.append((tag, *args))
        return self(tag)

    def feature(self, tag: str) -> _Node:
        """Return a feature by tag."""
        return self(tag)

    def selection(self, tag: str | None = None) -> _Node:
        """Return this node's own selection, or a child selection by name."""
        if tag is None:
            return self
        return self(f"selection:{tag}")

    def set(self, name: str, value: str) -> None:
        """Record a property assignment."""
        self.properties[name] = value

    def named(self, tag: str) -> None:
        """Record an assignment to a named selection."""
        self.named_tags.append(tag)

    def autoMeshSize(self, size: int) -> None:
        """Record the automatic mesh size."""
        self.auto_mesh_size = size

    def run(self) -> None:
        """Record that the node was run."""
        self.runs += 1

    def tags(self) -> list[str]:
        """Return the tags of the children created so far."""
        return [entry[0] for entry in self.created]


class _Component:
    """Stands in for ``comp1``: its selections, physics, and mesh."""

    def __init__(self, sheet: _Sheet) -> None:
        self.sheet = sheet
        self.created: list[tuple[str, str]] = []
        self.selections: dict[str, _Selection] = {}
        self.physics = _Node()
        self.mesh = _Node()

    def selection(self, tag: str | None = None) -> Any:
        """Return this component, or a created Box selection by tag."""
        if tag is None:
            return self
        return self.selections.setdefault(tag, _Selection(self.sheet))

    def create(self, tag: str, selection_type: str) -> _Selection:
        """Record a selection creation and return the new selection."""
        self.created.append((tag, selection_type))
        return self.selection(tag)

    def tags(self) -> list[str]:
        """Return the tags of the selections created so far."""
        return [tag for tag, _ in self.created]


class _FakeJava:
    """The fake ``model.java`` tree."""

    def __init__(self, sheet: _Sheet) -> None:
        self.sheet = sheet
        self.components: dict[str, _Component] = {}
        self.study = _Node()

    def component(self, tag: str) -> _Component:
        """Return the fake component for the tag asked for."""
        return self.components.setdefault(tag, _Component(self.sheet))


def _rect(xmin: float, ymin: float, xmax: float, ymax: float) -> ComsolPolygon:
    """Return an axis-aligned rectangular metal polygon.

    Returns:
        The polygon.
    """
    return ComsolPolygon(
        outline=((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax))
    )


def _horizontal_layout() -> ComsolLayout:
    """Return a CPW fed left to right: two ground planes and a conductor.

    Returns:
        The layout, its feeds on the x bounding planes.
    """
    return ComsolLayout(
        polygons=(
            _rect(-300.0, -50.0, 900.0, -11.0),
            _rect(-300.0, -5.0, 900.0, 5.0),
            _rect(-300.0, 11.0, 900.0, 50.0),
        ),
        feed_ports=(
            ComsolFeedPort(
                name="in", center=(-300.0, 0.0), width=10.0, orientation=180.0
            ),
            ComsolFeedPort(
                name="out", center=(900.0, 0.0), width=10.0, orientation=0.0
            ),
        ),
        bbox=ComsolBoundingBox(xmin=-300.0, ymin=-50.0, xmax=900.0, ymax=50.0),
    )


def _vertical_layout() -> ComsolLayout:
    """Return the same CPW fed bottom to top, so x and y swap roles.

    Returns:
        The layout, its feeds on the y bounding planes.
    """
    return ComsolLayout(
        polygons=(
            _rect(-50.0, -300.0, -11.0, 900.0),
            _rect(-5.0, -300.0, 5.0, 900.0),
            _rect(11.0, -300.0, 50.0, 900.0),
        ),
        feed_ports=(
            ComsolFeedPort(
                name="in", center=(0.0, -300.0), width=10.0, orientation=270.0
            ),
            ComsolFeedPort(
                name="out", center=(0.0, 900.0), width=10.0, orientation=90.0
            ),
        ),
        bbox=ComsolBoundingBox(xmin=-50.0, ymin=-300.0, xmax=50.0, ymax=900.0),
    )


def _sheet(layout: ComsolLayout, metal_faces: list[int] | None = None) -> _Sheet:
    """Return the geometry model matching a layout's three-metal CPW.

    The gap between the centre conductor and each ground runs from 5 to 11 µm
    off the midline, and the face and edge IDs are the ones the live COMSOL 6.3
    model reported.

    Returns:
        The geometry model.
    """
    axis = (
        0
        if any(round(port.orientation) % 180 == 0 for port in layout.feed_ports)
        else 1
    )
    planes = (
        (layout.bbox.xmin, layout.bbox.xmax)
        if axis == 0
        else (layout.bbox.ymin, layout.bbox.ymax)
    )
    low, high = (
        (layout.bbox.ymin, layout.bbox.ymax)
        if axis == 0
        else (layout.bbox.xmin, layout.bbox.xmax)
    )
    port_faces = {
        (axis, planes[0]): [1, 2],
        (axis, planes[1]): [3, 4],
    }
    gap_edges = [
        (axis, planes[0], low, -11.0, 101),
        (axis, planes[0], -11.0, -5.0, 102),
        (axis, planes[0], 5.0, 11.0, 13),
        (axis, planes[0], 11.0, high, 105),
        (axis, planes[1], 5.0, 11.0, 29),
    ]
    return _Sheet(
        polygons=[Polygon(p.outline, p.holes) for p in layout.polygons],
        # COMSOL reported the three metal faces as 6, 9, and 11.
        metal_faces=[6, 9, 11] if metal_faces is None else metal_faces,
        port_faces=port_faces,
        gap_edges=gap_edges,
    )


def _model(sheet: _Sheet) -> MagicMock:
    """Return an MPh model double whose Java tree resolves against ``sheet``.

    Returns:
        The model double.
    """
    model = MagicMock()
    model.java = _FakeJava(sheet)
    return model


def _study(
    layout: ComsolLayout | None = None,
    *,
    sheet: _Sheet | None = None,
    **overrides: Any,
) -> MagicMock:
    """Add the CPW study to a model double built for a layout.

    Returns:
        The model double.
    """
    layout = _horizontal_layout() if layout is None else layout
    arguments: dict[str, Any] = {"cpw_gap_um": 6.0}
    arguments.update(overrides)
    return add_cpw_rf_study(
        _model(_sheet(layout) if sheet is None else sheet), layout, **arguments
    )


def test_each_polygon_probe_selects_its_own_metal_face():
    """A representative point inside a polygon picks that polygon's face."""
    model = _study()
    component = model.java.component("comp1")

    # The port planes are checked first, so a misplaced plane fails before
    # anything else is added to the model.
    assert component.created == [
        (INPUT_FACES_SELECTION, "Box"),
        (OUTPUT_FACES_SELECTION, "Box"),
        ("metal0", "Box"),
        ("metal1", "Box"),
        ("metal2", "Box"),
        (METAL_FACES_SELECTION, "Union"),
        (INPUT_GAP_SELECTION, "Box"),
        (OUTPUT_GAP_SELECTION, "Box"),
    ]
    assert [component.selection(f"metal{index}").entities() for index in range(3)] == [
        [6],
        [9],
        [11],
    ]
    for index in range(3):
        box = component.selection(f"metal{index}").properties
        assert box["entitydim"] == "2"
        assert box["condition"] == "intersects"
        assert _centre(box, "z") == pytest.approx(0.0)
        assert float(box["xmax"]) - float(box["xmin"]) == pytest.approx(0.02)
    union = component.selection(METAL_FACES_SELECTION)
    assert union.properties["entitydim"] == "2"
    assert union.properties["input"] == ["metal0", "metal1", "metal2"]


def test_emw_drives_the_low_port_and_loads_the_high_one():
    """EMW carries a PEC on the metal and two numeric ports with a TEM line."""
    model = _study()
    physics = model.java.component("comp1").physics
    emw = physics("emw")

    assert physics.created == [("emw", "ElectromagneticWaves", "geom1")]
    assert emw.created == [
        ("pecMetal", "PerfectElectricConductor", 2),
        ("port1", "Port", 2),
        ("port2", "Port", 2),
    ]
    assert emw.feature("pecMetal").named_tags == [METAL_FACES_SELECTION]
    first = emw.feature("port1")
    assert first.named_tags == [INPUT_FACES_SELECTION]
    assert first.properties["PortType"] == "Numeric"
    assert first.properties["numericTEM"] == "1"
    assert first.properties["PortName"] == "1"
    assert "PortExcitation" not in first.properties
    assert first.created == [("ivl", "IntegrationLineforVoltage")]
    assert first.feature("ivl").named_tags == [INPUT_GAP_SELECTION]
    second = emw.feature("port2")
    assert second.named_tags == [OUTPUT_FACES_SELECTION]
    assert second.properties["PortName"] == "2"
    assert second.properties["PortExcitation"] == "off"
    assert second.feature("ivl").named_tags == [OUTPUT_GAP_SELECTION]


def test_port_faces_and_gap_edges_sit_on_the_bounding_planes():
    """Each port plane holds a thin slab on it and a box across one gap."""
    model = _study()
    component = model.java.component("comp1")

    for tag, plane in (
        (INPUT_FACES_SELECTION, -300.0),
        (OUTPUT_FACES_SELECTION, 900.0),
    ):
        box = component.selection(tag).properties
        assert box["entitydim"] == "2"
        assert box["condition"] == "inside"
        assert (float(box["xmin"]), float(box["xmax"])) == pytest.approx(
            (
                plane - 0.001,
                plane + 0.001,
            )
        )
        # Transverse and z stay unbounded: the plane alone picks the faces.
        assert not {"ymin", "ymax", "zmin", "zmax"} & box.keys()
        assert component.selection(tag).entities() == (
            [1, 2] if plane < 0.0 else [3, 4]
        )

    for tag, plane in ((INPUT_GAP_SELECTION, -300.0), (OUTPUT_GAP_SELECTION, 900.0)):
        box = component.selection(tag).properties
        assert box["entitydim"] == "1"
        assert box["condition"] == "inside"
        assert (float(box["xmin"]), float(box["xmax"])) == pytest.approx(
            (
                plane - 0.001,
                plane + 0.001,
            )
        )
        # Half the 10 µm conductor over, then the 6 µm gap.
        assert (float(box["ymin"]), float(box["ymax"])) == pytest.approx(
            (
                4.999,
                11.001,
            )
        )
        assert (float(box["zmin"]), float(box["zmax"])) == pytest.approx(
            (
                -0.001,
                0.001,
            )
        )
        assert component.selection(tag).entities() == [13 if plane < 0.0 else 29]


def test_only_the_port_face_boxes_leave_z_unbounded():
    """A z bound on the port slab would drop every face taller than the box.

    The air block can be taller than any fixed height, so the port box has to
    span z without limit; a capped one then reports only the silicon half of the
    cross section. The gap probes stay tightly bound in z.
    """
    model = _study()
    component = model.java.component("comp1")

    for tag in (INPUT_FACES_SELECTION, OUTPUT_FACES_SELECTION):
        box = component.selection(tag).properties
        assert "zmin" not in box
        assert "zmax" not in box
    for tag in (INPUT_GAP_SELECTION, OUTPUT_GAP_SELECTION):
        box = component.selection(tag).properties
        assert "zmin" in box
        assert "zmax" in box


def test_vertical_feeds_swap_the_axes():
    """A CPW fed bottom to top port and probes along y instead of x."""
    layout = _vertical_layout()
    model = _study(layout)
    component = model.java.component("comp1")

    assert component.selection(INPUT_FACES_SELECTION).entities() == [1, 2]
    faces = component.selection(INPUT_FACES_SELECTION).properties
    assert (float(faces["ymin"]), float(faces["ymax"])) == (-300.001, -299.999)
    assert not {"xmin", "xmax"} & faces.keys()
    gap = component.selection(INPUT_GAP_SELECTION).properties
    assert (float(gap["ymin"]), float(gap["ymax"])) == (-300.001, -299.999)
    assert (float(gap["xmin"]), float(gap["xmax"])) == pytest.approx((4.999, 11.001))
    assert component.selection(INPUT_GAP_SELECTION).entities() == [13]


def test_mesh_and_frequency_study_are_built_but_not_run():
    """The mesh takes the requested size and one BMA step covers each port."""
    model = _study(mesh_size=6, frequency_ghz=4.25)
    component = model.java.component("comp1")

    assert component.mesh.created == [("mesh1", "geom1")]
    assert component.mesh("mesh1").auto_mesh_size == 6
    assert component.mesh("mesh1").runs == 0
    study = model.java.study("std1")
    assert model.java.study.created == [("std1",)]
    assert study.created == [
        ("bma1", "BoundaryModeAnalysis"),
        ("bma2", "BoundaryModeAnalysis"),
        ("freq", "Frequency"),
    ]
    assert study.feature("bma1").properties == {
        "PortName": "1",
        "modeFreq": "4.25[GHz]",
        "shift": "2.5",
        "shiftactive": "on",
    }
    assert study.feature("bma2").properties["PortName"] == "2"
    assert study.feature("freq").properties["plist"] == "4.25[GHz]"
    assert study.runs == 0
    model.mesh.assert_not_called()
    model.solve.assert_not_called()


def test_the_effective_index_shift_reaches_both_bma_steps():
    """An explicit shift overrides the 2.5 every saved example used."""
    model = _study(effective_index_shift=3.4)
    study = model.java.study("std1")

    for index in (1, 2):
        feature = study.feature(f"bma{index}")
        assert feature.properties["shift"] == "3.4"
        assert feature.properties["shiftactive"] == "on"


def test_the_dielectric_selections_are_left_to_the_sheet_model():
    """The study does not re-create or re-point the air and silicon selections."""
    model = _study()
    created = {tag for tag, _ in model.java.component("comp1").created}

    assert AIR_SELECTION not in created
    assert SILICON_SELECTION not in created


def test_returns_the_same_model():
    """The study is added in place and the model is handed back."""
    layout = _horizontal_layout()
    model = _model(_sheet(layout))
    assert add_cpw_rf_study(model, layout, cpw_gap_um=6.0) is model


def test_polygons_that_merge_into_one_face_are_refused():
    """Two metal regions that the union joined would ground the wrong area."""
    layout = _horizontal_layout()
    sheet = _sheet(layout, metal_faces=[6, 9, 9])
    with pytest.raises(ValueError, match="must select different faces"):
        _study(layout, sheet=sheet)


def test_a_polygon_that_becomes_no_face_is_refused():
    """A degenerate sliver imprints nothing, so its probe finds no face."""
    base = _horizontal_layout()
    layout = ComsolLayout(
        polygons=(*base.polygons, _rect(20.0, 8.0, 30.0, 8.0)),
        feed_ports=base.feed_ports,
        bbox=base.bbox,
    )
    with pytest.raises(ValueError, match="metal polygon 3 selects 0 faces"):
        _study(layout, sheet=_sheet(layout, metal_faces=[6, 9, 11, 12]))


def test_a_gap_that_is_not_a_single_edge_is_refused():
    """A gap wider than the ground strip would span more than one edge."""
    layout = _horizontal_layout()
    sheet = _sheet(layout)
    sheet.gap_edges.append((0, -300.0, 6.0, 8.0, 14))
    with pytest.raises(ValueError, match="input port gap selects 2 edges"):
        _study(layout, sheet=sheet)


def test_a_feed_with_one_short_circuited_gap_is_refused():
    layout = _horizontal_layout()
    shorted = ComsolLayout(
        polygons=(
            _rect(-300.0, -50.0, 900.0, 5.0),
            _rect(-300.0, 11.0, 900.0, 50.0),
        ),
        feed_ports=layout.feed_ports,
        bbox=layout.bbox,
    )
    sheet = _sheet(shorted, metal_faces=[6, 9])
    model = _model(sheet)
    with pytest.raises(ValueError, match="CPW gap is shorted"):
        add_cpw_rf_study(model, shorted, cpw_gap_um=6.0)
    # The cross sections are checked before anything is added to the model.
    assert model.java.component("comp1").created == []


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"cpw_gap_um": 0.0}, "cpw_gap_um"),
        ({"cpw_gap_um": -6.0}, "cpw_gap_um"),
        ({"cpw_gap_um": float("nan")}, "cpw_gap_um"),
        ({"frequency_ghz": 0.0}, "frequency_ghz"),
        ({"frequency_ghz": float("inf")}, "frequency_ghz"),
        ({"mesh_size": 0}, "mesh_size"),
        ({"mesh_size": 10}, "mesh_size"),
        ({"mesh_size": "8"}, "mesh_size"),
        ({"mesh_size": True}, "mesh_size"),
        ({"effective_index_shift": 0.0}, "effective_index_shift"),
        ({"effective_index_shift": -2.5}, "effective_index_shift"),
        ({"effective_index_shift": float("inf")}, "effective_index_shift"),
    ],
)
def test_rejects_bad_arguments_before_touching_comsol(
    overrides: dict[str, Any], match: str
):
    """Invalid arguments are refused before any Java call is made."""
    model = _model(_sheet(_horizontal_layout()))
    arguments: dict[str, Any] = {"cpw_gap_um": 6.0}
    arguments.update(overrides)
    with pytest.raises(ValueError, match=match):
        add_cpw_rf_study(model, _horizontal_layout(), **arguments)

    assert model.java.components == {}


def _with_feed_ports(
    *feed_ports: ComsolFeedPort, bbox: ComsolBoundingBox | None = None
) -> ComsolLayout:
    """Return the horizontal layout with its feeds replaced.

    Returns:
        The layout.
    """
    layout = _horizontal_layout()
    return ComsolLayout(
        polygons=layout.polygons,
        feed_ports=feed_ports,
        bbox=layout.bbox if bbox is None else bbox,
    )


@pytest.mark.parametrize(
    ("feed_ports", "message"),
    [
        ((), "exactly two feed ports"),
        (
            (
                ComsolFeedPort(
                    name="a", center=(-300.0, 0.0), width=10.0, orientation=180.0
                ),
            ),
            "exactly two feed ports",
        ),
        (
            (
                ComsolFeedPort(
                    name="a", center=(-300.0, 0.0), width=10.0, orientation=180.0
                ),
                ComsolFeedPort(
                    name="b", center=(900.0, 0.0), width=10.0, orientation=180.0
                ),
            ),
            "face outwards",
        ),
        (
            (
                ComsolFeedPort(
                    name="a", center=(-300.0, 0.0), width=10.0, orientation=180.0
                ),
                ComsolFeedPort(
                    name="b", center=(0.0, 50.0), width=10.0, orientation=90.0
                ),
            ),
            "same axis",
        ),
    ],
)
def test_feeds_that_do_not_pair_up_are_refused(
    feed_ports: tuple[ComsolFeedPort, ...], message: str
):
    """The pair has to be two feet on opposite sides, facing outwards."""
    layout = _with_feed_ports(*feed_ports)
    with pytest.raises(ValueError, match=message):
        _study(layout)


def test_feeds_inside_the_bounding_box_are_refused():
    """Without cropping the feeds sit in solid ground and have no cross section."""
    layout = _with_feed_ports(
        *_horizontal_layout().feed_ports,
        bbox=ComsolBoundingBox(xmin=-400.0, ymin=-50.0, xmax=1000.0, ymax=50.0),
    )
    with pytest.raises(ValueError, match="opposite bounding-box faces"):
        _study(layout)


def test_a_port_plane_with_no_face_is_refused():
    """A model whose geometry misses the layout's box cannot be ported."""
    layout = _horizontal_layout()
    sheet = _sheet(layout)
    sheet.port_faces = {(0, 900.0): [3, 4]}
    with pytest.raises(ValueError, match="selects no face on the port plane"):
        _study(layout, sheet=sheet)


def test_a_sheet_built_with_a_lateral_margin_is_refused():
    """With a margin the outer faces sit past the feed metal, not on its end."""
    layout = _horizontal_layout()
    sheet = _sheet(layout)
    # The geometry's outer faces moved out by a 50 µm margin.
    sheet.port_faces = {(0, -350.0): [1, 2], (0, 950.0): [3, 4]}
    with pytest.raises(ValueError, match="lateral_margin_um=0"):
        _study(layout, sheet=sheet)


@pytest.mark.parametrize("existing", ["mesh", "study"])
def test_a_model_that_already_holds_a_study_is_refused(existing: str):
    """A second study would collide with the fixed mesh1 and std1 tags."""
    model = _model(_sheet(_horizontal_layout()))
    if existing == "mesh":
        model.java.component("comp1").mesh.create("mesh1", "geom1")
    else:
        model.java.study.create("std1")
    with pytest.raises(ValueError, match="already holds"):
        add_cpw_rf_study(model, _horizontal_layout(), cpw_gap_um=6.0)
    assert model.java.component("comp1").created == []


def test_a_port_plane_holding_one_face_is_refused():
    """A plane carrying only one dielectric half is not a full cross section.

    This is what a capped z box used to return for a tall air block: the silicon
    face alone, which would have been ported silently as a half port.
    """
    layout = _horizontal_layout()
    sheet = _sheet(layout)
    sheet.port_faces = {(0, -300.0): [1], (0, 900.0): [3, 4]}
    with pytest.raises(ValueError, match="expected two, one air and one silicon"):
        _study(layout, sheet=sheet)


def _centre(box: dict[str, str], axis: str) -> float:
    """Return the centre of a recorded box span.

    Returns:
        The centre in µm.
    """
    return (float(box[f"{axis}min"]) + float(box[f"{axis}max"])) / 2.0


def test_mph_is_not_imported_at_runtime():
    """The MPh import stays behind TYPE_CHECKING."""
    assert "mph" not in vars(comsol_rf)
