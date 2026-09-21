"""Test the grating-coupler fibre simulation geometry."""

from __future__ import annotations

import meep as mp
import numpy as np
import pytest

from gplugins.gmeep.get_simulation_grating_fiber import get_simulation_grating_fiber

RESOLUTION = 15


def _core_centre_on_port_line(sim, region, n_core: float) -> float:
    """Where the fibre core actually is, measured from the simulation's own
    epsilon along the fibre port line.

    Independent of every port variable: it only looks at the dielectric that
    was built, so it cannot agree with a mis-placed port by construction.
    """
    y = region.center.y
    xs = np.linspace(
        region.center.x - region.size.x / 2,
        region.center.x + region.size.x / 2,
        2001,
    )
    eps = np.array([sim.get_epsilon_point(mp.Vector3(x, y)) for x in xs])
    in_core = np.abs(eps - n_core**2) < 1e-4
    assert in_core.any(), "fibre core not found on the port line"
    xs_core = xs[in_core]
    return 0.5 * (xs_core.min() + xs_core.max())


@pytest.mark.parametrize("fiber_angle_deg", [10.0, 20.0])
def test_fiber_port_sits_on_the_fiber_axis(fiber_angle_deg: float) -> None:
    """The fibre port must be centred on the fibre, at any fibre angle.

    The fibre core block is built centred on x=0 and rotated by fiber_angle,
    so its axis crosses height y at x = y * tan(fiber_angle). A port whose x
    is computed from a different height than the one it is placed at drifts
    off the fibre by y_error * tan(fiber_angle), which grows with the angle
    and silently spoils the mode overlap.

    Tolerance: the monitor is deliberately offset 0.2 um in y from the port
    plane, which displaces it along the tilted axis by 0.2 * tan(angle); the
    core edges are also resolved only to one pixel. The bound is that
    geometric offset plus two pixels.
    """
    fiber_numerical_aperture = 0.14
    fiber_clad_material = 1.44
    n_core = float(np.sqrt(fiber_numerical_aperture**2 + fiber_clad_material**2))

    sim_dict = get_simulation_grating_fiber(
        period=0.66,
        fill_factor=0.5,
        n_periods=8,
        resolution=RESOLUTION,
        wavelength_start=1.5,
        wavelength_stop=1.6,
        wavelength_points=3,
        fiber_angle_deg=fiber_angle_deg,
        fiber_numerical_aperture=fiber_numerical_aperture,
        fiber_clad_material=fiber_clad_material,
        xmargin=25.0,
        fiber_port_x_size=36.4,
    )
    sim = sim_dict["sim"]
    sim.init_sim()

    region = sim_dict["fiber_monitor"].regions[0]
    core_centre = _core_centre_on_port_line(sim, region, n_core)

    tan_angle = np.tan(np.radians(fiber_angle_deg))
    tolerance = 0.2 * tan_angle + 2 / RESOLUTION

    assert abs(region.center.x - core_centre) < tolerance, (
        f"fibre port centred at x={region.center.x:.4f} um but the fibre core "
        f"on that line is centred at x={core_centre:.4f} um "
        f"(off by {region.center.x - core_centre:+.4f} um, "
        f"tolerance {tolerance:.4f} um)"
    )
