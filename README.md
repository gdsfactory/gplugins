# gplugins 0.0.2 gdsfactory plugins

* [Optimization](https://gdsfactory.github.io/gplugins/plugins_optimization.html)
  - [Ray Tune Generic Black-Box Optimiser](https://gdsfactory.github.io/gplugins/notebooks/ray/optimiser.html)

* [Meshing](https://gdsfactory.github.io/gplugins/notebooks/devsim/01_pin_waveguide.html#Meshing)

* [Device Simulators](https://gdsfactory.github.io/gplugins/plugins_process.html)
  - [Thermal Simulation](https://gdsfactory.github.io/gplugins/notebooks/thermal/thermal.html)
  - [DEVSIM TCAD Simulation](https://gdsfactory.github.io/gplugins/notebooks/devsim/01_pin_waveguide.html)
  - [Analytical Process Simulation](https://gdsfactory.github.io/gplugins/notebooks/tcad/02_analytical_process.html)
  - [Montecarlo Implant Simulation](https://gdsfactory.github.io/gplugins/notebooks/tcad/03_numerical_implantation.html)

* [Mode Solvers & Eigenmode Expansion (EME)](https://gdsfactory.github.io/gplugins/plugins_mode_solver.html)
  - Finite Element Mode Solvers
    - [Femwell](https://gdsfactory.github.io/gplugins/notebooks/fem/01_mode_solving.html)
  - Finite Difference Mode Solvers
    - [tidy3d](https://gdsfactory.github.io/gplugins/notebooks/tidy3d/01_tidy3d_modes.html)
    - [MPB](https://gdsfactory.github.io/gplugins/notebooks/mpb/001_mpb_waveguide.html)
  - Eigenmode Expansion (EME)
    - [MEOW](https://gdsfactory.github.io/gplugins/notebooks/eme/01_meow.html)

* [Electromagnetic Wave Solvers using Finite Difference Time Domain (FDTD)](https://gdsfactory.github.io/gplugins/plugins_fdtd.html)
  - [tidy3d](https://gdsfactory.github.io/gplugins/notebooks/tidy3d/00_tidy3d.html)
  - [MEEP](https://gdsfactory.github.io/gplugins/notebooks/meep/001_meep_sparameters.html)
  - [Ansys Lumerical FDTD](https://gdsfactory.github.io/gplugins/notebooks/lumerical/1_fdtd_sparameters.html)

* [S-Parameter Circuit Solvers](https://gdsfactory.github.io/gplugins/plugins_circuits.html)
  - [SAX](https://gdsfactory.github.io/gplugins/notebooks/sax/sax.html)
  - [Ansys Lumerical INTERCONNECT](https://gdsfactory.github.io/gplugins/notebooks/lumerical/2_interconnect.html)

* [Database](https://gdsfactory.github.io/gplugins/notebooks/12_database.html)


## Installation

You can install all plugins with:

```
pip install "gplugins[database,devsim,femwell,gmsh,kfactory,meow,meshwell,ray,sax,tidy3d]" --upgrade
```

Or Install only the plugins you need `pip install gplugins[plugin1,plugin2]` from the available plugins:

- `database` for simulation and measurement database.
- `devsim` TCAD device simulator.
- `femwell` Finite Element Method Solver (heaters, modes, TCAD, RF waveguides).
- `gmsh` mesh structures.
- `kfactory` for fill, dataprep and testing.
- `meow` Eigen Mode Expansion (EME).
- `ray` for distributed computing and optimization.
- `sax` S-parameter circuit solver.
- `tidy3d` Finite Difference Time Domain (FDTD) simulations on the cloud using GPU.

To install open source FDTD Meep you need to use `conda` or `mamba` on MacOS or Linux, so for Windows you need to use the [WSL (Windows Subsystem for Linux)](https://learn.microsoft.com/en-us/windows/wsl/install).
- `conda install pymeep=*=mpi_mpich_* -c conda-forge -y`
