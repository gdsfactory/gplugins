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
# You can do this at the component level or at the top reticle assembled level.
#
# This tutorial is focusing on cleaning DRC on masks that have already been created.

# %%
import gdsfactory as gf
from gdsfactory.generic_tech.layer_map import LAYER

import gplugins.klayout.dataprep as dp

gf.CONF.display_type = "klayout"

# %% [markdown]
#
# You can manipulate layers using the klayout LayerProcessor to create a `RegionCollection` to operate on different layers.
#
# The advantage is that this can easily clean up routing, proximity effects, acute angles.

# %%
c = gf.Component()
ring = c << gf.components.coupler_ring(radius=20)
c.write_gds("input.gds")
d = dp.RegionCollection(gdspath="input.gds")
c.plot()

# %% [markdown]
# ## Copy layers
#
# You can access each layer as a dict.

# %%
d[LAYER.N] = d[
    LAYER.WG
].copy()  # make sure you add the copy to create a copy of the layer
d.plot()

# %% [markdown]
# ## Remove layers

# %%
d[LAYER.N].clear()
d.plot()

# %% [markdown]
# ### Size
#
# You can size layers, positive numbers grow and negative shrink.

# %%
d[LAYER.SLAB90] = d[LAYER.WG] + 2  # size layer by 4 um
d.plot()

# %% [markdown]
# ## Over / Under
#
# To avoid acute angle DRC errors you can grow and shrink polygons. This will remove regions smaller

# %%

d[LAYER.SLAB90] += 2  # size layer by 4 um
d[LAYER.SLAB90] -= 2  # size layer by 2 um
d.plot()

# %% [markdown]
# ## Smooth
#
# You can smooth using [RDP](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm)

# %%
d[LAYER.SLAB90].smooth(
    1 * 1e3
)  # smooth by 1um, Notice that klayout units are in DBU (database units) in this case 1nm, so 1um = 1e3
d.plot()

# %% [markdown]
# ### Booleans
#
# You can derive layers and do boolean operations.
#

# %%
d[LAYER.DEEP_ETCH] = d[LAYER.SLAB90] - d[LAYER.WG]
d.plot()


# %% [markdown]
# ### Fill
#
# You can add rectangular fill, using booleans to decide where to add it:

# %%
region = d[LAYER.FLOORPLAN] = d[LAYER.WG] + 50
region.round_corners(1 * 1e3, 1 * 1e3, 100)  # round corners by 1um
d.show()
d.plot()

# %%
fill_region = d[LAYER.FLOORPLAN] - d[LAYER.WG]

# %%
fill_cell = d.get_fill(
    fill_region,
    size=[0.1, 0.1],
    spacing=[0.1, 0.1],
    fill_layers=[LAYER.WG, LAYER.M1],
)
fill_cell

# %%
c = d.get_kcell()
c << fill_cell
c
