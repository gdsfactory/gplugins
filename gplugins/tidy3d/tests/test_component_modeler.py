import gdsfactory as gf
from gdsfactory.generic_tech import LAYER_STACK

import gplugins.tidy3d as gt

component = gf.components.coupler_ring()


def test_component_modeler_3d() -> None:
    c = gt.Tidy3DComponent(
        component=component,
        layer_stack=LAYER_STACK,
        pad_xy_inner=2.0,
        pad_xy_outer=2.0,
        pad_z_inner=0,
        pad_z_outer=0,
        extend_ports=2.0,
    )
    modeler = c.get_component_modeler(
        center_z="core", port_size_mult=(6, 4), sim_size_z=3
    )
    assert modeler


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    c = gt.Tidy3DComponent(
        component=component,
        layer_stack=LAYER_STACK,
        pad_xy_inner=2.0,
        pad_xy_outer=2.0,
        pad_z_inner=0,
        pad_z_outer=0,
        extend_ports=2.0,
    )
    modeler = c.get_component_modeler(
        center_z="core", port_size_mult=(6, 4), sim_size_z=0
    )
    fig, ax = plt.subplots(2, 1)
    modeler.plot_sim(z=c.get_layer_center("core")[2], ax=ax[0])
    modeler.plot_sim(x=c.ports[0].center[0], ax=ax[1])
    fig.tight_layout()
    plt.show()
