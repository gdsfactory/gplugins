from __future__ import annotations

from pathlib import Path

import klayout.db as pya
from gdsfactory.typings import ComponentOrPath


def check_exclusion(
    gdspath: ComponentOrPath,
    layer1: tuple[int, int] = (1, 0),
    layer2: tuple[int, int] = (2, 0),
    min_space: float = 0.150,
    dbu: float = 1e3,
    ignore_angle_deg: int = 80,
    whole_edges: bool = False,
    metrics: str = "Square",
    min_projection: None = None,
    max_projection: None = None,
) -> int:
    """Reads layer from top cell and returns a the area that violates min \
    exclusion if 0 no area violates exclusion.

    Args:
        gdspath: path to GDS.
        layer1: tuple.
        layer2: tuple.
        min_space: in um.
        dbu: database units (1000 um/nm).
        ignore_angle_deg: The angle above which no check is performed.
        whole_edges: If true, deliver the whole edges.
        metrics: Specify the metrics type.
        min_projection: lower threshold of the projected length of one edge onto another.
        max_projection: upper limit of the projected length of one edge onto another.

    """
    if isinstance(gdspath, str | Path):
        gdspath = gf.import_gds(gdspath)

    layout = gdspath.kcl
    cell = gdspath._kdb_cell
    a = pya.Region(cell.begin_shapes_rec(layout.layer(layer1[0], layer1[1])))
    b = pya.Region(cell.begin_shapes_rec(layout.layer(layer2[0], layer2[1])))

    valid_metrics = ["Square", "Euclidean"]
    if metrics not in valid_metrics:
        raise ValueError("metrics = {metrics} not in {valid_metrics}")
    metrics = getattr(pya.Region, metrics)

    d = a.separation_check(
        b,
        min_space * dbu,
        whole_edges,
        metrics,
        ignore_angle_deg,
        min_projection,
        max_projection,
    )
    # print(d.polygons().area())
    return d.polygons().area()


if __name__ == "__main__":
    import gdsfactory as gf

    w = 0.5
    space = 0.1
    min_space = 0.11
    dbu = 1000
    layer = (1, 0)
    c = gf.Component()
    r1 = c << gf.components.rectangle(size=(w, w), layer=(1, 0))
    r2 = c << gf.components.rectangle(size=(w, w), layer=(2, 0))
    r1.dxmax = 0
    r2.dxmin = space
    gdspath = c
    gf.show(gdspath)
    print(check_exclusion(c))

    # if isinstance(gdspath, gf.Component):
    #     gdspath.flatten()
    #     gdspath = gdspath.write_gds()
    # layout = pya.Layout()
    # layout.read(str(gdspath))
    # cell = layout.top_cell()
    # region = pya.Region(cell.begin_shapes_rec(layout.layer(layer[0], layer[1])))

    # d = region.space_check(min_space * dbu)
    # print(d.polygons().area())
