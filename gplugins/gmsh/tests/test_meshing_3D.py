from __future__ import annotations

import gdsfactory as gf
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.gmsh.get_mesh import get_mesh


def test_gmsh_xyz_mesh() -> None:
    # Choose some component
    c = gf.get_component(gf.components.straight_heater_metal(length=40))

    # Generate a new component and layer_stack with new logical layers
    layer_stack = get_layer_stack()

    # FIXME: .filtered returns all layers
    # filtered_layer_stack = layer_stack.filtered_from_layerspec(layerspecs=c.get_layers())
    filtered_layer_stack = LayerStack(
        layers={
            k: layer_stack.layers[k]
            for k in (
                # "via1",
                "box",
                "clad",
                # "metal2",
                "heater",
                "via2",
                "core",
                "metal3",
                # "via_contact",
                # "metal1"
            )
        }
    )

    resolutions = {
        "core": {"resolution": 0.3},
    }
    get_mesh(
        type="3D",
        component=c,
        layer_stack=filtered_layer_stack,
        resolutions=resolutions,
        filename="mesh.msh",
        default_characteristic_length=5,
        verbosity=5,
        # port_names=["r_e2", "l_e4"],
        wafer_padding=2.0,
        wafer_layer=(999, 0),
    )


if __name__ == "__main__":
    test_gmsh_xyz_mesh()
