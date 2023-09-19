from __future__ import annotations

try:
    import meep as mp
except ModuleNotFoundError as e:
    print("You need to 'conda install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y'")
    raise e

from gdsfactory.config import logger

from gplugins.common.utils import plot, port_symmetries
from gplugins.common.utils.get_sparameters_path import get_sparameters_data_meep
from gplugins.gmeep.get_simulation import get_simulation
from gplugins.gmeep.meep_adjoint_optimization import (
    get_meep_adjoint_optimizer,
    run_meep_adjoint_optimizer,
)
from gplugins.gmeep.write_sparameters_grating import (
    write_sparameters_grating,
    write_sparameters_grating_batch,
    write_sparameters_grating_mpi,
)
from gplugins.gmeep.write_sparameters_meep import (
    write_sparameters_meep,
    write_sparameters_meep_1x1,
    write_sparameters_meep_1x1_bend90,
)
from gplugins.gmeep.write_sparameters_meep_batch import (
    write_sparameters_meep_batch,
    write_sparameters_meep_batch_1x1,
    write_sparameters_meep_batch_1x1_bend90,
)
from gplugins.gmeep.write_sparameters_meep_mpi import (
    write_sparameters_meep_mpi,
    write_sparameters_meep_mpi_1x1,
    write_sparameters_meep_mpi_1x1_bend90,
)

logger.info(f"Meep {mp.__version__!r} installed at {mp.__path__!r}")

__all__ = [
    "get_meep_adjoint_optimizer",
    "get_simulation",
    "get_sparameters_data_meep",
    "run_meep_adjoint_optimizer",
    "write_sparameters_meep",
    "write_sparameters_meep_1x1",
    "write_sparameters_meep_1x1_bend90",
    "write_sparameters_meep_mpi",
    "write_sparameters_meep_mpi_1x1",
    "write_sparameters_meep_mpi_1x1_bend90",
    "write_sparameters_meep_batch",
    "write_sparameters_meep_batch_1x1",
    "write_sparameters_meep_batch_1x1_bend90",
    "write_sparameters_grating",
    "write_sparameters_grating_mpi",
    "write_sparameters_grating_batch",
    "plot",
    "port_symmetries",
]
__version__ = "0.0.3"
