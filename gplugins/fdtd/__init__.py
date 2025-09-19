from gplugins.fdtd import materials, modes
from gplugins.fdtd.geometry import (
    material_name_to_medium,
    write_sparameters,
)
from gplugins.fdtd.simulation import (
    FDTDSimulation,
    Material,
    Mesh,
    Physics,
    Results,
    Solver,
)

# Import Geometry from geometry module
from gplugins.fdtd.geometry import Geometry

__all__ = [
    # New modular API
    "FDTDSimulation",
    "Geometry",
    "Material",
    "Mesh",
    "Physics",
    "Solver",
    "Results",
    # Legacy functions
    "material_name_to_medium",
    "materials",
    "modes",
    "write_sparameters",
]
