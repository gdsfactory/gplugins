# gplugins 0.8.5

[![docs](https://github.com/gdsfactory/gplugins/actions/workflows/pages.yml/badge.svg)](https://gdsfactory.github.io/gplugins/)
[![PyPI](https://img.shields.io/pypi/v/gplugins)](https://pypi.org/project/gplugins/)
[![PyPI Python](https://img.shields.io/pypi/pyversions/gplugins.svg)](https://pypi.python.org/pypi/gplugins)
[![MIT](https://img.shields.io/github/license/gdsfactory/gplugins)](https://choosealicense.com/licenses/mit/)
[![codecov](https://img.shields.io/codecov/c/github/gdsfactory/gplugins)](https://codecov.io/gh/gdsfactory/gdsfactory/tree/main/gplugins)

gdsfactory plugins:

- `database` for simulation and measurement database and dagster for data pipelines.
- `devsim` TCAD device simulator.
- `meow` Eigen Mode Expansion (EME).
- `femwell` Finite Element Method Solver (heaters, modes, TCAD, RF waveguides).
- `gmsh` mesh structures.
- `tidy3d` Finite Difference Time Domain (FDTD) simulations on the cloud using GPU.
- `lumerical` For Ansys FDTD and Circuit interconnect.
- `klayout` for fill, dataprep and testing.
- `ray` for distributed computing and optimization.
- `sax` S-parameter circuit solver.
- `schematic`: for bokeh schematic editor and `path_length_analysis`.
- `meep` for FDTD.
- `mpb` for MPB mode solver.
- `elmer` for electrostatic (capacitive) simulations.
- `palace` for full-wave driven (S parameter) and electrostatic (capacitive) simulations.
- `web` for gdsfactory webapp.
- `vlsir` for parsing GDS-extracted circuit netlists into Spice, Spectre and Xyce Schematic File formats.

## Installation

You can install most plugins with:

```
pip install "gplugins[database,devsim,femwell,gmsh,schematic,meow,meshwell,ray,sax,tidy3d]" --upgrade
```

Or install only the plugins you need with for example `pip install gplugins[schematic,femwell,meow,sax,tidy3d]` from the available plugins.

### Non-pip plugins

The following plugins require special installation without pip:

- For Meep and MPB you need to use `conda` or `mamba` on MacOS, Linux or [Windows WSL (Windows Subsystem for Linux)](https://learn.microsoft.com/en-us/windows/wsl/install) with `conda install pymeep=*=mpi_mpich_* -c conda-forge -y`
- For Elmer, refer to [Elmer FEM – Installation](https://www.elmerfem.org/blog/binaries/) for installation or compilation instructions each platform. Gplugins assumes `ElmerSolver`, `ElmerSolver_mpi`, and `ElmerGrid` are available in your PATH environment variable.
- For Palace, refer to [Palace – Installation](https://awslabs.github.io/palace/stable/install/) for compilation instructions using Spack or Singularity. Gplugins assumes `palace` is available in your PATH environment variable.


## Getting started

- [Read docs](https://gdsfactory.github.io/gplugins/)
- [Read gdsfactory docs](https://gdsfactory.github.io/gdsfactory/)
- [![Join the chat at https://gitter.im/gdsfactory-dev/community](https://badges.gitter.im/gdsfactory-dev/community.svg)](https://gitter.im/gdsfactory-dev/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
