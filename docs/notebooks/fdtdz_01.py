# ---
# jupyter:
#   jupytext:
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: fdtdz_debug
#     language: python
#     name: python3
# ---

# %% [markdown]
# # FDTDz
#
# fdtdz (alongside its associated utilities such as pjz) is an open-source library executing differentiable finite-difference time domain s-parameter extraction on GPU. See whitepaper.
#
# `gplugins.fdtdz` allows you to execute forward S-parameter simulations with `fdtdz`, by providing a `gdsfactory` `Component` and `LayerStack`.

# %% [markdown]
# ## Installation
#
# Before proceeding, you will need to make sure `fdtdz` is properly installed. Make sure your CUDA installation is properly linked to `jax` and findable by `fdtdz` when building the wheel.

# %% [markdown]
# The function `get_sparameters_fdtdz` will quickly return the S-parameters of the provided Component + LayerStack combination at the specified wavelength (in um).
#
# Since fdtdz has a fixed domain size in the z-direction, you can also manually specify `zmin`, which will clip the LayerStack from below.

# %% [markdown]
# ### Define your component
#
# Like in the gmsh plugin, we add a `LAYER.WAFER` bbox around the component to parametrize the simulation domain:

# %%
# %load_ext autoreload
# %autoreload 2


# %%
import gdsfactory as gf
from gdsfactory.cross_section import rib
from gdsfactory.generic_tech import LAYER, LAYER_STACK
from gdsfactory.technology import LayerStack

from gplugins.fdtdz.get_sparameters_fdtdz import get_sparameters_fdtdz

length = 10

c = gf.Component()
waveguide_rib = c << gf.components.straight(length=length, cross_section=rib)
nitride_feature = c << gf.components.circle(radius=2, layer=LAYER.WGN)
nitride_feature.x = 5
padding = c << gf.components.bbox(
    waveguide_rib.bbox, top=2, bottom=2, layer=LAYER.WAFER
)
c.add_ports(gf.components.straight(length=length).get_ports_list())

c.plot()

# %% [markdown]
# ### Define your LayerStack
#
# Here we load the generic LayerStack, but only keep the `core`, `clad`, and `box` layers:

# %%
filtered_layer_stack = LayerStack(
    layers={
        k: LAYER_STACK.layers[k] for k in ["clad", "box", "core", "slab90", "nitride"]
    }
)
filtered_layer_stack

# %% [markdown]
# We show how to inspect the resulting permittivity below to troubleshoot.

# %% [markdown]
# ### Run the simulation
#
# The we just need to call the get_s_parameters function with some settings
#
# * `nm_per_pixel`: resolution, how many nm corresponds to each grid pixel
# * `extend_ports_length`: ports are extended by this amount prior to inputting into the simulation, so that the mode does not overlap with absorbing boundaries
# * `zmin`: z-value (um) for the lower end of the simulation, since the z-extent is fixed to zz * nm_per_pixel in fdtdz
# * `zz`: (int) number of grid points in the z-direction. Defaults to 126 (reduced precision) - 2*16 for PMLs
# * `tt`: (int) number of time steps
# * `wavelength`: (float) of the monochromatic source, converts to frequency omega as 1/wavelength
# * `port_margin`: (um) how far around each port to consider the permittivity in the mode calculation
# * `material_name_to_fdtdz`: mapping between LayerStack material name and refractive index
# * default_index: in case the LayerStack does not cover the whole domain, what default nonzero index to assign to pixels

# %%
material_name_to_fdtdz = {
    "si": 3.45,
    "sio2": 1.44,
    "sin": 2.0,
}

out = get_sparameters_fdtdz(
    component=c,
    layer_stack=filtered_layer_stack,
    nm_per_pixel=20,
    extend_ports_length=0.0,
    zmin=-0.5,
    zz=96,
    tt=10000,
    wavelength=1.55,
    port_margin=1,
    material_name_to_fdtdz=material_name_to_fdtdz,
    default_index=1.44,
)

out

# %%
import numpy as np

# %%
np.abs(out)

# %% [markdown]
# ## Inspecting the simulation
#
# The internal functions can be directly run to make sure the simulation is setup properly.
#
# ### Permittivity distribution
#
# Pass the component, layer_stack, and minz, and slice the simulation domain to inspect the permittivity.
#
# For xy-plane visualization, set `x = y = None` and choose a z-value:

# %%
from gplugins.fdtdz.get_epsilon_fdtdz import component_to_epsilon_pjz, plot_epsilon

zmin = -0.5
nm_per_pixel = 20

epsilon = component_to_epsilon_pjz(
    component=c, layer_stack=filtered_layer_stack, zmin=zmin
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=None,
    z=-0.1,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=None,
    z=0.05,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=None,
    z=0.11,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=None,
    z=0.5,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=None,
    z=0.75,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

# %% [markdown]
# Proceed similarly for `xz` and `yz` planes:

# %%
fig = plot_epsilon(
    epsilon=epsilon,
    x=1.0,
    y=None,
    z=None,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=5.0,
    y=None,
    z=None,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=-5,
    z=None,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=-3,
    z=None,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=-1.5,
    z=None,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

fig = plot_epsilon(
    epsilon=epsilon,
    x=None,
    y=0,
    z=None,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(11, 4),
)

# %% [markdown]
# ### Mode profiles
#
# When used through gdsfactory, the optical ports of the Component are used to set the S-parameter monitors of the simulation. They can be inspected:

# %%
from gplugins.fdtdz.get_ports_fdtdz import get_mode_port, plot_mode

omega = 1 / 1.55

excitation, pos, epsilon_port = get_mode_port(
    omega=omega,
    port=c.ports["o1"],
    epsilon=epsilon,
    xmin=c.xmin,
    ymin=c.ymin,
    nm_per_pixel=nm_per_pixel,
    port_extent_xy=1,
)

fig = plot_mode(
    port=c.ports["o1"],
    epsilon_port=epsilon_port,
    excitation=excitation,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(20, 6),
)

excitation, pos, epsilon_port = get_mode_port(
    omega=omega,
    port=c.ports["o2"],
    epsilon=epsilon,
    xmin=c.xmin,
    ymin=c.ymin,
    nm_per_pixel=nm_per_pixel,
    port_extent_xy=1,
)

fig = plot_mode(
    port=c.ports["o2"],
    epsilon_port=epsilon_port,
    excitation=excitation,
    xmin=c.xmin,
    ymin=c.ymin,
    zmin=zmin,
    nm_per_pixel=nm_per_pixel,
    figsize=(20, 6),
)
