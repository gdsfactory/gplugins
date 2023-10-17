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
# # Path length analysis
#
# You can use the `report_pathlenghts` functionality to get a detailed CSV report and interactive visualization about the routes in your PIC.

# %%
import gdsfactory as gf

gf.config.CONF.display_type = "klayout"

xs_top = [0, 10, 20, 40, 50, 80]
pitch = 127.0
N = len(xs_top)
xs_bottom = [(i - N / 2) * pitch for i in range(N)]
layer = (1, 0)

top_ports = [
    gf.Port(f"top_{i}", center=(xs_top[i], 0), width=0.5, orientation=270, layer=layer)
    for i in range(N)
]

bot_ports = [
    gf.Port(
        f"bot_{i}",
        center=(xs_bottom[i], -300),
        width=0.5,
        orientation=90,
        layer=layer,
    )
    for i in range(N)
]

c = gf.Component(name="connect_bundle_separation")
routes = gf.routing.get_bundle(
    top_ports, bot_ports, separation=5.0, end_straight_length=100
)
for route in routes:
    c.add(route.references)

c.plot()

# %% [markdown]
# Let's quickly demonstrate our new cross-sections and transition component.

# %%
from pathlib import Path

from gplugins.path_length_analysis.path_length_analysis import report_pathlengths

report_pathlengths(
    pic=c,
    result_dir=Path("rib_strip_pathlengths"),
    visualize=True,
)

# %% [markdown]
# You should see an interactive webpage like the following appear in your browser, summarizing the paths in your PIC.
#
# To the left is a stick diagram, showing all the instances and paths in your circuit (with straight lines connecting ports for simplification).
# To the right is a table of the aggregate paths from all routing components in your circuit (those with `route_info` included in their `info` dictionary).
# You will see that there is also a CSV table in the results folder which has more in-depth statistics.
#
# ![](https://i.imgur.com/HbRC3R5.png)

# %% [markdown]
# Clicking any of the routes or checking any of the boxes should highlight the respective route in the color shown in the table to the right to help you better identify them. Hovering over any of the routes or ports will display additional information.
