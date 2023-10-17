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
#     display_name: ''
#     language: ''
#     name: ''
# ---

# %% [markdown]
# # Netlist extractor SPICE
#
# This notebook demonstrates how to extract the SPICE netlist of a Component or a GDS file using gdsfactory. It uses the :func:`~get_netlist` and :func:`~get_l2n` functions from the `gplugins.klayout` module to extract the netlist and connectivity mapping, respectively. It also uses the `plot_nets` function to visualize the connectivity.
#

# %%
import pathlib

from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

from gplugins.klayout.get_netlist import get_l2n, get_netlist
from gplugins.klayout.plot_nets import plot_nets

# %% [markdown]
# ## Sample layouts
#
# We generate a sample layout using `pads_correct` and write a GDS file.

# %%
c = pads_correct()
gdspath = c.write_gds()
c.plot()

# %% [markdown]
# We obtain the netlist using KLayout by simply calling the :func:`~get_netlist` function from the `gplugins.klayout` module. The function takes the path to the GDS file as an argument and returns the netlist as a `kdb.Netlist` object.

# %%
netlist = get_netlist(gdspath)
print(netlist)

# %% [markdown]
# The connectivity between the components in the GDS file can be visualized using the :func:`~plot_nets` function from the `gplugins.klayout` module. The function takes the path to the GDS file as an argument and plots the connectivity between the components in the GDS file.

# %%
l2n = get_l2n(gdspath)
cwd = pathlib.Path.cwd()
filepath = cwd / f"{c.name}.txt"
l2n.write_l2n(str(filepath))
plot_nets(filepath)

# %% [markdown]
# The same steps as above are done for a shorted case.

# %%
c = pads_shorted()
gdspath = c.write_gds()
c.plot()

# %%
netlist = get_netlist(gdspath)
print(netlist)

# %%
l2n = get_l2n(gdspath)
filepath = cwd / f"{c.name}.txt"
l2n.write_l2n(str(filepath))
plot_nets(filepath)

# %%
