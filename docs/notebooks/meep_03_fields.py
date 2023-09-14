# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.1
#   kernelspec:
#     display_name: base
#     language: python
#     name: python3
# ---

# # Meep fields
#
# Using the gplugins/gmeep utilities, we can also extract the output fields of the simulations.
#
# This requires using a continuous source instead of the broad(er)band gaussian used in S-parameter extraction. Since we are working at a definite frequency, we can also leverage the [finite-difference frequency domain solver](https://meep.readthedocs.io/en/latest/Python_Tutorials/Frequency_Domain_Solver/).
#
# In the spatial domain, this reuses the geometry and eigenmode source definitions of the plugin.

# +
from __future__ import annotations

import gdsfactory as gf
import meep as mp

from gplugins.gmeep.get_simulation import get_simulation

# -

# ## Define a component

# +
c = gf.components.straight(length=10)

component = gf.add_padding_container(
    c,
    default=0,
    top=3.2,
    bottom=3.2,
)

component.plot_matplotlib()
# -

# ## Define a continuous source simulation

# +
import matplotlib.pyplot as plt

component = gf.add_padding_container(
    c,
    default=0,
    top=3.2,
    bottom=3.2,
)

sim_dict = get_simulation(
    component,
    is_3d=False,
    port_source_offset=-0.1,
    extend_ports_length=3,
    continuous_source=True,
    force_complex_fields=True,
)
sim = sim_dict["sim"]
sim.plot2D()
plt.show()
# -

# ## FDFD simulation

sim.init_sim()
sim.solve_cw(1e-6, 10000, 10)

sx = sim.cell_size.x
sy = sim.cell_size.y
dpml = sim.boundary_layers[0].thickness
nonpml_vol = mp.Volume(mp.Vector3(), size=mp.Vector3(sx - 2 * dpml, sy - 2 * dpml))
ez_dat = sim.get_array(vol=nonpml_vol, component=mp.Ez)

# +
import numpy as np

eps_data = sim.get_array(vol=nonpml_vol, component=mp.Dielectric)
ez_data = np.real(ez_dat)

plt.figure()
plt.imshow(eps_data.transpose(), interpolation="spline36", cmap="binary")
plt.imshow(ez_data.transpose(), interpolation="spline36", cmap="RdBu", alpha=0.9)
plt.axis("off")
plt.show()
# -

# ## Steady-state FDTD simulation
#
# We can also just run the time-domain simulation with the continuous source until the field is stabilized:

sim.run(until=400)

# +
eps_data = sim.get_epsilon()
ez_data = np.real(sim.get_efield_z())

import matplotlib.pyplot as plt

plt.figure()
sim.plot2D(
    fields=mp.Ez,
    plot_sources_flag=True,
    plot_monitors_flag=False,
    plot_boundaries_flag=True,
)
plt.axis("off")
plt.show()
