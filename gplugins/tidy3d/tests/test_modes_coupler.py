from __future__ import annotations

import numpy as np

import gplugins.tidy3d as gt

nm = 1e-3


def test_neff() -> None:
    wg = gt.modes.WaveguideCoupler(
        wavelength=1.55,
        core_width=(500 * nm, 500 * nm),
        gap=200 * nm,
        core_thickness=220 * nm,
        slab_thickness=100 * nm,
        core_material="si",
        clad_material="sio2",
    )
    n_eff = wg.n_eff[0].real
    n_eff_ref = 2.5743837634515767
    assert np.isclose(n_eff, n_eff_ref, rtol=0.01), n_eff


if __name__ == "__main__":
    test_neff()
