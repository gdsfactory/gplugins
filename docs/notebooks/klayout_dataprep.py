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
# # Dataprep
#
# When building a reticle sometimes you want to do boolean operations. This is usually known as dataprep.
#
# You can do this at the component level or at the top reticle assembled level, each having different advantages and disadvantages.
#

# %%
import gdsfactory as gf
from gdsfactory.generic_tech.layer_map import LAYER as l

gf.config.rich_output()
PDK = gf.generic_tech.get_generic_pdk()
PDK.activate()

# %% [markdown]
#
# You can flatten the hierarchy and use klayout LayerProcessor to create a `RegionCollection` where you can easily grow and shrink layers.
#
# The advantage is that this can easily clean up routing, proximity effects, boolean operations on big masks.
#
# The disadvantage is that the design is no longer hierarchical and can take up more space.
#
# ### Size
#
# You can copy/size layers

# %%
c = gf.Component()

device = c << gf.components.coupler_ring()
floorplan = c << gf.components.bbox(device.bbox, layer=l.FLOORPLAN)
c.write_gds("src.gds")
c.plot()

# %%
import gplugins.klayout.dataprep as dp

d = dp.RegionCollection(filepath="src.gds", layermap=dict(l))
d.SLAB150 = d.WG.copy()  # copy layer
d.SLAB150 += 4  # size layer by 4 um
d.SLAB150 -= 2  # size layer by 2 um
c = d.write("dst.gds")
c.plot()

# %% [markdown]
# ### Booleans
#
# You can derive layers and do boolean operations.
#

# %%
d = dp.RegionCollection(filepath="src.gds", layermap=dict(l))
d.SLAB150 = d.WG.copy()
d.SLAB150 += 3  # size layer by 3 um
d.SHALLOW_ETCH = d.SLAB150 - d.WG
c = d.write("dst.gds")
c.plot()


# %% [markdown]
# ### Fill
#
# You can add rectangular fill, using booleans to decide where to add it:

# %%
d = dp.RegionCollection(filepath="src.gds", layermap=dict(l))

fill_region = d.FLOORPLAN - d.WG
fill_cell = d.get_fill(
    fill_region,
    size=[0.1, 0.1],
    spacing=[0.1, 0.1],
    fill_layers=[l.WG, l.M1],
    fill_name="test",
)
fill_cell

# %% [markdown]
# ### KLayout operations
#
# Any operation from Klayout Region can be called directly:

# %%
d = dp.RegionCollection(filepath="src.gds", layermap=dict(l))
d.SLAB150 = d.WG.copy()
d.SLAB150.round_corners(1 * 1e3, 1 * 1e3, 100)  # round corners by 1um
c = d.write("dst.gds")
c.plot()

# %%
