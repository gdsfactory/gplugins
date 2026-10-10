"""Tests for the COMSOL metal geometry builder's public surface.

The builder talks to COMSOL through MPh, which is not installed here. These
tests cover only what runs before the client is touched (argument validation)
plus what the package exposes, so nothing needs to mock MPh or the Java API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest

from gplugins import comsol as simulation
from gplugins.comsol import layout as comsol_layout
from gplugins.comsol import metal as comsol
from gplugins.comsol.layout import (
    ComsolBoundingBox,
    ComsolLayout,
    ComsolPolygon,
)
from gplugins.comsol.metal import build_comsol_metal_model


def _empty_layout() -> ComsolLayout:
    """A layout with a bounding box but no metal to extrude.

    Returns:
        The empty layout.
    """
    return ComsolLayout(
        polygons=(),
        feed_ports=(),
        bbox=ComsolBoundingBox(xmin=0.0, ymin=0.0, xmax=1.0, ymax=1.0),
    )


def test_historical_cpw_alias_is_gone():
    """The builder is named for what it does; the old CPW alias was removed."""
    assert not hasattr(simulation, "build_comsol_cpw_model")
    assert not hasattr(comsol, "build_comsol_cpw_model")
    assert build_comsol_metal_model.__name__ == "build_comsol_metal_model"


def test_comsol_class_is_exposed_lazily():
    """The model class is public, and importing it stays the caller's choice."""
    assert "COMSOL" in simulation.__all__
    assert "COMSOL" not in vars(simulation) or (
        vars(simulation)["COMSOL"].__module__ == "gplugins.comsol.model"
    )


@pytest.mark.parametrize(
    "name",
    [
        "ComsolBoundingBox",
        "ComsolFeedPort",
        "ComsolLayout",
        "ComsolPolygon",
        "CropPlanes",
        "crop_planes",
        "feed_port",
        "prepare_comsol_layout",
        "validate_crop_containment",
    ],
)
def test_comsol_layout_public_exports(name: str):
    """The lazy package exports resolve to the geometry module's objects."""
    assert getattr(simulation, name) is getattr(comsol_layout, name)


def test_build_metal_model_subtracts_each_hole_before_extrusion():
    """The Java geometry calls retain both etched voids in the metal solid."""
    layout = ComsolLayout(
        polygons=(
            ComsolPolygon(
                outline=((0, 0), (10, 0), (10, 10), (0, 10)),
                holes=(
                    ((1, 1), (2, 1), (2, 2), (1, 2)),
                    ((3, 3), (4, 3), (4, 4), (3, 4)),
                ),
            ),
        ),
        feed_ports=(),
        bbox=ComsolBoundingBox(xmin=0, ymin=0, xmax=10, ymax=10),
    )
    client = MagicMock()
    model = client.create.return_value
    geometry = model.java.component.return_value.geom.return_value.create.return_value
    work_plane_feature = MagicMock()
    extrude = MagicMock()
    geometry.feature.side_effect = {"wp1": work_plane_feature, "ext1": extrude}.get
    work_plane = work_plane_feature.geom.return_value
    features = {
        tag: MagicMock() for tag in ("pol0", "hole0_0", "hole0_1", "dif0_0", "dif0_1")
    }
    work_plane.feature.side_effect = features.get
    for tag in ("dif0_0", "dif0_1"):
        features[tag].selection.side_effect = {
            "input": MagicMock(),
            "input2": MagicMock(),
        }.get

    result = build_comsol_metal_model(client, layout, metal_thickness_um=0.35)

    assert result is model
    client.create.assert_called_once_with("gdsfactory metal")
    geometry.lengthUnit.assert_called_once_with("um")
    assert geometry.create.call_args_list == [
        call("wp1", "WorkPlane"),
        call("ext1", "Extrude"),
    ]
    assert work_plane.create.call_args_list == [
        call("pol0", "Polygon"),
        call("hole0_0", "Polygon"),
        call("dif0_0", "Difference"),
        call("hole0_1", "Polygon"),
        call("dif0_1", "Difference"),
    ]
    features["pol0"].set.assert_any_call("x", "0,10,10,0")
    features["pol0"].set.assert_any_call("y", "0,0,10,10")
    features["hole0_0"].set.assert_any_call("x", "1,2,2,1")
    features["hole0_0"].set.assert_any_call("y", "1,1,2,2")
    features["hole0_1"].set.assert_any_call("x", "3,4,4,3")
    features["hole0_1"].set.assert_any_call("y", "3,3,4,4")
    features["dif0_0"].selection("input").set.assert_called_once_with("pol0")
    features["dif0_0"].selection("input2").set.assert_called_once_with("hole0_0")
    features["dif0_1"].selection("input").set.assert_called_once_with("dif0_0")
    features["dif0_1"].selection("input2").set.assert_called_once_with("hole0_1")
    extrude.set.assert_any_call("workplane", "wp1")
    extrude.set.assert_any_call("distance", "0.35")
    extrude.selection.assert_called_once_with("input")
    extrude.selection.return_value.set.assert_called_once_with("wp1")
    geometry.run.assert_called_once_with()
    client.remove.assert_not_called()


def _one_polygon_layout() -> ComsolLayout:
    """A layout with one metal polygon and no holes.

    Returns:
        The layout.
    """
    return ComsolLayout(
        polygons=(ComsolPolygon(outline=((0, 0), (10, 0), (10, 10), (0, 10))),),
        feed_ports=(),
        bbox=ComsolBoundingBox(xmin=0, ymin=0, xmax=10, ymax=10),
    )


def test_a_failed_build_removes_the_native_model():
    """A failure after the model exists does not leak it in the COMSOL process."""
    client = MagicMock()
    model = client.create.return_value
    model.java.component.side_effect = ValueError("no geometry")

    with pytest.raises(ValueError, match="no geometry"):
        build_comsol_metal_model(client, _one_polygon_layout())

    client.remove.assert_called_once_with(model)


def test_a_failing_cleanup_keeps_the_original_error():
    """A cleanup that itself fails must not mask the build failure."""
    client = MagicMock()
    model = client.create.return_value
    model.java.component.side_effect = ValueError("no geometry")
    client.remove.side_effect = RuntimeError("cleanup failed")

    with pytest.raises(ValueError, match="no geometry"):
        build_comsol_metal_model(client, _one_polygon_layout())

    client.remove.assert_called_once_with(model)


@pytest.mark.parametrize("thickness", [0.0, -0.2, float("nan"), float("inf")])
def test_rejects_bad_thickness_before_touching_comsol(thickness: float):
    """Thickness is validated before any MPh/COMSOL call."""
    client: Any = None
    with pytest.raises(ValueError, match="metal_thickness_um"):
        build_comsol_metal_model(client, _empty_layout(), metal_thickness_um=thickness)


def test_rejects_layout_without_polygons_before_touching_comsol():
    """An empty layout is refused before any MPh/COMSOL call."""
    client: Any = None
    with pytest.raises(ValueError, match="no polygons"):
        build_comsol_metal_model(client, _empty_layout())
