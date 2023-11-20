"""Test functional verification of a simple layout """
import os

import gdsfactory as gf
from verification import layout_check

"""
path_GitHub = '/Users/lukasc/Documents/GitHub/'
if os.path.exists(path_GitHub):
    path_ubcpdk = os.path.join(path_GitHub, 'gdsfactory_ubcpdk')
    if not path_ubcpdk in sys.path:
        sys.path.insert(0,path_ubcpdk)  # put SiEPIC at the beginning so that it is overrides the system-installed module
import ubcpdk
"""

if __name__ == "__main__":
    # c = gf.components.mmi2x2()

    file_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "tests/mmi2x2.oas"
    )
    c = gf.import_gds(file_path, read_metadata=True)

    # Uses the SiEPIC-EBeam-PDK, and assumes it is located in
    # ~/Documents/GitHub/SiEPIC_EBeam_PDK/klayout
    techname = "EBeam"
    path_module = "~/Documents/GitHub/SiEPIC_EBeam_PDK/klayout"
    path_module = os.path.expanduser(path_module)

    #    klive.show(gdspath)

    # Run verification
    layout_check(c, techname, path_module, show_klive=True)
