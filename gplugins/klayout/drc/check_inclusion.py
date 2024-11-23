from __future__ import annotations

from pathlib import Path

import klayout.db as pya
from gdsfactory.typings import ComponentOrPath


def check_inclusion(
    gdspath: ComponentOrPath,
    layer_in: tuple[int, int] = (1, 0),
    layer_out: tuple[int, int] = (2, 0),
    min_inclusion: float = 0.150,
    dbu: float = 1e3,
    ignore_angle_deg: int = 80,
    whole_edges: bool = False,
    metrics: str = "Square",
    min_projection: None = None,
    max_projection: None = None,
) -> int:
    """Reads layer from top cell and returns a the area that violates min \
    inclusion if 0 no area violates exclusion.

    Args:
        gdspath: path to GDS.
        layer_in: tuple.
        layer_out: tuple.
        min_inclusion: in um.
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
    a = pya.Region(cell.begin_shapes_rec(layout.layer(layer_in[0], layer_in[1])))
    b = pya.Region(cell.begin_shapes_rec(layout.layer(layer_out[0], layer_out[1])))

    valid_metrics = ["Square", "Euclidean"]
    if metrics not in valid_metrics:
        raise ValueError("metrics = {metrics!r} not in {valid_metrics}")
    metrics = getattr(pya.Region, metrics)

    d = b.inside_check(
        a,
        min_inclusion * dbu,
        whole_edges,
        metrics,
        ignore_angle_deg,
        min_projection,
        max_projection,
    )
    return d.polygons().area()


if __name__ == "__main__":
    import gdsfactory as gf

    w1 = 0.5
    inclusion = 0.1
    w2 = w1 - inclusion
    min_inclusion = 0.11
    # min_inclusion = 0.01
    dbu = 1000
    layer = (1, 0)
    c = gf.Component()
    r1 = c << gf.components.rectangle(size=(w1, w1), layer=(1, 0))
    r2 = c << gf.components.rectangle(size=(w2, w2), layer=(2, 0))
    r1.dx = 0
    r1.dy = 0
    r2.dx = 0
    r2.dy = 0
    gdspath = c
    gf.show(gdspath)
    print(check_inclusion(c, min_inclusion=min_inclusion))

    # if isinstance(gdspath, gf.Component):
    #     gdspath.flatten()
    #     gdspath = gdspath.write_gds()
    # layout = pya.Layout()
    # layout.read(str(gdspath))
    # cell = layout.top_cell()
    # region = pya.Region(cell.begin_shapes_rec(layout.layer(layer[0], layer[1])))

    # d = region.space_check(min_inclusion * dbu)
    # print(d.polygons().area())
