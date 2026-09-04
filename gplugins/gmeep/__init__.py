from __future__ import annotations

# Every submodule under gplugins/gmeep/ (write_sparameters_meep.py,
# write_sparameters_grating.py, ...) is re-exported here under the same
# name as the one function it defines. That means
# `import gplugins.gmeep.write_sparameters_meep as x` can bind `x` to the
# FUNCTION below, not the module - the function is what this __init__
# puts into gplugins.gmeep's own namespace, and a plain dotted import
# resolves the already-imported name first. If you need the module object
# itself (e.g. to monkeypatch or inspect it), index sys.modules directly:
#
#     import sys
#     mod = sys.modules["gplugins.gmeep.write_sparameters_meep"]

try:
    import meep as mp
except ModuleNotFoundError as e:
    print("You need to 'conda install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y'")
    raise e

from gdsfactory import logger

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
    "plot",
    "port_symmetries",
    "run_meep_adjoint_optimizer",
    "write_sparameters_grating",
    "write_sparameters_grating_batch",
    "write_sparameters_grating_mpi",
    "write_sparameters_meep",
    "write_sparameters_meep_1x1",
    "write_sparameters_meep_1x1_bend90",
    "write_sparameters_meep_batch",
    "write_sparameters_meep_batch_1x1",
    "write_sparameters_meep_batch_1x1_bend90",
    "write_sparameters_meep_mpi",
    "write_sparameters_meep_mpi_1x1",
    "write_sparameters_meep_mpi_1x1_bend90",
]
__version__ = "0.0.3"
