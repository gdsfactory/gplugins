from __future__ import annotations

from gplugins.modes import coupler, waveguide
from gplugins.modes.find_coupling_vs_gap import (
    find_coupling_vs_gap,
    plot_coupling_vs_gap,
)
from gplugins.modes.find_mode_dispersion import find_mode_dispersion
from gplugins.modes.find_modes import (
    find_modes_coupler,
    find_modes_waveguide,
)
from gplugins.modes.find_neff_ng_dw_dh import (
    find_neff_ng_dw_dh,
    plot_neff_ng_dw_dh,
)
from gplugins.modes.find_neff_vs_width import (
    find_neff_vs_width,
    plot_neff_vs_width,
)

__all__ = [
    "find_modes_waveguide",
    "find_modes_coupler",
    "find_neff_vs_width",
    "find_mode_dispersion",
    "find_coupling_vs_gap",
    "find_neff_ng_dw_dh",
    "plot_neff_ng_dw_dh",
    "plot_neff_vs_width",
    "plot_coupling_vs_gap",
    "coupler",
    "waveguide",
]
__version__ = "0.0.2"
