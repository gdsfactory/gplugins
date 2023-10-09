from __future__ import annotations

import gdsfactory as gf
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.gmsh.get_mesh import get_mesh


def test_custom_physical_uz() -> None:
    waveguide = gf.components.straight_pin(length=10, taper=None)

    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "via_contact",
            )
        }
    )

    layer_physical_map = {
        "slab90": "silicon",
        "core": "silicon",
        "via_contact": "metal",
    }

    mesh = get_mesh(
        type="uz",
        component=waveguide,
        xsection_bounds=[(4, -15), (4, 15)],
        layer_stack=filtered_layer_stack,
        layer_physical_map=layer_physical_map,
        background_tag="Oxide",
        filename="uzmesh_ref.msh",
    )

    for value in layer_physical_map.values():
        assert value in mesh.cell_sets_dict.keys()


def test_custom_physical_xy() -> None:
    waveguide = gf.components.straight_pin(length=10, taper=None)

    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "via_contact",
            )
        }
    )

    layer_physical_map = {
        "slab90": "silicon",
        "core": "silicon",
        "via_contact": "metal",
    }

    mesh = get_mesh(
        type="xy",
        component=waveguide,
        z=0.09,
        layer_stack=filtered_layer_stack,
        layer_physical_map=layer_physical_map,
        background_tag="Oxide",
        filename="xymesh.msh",
    )

    for value in layer_physical_map.values():
        assert value in mesh.cell_sets_dict.keys()


def test_custom_physical_xyz() -> None:
    waveguide = gf.components.straight_pin(length=10, taper=None)

    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "via_contact",
            )
        }
    )

    layer_physical_map = {
        "slab90": "silicon",
        "core": "silicon",
        "via_contact": "metal",
    }

    mesh = get_mesh(
        type="3D",
        component=waveguide,
        layer_stack=filtered_layer_stack,
        layer_physical_map=layer_physical_map,
        background_tag="Oxide",
        filename="xyzmesh.msh",
    )

    for value in layer_physical_map.values():
        assert value in mesh.cell_sets_dict.keys()


if __name__ == "__main__":
    test_custom_physical_uz()
