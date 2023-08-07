from __future__ import annotations

import gdsfactory as gf

import gplugins.tidy3d as gt


def test_plot_sparameters_3d() -> None:
    """Checks simulation for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    gt.write_sparameters_1x1(c, is_3d=True, run=False)


def test_plot_sparameters_2d() -> None:
    """Checks simulation for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    gt.write_sparameters_1x1(c, is_3d=False, run=False)


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    c = gf.components.straight(length=2)
    is_3d = True
    is_3d = False
    gt.write_sparameters_1x1(c, run=False, is_3d=is_3d)
    plt.show()
