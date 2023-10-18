from pathlib import Path

import pytest
from gdsfactory.samples.demo.lvs import pads_correct

from gplugins.klayout.get_netlist import get_l2n
from gplugins.klayout.plot_nets import plot_nets


@pytest.fixture
def klayout_netlist(tmp_path):
    c = pads_correct()

    gdspath = c.write_gds(gdsdir=tmp_path)
    l2n = get_l2n(gdspath)
    netlist_path = str(Path(tmp_path) / f"{c.name}.txt")
    l2n.write_l2n(netlist_path)
    return netlist_path


def test_plot_nets(klayout_netlist):
    plot_nets(klayout_netlist)


def test_plot_nets_interactive(klayout_netlist):
    plot_nets(klayout_netlist, interactive=True)
    assert Path("connectivity.html").exists()
