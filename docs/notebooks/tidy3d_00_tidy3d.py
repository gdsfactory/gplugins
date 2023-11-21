# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: base
#     language: python
#     name: python3
# ---

# %% [markdown]
# # FDTD tidy3d
#
# [tidy3D](https://docs.flexcompute.com/projects/tidy3d/en/latest/) is a fast GPU based FDTD tool developed by flexcompute.
#
# To run, you need to [create an account](https://simulation.cloud/) and add credits. The number of credits that each simulation takes depends on the simulation size and computation time.
#
# ![cloud_model](https://i.imgur.com/5VTCPLR.png)
#
# ## Materials
#
# To use gdsfactory LayerStack for different PDKs into tidy3d you have to create a mapping between each material name from the LayerStack into a tidy3d Medim
#
# Tidy3d provides you with a material database that also includes dispersive materials.

# %%
import gdsfactory as gf
import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td

import gplugins as gp
import gplugins.tidy3d as gt
from gplugins import plot
from gplugins.common.config import PATH

# %%
gt.material_name_to_medium

# %%
nm = 1e-3
wavelength = np.linspace(1500, 1600) * nm
f = td.C_0 / wavelength
eps_complex = td.material_library["cSi"]["Li1993_293K"].eps_model(f)
n, k = td.Medium.eps_complex_to_nk(eps_complex)
plt.plot(wavelength, n)
plt.title("cSi crystalline silicon")
plt.xlabel("wavelength")
plt.ylabel("n")

# %%
eps_complex = td.material_library["Si3N4"]["Luke2015PMLStable"].eps_model(f)
n, k = td.Medium.eps_complex_to_nk(eps_complex)
plt.plot(wavelength, n)
plt.title("SiN")
plt.xlabel("wavelength")
plt.ylabel("n")

# %%
eps_complex = td.material_library["SiO2"]["Horiba"].eps_model(f)
n, k = td.Medium.eps_complex_to_nk(eps_complex)
plt.plot(wavelength, n)
plt.title("SiO2")
plt.xlabel("wavelength")
plt.ylabel("n")

# %% [markdown]
# ## Component Modeler
#
# You can easily convert a gdsfactory planar Component into a tidy3d simulation and make sure the simulation looks correct before running it

# %%
from gdsfactory.generic_tech import LAYER_STACK, get_generic_pdk

pdk = get_generic_pdk()
pdk.activate()

component = gf.components.coupler_ring()
component.plot()

# %%
# define a mapping of pdk material names to tidy3d medium objects
mapping = {
    "si": td.Medium(name="Si", permittivity=3.47**2),
    "sio2": td.Medium(name="SiO2", permittivity=1.47**2),
}

# setup the tidy3d component
c = gt.Tidy3DComponent(
    component=component,
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


# %%
LAYER_STACK.layers.pop("substrate", None)

# setup the tidy3d component
c = gt.Tidy3DComponent(
    component=component,
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

# %%
c.plot_slice(x="core")

# %%
# initialize the tidy3d ComponentModeler
modeler = c.get_component_modeler(
    center_z="core", port_size_mult=(6, 4), sim_size_z=3.0
)

# we can plot the tidy3d simulation setup
fig, ax = plt.subplots(2, 1)
modeler.plot_sim(z=c.get_layer_center("core")[2], ax=ax[0])
modeler.plot_sim(x=c.ports[0].center[0], ax=ax[1])
fig.tight_layout()
plt.show()

# %% [markdown]
# ## Write S-parameters
#
# The most useful function is `gt.write_sparameters` which allows you to:
#
# - leverage a file cache to avoid running the same simulation twice.
# - plot_simulation and modes before running
# - run in 2D or 3D
#
#
# ### file cache
#
# `write_sparameters` automatically will write your Sparameters in your home directory. By default uses a hidden folder in your home directory `dirpath=~/.gdsfactory/sparameters`.
# If simulation is found it will load it automatically, if not it will run it and write the Sparameters to `filepath`
# You can also specify a particular filepath to store simulations and load Sparameters from:

# %%
sp = gt.write_sparameters(
    component,
    filepath=PATH.sparameters_repo / "coupler_ring_2d.npz",
    sim_size_z=0,
    center_z="core",
)

# %%
gp.plot.plot_sparameters(sp)

# %% [markdown]
# ### Plot Simulations
#
# When setting up a simulation it's important to check if simulation and modes looks correct.

# %%
c = gf.components.taper_sc_nc()
c.plot()

# %%
sp = gt.write_sparameters(c, plot_simulation_layer_name="core", layer_stack=LAYER_STACK)

# %%
# lets plot the fundamental input mode
sp = gt.write_sparameters(
    c, plot_mode_port_name="o1", plot_mode_index=0, layer_stack=LAYER_STACK
)

# %%
# lets plot the second order input mode
mode_spec = td.ModeSpec(num_modes=2, filter_pol="te")
sp = gt.write_sparameters(
    c,
    plot_mode_port_name="o1",
    plot_mode_index=1,
    layer_stack=LAYER_STACK,
    mode_spec=mode_spec,
)

# %%
sp = gt.write_sparameters(
    c,
    plot_simulation_layer_name="nitride",
    plot_simulation_port_index=1,
    layer_stack=LAYER_STACK,
)

# %%
# lets plot the output mode
sp = gt.write_sparameters(
    c, plot_mode_port_name="o2", plot_mode_index=0, layer_stack=LAYER_STACK
)

# %% [markdown]
# ### 2D
#
# 2D simulations take less credits but are also less accurate than 3D.
# When running in 2D we don't consider the component thickness in the z dimension.
#
# For running simulations in 2D you need to set `sim_size_z = 0`.
#
# It is also important that you choose `center_z` correctly.

# %%
sp = gt.write_sparameters(
    component,
    filepath=PATH.sparameters_repo / "coupler_ring_2d.npz",
    sim_size_z=0,
    layer_stack=LAYER_STACK,
    plot_simulation_layer_name="core",
    center_z="core",
)

# %%
component = gf.components.straight()
sp = gt.write_sparameters(
    component,
    filepath=PATH.sparameters_repo / "straight_2d.npz",
    sim_size_z=0,
    center_z="core",
)

# %%
gp.plot.plot_sparameters(sp)

# %% [markdown]
# ### 3D
#
# By default all simulations run in 3D unless indicated otherwise.
# 3D simulations run quite fast thanks to the GPU solver on the server side hosted by tidy3d cloud.

# %%
c = gf.components.straight(length=2)
sp = gt.write_sparameters(
    c, filepath=PATH.sparameters_repo / "straight_3d.npz", sim_size_z=4
)
gp.plot.plot_sparameters(sp)

# %% [markdown]
# ## Erosion / dilation

# %%
component = gf.components.straight(length=0.1)
sp = gt.write_sparameters(
    component, layer_stack=LAYER_STACK, plot_simulation_layer_name="core", dilation=0
)


# %% [markdown]
# A `dilation = 0.5` makes a 0.5um waveguide 0.75um

# %%
0.5 * 0.8

# %%
component = gf.components.straight(length=0.1)
sp = gt.write_sparameters(
    component, layer_stack=LAYER_STACK, plot_simulation_layer_name="core", dilation=0.5
)

# %% [markdown]
# A `dilation = -0.2` makes a 0.5um eroded down to 0.1um

# %%
0.2 * 0.5

# %%
component = gf.components.straight(length=0.1)
sp = gt.write_sparameters(
    component, layer_stack=LAYER_STACK, plot_simulation_layer_name="core", dilation=-0.2
)

# %% [markdown]
# ## Plot monitors

# %%
component = gf.components.taper_strip_to_ridge(length=10)
component.plot()

# %%
sp = gt.write_sparameters(
    c,
    plot_simulation_layer_name="core",
    plot_simulation_port_index=0,
    layer_stack=LAYER_STACK,
)

# %%
sp = gt.write_sparameters(
    c,
    plot_simulation_layer_name="core",
    plot_simulation_port_index=1,
    layer_stack=LAYER_STACK,
)
sp = gt.write_sparameters(
    c,
    plot_simulation_layer_name="slab90",
    plot_simulation_port_index=1,
    layer_stack=LAYER_STACK,
)

# %%
components = [
    "bend_euler",
    "bend_s",
    "coupler",
    "coupler_ring",
    "crossing",
    "mmi1x2",
    "mmi2x2",
    "taper",
    "straight",
]

for component_name in components:
    print(component_name)
    component = gf.get_component(component_name)
    gt.write_sparameters(
        component=component,
        layer_stack=LAYER_STACK,
        plot_simulation_layer_name="core",
        plot_simulation_port_index=0,
    )

# %%
c = gf.components.bend_circular(radius=2)
s = gt.write_sparameters(
    c,
    layer_stack=LAYER_STACK,
    plot_simulation_layer_name="core",
    plot_simulation_port_index=0,
)

# %% [markdown]
# For a 2 port reciprocal passive component you can always assume `s21 = s12`
#
# Another approximation you can make for planar devices is that `s11 = s22`, which saves 1 extra simulation.
# This approximation only works well for straight and bends.
# We call this `1x1` port symmetry

# %%
sp = np.load(
    PATH.sparameters_repo / "bend_circular_radius2_9d7742b34c224827aeae808dc986308e.npz"
)
plot.plot_sparameters(sp)

# %%
plot.plot_sparameters(sp, keys=("o2@0,o1@0",))

# %%
c = gf.components.mmi1x2()
s = gt.write_sparameters(
    c,
    layer_stack=LAYER_STACK,
    plot_simulation_layer_name="core",
    plot_simulation_port_index=0,
)

# %%
# sp = gt.write_sparameters(c)
sp = np.load(PATH.sparameters_repo / "mmi1x2_507de731d50770de9096ac9f23321daa.npz")

# %%
plot.plot_sparameters(sp)

# %%
plot.plot_sparameters(sp, keys=("o1@0,o2@0", "o1@0,o3@0"))

# %%
plot.plot_loss1x2(sp)

# %%
plot.plot_imbalance1x2(sp)

# %%
c = gf.components.mmi2x2_with_sbend(with_sbend=False)
c.plot()

# %%
sp = gt.write_sparameters(
    c,
    layer_stack=LAYER_STACK,
    plot_simulation_layer_name="core",
    plot_simulation_port_index=0,
)

# %%
# sp = gt.write_sparameters(c, filepath=PATH.sparameters_repo / 'mmi2x2_without_sbend.npz')
sp = np.load(PATH.sparameters_repo / "mmi2x2_without_sbend.npz")
plot.plot_loss2x2(sp)

# %%
plot.plot_imbalance2x2(sp)

# %% [markdown]
# ## get_simulation_grating_coupler
#
# You can also expand the planar component simulations to simulate an out-of-plane grating coupler.
#
# The following simulations run in 2D but can also run in 3D.

# %%
help(gt.get_simulation_grating_coupler)

# %%
c = (
    gf.components.grating_coupler_elliptical_lumerical()
)  # inverse design grating apodized
fiber_angle_deg = 5
s = gt.get_simulation_grating_coupler(
    c, is_3d=False, fiber_angle_deg=fiber_angle_deg, fiber_xoffset=0
)
f = gt.plot_simulation(s)

# %%
f = c.plot()

# %% [markdown]
# Lets compare the xtolerance of a constant pitch vs an apodized grating.
#
# We run simulations in 2D for faster.
#
# Lets simulate 2 different grating couplers:
#
# - apodized inverse design example from lumerical website (5 degrees fiber angle)
# - constant pitch grating from gdsfactory generic PDK (20 degrees fiber angle)

# %%
sim = gt.get_simulation_grating_coupler(
    c, is_3d=False, fiber_angle_deg=fiber_angle_deg, fiber_xoffset=-5
)
f = gt.plot_simulation(sim)

# %%
sim = gt.get_simulation_grating_coupler(
    c, is_3d=False, fiber_angle_deg=fiber_angle_deg, fiber_xoffset=+5
)
f = gt.plot_simulation(sim)

# %%
offsets = np.arange(-5, 6, 5)
offsets = [-10, -5, 0]
offsets = [0]

# %%
dfs = [
    gt.write_sparameters_grating_coupler(
        component=c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        fiber_xoffset=fiber_xoffset,
        filepath=PATH.sparameters_repo / f"gc_offset{fiber_xoffset}",
    )
    for fiber_xoffset in offsets
]


# %%
def log(x):
    return 20 * np.log10(x)


# %%
for offset in offsets:
    sp = gt.write_sparameters_grating_coupler(
        c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        fiber_xoffset=offset,
        filepath=PATH.sparameters_repo / f"gc_offset{offset}",
    )
    plt.plot(
        sp["wavelengths"], 20 * np.log10(np.abs(sp["o2@0,o1@0"])), label=str(offset)
    )

plt.xlabel("wavelength (um")
plt.ylabel("Transmission (dB)")
plt.title("transmission vs fiber xoffset (um)")
plt.legend()

# %%
sp.keys()

# %%
fiber_angles = [3, 5, 7]
dfs = [
    gt.write_sparameters_grating_coupler(
        component=c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        filepath=PATH.sparameters_repo / f"gc_angle{fiber_angle_deg}",
    )
    for fiber_angle_deg in fiber_angles
]

# %%
for fiber_angle_deg in fiber_angles:
    sp = gt.write_sparameters_grating_coupler(
        c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        filepath=PATH.sparameters_repo / f"gc_angle{fiber_angle_deg}",
    )
    plt.plot(
        sp["wavelengths"],
        20 * np.log10(np.abs(sp["o2@0,o1@0"])),
        label=str(fiber_angle_deg),
    )

plt.xlabel("wavelength (um")
plt.ylabel("Transmission (dB)")
plt.title("transmission vs fiber angle (degrees)")
plt.legend()

# %%
c = gf.components.grating_coupler_elliptical_arbitrary(
    widths=[0.343] * 25, gaps=[0.345] * 25
)
f = c.plot()

# %%
fiber_angle_deg = 20
sim = gt.get_simulation_grating_coupler(
    c, is_3d=False, fiber_angle_deg=fiber_angle_deg, fiber_xoffset=0
)
f = gt.plot_simulation(sim, figsize=(22, 8))

# %%
offsets = [0]
offsets

# %%
dfs = [
    gt.write_sparameters_grating_coupler(
        component=c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        fiber_xoffset=fiber_xoffset,
        filepath=PATH.sparameters_repo / f"gc_offset{offset}",
    )
    for fiber_xoffset in offsets
]

# %%
port_name = c.get_ports_list()[1].name

for offset in offsets:
    sp = gt.write_sparameters_grating_coupler(
        c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        fiber_xoffset=offset,
        filepath=PATH.sparameters_repo / f"gc_offset{offset}",
    )
    plt.plot(
        sp["wavelengths"],
        20 * np.log10(np.abs(sp["o2@0,o1@0"])),
        label=str(offset),
    )

plt.xlabel("wavelength (um")
plt.ylabel("Transmission (dB)")
plt.title("transmission vs xoffset")
plt.legend()

# %% [markdown]
# ## Run jobs in parallel
#
# You can run multiple simulations in parallel on separate threads.
#
# Only when you `sp.result()` you will wait for the simulations to finish.

# %%
c = gf.components.grating_coupler_elliptical_lumerical()
fiber_angles = [3, 5, 7]
jobs = [
    dict(
        component=c,
        is_3d=False,
        fiber_angle_deg=fiber_angle_deg,
        filepath=PATH.sparameters_repo / f"gc_angle{fiber_angle_deg}",
    )
    for fiber_angle_deg in fiber_angles
]
sps = gt.write_sparameters_grating_coupler_batch(jobs)

# %%
for sp, fiber_angle_deg in zip(sps, fiber_angles):
    sp = sp.result()
    plt.plot(
        sp["wavelengths"],
        20 * np.log10(np.abs(sp["o2@0,o1@0"])),
        label=str(fiber_angle_deg),
    )

plt.xlabel("wavelength (um")
plt.ylabel("Transmission (dB)")
plt.title("transmission vs fiber angle (degrees)")
plt.legend()
