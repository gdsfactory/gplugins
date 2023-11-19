# Deprecated
from gplugins.tidy3d import materials, modes
from gplugins.tidy3d.component import (
    Tidy3DComponent,
    material_name_to_medium,
)
from gplugins.tidy3d.get_simulation import (
    get_simulation,
    plot_simulation,
    plot_simulation_xz,
    plot_simulation_yz,
)
from gplugins.tidy3d.get_simulation_grating_coupler import (
    get_simulation_grating_coupler,
)
from gplugins.tidy3d.types import (
    Tidy3DElementMapping,
    Tidy3DMedium,
    validate_medium,
)
from gplugins.tidy3d.util import (
    get_mode_solvers,
    get_port_normal,
    sort_layers,
)
from gplugins.tidy3d.write_sparameters import (
    write_sparameters,
    write_sparameters_1x1,
    write_sparameters_batch,
    write_sparameters_batch_1x1,
)
from gplugins.tidy3d.write_sparameters_grating_coupler import (
    write_sparameters_grating_coupler,
    write_sparameters_grating_coupler_batch,
)

__all__ = [
    "Tidy3DComponent",
    "Tidy3DElementMapping",
    "Tidy3DMedium",
    "get_mode_solvers",
    "get_port_normal",
    "material_name_to_medium",
    "sort_layers",
    "validate_medium",
    "modes",
    "materials",
    "get_simulation",
    "plot_simulation",
    "plot_simulation_xz",
    "plot_simulation_yz",
    "get_simulation_grating_coupler",
    "write_sparameters",
    "write_sparameters_1x1",
    "write_sparameters_batch",
    "write_sparameters_batch_1x1",
    "write_sparameters_grating_coupler",
    "write_sparameters_grating_coupler_batch",
]
