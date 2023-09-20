from typing import Any

import gdsfactory as gf
import jax.numpy as jnp
from gdsfactory.component import Component
from gdsfactory.technology import LayerStack
from pjz._field import SimParams, scatter

from gplugins.fdtdz.get_epsilon_fdtdz import (
    component_to_epsilon_pjz,
    material_name_to_fdtdz,
)
from gplugins.fdtdz.get_ports_fdtdz import get_mode_port


def get_sparameters_fdtdz(
    component: Component,
    layer_stack: LayerStack | None = None,
    nm_per_pixel: int = 20,
    extend_ports_length: float | None = 2.0,
    zmin: float = -0.75,
    zz: int = 96,
    tt: int = 10000,
    wavelength: float = 1.55,
    port_margin: float = 1,
    material_name_to_fdtdz: dict = material_name_to_fdtdz,
    default_index: float = 1.44,
) -> dict[str, Any]:
    r"""Returns Simulation dict from gdsfactory Component and LayerStack.

    Args:
        component: gdsfactory component.
        layer_stack: gdsfactory layer_stack.
        nm_per_pixel: nm per pixel.
        extend_ports_length: length to extend ports.
        zmin: can be used to clip the layer_stack at the lower end; upper end determined by zz * num_per_pixel
        zz: number of vertical grid points
        tt: tt.
        wavelength: wavelength.
        port_margin: port_margin.
        material_name_to_fdtdz: material_name_to_fdtdz.
        default_index: default_index.

    Returns:
        simulation dict: sim, monitors, sources.

    .. code::

         top view
              ________________________________
             |                               |
             | xmargin_left                  | port_extension
             |<------>          port_margin ||<-->
          ___|___________          _________||___
             |           \        /          |
             |            \      /           |
             |             ======            |
             |            /      \           |
          ___|___________/        \__________|___
             |   |                 <-------->|
             |   |ymargin_bot   xmargin_right|
             |   |                           |
             |___|___________________________|

        side view
              ________________________________
             |                     |         |
             |                     |         |
             |                   zmargin_top |
             |ymargin              |         |
             |<---> _____         _|___      |
             |     |     |       |     |     |
             |     |     |       |     |     |
             |     |_____|       |_____|     |
             |       |                       |
             |       |                       |
             |       |zmargin_bot            |
             |       |                       |
             |_______|_______________________|



    Make sure you review the simulation before you simulate a component

    .. code::

        import gdsfactory as gf
        import gplugins.fdtdz as gz

        c = gf.components.bend_circular()
        sp = gz.get_sparameters(c, run=False)

    """

    # Checks from gmeep
    component_ref = component.ref()
    component_ref.x = 0
    component_ref.y = 0

    optical_port_names = list(component_ref.get_ports_dict(port_type="optical").keys())

    assert isinstance(
        component, Component
    ), f"component needs to be a gf.Component, got Type {type(component)}"

    component_extended = (
        gf.components.extension.extend_ports(
            component=component, length=extend_ports_length, centered=True
        )
        if extend_ports_length
        else component
    )

    # Create epsilon distribution
    epsilon = component_to_epsilon_pjz(
        component=component_extended,
        layer_stack=layer_stack,
        zmin=zmin,
        zz=zz,
        material_name_to_index=material_name_to_fdtdz,
        default_index=default_index,
    )

    # Setup modes sources/monitors
    omega = 1 / wavelength
    excitations = []
    positions = []
    for portname in optical_port_names:
        excitation, pos, epsilon_port = get_mode_port(
            omega=omega,
            port=component.ports[portname],
            epsilon=epsilon,
            xmin=component_extended.xmin,
            ymin=component_extended.ymin,
            nm_per_pixel=nm_per_pixel,
            port_extent_xy=port_margin,
        )
        excitations.append(excitation)
        positions.append(pos)

    return scatter(
        epsilon=epsilon,
        omega=jnp.array([omega]),
        modes=tuple(excitations),
        pos=tuple(positions),
        sim_params=SimParams(tt=tt, omega_range=(omega, omega)),
    )


if __name__ == "__main__":
    from gdsfactory.generic_tech import LAYER, LAYER_STACK

    length = 5

    c = gf.Component()
    waveguide = c << gf.components.straight(length=length, layer=LAYER.WG).extract(
        layers=(LAYER.WG,)
    )
    padding = c << gf.components.bbox(
        waveguide.bbox, top=2, bottom=2, layer=LAYER.WAFER
    )
    c.add_ports(gf.components.straight(length=length).get_ports_list())

    filtered_layer_stack = LayerStack(
        layers={k: LAYER_STACK.layers[k] for k in ["clad", "box", "core"]}
    )

    out = get_sparameters_fdtdz(
        component=c,
        layer_stack=filtered_layer_stack,
        nm_per_pixel=20,
        extend_ports_length=2.0,
        zmin=-0.75,
        zz=96,
        tt=10000,
        wavelength=1.55,
        port_margin=1,
    )

    print(out)
