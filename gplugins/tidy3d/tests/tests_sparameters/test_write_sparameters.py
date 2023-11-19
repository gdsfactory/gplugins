from __future__ import annotations

import gdsfactory as gf
import numpy as np
import tidy3d as td

import gplugins.tidy3d as gt
from gplugins.common.config import PATH


def test_sparameters_straight_3d(overwrite=True) -> None:
    """Checks Sparameters for a straight waveguide in 3D."""
    c = gf.components.straight(length=2)
    sp = gt.write_sparameters_1x1(
        c, overwrite=overwrite, is_3d=True, dirpath=PATH.sparameters_repo
    )

    assert 1 > np.abs(sp["o1@0,o2@0"]).min() > 0.8, np.abs(sp["o1@0,o2@0"]).min()
    assert 0 < np.abs(sp["o1@0,o1@0"]).max() < 0.1, np.abs(sp["o1@0,o1@0"]).max()


def test_sparameters_straight_2d(overwrite=True) -> None:
    """Checks Sparameters for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    sp = gt.write_sparameters_1x1(
        c,
        dirpath=PATH.sparameters_repo,
        overwrite=overwrite,
        is_3d=False,
        run=True,
        port_margin=2.0,
        num_modes=1,
        wavelength_start=1.5,
        wavelength_stop=1.6,
        grid_spec=td.GridSpec.auto(min_steps_per_wvl=10, wavelength=1.5),
    )

    np.testing.assert_allclose(np.abs(sp["o1@0,o2@0"]), 1, atol=1e-2)
    np.testing.assert_allclose(np.abs(sp["o1@0,o1@0"]), 0, atol=1e-2)


if __name__ == "__main__":
    overwrite = False
    c = gf.components.straight(length=3)
    sp = gt.write_sparameters_1x1(c, overwrite=overwrite, is_3d=True, run=True)

    # Check reasonable reflection/transmission
    assert 1 > np.abs(sp["o1@0,o2@0"]).min() > 0.6, np.abs(sp["o1@0,o2@0"]).min()
    assert 0 < np.abs(sp["o1@0,o1@0"]).max() < 0.1, np.abs(sp["o1@0,o1@0"]).max()
