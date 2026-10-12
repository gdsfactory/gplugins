"""Tests for the electrostatic capacitance study.

The study talks to COMSOL through MPh, which is not installed here, so a small
fake of the Java tree answers ``entities()`` for a Box selection from a map of
which face sits at which point. That keeps the tests on behaviour: that a point
picks the face under it, that a point which picks nothing or picks a face
already taken is refused, that the conductor tags have to name a terminal and a
ground each, and that the terminal, grounds, mesh, and study are wired but not
run.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from gplugins.comsol import capacitance as comsol_capacitance
from gplugins.comsol.capacitance import (
    add_capacitance_study,
    add_electrostatics,
)
from gplugins.comsol.layout import (
    ComsolBoundingBox,
    ComsolLayout,
    ComsolPolygon,
)
from gplugins.comsol.sheet import AIR_SELECTION, SILICON_SELECTION

_DRIVE = (-132.5, 0.0)
_SENSE = (132.5, 0.0)
_GROUND = (300.0, 200.0)
_CONDUCTORS = (("drive", _DRIVE), ("sense", _SENSE), ("gnd", _GROUND))
_TERMINAL = "drive"
_GROUNDS = ("sense", "gnd")
_FACES = {_DRIVE: [3], _SENSE: [4], _GROUND: [5]}
_LAYOUT = ComsolLayout(
    polygons=tuple(
        ComsolPolygon(
            outline=(
                (x - 10, y - 10),
                (x + 10, y - 10),
                (x + 10, y + 10),
                (x - 10, y + 10),
            )
        )
        for x, y in (_DRIVE, _SENSE, _GROUND)
    ),
    feed_ports=(),
    bbox=ComsolBoundingBox(xmin=-200, ymin=-20, xmax=320, ymax=220),
)


class _Selection:
    """A fake Box selection that resolves to whatever face map says."""

    def __init__(self, faces: dict[tuple[float, float], list[int]]) -> None:
        self.faces = faces
        self.properties: dict[str, Any] = {}
        self.named_tags: list[str] = []

    def set(self, name: str, value: str) -> None:
        """Record a property assignment."""
        self.properties[name] = value

    def named(self, tag: str) -> None:
        """Record an assignment to a named selection."""
        self.named_tags.append(tag)

    def entities(self) -> list[int]:
        """Return the faces the box, as recorded, is centred on.

        Returns:
            The registered face IDs, empty if the box misses every face.
        """
        if not {"xmin", "xmax", "ymin", "ymax"} <= self.properties.keys():
            return []
        centre = (
            _mid(self.properties["xmin"], self.properties["xmax"]),
            _mid(self.properties["ymin"], self.properties["ymax"]),
        )
        return list(self.faces.get(centre, []))


def _mid(low: str, high: str) -> float:
    """Return the centre of a recorded box span.

    Returns:
        The centre in µm.
    """
    return (float(low) + float(high)) / 2.0


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

    def __init__(self, faces: dict[tuple[float, float], list[int]]) -> None:
        self.faces = faces
        self.created: list[tuple[str, str]] = []
        self.selections: dict[str, _Selection] = {}
        self.physics = _Node()
        self.mesh = _Node()

    def selection(self, tag: str | None = None) -> Any:
        """Return this component, or a created Box selection by tag."""
        if tag is None:
            return self
        return self.selections.setdefault(tag, _Selection(self.faces))

    def create(self, tag: str, selection_type: str) -> _Selection:
        """Record a selection creation and return the new selection."""
        self.created.append((tag, selection_type))
        return self.selection(tag)

    def tags(self) -> list[str]:
        """Return the tags of the selections created so far."""
        return [tag for tag, _ in self.created]


class _FakeJava:
    """The fake ``model.java`` tree."""

    def __init__(self, faces: dict[tuple[float, float], list[int]]) -> None:
        self.faces = faces
        self.component_tags: list[str] = []
        self.components: dict[str, _Component] = {}
        self.study = _Node()

    def component(self, tag: str) -> _Component:
        """Return the fake component for the tag asked for."""
        self.component_tags.append(tag)
        return self.components.setdefault(tag, _Component(self.faces))


def _model(faces: dict[tuple[float, float], list[int]] | None = None) -> MagicMock:
    """Return an MPh model double whose Java tree resolves the given faces.

    Returns:
        The model double.
    """
    model = MagicMock()
    model.java = _FakeJava(_FACES if faces is None else faces)
    return model


def _study(model: MagicMock, **overrides: Any) -> MagicMock:
    """Add the capacitance study with default conductors.

    Returns:
        The model double.
    """
    arguments: dict[str, Any] = {
        "layout": _LAYOUT,
        "conductors": _CONDUCTORS,
        "terminal": _TERMINAL,
        "grounds": _GROUNDS,
    }
    arguments.update(overrides)
    return add_capacitance_study(model, **arguments)


def _assert_comsol_untouched(model: MagicMock) -> None:
    """Assert nothing on the model reached the Java tree."""
    assert model.java.component_tags == []
    assert model.java.study.created == []


def test_each_conductor_point_becomes_a_box_selection():
    """Each conductor point becomes a Box selection on the sheet plane."""
    model = _model()
    _study(model)
    assert model.java.component_tags == ["comp1"]
    component = model.java.component("comp1")

    assert component.created == [(tag, "Box") for tag, _ in _CONDUCTORS]
    for tag, point in _CONDUCTORS:
        box = component.selection(tag).properties
        assert box["entitydim"] == "2"
        assert box["condition"] == "intersects"
        assert _mid(box["xmin"], box["xmax"]) == pytest.approx(point[0])
        assert _mid(box["ymin"], box["ymax"]) == pytest.approx(point[1])
        assert _mid(box["zmin"], box["zmax"]) == pytest.approx(0.0)


def test_a_layout_with_an_extra_metal_polygon_is_refused():
    """An unassigned metal polygon would be solved as a dielectric interface."""
    stray = ComsolPolygon(
        outline=((500.0, 300.0), (520.0, 300.0), (520.0, 320.0), (500.0, 320.0))
    )
    layout = ComsolLayout(
        polygons=(*_LAYOUT.polygons, stray),
        feed_ports=(),
        bbox=_LAYOUT.bbox,
    )
    model = _model()
    with pytest.raises(ValueError, match="one metal polygon per conductor"):
        _study(model, layout=layout)
    component = model.java.component("comp1")
    assert component.created == []
    assert component.physics.created == []
    assert model.java.study.created == []


def test_a_point_that_selects_no_face_is_refused():
    """A point in a pad gap must not quietly leave an electrode unassigned."""
    model = _model({**_FACES, (0.0, 0.0): []})
    conductors = (("drive", _DRIVE), ("sense", _SENSE), ("gnd", (0.0, 0.0)))
    with pytest.raises(ValueError, match="inside exactly one metal polygon"):
        _study(model, conductors=conductors)
    assert model.java.study.created == []


def test_a_gap_point_is_refused_even_when_comsol_returns_a_dielectric_face():
    model = _model({**_FACES, (0.0, 0.0): [9]})
    conductors = (("drive", _DRIVE), ("sense", _SENSE), ("gnd", (0.0, 0.0)))
    with pytest.raises(ValueError, match="inside exactly one metal polygon"):
        _study(model, conductors=conductors)
    assert model.java.study.created == []


def test_two_conductor_points_in_the_same_polygon_are_refused():
    """Two conductors on one polygon would leave that polygon's other face out."""
    model = _model()
    conductors = (("drive", _DRIVE), ("sense", (-132.5, 5.0)), ("gnd", _GROUND))
    with pytest.raises(ValueError, match="different metal polygons"):
        _study(model, conductors=conductors)
    assert model.java.study.created == []


def test_a_point_that_selects_two_faces_is_refused():
    """A box straddling two metal faces is ambiguous and refused."""
    model = _model({**_FACES, _GROUND: [5, 6]})
    with pytest.raises(ValueError, match="selects 2 faces"):
        _study(model)


def test_two_points_on_the_same_face_are_refused():
    """Grounding the same face twice would short two conductors together."""
    model = _model({**_FACES, _GROUND: [3]})
    with pytest.raises(ValueError, match="different faces"):
        _study(model)


def test_electrostatics_drives_the_terminal_and_grounds_the_rest():
    """The terminal is a voltage source and the other conductors are grounded."""
    model = _model()
    _study(model, voltage_v=0.5)
    physics = model.java.component("comp1").physics

    assert physics.created == [("es", "Electrostatics", "geom1")]
    electrostatics = physics("es")
    assert electrostatics.created == [
        ("ccSi", "ChargeConservation", 3),
        ("term1", "Terminal", 2),
        ("gnd1", "Ground", 2),
        ("gnd2", "Ground", 2),
    ]
    assert electrostatics.feature("ccSi").named_tags == [SILICON_SELECTION]
    terminal = electrostatics.feature("term1")
    assert terminal.named_tags == [_TERMINAL]
    assert terminal.properties["TerminalType"] == "Voltage"
    assert terminal.properties["V0"] == "0.5[V]"
    assert electrostatics.feature("gnd1").named_tags == [_GROUNDS[0]]
    assert electrostatics.feature("gnd2").named_tags == [_GROUNDS[1]]
    assert "V0" not in electrostatics.feature("gnd1").properties


def test_add_electrostatics_grounds_every_selection_it_is_given():
    """The public helper adds one Ground feature per grounded selection."""
    component = _Component(_FACES)
    add_electrostatics(
        component, terminal="drive", grounds=("a", "b", "c"), voltage_v=1.0
    )
    electrostatics = component.physics("es")

    assert electrostatics.created == [
        ("ccSi", "ChargeConservation", 3),
        ("term1", "Terminal", 2),
        ("gnd1", "Ground", 2),
        ("gnd2", "Ground", 2),
        ("gnd3", "Ground", 2),
    ]
    assert electrostatics.feature("term1").named_tags == ["drive"]
    assert [
        electrostatics.feature(f"gnd{index}").named_tags[0] for index in (1, 2, 3)
    ] == ["a", "b", "c"]


def test_the_dielectric_selections_are_left_to_the_sheet_model():
    """The study does not re-create or re-point the air and silicon selections."""
    model = _model()
    _study(model)
    component = model.java.component("comp1")

    assert set(component.selections) == {tag for tag, _ in _CONDUCTORS}
    assert AIR_SELECTION not in component.selections
    assert SILICON_SELECTION not in component.selections


def test_mesh_and_study_are_built_but_not_run():
    """The mesh takes the requested size and the study is left unsolved."""
    model = _model()
    _study(model, mesh_size=4)
    component = model.java.component("comp1")

    assert component.mesh.created == [("mesh1", "geom1")]
    assert component.mesh("mesh1").auto_mesh_size == 4
    assert component.mesh("mesh1").runs == 0
    study = model.java.study("std1")
    assert model.java.study.created == [("std1",)]
    assert study.created == [("stat", "Stationary")]
    assert study.runs == 0
    model.mesh.assert_not_called()
    model.solve.assert_not_called()


def test_returns_the_same_model():
    """The study is added in place and the model is handed back."""
    model = _model()
    assert _study(model) is model


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"voltage_v": 0.0}, "voltage_v"),
        ({"voltage_v": -1.0}, "voltage_v"),
        ({"voltage_v": float("nan")}, "voltage_v"),
        ({"mesh_size": 0}, "mesh_size"),
        ({"mesh_size": 10}, "mesh_size"),
        ({"mesh_size": True}, "mesh_size"),
        ({"mesh_size": "7"}, "mesh_size"),
        (
            {
                "conductors": (
                    ("drive", (0.0, float("nan"))),
                    ("sense", _SENSE),
                    ("gnd", _GROUND),
                )
            },
            "drive",
        ),
        (
            {
                "conductors": (
                    ("drive", (0.0, 0.0, 0.0)),
                    ("sense", _SENSE),
                    ("gnd", _GROUND),
                )
            },
            "drive",
        ),
        (
            {
                "conductors": (
                    ("drive", _DRIVE),
                    ("sense", _SENSE),
                    ("gnd", (float("inf"), 0.0)),
                )
            },
            "gnd",
        ),
    ],
)
def test_rejects_bad_arguments_before_touching_comsol(
    overrides: dict[str, Any], match: str
):
    """Invalid arguments are refused before any Java call is made."""
    model = _model()
    with pytest.raises(ValueError, match=match):
        _study(model, **overrides)

    _assert_comsol_untouched(model)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        (
            {
                "conductors": (("a", _DRIVE), ("a", _SENSE), ("gnd", _GROUND)),
                "terminal": "a",
                "grounds": ("gnd",),
            },
            "conductor tags must be unique",
        ),
        ({"terminal": "missing"}, "not one of the conductors"),
        ({"grounds": ()}, "at least one grounded conductor"),
        ({"grounds": ("sense", "missing")}, "not one of the conductors"),
        ({"grounds": ("sense", "sense")}, "ground tags must be unique"),
        ({"grounds": ("drive", "gnd")}, "must not also be grounded"),
        ({"grounds": ("sense",)}, "neither the terminal nor a ground"),
    ],
)
def test_rejects_tags_that_do_not_name_every_conductor(
    overrides: dict[str, Any], match: str
):
    """Tags that leave a conductor unnamed are refused before COMSOL is touched."""
    model = _model()
    with pytest.raises(ValueError, match=match):
        _study(model, **overrides)

    _assert_comsol_untouched(model)


@pytest.mark.parametrize("bad", ["pad left", "1pad", "", "pad-left"])
def test_a_conductor_tag_that_is_not_a_comsol_tag_is_refused(bad: str):
    """A tag COMSOL would reject is refused before the model is touched."""
    model = _model()
    conductors = (("drive", _DRIVE), ("sense", _SENSE), (bad, _GROUND))
    with pytest.raises(ValueError, match="are not COMSOL tags"):
        _study(model, conductors=conductors, grounds=("sense", bad))

    _assert_comsol_untouched(model)


def test_a_conductor_tag_that_is_already_a_selection_is_refused():
    """Reusing a sheet selection tag would overwrite it with a conductor box."""
    model = _model()
    component = model.java.component("comp1")
    component.create("gnd", "Box")
    with pytest.raises(ValueError, match=r"conductor tags \['gnd'\]"):
        _study(model)
    assert component.created == [("gnd", "Box")]


@pytest.mark.parametrize("existing", ["mesh", "study"])
def test_a_model_that_already_holds_a_study_is_refused(existing: str):
    """A second study would collide with the fixed mesh1 and std1 tags."""
    model = _model()
    component = model.java.component("comp1")
    if existing == "mesh":
        component.mesh.create("mesh1", "geom1")
    else:
        model.java.study.create("std1")
    with pytest.raises(ValueError, match="already holds"):
        _study(model)
    assert component.created == []


def test_mph_is_not_imported_at_runtime():
    """The MPh import stays behind TYPE_CHECKING."""
    assert "mph" not in vars(comsol_capacitance)
