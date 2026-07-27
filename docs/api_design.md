# API Design

## Meshing

::: gplugins.meshwell.get_meshwell_prisms

## Mode Solvers

### Mode solver tidy3d

::: gplugins.tidy3d.modes.Waveguide

::: gplugins.tidy3d.modes.WaveguideCoupler

::: gplugins.tidy3d.modes.sweep_n_eff

::: gplugins.tidy3d.modes.sweep_n_group

::: gplugins.tidy3d.modes.sweep_bend_mismatch

::: gplugins.tidy3d.modes.sweep_coupling_length

### Mode solver Femwell

::: gplugins.femwell.mode_solver.compute_cross_section_modes

### Mode solver EMode

::: gplugins.emode.EMode

::: gplugins.emode.get_emode_settings

::: gplugins.emode.get_shapes_from_layer_stack

### EME (Eigen Mode Expansion)

::: gplugins.meow.MEOW

## FDTD Simulation

### S-parameter utils

::: gplugins.common.utils.plot.plot_sparameters

::: gplugins.common.utils.plot.plot_imbalance2x2

::: gplugins.common.utils.plot.plot_loss2x2

### Common FDTD functions

::: gplugins.common.utils.get_effective_indices.get_effective_indices

### S-parameter conversion

::: gplugins.common.utils.convert_sparameters.pandas_to_float64

::: gplugins.common.utils.convert_sparameters.pandas_to_numpy

::: gplugins.common.utils.convert_sparameters.csv_to_npz

::: gplugins.common.utils.convert_sparameters.convert_directory_csv_to_npz

### FDTD tidy3d

::: gplugins.tidy3d.write_sparameters

::: gplugins.tidy3d.write_sparameters_grating_coupler

::: gplugins.tidy3d.write_sparameters_grating_coupler_batch

### FDTD lumerical

::: gplugins.lumerical.write_sparameters_lumerical

## Circuit Solver

### SAX

::: gplugins.sax.read.model_from_csv

::: gplugins.sax.read.model_from_component

::: gplugins.sax.plot_model

::: gplugins.sax.models

## Electrostatics

### Elmer

::: gplugins.elmer.run_capacitive_simulation_elmer

### Palace

::: gplugins.palace.run_capacitive_simulation_palace

## Full-wave RF

### Palace

::: gplugins.palace.run_scattering_simulation_palace
