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
# # VLSIR
#
# Thanks to [VLSIR](https://github.com/Vlsir/Vlsir) you can parse for KLayout's gds-extracted netlist's and convert it to Spectre, Spice and Xyce simulator schematic file formats
#
#
# ## Simulator and Analysis Support
#
# Each spice-class simulator includes its own netlist syntax and opinions about the specification for analyses. [See](https://github.com/Vlsir/Vlsir/blob/main/VlsirTools/readme.md)
#
# | Analysis             | Spectre            | Xyce               | NgSpice     |
# | -------------------- | ------------------ | ------------------ | ------------------ |
# | Op                   | ✅ | ✅ | ✅ |
# | Dc                   | ✅ | ✅ | |
# | Tran                 | ✅ | ✅ | ✅ |
# | Ac                   | ✅ | ✅ | ✅ |
# | Noise                |                    |                    | ✅ |
# | Sweep                |  |  |  |
# | Monte Carlo          |  |  |  |
# | Custom               |  |  |  |
#

# %%
from io import StringIO

from gdsfactory.samples.demo.lvs import pads_correct

import gplugins.vlsir as gs
from gplugins.klayout.get_netlist import get_netlist

# %%
c = pads_correct()
c.plot()

# %%
gdspath = c.write_gds()

# get the netlist
kdbnetlist = get_netlist(gdspath)

# convert it to a VLSIR Package
pkg = gs.kdb_vlsir(kdbnetlist, domain="gplugins.klayout.example")

# %% [markdown]
# ## Spectre RF

# %%
out = StringIO()
gs.export_netlist(pkg, dest=out, fmt="spectre")
print(out.getvalue())

# %% [markdown]
# ## Xyce

# %%
out = StringIO()
gs.export_netlist(pkg, dest=out, fmt="xyce")
print(out.getvalue())

# %% [markdown]
# ## ngspice
#

# %%
out = StringIO()
gs.export_netlist(pkg, dest=out, fmt="spice")
print(out.getvalue())

# %%
