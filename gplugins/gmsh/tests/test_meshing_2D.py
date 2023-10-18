from __future__ import annotations

import gdsfactory as gf
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.gmsh.get_mesh import get_mesh


def test_gmsh_uz_xsection_mesh() -> None:
    waveguide = gf.components.straight_pin(length=10, taper=None)

    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "via_contact",
                # "metal2",
            )  # "slab90", "via_contact")#"via_contact") # "slab90", "core"
        }
    )

    resolutions = {
        "core": {"resolution": 0.05, "DistMax": 2},
        "slab90": {"resolution": 0.03, "DistMax": 1},
        "via_contact": {"resolution": 0.1, "DistMax": 1},
    }
    get_mesh(
        type="uz",
        component=waveguide,
        xsection_bounds=[(4, -15), (4, 15)],
        layer_stack=filtered_layer_stack,
        resolutions=resolutions,
        background_tag="Oxide",
        filename="uzmesh_ref.msh",
    )


def test_gmsh_xy_xsection_mesh() -> None:
    import gdsfactory as gf

    waveguide = gf.components.straight_pin(length=10, taper=None)

    from gdsfactory.pdk import get_layer_stack

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

    resolutions = {
        "core": {"resolution": 0.05, "distance": 0.1},
        "via_contact": {"resolution": 0.1, "distance": 0},
    }
    get_mesh(
        type="xy",
        component=waveguide,
        z=0.09,
        layer_stack=filtered_layer_stack,
        resolutions=resolutions,
        background_tag="Oxide",
        filename="xymesh.msh",
    )


if __name__ == "__main__":
    test_gmsh_xy_xsection_mesh()
    test_gmsh_uz_xsection_mesh()
