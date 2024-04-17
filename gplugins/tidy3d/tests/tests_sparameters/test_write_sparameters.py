from __future__ import annotations

import gdsfactory as gf
import numpy as np
import pytest

import gplugins.tidy3d as gt


@pytest.mark.parametrize("overwrite", [True, False])
def test_write_sparameters_straight_2d(overwrite=True) -> None:
    """Checks Sparameters for a straight waveguide in 2D."""
    c = gf.components.straight(length=2)
    sp = gt.write_sparameters(c, sim_size_z=0, center_z="core", overwrite=overwrite)

    np.testing.assert_allclose(np.abs(sp["o1@0,o2@0"]), 1, atol=1e-2)
    np.testing.assert_allclose(np.abs(sp["o1@0,o1@0"]), 0, atol=1e-2)


if __name__ == "__main__":
    overwrite = False
    c = gf.components.straight(length=3)
    sp = gt.write_sparameters(c, sim_size_z=0, center_z="core")

    # Check reasonable reflection/transmission
    assert 1 > np.abs(sp["o1@0,o2@0"]).min() > 0.6, np.abs(sp["o1@0,o2@0"]).min()
    assert 0 < np.abs(sp["o1@0,o1@0"]).max() < 0.1, np.abs(sp["o1@0,o1@0"]).max()
