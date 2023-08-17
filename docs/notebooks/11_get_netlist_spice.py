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
# # Netlist extractor SPICE
#
# You can also extract the SPICE netlist using klayout
#

# %%
from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

from gplugins.config import PATH
from gplugins.verification.get_netlist import get_l2n, get_netlist
from gplugins.verification.plot_nets import plot_nets

c = pads_correct()
gdspath = c.write_gds()
c.plot()

# %%
netlist = get_netlist(gdspath)
print(netlist)

# %%
l2n = get_l2n(gdspath)
filepath = PATH.extra / f"{c.name}.txt"
l2n.write_l2n(str(filepath))
plot_nets(filepath)

# %%
c = pads_shorted()
gdspath = c.write_gds()
c.plot()

# %%
netlist = get_netlist(gdspath)
print(netlist)

# %%
l2n = get_l2n(gdspath)
filepath = PATH.extra / f"{c.name}.txt"
l2n.write_l2n(str(filepath))
plot_nets(filepath)
