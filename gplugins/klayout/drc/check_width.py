from __future__ import annotations

from pathlib import Path

import gdsfactory as gf
import klayout.db as pya
from gdsfactory.component import Component


def check_width(
    gdspath: Path | Component | str,
    layer: tuple[int, int] = (1, 0),
    min_width: float = 0.150,
    dbu: float = 1e3,
) -> int:
    """Reads layer from top cell and returns a number of edges violating min width.

    Args:
        gdspath: path to GDS or Component.
        layer: tuple (int, int).
        min_width: in um.
        dbu: database units (1000 um/nm).
    """
    if isinstance(gdspath, str | Path):
        gdspath = gf.import_gds(gdspath)

    layout = gdspath.kcl
    cell = gdspath.kdb_cell
    region = pya.Region(cell.begin_shapes_rec(layout.layer(layer[0], layer[1])))
    # print(region)
    # print(min_width*1e3)
    return len(region.width_check(min_width * dbu))


def demo() -> None:
    import klayout.db as pya

    a = pya.Region()
    a.insert(pya.Box(0, 0, 100, 1000))

    b = pya.Region()
    b.insert(pya.Box(200, 0, 300, 1000))

    c = pya.Region()
    c.insert(pya.Box(0, 0, 500, 500))
    print("c", c.width_check(200))

    # width check (w < 200 DBU)
    # simple version -> more options available for the complex variant of this method
    too_small = a.width_check(200)

    # space check (here: separation between a and b, s < 200 DBU)
    too_close = a.separation_check(b, 200)
    # NOTE: "too_small" and "too_close" are pya.EdgePairs collections of error markers
    print("too_small is: ", too_small)
    print("too_close is: ", too_close)


if __name__ == "__main__":
    import gdsfactory as gf
    from gdsfactory.generic_tech import LAYER

    w = 0.12
    c = gf.components.rectangle(size=(w, w), layer=LAYER.WG)
    r = check_width(c)
    print(r)
