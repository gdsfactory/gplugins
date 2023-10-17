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
# # Klayout Design Rule Checking (DRC)
#
# Your device can be fabricated correctly when it meets the Design Rule Checks (DRC) from the foundry, you can write DRC rules from gdsfactory and customize the shortcut to run the checks in Klayout.
#
# Here are some rules explained in [repo generic DRC technology](https://github.com/klayoutmatthias/si4all) and [video](https://peertube.f-si.org/videos/watch/addc77a0-8ac7-4742-b7fb-7d24360ceb97)
#
# ![rules1](https://i.imgur.com/gNP5Npn.png)

# %%
import gdsfactory as gf
from gdsfactory.component import Component
from gdsfactory.generic_tech import LAYER
from gdsfactory.typings import Float2, Layer

from gplugins.klayout.drc.write_drc import (
    check_area,
    check_density,
    check_enclosing,
    check_separation,
    check_space,
    check_width,
    write_drc_deck_macro,
)

gf.CONF.display_type = "klayout"

# %%
help(write_drc_deck_macro)

# %%
rules = [
    check_width(layer="WG", value=0.2),
    check_space(layer="WG", value=0.2),
    check_width(layer="M1", value=1),
    check_width(layer="M2", value=2),
    check_space(layer="M2", value=2),
    check_separation(layer1="HEATER", layer2="M1", value=1.0),
    check_enclosing(layer1="M1", layer2="VIAC", value=0.2),
    check_area(layer="WG", min_area_um2=0.05),
    check_density(
        layer="WG", layer_floorplan="FLOORPLAN", min_density=0.5, max_density=0.6
    ),
]

drc_check_deck = write_drc_deck_macro(
    rules=rules,
    layers=LAYER,
    shortcut="Ctrl+Shift+D",
)

# %% [markdown]
# Lets create some DRC errors and check them on klayout.

# %%

layer = LAYER.WG


@gf.cell
def width_min(size: Float2 = (0.1, 0.1)) -> Component:
    return gf.components.rectangle(size=size, layer=layer)


@gf.cell
def area_min() -> Component:
    size = (0.2, 0.2)
    return gf.components.rectangle(size=size, layer=layer)


@gf.cell
def gap_min(gap: float = 0.1) -> Component:
    c = gf.Component()
    r1 = c << gf.components.rectangle(size=(1, 1), layer=layer)
    r2 = c << gf.components.rectangle(size=(1, 1), layer=layer)
    r1.xmax = 0
    r2.xmin = gap
    return c


@gf.cell
def separation(
    gap: float = 0.1, layer1: Layer = LAYER.HEATER, layer2: Layer = LAYER.M1
) -> Component:
    c = gf.Component()
    r1 = c << gf.components.rectangle(size=(1, 1), layer=layer1)
    r2 = c << gf.components.rectangle(size=(1, 1), layer=layer2)
    r1.xmax = 0
    r2.xmin = gap
    return c


@gf.cell
def enclosing(
    enclosing: float = 0.1, layer1: Layer = LAYER.VIAC, layer2: Layer = LAYER.M1
) -> Component:
    """Layer1 must be enclosed by layer2 by value.

    checks if layer1 encloses (is bigger than) layer2 by value
    """
    w1 = 1
    w2 = w1 + enclosing
    c = gf.Component()
    c << gf.components.rectangle(size=(w1, w1), layer=layer1, centered=True)
    r2 = c << gf.components.rectangle(size=(w2, w2), layer=layer2, centered=True)
    r2.movex(0.5)
    return c


@gf.cell
def snapping_error(gap: float = 1e-3) -> Component:
    c = gf.Component()
    r1 = c << gf.components.rectangle(size=(1, 1), layer=layer)
    r2 = c << gf.components.rectangle(size=(1, 1), layer=layer)
    r1.xmax = 0
    r2.xmin = gap
    return c


@gf.cell
def errors() -> Component:
    components = [width_min(), gap_min(), separation(), enclosing()]
    c = gf.pack(components, spacing=1.5)
    c = gf.add_padding_container(c[0], layers=(LAYER.FLOORPLAN,), default=5)
    return c


c = errors()
c.show()  # show in klayout
c.plot()

# %% [markdown]
# # Klayout connectivity checks
#
# You can you can to check for component overlap and unconnected pins using klayout DRC.
#
#
# The easiest way is to write all the pins on the same layer and define the allowed pin widths.
# This will check for disconnected pins or ports with width mismatch.

# %%

import gplugins.klayout.drc.write_connectivity as wc

nm = 1e-3

rules = [
    wc.write_connectivity_checks(pin_widths=[0.5, 0.9, 0.45], pin_layer=LAYER.PORT)
]
script = wc.write_drc_deck_macro(rules=rules, layers=None)


# %% [markdown]
# You can also define the connectivity checks per section

# %%
connectivity_checks = [
    wc.ConnectivyCheck(cross_section="xs_sc", pin_length=1 * nm, pin_layer=(1, 10)),
    wc.ConnectivyCheck(
        cross_section="xs_sc_auto_widen", pin_length=1 * nm, pin_layer=(1, 10)
    ),
]
rules = [
    wc.write_connectivity_checks_per_section(connectivity_checks=connectivity_checks),
]
script = wc.write_drc_deck_macro(rules=rules, layers=None)
