from __future__ import annotations

import gdsfactory as gf

import gplugins.tidy3d as gt


def test_write_sparameters_3d() -> None:
    """Checks simulation for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    gt.write_sparameters(c, run=False, sim_size_z=4)


def test_write_sparameters_2d() -> None:
    """Checks simulation for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    gt.write_sparameters(c, run=False, sim_size_z=0)
