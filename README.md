# gplugins 2.0.1

[![docs](https://github.com/gdsfactory/gplugins/actions/workflows/pages.yml/badge.svg)](https://gdsfactory.github.io/gplugins/)
[![PyPI](https://img.shields.io/pypi/v/gplugins)](https://pypi.org/project/gplugins/)
[![PyPI Python](https://img.shields.io/pypi/pyversions/gplugins.svg)](https://pypi.python.org/pypi/gplugins)
[![MIT](https://img.shields.io/github/license/gdsfactory/gplugins)](https://choosealicense.com/licenses/mit/)
[![codecov](https://img.shields.io/codecov/c/github/gdsfactory/gplugins)](https://codecov.io/gh/gdsfactory/gdsfactory/tree/main/gplugins)

## GDSFactory plugins

Run simulations with GDSFactory by installing plugins.

- Device simulators
    - Meshing
    - FDTD
        - `Ansys Lumerical`
        - tidy3d
        - Luminescent
        - FDTDz
        - MEEP
    - FEM
        - `femwell` Finite Element Method Solver (heaters, modes, TCAD, RF waveguides).
        - `elmer` for electrostatic (capacitive) simulations.
        - `palace` for full-wave driven (S parameter) and electrostatic (capacitive) simulations.
    - EME
        - `meow` Eigen Mode Expansion (EME).
    - Mode Solver
        - Tidy3d
        - Femwell
        - MPB
    - TCAD
        - `devsim` TCAD device simulator.
- Circuit simulations
    - `sax` S-parameter circuit solver.
    - `vlsir` for parsing GDS-extracted circuit netlists into Cadence Spectre, NgSpice and Xyce Schematic File formats.


## Installation

You can install most plugins with:

```bash
pip install "gdsfactory[full]" --upgrade
```

Or list the plugins individually:

```bash
pip install "gplugins[devsim,femwell,gmsh,schematic,meow,meshwell,sax,tidy3d]" --upgrade
```

Or install only the plugins you need. For example:

```bash
pip install "gplugins[schematic,femwell,meow,sax,tidy3d]" --upgrade
```

### Non-pip plugins

The following plugins require special installation as they can't be installed with `pip`:

- For Meep and MPB you need to use `conda` or `mamba` on MacOS, Linux or [Windows WSL (Windows Subsystem for Linux)](https://learn.microsoft.com/en-us/windows/wsl/install) with `conda install pymeep=*=mpi_mpich_* -c conda-forge -y`
- For Elmer, refer to [Elmer FEM – Installation](https://www.elmerfem.org/blog/binaries/) for installation or compilation instructions each platform. Gplugins assumes `ElmerSolver`, `ElmerSolver_mpi`, and `ElmerGrid` are available in your PATH environment variable.
- For Palace, refer to [Palace – Installation](https://awslabs.github.io/palace/stable/install/) for compilation instructions using Spack or Singularity. Gplugins assumes `palace` is available in your PATH environment variable.

## Installation for contributors

We recommend `uv` for installing GDSfactory.
If you don't already have uv, install with the following command:

```bash
# On macOS and Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
# On Windows.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

-Then you can install GDSFactory with:

```bash
uv venv --python 3.12
uv sync --extra docs --extra dev
```

## Getting started

- [Read the gplugins docs](https://gdsfactory.github.io/gplugins/)
- [Read the GDSFactory docs](https://gdsfactory.github.io/gdsfactory/)
- [Read the GDSFactory+ docs](https://gdsfactory.com/plus/))
- [Join the discussion at GDSFactory Community Slack](https://join.slack.com/t/gdsfactory-community/shared_invite/zt-3aoygv7cg-r5BH6yvL4YlHfY8~UXp0Wg)
