from pathlib import Path

import klayout.db as kdb
import pytest
from gdsfactory.samples.demo.lvs import pads_correct

from gplugins.klayout.get_netlist import get_l2n, get_netlist
from gplugins.klayout.plot_nets import plot_nets


@pytest.fixture(scope="session")
def klayout_netlist(tmpdir_factory) -> str:
    """Get KLayout netlist file for `pads_correct`. Cached for session scope."""
    tmp_path = tmpdir_factory.mktemp("data")
    c = pads_correct()
    gdspath = c.write_gds(gdsdir=tmp_path)
    l2n = get_l2n(gdspath)
    netlist_path = str(Path(tmp_path) / f"{c.name}.txt")
    l2n.write_l2n(netlist_path)
    return netlist_path


@pytest.fixture(scope="session")
def spice_netlist(tmpdir_factory) -> str:
    """Get SPICE netlist file for `pads_correct`. Cached for session scope."""
    tmp_path = tmpdir_factory.mktemp("data")
    c = pads_correct()
    gdspath = c.write_gds(gdsdir=tmp_path)
    netlist = get_netlist(gdspath)
    netlist_path = str(Path(tmp_path) / f"{c.name}.spice")
    netlist.write(netlist_path, kdb.NetlistSpiceWriter())
    return netlist_path


def test_plot_nets(klayout_netlist):
    plot_nets(klayout_netlist)


def test_plot_nets_interactive(klayout_netlist):
    plot_nets(klayout_netlist, interactive=True)
    assert Path("connectivity.html").exists()


def test_plot_nets_not_fully_connected(klayout_netlist):
    plot_nets(klayout_netlist, fully_connected=False)


def test_plot_nets_no_labels(klayout_netlist):
    plot_nets(klayout_netlist, include_labels=False)


def test_plot_nets_spice(spice_netlist):
    plot_nets(spice_netlist)
