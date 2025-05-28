# Mode solvers

A mode solver computes the modes supported by a waveguide cross-section at a particular wavelength. Modes are definite-frequency eigenstates of Maxwell's equations.

You can use several mode solvers with GDSFactory:

**Open Source:**
- ``tidy3d``: Finite difference Frequency Domain (FDFD).
- ``MPB``: FDFD with periodic boundary conditions.
- ``Femwell``: Finite Element (FEM).
- ``meow``: The tidy3d mode solver is also used by the MEOW plugin to get the Sparameters of components via Eigenmode Expansion.

    **Notice**: The tidy3d FDTD solver is not open source as it runs on the cloud server, but the mode solver is open source and runs locally on your computer.

**Proprietary:**
- ``EMode``: A versatile waveguide mode solver using the Finite-Difference Frequency Domain (FDFD) method, and a propagation tool using the Eigenmode Expansion method (EME). Requires the EMode software suite to be installed separately. See [docs.emodephotonix.com/installation](https://docs.emodephotonix.com/installation) for installation instructions.

```{tableofcontents}
```
