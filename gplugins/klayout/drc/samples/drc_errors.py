"""Write GDS with sample errors."""

from __future__ import annotations

import gdsfactory as gf
import numpy as np
from gdsfactory.component import Component
from gdsfactory.typings import Layer

layer = (1, 0)


@gf.cell
def width_min(width: float = 0.1) -> Component:
    return gf.components.rectangle(size=(width, width), layer=layer)


@gf.cell
def area_min(width: float = 0.2) -> Component:
    return gf.components.rectangle(size=(width, width), layer=layer)


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
    gap: float = 0.1, layer1: Layer = (47, 0), layer2: Layer = (41, 0)
) -> Component:
    c = gf.Component()
    r1 = c << gf.components.rectangle(size=(1, 1), layer=layer1)
    r2 = c << gf.components.rectangle(size=(1, 1), layer=layer2)
    r1.xmax = 0
    r2.xmin = gap
    return c


@gf.cell
def enclosing(
    enclosing: float = 0.1, layer1: Layer = (40, 0), layer2: Layer = (41, 0)
) -> Component:
    """Layer1 must be enclosed by layer2 by value, checks if layer1 encloses (is bigger than) layer2 by value.

    Args:
        enclosing: value to enclose layer1 by layer2.
        layer1: layer to enclose.
        layer2: layer to enclose by.

    """
    w1 = 1
    w2 = w1 + enclosing
    c = gf.Component()
    c << gf.components.rectangle(size=(w1, w1), layer=layer1, centered=True)
    r2 = c << gf.components.rectangle(size=(w2, w2), layer=layer2, centered=True)
    r2.dmovex(0.5)
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
def errors(n: int = 20) -> Component:
    """Write a GDS with sample errors."""
    wmin = 0.1
    # components = [width_min(), gap_min(), separation(), enclosing()]
    cs = []
    cs += [width_min(wmin * np.random.rand()) for _ in range(n)]
    cs += [gap_min(gap=0.1 * np.random.rand()) for _ in range(n)]
    cs += [separation(gap=0.1 * np.random.rand()) for _ in range(n)]
    cs += [enclosing(enclosing=0.1 * np.random.rand()) for _ in range(n)]

    c = gf.pack(cs, spacing=1.5)
    return gf.add_padding_container(c[0], layers=((64, 0),), default=5)


if __name__ == "__main__":
    # c = width_min()
    # c.write_gds("wmin.gds")
    # c = gap_min()
    # c.write_gds("gmin.gds")
    # c = snapping_error()
    # c.write_gds("snap.gds")

    c = errors()
    c.write_gds("errors.gds")
    c.show()
