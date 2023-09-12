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
# # Full-wave driven simulations with Palace
#
# ```{warning}
# The full-wave driven plugin for Palace is experimental and currently supports only lumped ports that have to be placed manually as rectangles in the geometry.
# ```
#
# Here, we show how Palace may be used to perform full-wave driven simulations in the frequency domain.
# See [Palace – Crosstalk Between Coplanar Waveguides](https://awslabs.github.io/palace/stable/examples/cpw/) for more details.
#
# For a given geometry, one needs to specify the terminals where to apply an excitation similar to Ansys HFSS.
# To this end, lumped ports (or wave ports) have to be added to the geometry to simulate.
# This effectively solves the scattering parameters for the terminals.
#
# In this notebook, we the same interdigital capacitor as in {doc}`palace_01_electrostatic.py` but add lumped ports to the geometry.
# Afterwards, the capacitance matrix can be computed from the scattering parameters as described in {eq}`s_to_y_to_c`.
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

# %%

import os
from math import inf
from pathlib import Path

import gdsfactory as gf
import numpy as np
import pyvista as pv
import skrf
from gdsfactory.components.interdigital_capacitor_enclosed import (
    interdigital_capacitor_enclosed,
)
from gdsfactory.generic_tech import LAYER, get_generic_pdk
from gdsfactory.technology import LayerStack
from gdsfactory.technology.layer_stack import LayerLevel
from IPython.display import display
from matplotlib import pyplot as plt

from gplugins.palace import run_scattering_simulation_palace
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
        bw_port=LayerLevel(
            layer=LAYER.PORT,
            thickness=200e-3,
            zmin=500,
            material="Nb",
            mesh_order=2,
        ),
    )
)
material_spec: RFMaterialSpec = {
    "Si": {"relative_permittivity": 11.45, "relative_permeability": 1},
    "Nb": {"relative_permittivity": inf, "relative_permeability": 1},
    "vacuum": {"relative_permittivity": 1, "relative_permeability": 1},
}

# %%
simulation_box = [[-200, -200], [200, 200]]
c = gf.Component("scattering_palace")
cap = c << interdigital_capacitor_enclosed(
    metal_layer=LAYER.WG, gap_layer=LAYER.DEEPTRENCH, enclosure_box=simulation_box
)
c.show()

# %%

# Add lumped port rectangles manually, see examples for https://awslabs.github.io/palace/stable/examples/cpw/
lumped_port_1_1 = gf.components.bbox(((-40, 11), (-46, 5)), layer=LAYER.PORT)
lumped_port_1_2 = gf.components.bbox(((-40, -11), (-46, -5)), layer=LAYER.PORT)
c << lumped_port_1_1
c << lumped_port_1_2
c.add_port("o1_1", lumped_port_1_1.center, layer=LAYER.PORT, width=1)
c.add_port("o1_2", lumped_port_1_2.center, layer=LAYER.PORT, width=1)

lumped_port_2_1 = gf.components.bbox(((40, 11), (46, 5)), layer=LAYER.PORT)
lumped_port_2_2 = gf.components.bbox(((40, -11), (46, -5)), layer=LAYER.PORT)
c << lumped_port_2_1
c << lumped_port_2_2
c.add_port("o2_1", lumped_port_2_1.center, layer=LAYER.PORT, width=1)
c.add_port("o2_2", lumped_port_2_2.center, layer=LAYER.PORT, width=1)

substrate = gf.components.bbox(bbox=simulation_box, layer=LAYER.WAFER)
c << substrate
c.flatten()
c.show()

# %% [markdown]
# ## Running the simulation
# ```{eval-rst}
# We use the function :func:`~run_scattering_simulation_palace`. This runs the simulation and returns an instance of :class:`~DrivenFullWaveResults` containing the capacitance matrix and a path to the mesh and the field solutions.
# ```

# %%
help(run_scattering_simulation_palace)

# %%
results = run_scattering_simulation_palace(
    c,
    layer_stack=layer_stack,
    material_spec=material_spec,
    only_one_port=True,
    simulation_folder=Path(os.getcwd()) / "temporary",
    driven_settings={
        "MinFreq": 0.1,
        "MaxFreq": 5,
        "FreqStep": 5,
    },
    mesh_parameters=dict(
        background_tag="vacuum",
        background_padding=(0,) * 5 + (700,),
        portnames=c.ports,
        verbosity=1,
        default_characteristic_length=200,
        layer_portname_delimiter=(delimiter := "__"),
        resolutions={
            "bw": {
                "resolution": 14,
            },
            "substrate": {
                "resolution": 50,
            },
            "vacuum": {
                "resolution": 120,
            },
            **{
                f"bw_port{delimiter}{port}_vacuum": {
                    "resolution": 8,
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


# %% [markdown]
#
# The capacitance matrix can be solved from the admittance matrix $Y$ as
#
# ```{math}
# :label: s_to_y_to_c
#     C_{\text{i,j}} = \frac{\mathrm{Im}\,Y_{\text{i,j}}}{\mathrm{i} \omega}
#     .
# ```

# %%
df = results.scattering_matrix
df.columns = df.columns.str.strip()
s_complex = 10 ** df["|S[2][1]| (dB)"].values * np.exp(
    1j * skrf.degree_2_radian(df["arg(S[2][1]) (deg.)"].values)
)
ntw = skrf.Network(f=df["f (GHz)"].values, s=s_complex, z0=50)
cap = np.imag(ntw.y.flatten()) / (ntw.f * 2 * np.pi)
display(cap)

plt.plot(ntw.f, cap * 1e15)
plt.xlabel("Freq (GHz)")
plt.ylabel("C (fF)")

# %% [markdown]
# <div class="alert alert-success">
# TODO the results don't seem good, something must be wrong in the setup…
# </div>

# %%
if results.field_file_locations:
    pv.start_xvfb()
    pv.set_jupyter_backend("panel")
    field = pv.read(results.field_file_locations[0])
    slice = field.slice_orthogonal(z=layer_stack.layers["bw"].zmin * 1e-6)

    p = pv.Plotter()
    p.add_mesh(slice, scalars="Ue", cmap="turbo")
    p.show_grid()
    p.camera_position = "xy"
    p.enable_parallel_projection()
    p.show()

# %% [markdown]
# ## Bibliography
# ```{bibliography}
# :style: unsrt
# ```
