"""Test functional verification of simple layouts """
import os

import gdsfactory as gf
from verification import layout_check

def test1():
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

def test2():
    import ubcpdk
    import ubcpdk.components as uc

    splitter = uc.ebeam_y_1550(decorator=gf.port.auto_rename_ports)
    mzi = gf.components.mzi(splitter=splitter)
    component_fiber_array = uc.add_fiber_array(component=mzi)

    # Uses the SiEPIC-EBeam-PDK, and assumes it is located in
    # ~/Documents/GitHub/SiEPIC_EBeam_PDK/klayout
    techname = "EBeam"
    path_module = "~/Documents/GitHub/SiEPIC_EBeam_PDK/klayout"
    path_module = os.path.expanduser(path_module)

    #    klive.show(gdspath)

    # Run verification
    layout_check(component_fiber_array, techname, path_module, show_klive=True)

if __name__ == "__main__":
    test1()
    test2()
