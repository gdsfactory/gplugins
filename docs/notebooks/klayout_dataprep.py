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
# ## Booleans
#
# You can derive layers and do boolean operations.
#

# %%
d[LAYER.DEEP_ETCH] = d[LAYER.SLAB90] - d[LAYER.WG]
d.plot()


# %% [markdown]
# ## Fill
#

# %%
import gdsfactory as gf
import kfactory as kf
from kfactory.utils.fill import fill_tiled

c = kf.KCell("ToFill")
c.shapes(kf.kcl.layer(1, 0)).insert(
    kf.kdb.DPolygon.ellipse(kf.kdb.DBox(5000, 3000), 512)
)
c.shapes(kf.kcl.layer(10, 0)).insert(
    kf.kdb.DPolygon(
        [kf.kdb.DPoint(0, 0), kf.kdb.DPoint(5000, 0), kf.kdb.DPoint(5000, 3000)]
    )
)

fc = kf.KCell("fill")
fc.shapes(fc.kcl.layer(2, 0)).insert(kf.kdb.DBox(20, 40))
fc.shapes(fc.kcl.layer(3, 0)).insert(kf.kdb.DBox(30, 15))

# fill.fill_tiled(c, fc, [(kf.kcl.layer(1,0), 0)], exclude_layers = [(kf.kcl.layer(10,0), 100), (kf.kcl.layer(2,0), 0), (kf.kcl.layer(3,0),0)], x_space=5, y_space=5)
fill_tiled(
    c,
    fc,
    [(kf.kcl.layer(1, 0), 0)],
    exclude_layers=[
        (kf.kcl.layer(10, 0), 100),
        (kf.kcl.layer(2, 0), 0),
        (kf.kcl.layer(3, 0), 0),
    ],
    x_space=5,
    y_space=5,
)

gdspath = "mzi_fill.gds"
c.write(gdspath)
c = gf.import_gds(gdspath)
c.plot()
