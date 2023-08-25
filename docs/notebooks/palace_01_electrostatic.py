# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.0
#   kernelspec:
#     display_name: base
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Electrostatic simulations with Palace
# Here, we show how Palace may be used to perform electrostatic simulations. For a given geometry, one needs to specify the terminals where to apply potential, similar to {doc}`./elmer_01_electrostatic.py`.
# This effectively solves the mutual capacitance matrix for the terminals and the capacitance to ground.
# For details on the physics, see {cite:p}`smolic_capacitance_2021`.
#
# ## Installation
# See [Palace – Installation](https://awslabs.github.io/palace/stable/install/) for installation or compilation instructions. Gplugins assumes `palace` is available in your PATH environment variable.
#
# Alternatively, [Singularity / Apptainer](https://apptainer.org/) containers may be used. Instructions for building and an example definition file are found at [Palace – Build using Singularity/Apptainer](https://awslabs.github.io/palace/dev/install/#Build-using-Singularity/Apptainer).
# Afterwards, an easy install method is to add a script to `~/.local/bin` (or elsewhere in `PATH`) calling the Singularity container. For example, one may create a `palace` file containing
# ```console
# #!/bin/bash
# singularity exec ~/palace.sif /opt/palace/bin/palace "$@"
# ```
#
# ## Geometry, layer config and materials

# %% tags=["hide-input"]

import os
from math import inf
from pathlib import Path

import gdsfactory as gf
import pyvista as pv
from gdsfactory.components.interdigital_capacitor_enclosed import (
    interdigital_capacitor_enclosed,
)
from gdsfactory.generic_tech import LAYER, get_generic_pdk
from gdsfactory.technology import LayerStack
from gdsfactory.technology.layer_stack import LayerLevel
from IPython.display import display

from gplugins.palace import run_capacitive_simulation_palace
from gplugins.typings import RFMaterialSpec

gf.config.rich_output()
PDK = get_generic_pdk()
PDK.activate()

# %% [markdown]
# We employ an example LayerStack used in superconducting circuits similar to {cite:p}`marxer_long-distance_2023`.

# %%
layer_stack = LayerStack(
    layers=dict(
        substrate=LayerLevel(
            layer=LAYER.WAFER,
            thickness=500,
            zmin=0,
            material="Si",
            mesh_order=99,
        ),
        bw=LayerLevel(
            layer=LAYER.WG,
            thickness=200e-3,
            zmin=500,
            material="Nb",
            mesh_order=2,
        ),
    )
)
material_spec: RFMaterialSpec = {
    "Si": {"relative_permittivity": 11.45},
    "Nb": {"relative_permittivity": inf},
    "vacuum": {"relative_permittivity": 1},
}

# %%
simulation_box = [[-200, -200], [200, 200]]
c = gf.Component("capacitance_palace")
cap = c << interdigital_capacitor_enclosed(
    metal_layer=LAYER.WG, gap_layer=LAYER.DEEPTRENCH, enclosure_box=simulation_box
)
c.add_ports(cap.ports)
substrate = gf.components.bbox(bbox=simulation_box, layer=LAYER.WAFER)
c << substrate
c.flatten()

# %% [markdown]
# ## Running the simulation
# ```{eval-rst}
# We use the function :func:`~run_capacitive_simulation_palace`. This runs the simulation and returns an instance of :class:`~ElectrostaticResults` containing the capacitance matrix and a path to the mesh and the field solutions.
# ```

# %%
help(run_capacitive_simulation_palace)

# %% [markdown]
# ```{eval-rst}
# .. note::
#    The meshing parameters and element order shown here are very lax. As such, the computed capacitances are not very accurate.
# ```

# %%
results = run_capacitive_simulation_palace(
    c,
    layer_stack=layer_stack,
    material_spec=material_spec,
    n_processes=1,
    element_order=1,
    simulation_folder=Path(os.getcwd()) / "temporary",
    mesh_parameters=dict(
        background_tag="vacuum",
        background_padding=(0,) * 5 + (700,),
        portnames=c.ports,
        default_characteristic_length=200,
        layer_portname_delimiter=(delimiter := "__"),
        resolutions={
            "bw": {
                "resolution": 15,
            },
            "substrate": {
                "resolution": 40,
            },
            "vacuum": {
                "resolution": 40,
            },
            **{
                f"bw{delimiter}{port}": {
                    "resolution": 20,
                    "DistMax": 30,
                    "DistMin": 10,
                    "SizeMax": 14,
                    "SizeMin": 3,
                }
                for port in c.ports
            },
        },
    ),
)
display(results)

# %%
if results.field_file_location:
    pv.start_xvfb()
    pv.set_jupyter_backend("panel")
    field = pv.read(results.field_file_location)
    slice = field.slice_orthogonal(z=layer_stack.layers["bw"].zmin * 1e-6)

    p = pv.Plotter()
    p.add_mesh(slice, scalars="E", cmap="turbo")
    p.show_grid()
    p.camera_position = "xy"
    p.enable_parallel_projection()
    p.show()


# %% [markdown]
# ## Bibliography
#
# ```{bibliography}
# :style: unsrt
# :filter: docname in docnames
# ```
