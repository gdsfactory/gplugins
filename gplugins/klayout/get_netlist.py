import kfactory as kf
import klayout.db as kdb
from gdsfactory.typings import PathType


def get_l2n(gdspath, klayout_tech_path: PathType | None = None) -> kdb.LayoutToNetlist:
    """Returns the layout to netlist object.

    Args:
        gdspath: Path to the GDS file.
        klayout_tech_path: Path to the klayout technology file.

    """
    lib = kf.kcell.KCLayout(str(gdspath))
    lib.read(filename=str(gdspath))
    c = lib[0]

    if klayout_tech_path:
        technology = kdb.Technology()
        technology.load(str(klayout_tech_path))

    l2n = kf.kdb.LayoutToNetlist(c.begin_shapes_rec(0))
    for l_idx in c.kcl.layer_indices():
        l2n.connect(l2n.make_layer(l_idx, f"layer{l_idx}"))
    l2n.extract_netlist()
    return l2n


def get_netlist(gdspath, **kwargs) -> kdb.Netlist:
    """Returns the SPICE netlist of a GDS file.

    Args:
        gdspath: Path to the GDS file.

    Keyword Args:
        klayout_tech_path: Path to the klayout technology file.

    """
    l2n = get_l2n(gdspath=gdspath, **kwargs)
    netlist = l2n.netlist()
    return netlist.dup()


if __name__ == "__main__":
    from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

    from gplugins.common.config import PATH

    c = pads_correct()
    c = pads_shorted()
    gdspath = c.write_gds()
    c.show()

    l2n = get_l2n(gdspath)
    l2n.write_l2n(str(PATH.extra / f"{c.name}.txt"))

    # netlist = get_netlist(gdspath)
    # print(netlist)

    # graph = netlist_to_graph(netlist)
    # print(len(graph.nodes))

    # graph.edges(data=True)
    # plot_graph(graph)
