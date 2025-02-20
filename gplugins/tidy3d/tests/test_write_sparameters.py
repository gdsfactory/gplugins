from __future__ import annotations

import gdsfactory as gf

import gplugins.tidy3d as gt


def test_write_sparameters_3d() -> None:
    """Checks simulation for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    gt.write_sparameters(c, sim_size_z=4, plot_simulation_layer_name="core")


def test_write_sparameters_2d() -> None:
    """Checks simulation for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    gt.write_sparameters(c, sim_size_z=0, plot_simulation_layer_name="core")


if __name__ == "__main__":
    test_write_sparameters_3d()
