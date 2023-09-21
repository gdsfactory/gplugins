from __future__ import annotations

import gdsfactory as gf
from gdsfactory.generic_tech import LAYER
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.gmsh.xyz_mesh import xyz_mesh


def test_gmsh_xyz_mesh() -> None:
    # Choose some component
    c = gf.component.Component()
    waveguide = c << gf.get_component(gf.components.straight_heater_metal(length=40))
    c.add_ports(waveguide.get_ports_list())

    # Add wafer / vacuum (could be automated)
    _ = c << gf.components.bbox(bbox=waveguide.bbox, layer=LAYER.WAFER)

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
    xyz_mesh(
        component=c,
        layer_stack=filtered_layer_stack,
        resolutions=resolutions,
        filename="mesh.msh",
        default_characteristic_length=5,
        verbosity=5,
        port_names=["r_e2", "l_e4"],
    )


if __name__ == "__main__":
    test_gmsh_xyz_mesh()
