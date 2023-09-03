#! Tests -----
import pytest

def test_import():
    import gplugins.parcirc

def test_kdb_vlsir():
    from gplugins.verification.get_netlist import get_netlist
    """Test the conversion from KLayout DB Netlist to VLSIR Package"""
    from gdsfactory.samples.demo.lvs import pads_correct
    from gplugins.parcirc import kdb_vlsir, export_netlist
    
    c = pads_correct()
    gdspath = c.write_gds()
    kdbnet = get_netlist(gdspath)
    pkg = kdb_vlsir(kdbnet, domain="gplugins.verification.example")
    assert pkg is not None
    assert len(pkg.modules) == 6
    assert len(pkg.modules["pads_correct"].instances) == 10
    
def test_export_netlist():
    """Test the export of a VLSIR Package to a netlist in the supported formats"""    
    from gplugins.parcirc import export_netlist, kdb_vlsir
    from gdsfactory.samples.demo.lvs import pads_correct
    from gplugins.verification.get_netlist import get_netlist
    
    c = pads_correct()
    gdspath = c.write_gds()
    kdbnet = get_netlist(gdspath)
    pkg = kdb_vlsir(kdbnet, domain="gplugins.verification.example")
    outfile = './resources/pads_correct'
    format_to_suffix = {
        "spice": ".sp",
        "spectre": ".scs",
        "xyce": ".cir",
    }
    for fmt in ["spice", "spectre", "xyce", "verilog"]:
        if fmt == "verilog": 
            with pytest.raises(NotImplementedError):
                export_netlist(pkg, fmt=fmt)
        else:
            outpath = outfile + format_to_suffix[fmt]
            with open(outpath, "w") as f:
                export_netlist(pkg, fmt=fmt, dest=f)
            with open(outpath, "r") as f:
                assert f.read() is not None
    