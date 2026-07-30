"""CI-safe tests for the EMode plugin.

These tests only require the pip-installable ``emodeconnection`` client. They
exercise the pure gdsfactory-to-EMode translation functions and use a stub
session to test ``EMode.build_waveguide`` without launching the EMode
application (which requires a separate installation and license).
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("emodeconnection")

import gdsfactory as gf
from gdsfactory.gpdk import LAYER_STACK
from gdsfactory.technology import LayerStack

from gplugins.emode import (
    EMode,
    get_emode_settings,
    get_shapes_from_layer_stack,
)
from gplugins.emode.emode import DIMENSIONAL_SETTINGS, get_emode_material

EMODE_MATERIALS = ["Air", "Si", "SiO2", "Si3N4"]


@pytest.fixture
def layer_stack() -> LayerStack:
    """Silicon-on-insulator rib stack with pinned dimensions and mesh orders."""
    updates = {
        "core": {"thickness": 0.22, "zmin": 0.0, "mesh_order": 1},
        "slab90": {"thickness": 0.09, "zmin": 0.0, "mesh_order": 2},
        "clad": {"thickness": 1.5, "zmin": 0.0, "mesh_order": 9},
        "box": {"thickness": 1.5, "zmin": -1.5, "mesh_order": 8},
    }
    return LayerStack(
        layers={
            name: LAYER_STACK.layers[name].model_copy(update=update)
            for name, update in updates.items()
        }
    )


class FakeEMode(EMode):
    """EMode session that records calls instead of launching the application."""

    def __init__(self) -> None:
        """Initialize without calling super().__init__, which launches the app."""
        self.recorded_settings: list[dict[str, Any]] = []
        self.recorded_shapes: list[dict[str, Any]] = []

    def settings(self, **kwargs: Any) -> None:
        self.recorded_settings.append(kwargs)

    def shape(self, **kwargs: Any) -> None:
        self.recorded_shapes.append(kwargs)

    def get(self, key: str) -> list[str]:
        assert key == "materials"
        return list(EMODE_MATERIALS)


def test_get_emode_settings_converts_dimensional_values() -> None:
    settings = get_emode_settings(
        wavelength=1.55,
        window_width=3.0,
        num_modes=2,
        background_material="Air",
    )
    assert settings["wavelength"] == pytest.approx(1550.0)
    assert settings["window_width"] == pytest.approx(3000.0)
    assert settings["num_modes"] == 2
    assert settings["background_material"] == "Air"


def test_get_emode_settings_passes_none_through() -> None:
    settings = get_emode_settings(wavelength=1.55, bend_radius=None)
    assert settings["wavelength"] == pytest.approx(1550.0)
    assert settings["bend_radius"] is None


@pytest.mark.parametrize("key", sorted(DIMENSIONAL_SETTINGS))
def test_get_emode_settings_converts_every_dimensional_key(key: str) -> None:
    settings = get_emode_settings(**{key: 1.0})
    assert settings[key] == pytest.approx(1000.0)


def test_get_emode_material_matches_case_insensitively() -> None:
    assert get_emode_material("si", EMODE_MATERIALS) == "Si"
    assert get_emode_material("SIO2", EMODE_MATERIALS) == "SiO2"
    assert get_emode_material("unknown_material", EMODE_MATERIALS) == "unknown_material"
    assert get_emode_material("si", ()) == "si"


def test_shapes_one_per_layer_in_order(layer_stack: LayerStack) -> None:
    shapes = get_shapes_from_layer_stack("rib", layer_stack)
    assert [shape["name"] for shape in shapes] == list(layer_stack.layers)


def test_shapes_mask_from_cross_section(layer_stack: LayerStack) -> None:
    shapes = {
        shape["name"]: shape
        for shape in get_shapes_from_layer_stack(
            gf.cross_section.rib(width=0.6), layer_stack
        )
    }
    # The core layer matches the WG section of the rib cross-section, so it
    # is patterned: masked and etched through its full thickness.
    assert shapes["core"]["mask"] == pytest.approx(600.0)
    assert shapes["core"]["mask_offset"] == pytest.approx(0.0)
    assert shapes["core"]["etch_depth"] == pytest.approx(220.0)
    # Layers without a matching section are blanket layers with no mask/etch.
    assert "mask" not in shapes["box"]
    assert "mask_offset" not in shapes["box"]
    assert "etch_depth" not in shapes["box"]


def test_shapes_mask_offset_from_cross_section(layer_stack: LayerStack) -> None:
    xs = gf.CrossSection(sections=(gf.Section(width=0.5, offset=0.1, layer="WG"),))
    shapes = {
        shape["name"]: shape for shape in get_shapes_from_layer_stack(xs, layer_stack)
    }
    assert shapes["core"]["mask"] == pytest.approx(500.0)
    assert shapes["core"]["mask_offset"] == pytest.approx(100.0)


def test_shapes_match_section_by_layer_tuple(layer_stack: LayerStack) -> None:
    # Layer specs are normalized through the PDK, so a section defined with a
    # (layer, datatype) tuple matches a layer stack that uses layer names.
    wg_tuple = gf.get_layer_tuple("WG")
    xs = gf.CrossSection(sections=(gf.Section(width=0.5, layer=wg_tuple),))
    shapes = {
        shape["name"]: shape for shape in get_shapes_from_layer_stack(xs, layer_stack)
    }
    assert shapes["core"]["mask"] == pytest.approx(500.0)
    assert "mask" not in shapes["clad"]


def test_shapes_positions_relative_to_stack_bottom(layer_stack: LayerStack) -> None:
    shapes = {
        shape["name"]: shape
        for shape in get_shapes_from_layer_stack("rib", layer_stack)
    }
    # min zmin is -1.5 (box), so the box spans 0..1500 nm with center at 750 nm.
    assert shapes["box"]["position"] == pytest.approx([0.0, 750.0])
    assert shapes["core"]["position"] == pytest.approx([0.0, 1610.0])
    assert shapes["slab90"]["position"] == pytest.approx([0.0, 1545.0])
    assert shapes["clad"]["position"] == pytest.approx([0.0, 2250.0])
    assert shapes["core"]["height"] == pytest.approx(220.0)


def test_shapes_priority_from_mesh_order(layer_stack: LayerStack) -> None:
    shapes = {
        shape["name"]: shape
        for shape in get_shapes_from_layer_stack("rib", layer_stack)
    }
    # gdsfactory mesh order (lower = higher priority) maps to EMode priority
    # (higher = higher priority): priority = max_order - mesh_order + 1.
    assert shapes["core"]["priority"] == 9
    assert shapes["slab90"]["priority"] == 8
    assert shapes["box"]["priority"] == 2
    assert shapes["clad"]["priority"] == 1


def test_shapes_match_materials(layer_stack: LayerStack) -> None:
    shapes = {
        shape["name"]: shape
        for shape in get_shapes_from_layer_stack("rib", layer_stack, EMODE_MATERIALS)
    }
    assert shapes["core"]["material"] == "Si"
    assert shapes["box"]["material"] == "SiO2"

    # Without a material list, gdsfactory names pass through unchanged.
    shapes = {
        shape["name"]: shape
        for shape in get_shapes_from_layer_stack("rib", layer_stack)
    }
    assert shapes["core"]["material"] == "si"


def test_empty_layer_stack_raises() -> None:
    with pytest.raises(ValueError, match="at least one layer"):
        get_shapes_from_layer_stack("rib", LayerStack(layers={}))


def test_layer_without_material_raises(layer_stack: LayerStack) -> None:
    layer_stack.layers["core"] = layer_stack.layers["core"].model_copy(
        update={"material": None}
    )
    with pytest.raises(ValueError, match="core"):
        get_shapes_from_layer_stack("rib", layer_stack)


def test_build_waveguide_forwards_to_session(layer_stack: LayerStack) -> None:
    em = FakeEMode()
    em.build_waveguide(
        cross_section="rib",
        layer_stack=layer_stack,
        wavelength=1.55,
        num_modes=2,
    )

    assert len(em.recorded_settings) == 1
    assert em.recorded_settings[0]["wavelength"] == pytest.approx(1550.0)
    assert em.recorded_settings[0]["num_modes"] == 2

    shapes = {shape["name"]: shape for shape in em.recorded_shapes}
    assert set(shapes) == set(layer_stack.layers)
    # Materials from the session are used to match gdsfactory material names.
    assert shapes["core"]["material"] == "Si"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
