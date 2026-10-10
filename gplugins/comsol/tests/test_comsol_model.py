"""Tests for the COMSOL model class.

The class subclasses :class:`mph.Model`, so importing it needs the ``comsol``
extra and the whole module skips without it. Nothing here needs a COMSOL licence
or a running client: the base class comes from MPh alone, the Java handle is a
mock, and each method is checked against the helper it dispatches to by
replacing that helper.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from gplugins.comsol.layout import ComsolBoundingBox, ComsolLayout, ComsolPolygon


def test_module_imports_without_mph():
    """Pytest can collect the module when the optional COMSOL extra is absent."""
    code = (
        "import sys; sys.modules['mph'] = None; "
        "from gplugins.comsol.model import COMSOL; "
        "assert COMSOL.__base__ is object; "
        "COMSOL(None, None)"
    )
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    assert result.returncode != 0
    assert "ImportError: Install gplugins[comsol]" in result.stderr


def test_dependency_import_failure_is_not_reported_as_missing_mph():
    """An installed MPh with a broken dependency keeps its original error."""
    code = """
import importlib
original = importlib.import_module
def broken(name, package=None):
    if name == "mph":
        raise ModuleNotFoundError("JPype failed to load", name="jpype")
    return original(name, package=package)
importlib.import_module = broken
import gplugins.comsol.model
"""
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    assert result.returncode != 0
    assert "ModuleNotFoundError: JPype failed to load" in result.stderr


def _layout() -> ComsolLayout:
    """A one-polygon layout to attach to a model.

    Returns:
        The layout.
    """
    return ComsolLayout(
        polygons=(ComsolPolygon(outline=((0, 0), (10, 0), (10, 10), (0, 10))),),
        feed_ports=(),
        bbox=ComsolBoundingBox(xmin=0, ymin=0, xmax=10, ymax=10),
    )


@pytest.fixture
def comsol() -> tuple[Any, Any]:
    """The MPh module and the COMSOL class, skipping without the extra.

    Returns:
        ``(mph, comsol_model)``.
    """
    mph = pytest.importorskip("mph", reason="the comsol extra is not installed")
    return mph, pytest.importorskip("gplugins.comsol.model")


@pytest.fixture
def wrapped(comsol: tuple[Any, Any]) -> tuple[Any, Any, Any]:
    """A COMSOL model around a mock Java handle, with the layout it holds.

    Returns:
        ``(model, java, layout)``.
    """
    mph, comsol_model = comsol
    java = MagicMock()
    layout = _layout()
    return comsol_model.COMSOL(mph.Model(java), layout), java, layout


def test_is_an_mph_model_around_the_same_java(
    comsol: tuple[Any, Any], wrapped: tuple[Any, Any, Any]
):
    """The class subclasses mph.Model and reuses the Java handle it was given."""
    mph, comsol_model = comsol
    model, java, layout = wrapped
    assert issubclass(comsol_model.COMSOL, mph.Model)
    assert isinstance(model, mph.Model)
    assert model.java is java
    assert model.layout is layout


def test_package_exposes_the_class(comsol: tuple[Any, Any]):
    """The package and the builder module both offer the class."""
    _, comsol_model = comsol
    package = importlib.import_module("gplugins.comsol.model")
    builder_module = importlib.import_module("gplugins.comsol")
    assert package.COMSOL is comsol_model.COMSOL
    assert builder_module.COMSOL is comsol_model.COMSOL


def test_create_sheet_dispatches_to_the_sheet_builder(
    comsol: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
):
    """create_sheet forwards its arguments and adopts the built model."""
    mph, comsol_model = comsol
    java = MagicMock()
    calls: list[tuple[Any, ...]] = []

    def fake_builder(client: Any, layout: Any, name: str, **kwargs: Any) -> Any:
        calls.append((client, layout, name, kwargs))
        return mph.Model(java)

    monkeypatch.setattr(comsol_model.sheet, "build_comsol_sheet_model", fake_builder)
    client = MagicMock()
    layout = _layout()
    model = comsol_model.COMSOL.create_sheet(
        client,
        layout,
        "sheet",
        substrate_thickness_um=250.0,
        air_height_um=150.0,
        silicon_relative_permittivity=11.7,
    )

    assert isinstance(model, comsol_model.COMSOL)
    assert model.java is java
    assert model.layout is layout
    assert calls == [
        (
            client,
            layout,
            "sheet",
            {
                "substrate_thickness_um": 250.0,
                "air_height_um": 150.0,
                "lateral_margin_um": 0.0,
                "silicon_relative_permittivity": 11.7,
            },
        )
    ]


def test_create_metal_dispatches_to_the_metal_builder(
    comsol: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
):
    """create_metal forwards its arguments and adopts the built model."""
    mph, comsol_model = comsol
    java = MagicMock()
    calls: list[tuple[Any, ...]] = []

    def fake_builder(client: Any, layout: Any, **kwargs: Any) -> Any:
        calls.append((client, layout, kwargs))
        return mph.Model(java)

    monkeypatch.setattr(comsol_model.metal, "build_comsol_metal_model", fake_builder)
    client = MagicMock()
    layout = _layout()
    model = comsol_model.COMSOL.create_metal(client, layout, metal_thickness_um=0.35)

    assert isinstance(model, comsol_model.COMSOL)
    assert model.java is java
    assert model.layout is layout
    assert calls == [
        (client, layout, {"metal_thickness_um": 0.35, "name": "gdsfactory metal"})
    ]


def test_add_cpw_rf_study_dispatches_and_chains(
    comsol: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    wrapped: tuple[Any, Any, Any],
):
    """The RF study method calls the helper with the stored layout and returns self."""
    _, comsol_model = comsol
    model, _, layout = wrapped
    calls: list[tuple[Any, ...]] = []

    def fake_study(study_model: Any, study_layout: Any, **kwargs: Any) -> Any:
        calls.append((study_model, study_layout, kwargs))
        return study_model

    monkeypatch.setattr(comsol_model.rf, "add_cpw_rf_study", fake_study)

    assert model.add_cpw_rf_study(cpw_gap_um=6.0, effective_index_shift=3.4) is model
    assert calls == [
        (
            model,
            layout,
            {
                "cpw_gap_um": 6.0,
                "frequency_ghz": 7.5,
                "mesh_size": 8,
                "effective_index_shift": 3.4,
            },
        )
    ]


def test_add_capacitance_study_dispatches_and_chains(
    comsol: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    wrapped: tuple[Any, Any, Any],
):
    """The capacitance method calls the helper with the stored layout and returns self."""
    _, comsol_model = comsol
    model, _, layout = wrapped
    conductors = (("pad_l", (2.0, 5.0)), ("pad_r", (8.0, 5.0)))
    calls: list[tuple[Any, ...]] = []

    def fake_study(study_model: Any, study_layout: Any, **kwargs: Any) -> Any:
        calls.append((study_model, study_layout, kwargs))
        return study_model

    monkeypatch.setattr(comsol_model.capacitance, "add_capacitance_study", fake_study)

    result = model.add_capacitance_study(
        conductors=conductors, terminal="pad_l", grounds=("pad_r",), voltage_v=2.0
    )

    assert result is model
    assert calls == [
        (
            model,
            layout,
            {
                "conductors": conductors,
                "terminal": "pad_l",
                "grounds": ("pad_r",),
                "voltage_v": 2.0,
                "mesh_size": 7,
            },
        )
    ]


def test_refine_metal_plane_mesh_returns_the_element_count(
    comsol: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    wrapped: tuple[Any, Any, Any],
):
    """The refinement method forwards its arguments and returns the helper's count."""
    _, comsol_model = comsol
    model, _, layout = wrapped
    box = ComsolBoundingBox(xmin=0.0, ymin=0.0, xmax=5.0, ymax=5.0)
    calls: list[tuple[Any, ...]] = []

    def fake_refine(
        refine_model: Any, refine_layout: Any, passes: int, **kwargs: Any
    ) -> int:
        calls.append((refine_model, refine_layout, passes, kwargs))
        return 11

    monkeypatch.setattr(comsol_model.mesh, "refine_metal_plane_mesh", fake_refine)

    assert model.refine_metal_plane_mesh(2, z_half_um=5.0, refine_box=box) == 11
    assert calls == [(model, layout, 2, {"z_half_um": 5.0, "refine_box": box})]


def test_pin_absolute_mesh_sizes_returns_the_element_count(
    comsol: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    wrapped: tuple[Any, Any, Any],
):
    """The absolute-size method forwards its arguments and returns the helper's count."""
    _, comsol_model = comsol
    model, _, _ = wrapped
    face_sizes = {"pad_l": (5.0, 0.5), "gnd": (10.0, 1.0)}
    calls: list[tuple[Any, ...]] = []

    def fake_pin(pin_model: Any, **kwargs: Any) -> int:
        calls.append((pin_model, kwargs))
        return 12

    monkeypatch.setattr(comsol_model.mesh, "pin_absolute_mesh_sizes", fake_pin)

    result = model.pin_absolute_mesh_sizes(
        global_hmax_um=40.0, global_hmin_um=4.0, face_sizes=face_sizes, hgrad=1.3
    )

    assert result == 12
    assert calls == [
        (
            model,
            {
                "global_hmax_um": 40.0,
                "global_hmin_um": 4.0,
                "face_sizes": face_sizes,
                "hgrad": 1.3,
                "hcurve": None,
                "hnarrow": None,
            },
        )
    ]


def test_pin_absolute_edge_mesh_sizes_returns_the_element_count(
    comsol: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    wrapped: tuple[Any, Any, Any],
):
    """The edge-size method forwards its arguments and returns the helper's count."""
    _, comsol_model = comsol
    model, _, _ = wrapped
    calls: list[tuple[Any, ...]] = []

    def fake_pin(pin_model: Any, **kwargs: Any) -> int:
        calls.append((pin_model, kwargs))
        return 13

    monkeypatch.setattr(comsol_model.mesh, "pin_absolute_edge_mesh_sizes", fake_pin)

    result = model.pin_absolute_edge_mesh_sizes(
        edge_selection="meander_edges",
        global_hmax_um=40.0,
        global_hmin_um=4.0,
        edge_hmax_um=2.0,
        edge_hmin_um=0.2,
    )

    assert result == 13
    assert calls == [
        (
            model,
            {
                "edge_selection": "meander_edges",
                "global_hmax_um": 40.0,
                "global_hmin_um": 4.0,
                "edge_hmax_um": 2.0,
                "edge_hmin_um": 0.2,
            },
        )
    ]
