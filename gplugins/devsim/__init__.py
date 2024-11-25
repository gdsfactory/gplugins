from __future__ import annotations

import devsim as tcad
from gdsfactory import logger

from gplugins.devsim.get_simulation_xsection import (
    PINWaveguide,
    alpha_to_k,
    clear_devsim_cache,
    dalpha_carriers,
    dn_carriers,
    k_to_alpha,
)
from gplugins.devsim.get_solver import DDComponent

logger.info(f"DEVSIM {tcad.__version__!r} installed at {tcad.__path__!r}")

__all__ = [
    "DDComponent",
    "PINWaveguide",
    "alpha_to_k",
    "clear_devsim_cache",
    "dalpha_carriers",
    "dn_carriers",
    "k_to_alpha",
]
__version__ = "0.0.1"
