from __future__ import annotations

import gdsfactory as gf
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.gmsh.uz_xsection_mesh import uz_xsection_mesh
from gplugins.gmsh.xy_xsection_mesh import xy_xsection_mesh


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
        "core": {"resolution": 0.05, "distance": 2},
        "slab90": {"resolution": 0.03, "distance": 1},
        "via_contact": {"resolution": 0.1, "distance": 1},
    }
    uz_xsection_mesh(
        waveguide,
        [(4, -15), (4, 15)],
        filtered_layer_stack,
        resolutions=resolutions,
        background_tag="Oxide",
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
    xy_xsection_mesh(
        component=waveguide,
        z=0.09,
        layer_stack=filtered_layer_stack,
        resolutions=resolutions,
        background_tag="Oxide",
    )


if __name__ == "__main__":
    test_gmsh_xy_xsection_mesh()
    # test_gmsh_uz_xsection_mesh()
