import gdsfactory as gf
import numpy as np
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.meow import MEOW


def test_meow_defaults() -> None:
    c = gf.components.taper_cross_section_linear()
    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "box",
                "clad",
            )
        }
    )

    sp = MEOW(
        component=c,
        layer_stack=filtered_layer_stack,
        wavelength=1.55,
        overwrite=True,
    ).compute_sparameters()

    for key in sp.keys():
        if key == "wavelengths":
            continue
        entry1, entry2 = key.split(",")
        port1, mode1 = entry1.split("@")
        port2, mode2 = entry2.split("@")

        # Transmission larger than 90%
        if port1 != port2 and mode1 == "0" and mode2 == "0":
            assert np.abs(sp[key]) ** 2 > 0.90

    # Reflection smaller than 5%
    assert abs(sp["o1@0,o1@0"]) < 0.05
    assert abs(sp["o2@0,o2@0"]) < 0.05


def test_cells() -> None:
    layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "box",
                "clad",
            )
        }
    )

    c = gf.components.taper(length=10, width2=2)
    m = MEOW(component=c, layer_stack=layer_stack, wavelength=1.55, cell_length=1)
    assert len(m.cells) == 11, len(m.cells)

    c = gf.components.taper(length=1, width2=2)
    m = MEOW(component=c, layer_stack=layer_stack, wavelength=1.55, cell_length=1)
    assert len(m.cells) == 4, len(m.cells)


if __name__ == "__main__":
    # test_cells()
    # test_meow_defaults()
    c = gf.components.taper_cross_section_linear()
    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "box",
                "clad",
            )
        }
    )

    sp = MEOW(
        component=c,
        layer_stack=filtered_layer_stack,
        wavelength=1.55,
        overwrite=True,
    ).compute_sparameters()
