from pathlib import Path

import klayout.db as kdb
import pytest
from gdsfactory.samples.demo.lvs import pads_correct

from gplugins.klayout.get_netlist import get_l2n, get_netlist
from gplugins.klayout.netlist_spice_reader import NoCommentReader
from gplugins.klayout.plot_nets import plot_nets


@pytest.fixture(scope="session")
def klayout_netlist(tmpdir_factory: pytest.TempdirFactory) -> str:
    """Get KLayout netlist file for `pads_correct`. Cached for session scope."""
    tmp_path = tmpdir_factory.mktemp("data")
    c = pads_correct()
    gdspath = c.write_gds(gdsdir=tmp_path)
    l2n = get_l2n(gdspath)
    netlist_path = str(Path(tmp_path) / f"{c.name}.txt")
    l2n.write_l2n(netlist_path)
    return netlist_path


@pytest.fixture(scope="session")
def spice_netlist(tmpdir_factory: pytest.TempdirFactory) -> str:
    """Get SPICE netlist file for `pads_correct`. Cached for session scope."""
    tmp_path = tmpdir_factory.mktemp("data")
    c = pads_correct()
    gdspath = c.write_gds(gdsdir=tmp_path)
    netlist = get_netlist(gdspath)
    netlist_path = str(Path(tmp_path) / f"{c.name}.spice")
    netlist.write(netlist_path, kdb.NetlistSpiceWriter())
    return netlist_path


@pytest.mark.skip(
    reason="Implementation changed to consider detected devices and current pads_correct example does not have any."
)
@pytest.mark.parametrize("interactive", [True, False])
@pytest.mark.parametrize("include_labels", [True, False])
@pytest.mark.parametrize(
    "nodes_to_reduce", [None, {"straight"}, {"straight", "bend_euler"}]
)
def test_plot_nets(
    klayout_netlist: str,
    interactive: bool,
    include_labels: bool,
    nodes_to_reduce: list[str] | None,
) -> None:
    plot_nets(
        klayout_netlist,
        interactive=interactive,
        include_labels=include_labels,
        nodes_to_reduce=nodes_to_reduce,
        spice_reader=NoCommentReader,
    )
    if interactive:
        assert Path("connectivity.html").exists()


def test_plot_nets_spice(spice_netlist: str) -> None:
    plot_nets(spice_netlist)
