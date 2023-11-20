
# SiEPIC - can be loaded from PyPI or in KLayout Application, or loaded from a local folder such as GitHub
import os, sys
path_GitHub = '/Users/lukasc/Documents/GitHub/'
if os.path.exists(path_GitHub):
    path_siepic = os.path.join(path_GitHub, 'SiEPIC-Tools/klayout_dot_config/python')
    if not path_siepic in sys.path:
        sys.path.insert(0,path_siepic)  # put SiEPIC at the beginning so that it is overrides the system-installed module
import SiEPIC

import pya
import SiEPIC
import SiEPIC.verification
from SiEPIC.utils import klive, load_klayout_technology, get_technology_by_name
from pathlib import Path
import os
import gdsfactory

def layout_check(
    component: gdsfactory.Component,
    techname: str, 
    path_module: str | Path,
    show_klive: bool = True
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
    tech = load_klayout_technology('EBeam', path_module)
    
    # load in KLayout database
    ly = pya.Layout()
    # load SiEPIC technology
    ly.TECHNOLOGY = get_technology_by_name(techname)
    ly.read(str(gdspath))
    if len(ly.top_cells()) != 1:
        raise ValueError(f"Layout can only have one top cell")
    topcell = ly.top_cell()

    # perform verification
    file_lyrdb = str(gdspath)+'.lyrdb'
    num_errors = SiEPIC.verification.layout_check(cell=topcell, file_rdb=file_lyrdb)

    # show results in KLayout
    if show_klive:
        klive.show(gdspath, lyrdb_filename=file_lyrdb, technology=techname)

    return num_errors
