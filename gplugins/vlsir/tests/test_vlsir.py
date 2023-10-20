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


def test_kdb_vlsir(pkg) -> None:
    """Test the conversion from KLayout DB Netlist to VLSIR Package"""

    assert pkg is not None
    assert len(pkg.modules) == 7
    assert len(pkg.modules[6].instances) == 10
    assert pkg.modules[6].name == "pads_correct"


@pytest.mark.parametrize("spice_format", ["spice", "spectre", "xyce", "verilog"])
def test_export_netlist(pkg, spice_format) -> None:
    """Test the export of a VLSIR Package to a netlist in the supported formats"""

    outfile = PATH.module / "vlsir" / "tests" / "resources" / "pads_correct"
    format_to_suffix = {
        "spice": ".sp",
        "spectre": ".scs",
        "xyce": ".cir",
    }
    if spice_format == "verilog":
        with pytest.raises(NotImplementedError):
            export_netlist(pkg, fmt=spice_format)
    else:
        outpath = outfile.with_suffix(format_to_suffix[spice_format])
        with open(outpath, "w") as f:
            export_netlist(pkg, fmt=spice_format, dest=f)
        with open(outpath) as f:
            assert f.read() is not None
