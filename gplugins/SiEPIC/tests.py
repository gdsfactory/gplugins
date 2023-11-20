"""Test functional verification of a simple layout """
import os

import gdsfactory as gf
from verification import layout_check

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
