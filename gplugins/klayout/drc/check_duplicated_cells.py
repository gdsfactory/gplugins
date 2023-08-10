from __future__ import annotations

from pathlib import Path

import klayout.db as pya
from gdsfactory.component import Component


def check_duplicated_cells(gdspath: Path | str):
    """Reads cell and checks for duplicated cells.

    klayout will fail to load the layout if it finds any duplicated cells.

    Args:
        gdspath: path to GDS or Component
    """

    if isinstance(gdspath, Component):
        gdspath = gdspath.write_gds()
    layout = pya.Layout()
    layout.read(str(gdspath))
    return layout.top_cell()
