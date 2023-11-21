"""Test functional verification of simple layouts """
import os

import siepic_ebeam_pdk

import gdsfactory as gf

from gplugins.siepic.verification import layout_check


def test1():
    techname = "EBeam"

    file_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "tests/mmi2x2.oas"
    )
    c = gf.import_gds(file_path, read_metadata=True)

    # Run verification
    layout_check(c, techname, show_klive=True)


def test2():
    import ubcpdk.components as uc

    splitter = uc.ebeam_y_1550(decorator=gf.port.auto_rename_ports)
    mzi = gf.components.mzi(splitter=splitter)
    component_fiber_array = uc.add_fiber_array(component=mzi)

    # Uses the SiEPIC-EBeam-PDK
    techname = "EBeam"

    # Run verification
    layout_check(component_fiber_array, techname, show_klive=True)


if __name__ == "__main__":
    test1()
    test2()
