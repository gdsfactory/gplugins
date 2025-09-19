"""FDTD Simulation module following COMSOL-style structure.

This module provides a modular approach to FDTD simulations with separate
components for geometry, materials, meshing, physics, solver, and results.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import tidy3d as td
from pydantic import BaseModel, ConfigDict, Field
from tidy3d.components.types import Symmetry

from gplugins.fdtd.geometry import Geometry




class Material(BaseModel):
    """Manages material assignments for simulation.

    Takes material mapping and applies it to geometry layers.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    mapping: dict[str, Any]  # Material name to medium mapping

    def get_medium(self, material_name: str) -> td.Medium:
        """Get the medium for a given material name."""
        if material_name not in self.mapping:
            raise ValueError(f"Material '{material_name}' not found in mapping")
        return self.mapping[material_name]


class Mesh(BaseModel):
    """Mesh settings for the simulation.

    Placeholder for future mesh configuration:
    - Grid resolution
    - Adaptive meshing
    - Refinement regions
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    # TODO: Implement mesh settings
    pass


class Physics(BaseModel):
    """Physics settings for the electromagnetic simulation.

    Handles:
    - Boundary conditions
    - Sources and monitors
    - Mode specifications
    - Symmetry planes
    """
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    boundary_spec: td.BoundarySpec = td.BoundarySpec.all_sides(boundary=td.PML())
    mode_spec: td.ModeSpec = td.ModeSpec(num_modes=1, filter_pol="te")
    symmetry: tuple[Symmetry, Symmetry, Symmetry] = (0, 0, 0)
    wavelength: float = 1.55
    bandwidth: float = 0.2
    num_freqs: int = 21


class Solver(BaseModel):
    """Solver settings for FDTD simulation.

    Placeholder for:
    - Time stepping
    - Convergence criteria
    - Solver-specific parameters
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_time: float = 1e-12
    shutoff: float = 1e-5

    # TODO: Add more solver settings
    pass


class Results(BaseModel):
    """Results processing and extraction.

    Placeholder for:
    - S-parameter extraction
    - Field monitors
    - Post-processing
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    # TODO: Implement results processing
    pass


class FDTDSimulation(BaseModel):
    """Main FDTD simulation class following COMSOL-style structure.

    Coordinates all simulation components:
    - Geometry: 3D structure definition
    - Material: Material properties
    - Mesh: Grid generation
    - Physics: EM physics settings
    - Solver: FDTD solver configuration
    - Results: Output processing

    Example 1 (traditional):
        # Create components
        geometry = Geometry(component=gf_component, layer_stack=stack, material_mapping=mats)
        material = Material(mapping={"si": td.Medium(...), "sio2": td.Medium(...)})
        physics = Physics(wavelength=1.55, bandwidth=0.2)

        # Create simulation
        sim = FDTDSimulation(
            geometry=geometry,
            material=material,
            physics=physics,
        )

    Example 2 (hybrid properties/methods API):
        # Create simulation first
        sim = FDTDSimulation()

        # Then set properties
        sim.geometry.component = gf_component
        sim.geometry.layer_stack = stack
        sim.material.mapping = {"si": td.Medium(...), "sio2": td.Medium(...)}
        sim.physics.wavelength = 1.55
    """
    model_config = ConfigDict(frozen=False, extra="forbid", arbitrary_types_allowed=True)

    geometry: Geometry | None = None
    material: Material | None = None
    mesh: Mesh | None = None
    physics: Physics | None = None
    solver: Solver | None = None
    results: Results | None = None

    def get_simulation(self) -> td.Simulation:
        """Build and return the Tidy3D simulation object.

        Returns:
            td.Simulation object ready to run
        """
        if self.geometry is None:
            raise ValueError("Geometry must be set before creating simulation")

        # Use defaults if components aren't set
        physics = self.physics or Physics()
        solver = self.solver or Solver()

        # Use the geometry's method to get simulation
        # This maintains compatibility with existing code
        center_z = float(np.mean([c[2] for c in self.geometry.port_centers]))
        sim_size_z = 4  # Default value as int

        return self.geometry.get_simulation(
            grid_spec=td.GridSpec.auto(
                wavelength=physics.wavelength,
                min_steps_per_wvl=30,
            ),
            center_z=center_z,
            sim_size_z=sim_size_z,
            boundary_spec=physics.boundary_spec,
            run_time=solver.run_time,
            shutoff=solver.shutoff,
            symmetry=physics.symmetry,
        )

    def run(self) -> dict:
        """Run the simulation and return results.

        Returns:
            Dictionary of S-parameters
        """
        # TODO: Implement full simulation run
        # For now, this is a placeholder
        raise NotImplementedError("Full simulation run not yet implemented")
