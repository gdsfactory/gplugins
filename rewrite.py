#!/usr/bin/env python

import gdsfactory as gf
import matplotlib.pyplot as plt
import tidy3d as td
from gdsfactory.generic_tech import LAYER_STACK

from gplugins.tidy3d.component import Tidy3DComponent
from gplugins.tidy3d.util import get_mode_solvers

device = gf.components.coupler_ring()

# define a mapping of pdk material names to tidy3d medium objects
mapping = {
    "si": td.Medium(name="Si", permittivity=3.47**2),
    "sio2": td.Medium(name="SiO2", permittivity=1.47**2),
}

# setup the tidy3d component
c = Tidy3DComponent(
    component=device,
    layer_stack=LAYER_STACK,
    material_mapping=mapping,
    pad_xy_inner=2.0,
    pad_xy_outer=2.0,
    pad_z_inner=0,
    pad_z_outer=0,
    extend_ports=2.0,
)

# plot the component and the layerstack
fig = plt.figure(constrained_layout=True)
gs = fig.add_gridspec(ncols=2, nrows=3, width_ratios=(3, 1))
ax0 = fig.add_subplot(gs[0, 0])
ax1 = fig.add_subplot(gs[1, 0])
ax2 = fig.add_subplot(gs[2, 0])
axl = fig.add_subplot(gs[1, 1])
c.plot_slice(x="core", ax=ax0)
c.plot_slice(y="core", ax=ax1)
c.plot_slice(z="core", ax=ax2)
axl.legend(*ax0.get_legend_handles_labels(), loc="center")
axl.axis("off")
plt.show()


# initialize the tidy3d ComponentModeler
modeler = c.get_component_modeler(center_z="core", port_size_mult=(6, 4), sim_size_z=3)

# we can plot the tidy3d simulation setup
fig, ax = plt.subplots(2, 1)
modeler.plot_sim(z=c.get_layer_center("core")[2], ax=ax[0])
modeler.plot_sim(x=c.ports[0].center[0], ax=ax[1])
fig.tight_layout()
plt.show()

# we can solve for the modes of the different ports
mode_solver = list(get_mode_solvers(modeler, "o1").values())[0]
mode_data = mode_solver.solve()

# and visualize them, this is taken directly from https://docs.flexcompute.com/projects/tidy3d/en/latest/notebooks/ModeSolver.html#Visualizing-Mode-Data
fig, ax = plt.subplots(1, 3, tight_layout=True, figsize=(10, 3))
abs(mode_data.Ex.isel(mode_index=0, f=0)).plot(x="y", y="z", ax=ax[0], cmap="magma")
abs(mode_data.Ey.isel(mode_index=0, f=0)).plot(x="y", y="z", ax=ax[1], cmap="magma")
abs(mode_data.Ez.isel(mode_index=0, f=0)).plot(x="y", y="z", ax=ax[2], cmap="magma")
ax[0].set_title("|Ex(x, y)|")
ax[1].set_title("|Ey(x, y)|")
ax[2].set_title("|Ez(x, y)|")
plt.setp(ax, aspect="equal")
plt.show()

# from here you can follow https://docs.flexcompute.com/projects/tidy3d/en/latest/notebooks/SMatrix.html?highlight=smatrix#Solving-for-the-S-matrix
# smatrix = modeler.run()
