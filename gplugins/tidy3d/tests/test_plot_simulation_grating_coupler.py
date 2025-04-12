from __future__ import annotations

import gdsfactory as gf

import gplugins.tidy3d as gt
from gplugins.common.config import PATH

fiber_port_name = "o2"


if __name__ == "__main__":
    c = gf.components.grating_coupler_elliptical_arbitrary(
        widths=(0.343,) * 25, gaps=(0.345,) * 25
    )
    gt.write_sparameters_grating_coupler(
        component=c,
        is_3d=False,
        fiber_angle_deg=20,
        fiber_xoffset=0,
        dirpath=PATH.sparameters_repo,
        run=False,
    )
