# SiEPIC - can be loaded from PyPI or in KLayout Application, or loaded from a local folder such as GitHub
import os
from pathlib import Path

import gdsfactory
import pya
import SiEPIC
import SiEPIC.verification
from SiEPIC.utils import get_technology_by_name, klive


def layout_check(
    component: gdsfactory.Component,
    techname: str,
    path_module: str | Path,
    show_klive: bool = True,
) -> int:
    """Run a layout check using SiEPIC-Tool's functional verification.

    Args:
        techname: KLayout technology name,
        path_module: location of the KLayout technology, as a Python module
    """
    if not os.path.isdir(path_module):
        raise ValueError(f"{path_module} does not exist")

    # save layout
    gdspath = component.write_gds()

    # Load KLayout technology
    from SiEPIC.utils import load_klayout_technology

    load_klayout_technology(techname, path_module)

    # load in KLayout database
    ly = pya.Layout()
    # load SiEPIC technology
    ly.TECHNOLOGY = get_technology_by_name(techname)
    ly.read(str(gdspath))
    if len(ly.top_cells()) != 1:
        raise ValueError("Layout can only have one top cell")
    topcell = ly.top_cell()

    # perform verification
    file_lyrdb = str(gdspath) + ".lyrdb"
    num_errors = SiEPIC.verification.layout_check(cell=topcell, file_rdb=file_lyrdb)

    # show results in KLayout
    if show_klive:
        klive.show(gdspath, lyrdb_filename=file_lyrdb, technology=techname)

    return num_errors
