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
    c << gf.components.bbox(bbox=waveguide.bbox, layer=LAYER.WAFER)

    # Generate a new component and layerstack with new logical layers
    layerstack = get_layer_stack()

    # FIXME: .filtered returns all layers
    # filtered_layerstack = layerstack.filtered_from_layerspec(layerspecs=c.get_layers())
    filtered_layerstack = LayerStack(
        layers={
            k: layerstack.layers[k]
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
        layerstack=filtered_layerstack,
        resolutions=resolutions,
        filename="mesh.msh",
        default_characteristic_length=5,
        verbosity=5,
        portnames=["r_e2", "l_e4"],
    )

    pass


if __name__ == "__main__":
    test_gmsh_xyz_mesh()
