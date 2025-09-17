import pytest
from gdsfactory.samples.demo.lvs import pads_correct
from vlsir.circuit_pb2 import (
    Package,
)

from gplugins.common.config import PATH
from gplugins.klayout.get_netlist import get_netlist
from gplugins.vlsir import export_netlist, kdb_vlsir


@pytest.fixture(scope="session")
def pkg() -> Package:
    """Get VLSIR Package for `pads_correct`. Cached for session scope."""
    c = pads_correct()
    gdspath = c.write_gds()
    kdbnet = get_netlist(gdspath)
    return kdb_vlsir(kdbnet, domain="gplugins.klayout.example")


@pytest.mark.parametrize(
    "expected_module_name",
    [
        "taper_gdsfactorypcomponentsptapersptaper_L10_W100_W10_L_e6a63921",
        "pad_gdsfactorypcomponentsppadsppad_S100_100_LMTOP_BLNon_457de54c",
        "pads_correct_Ppad_CSmetal3",
    ],
)
def test_kdb_vlsir(pkg: Package, expected_module_name: str) -> None:
    """Test the conversion from KLayout DB Netlist to VLSIR Package."""
    assert pkg is not None, "Package should not be None"
    module_names = (module.name for module in pkg.modules)
    assert expected_module_name in module_names, (
        f"Expected module '{expected_module_name}' in package modules"
    )


@pytest.mark.parametrize("spice_format", ["spice", "spectre", "xyce", "verilog"])
def test_export_netlist(pkg: Package, spice_format: str) -> None:
    """Test the export of a VLSIR Package to a netlist in the supported formats."""
    if spice_format == "verilog":
        with pytest.raises(NotImplementedError):
            export_netlist(pkg, fmt=spice_format)
    else:
        outfile = PATH.module / "vlsir" / "tests" / "resources" / "pads_correct"
        format_to_suffix = {
            "spice": ".sp",
            "spectre": ".scs",
            "xyce": ".cir",
        }
        outpath = outfile.with_suffix(format_to_suffix[spice_format])
        with open(outpath, "w") as f:
            export_netlist(pkg, fmt=spice_format, dest=f)
        with open(outpath) as f:
            assert f.read() is not None


if __name__ == "__main__":
    test_kdb_vlsir()
