"""gdsfactory tidy3d plugin.

[tidy3D is a fast GPU based commercial FDTD
solver](https://simulation.cloud/)

"""


try:
    import tidy3d as td
except ModuleNotFoundError as e:
    print("You need to 'pip install tidy3d'")
    raise e

from gdsfactory.config import logger

from gplugins.gtidy3d import materials, modes, utils
from gplugins.gtidy3d.get_results import get_results
from gplugins.gtidy3d.get_simulation import (
    get_simulation,
    plot_simulation,
    plot_simulation_xz,
    plot_simulation_yz,
)
from gplugins.gtidy3d.get_simulation_grating_coupler import (
    get_simulation_grating_coupler,
)
from gplugins.gtidy3d.write_sparameters import (
    write_sparameters,
    write_sparameters_1x1,
    write_sparameters_batch,
    write_sparameters_batch_1x1,
    write_sparameters_crossing,
)
from gplugins.gtidy3d.write_sparameters_grating_coupler import (
    write_sparameters_grating_coupler,
    write_sparameters_grating_coupler_batch,
)

__version__ = "0.0.3"
__all__ = [
    "plot_simulation",
    "plot_simulation_xz",
    "plot_simulation_yz",
    "get_simulation",
    "get_simulation_grating_coupler",
    "get_results",
    "materials",
    "modes",
    "utils",
    "write_sparameters",
    "write_sparameters_crossing",
    "write_sparameters_1x1",
    "write_sparameters_batch",
    "write_sparameters_batch_1x1",
    "write_sparameters_grating_coupler",
    "write_sparameters_grating_coupler_batch",
]

logger.info(f"Tidy3d {td.__version__!r} installed at {td.__path__!r}")
