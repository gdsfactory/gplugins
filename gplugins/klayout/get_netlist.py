from typing import Any

import gdsfactory as gf
import kfactory as kf
import klayout.db as kdb
from gdsfactory.typings import PathType

from gplugins.common.config import PATH


def get_l2n(
    gdspath: PathType,
    klayout_tech_path: PathType | None = None,
    include_labels: bool = True,
) -> kdb.LayoutToNetlist:
    """Get the layout to netlist object from a given GDS and klayout technology file.

    Args:
        gdspath: Path to the GDS file.
        klayout_tech_path: Path to the klayout technology file.
        include_labels: Whether to include labels in the netlist connected as individual nets.

    Returns:
        kdb.LayoutToNetlist: The layout to netlist object.

    """
    lib = kf.KCLayout(str(gdspath))
    Tech = kdb.Technology()

    tech_dir = PATH.klayout
    tech_dir.mkdir(exist_ok=True, parents=True)
    if not klayout_tech_path:
        gf.get_active_pdk().klayout_technology.write_tech(tech_dir)
        klayout_tech_path = tech_dir / "tech.lyt"

    # klayout tech path is now assumed to contain a `tech.lyt`` file to use
    Tech.load(str(klayout_tech_path))
    technology = Tech

    lib.read(filename=str(gdspath))
    c = lib.top_kcell()

    l2n = kf.kdb.LayoutToNetlist(c.begin_shapes_rec(0))
    l2n.threads = kf.config.n_threads

    reversed_layer_map = {}
    layers = gf.get_active_pdk().layers
    assert layers is not None

    # Reversed layer map with names as sets in order to support layer aliases
    for k, v in {layer.name: (layer.layer, layer.datatype) for layer in layers}.items():
        reversed_layer_map[v] = reversed_layer_map.get(v, set()) | {k}

    # define stack connections through vias
    layer_connection_iter = [
        [
            (connection.layer_a(), connection.via_layer(), connection.layer_b())
            for connection in connectivity.each_connection()
        ]
        for connectivity in technology.component("connectivity").each()
    ]
    layer_connection_iter = layer_connection_iter[0] if layer_connection_iter else []
    correct_layer_names = set(sum(layer_connection_iter, ()))

    # label locations on the connected layers on a special layer
    labels = kdb.Texts(c.begin_shapes_rec(0))
    # define the layers to be extracted
    for l_idx in c.kcl.layer_indexes():
        layer_info = c.kcl.get_info(l_idx)
        names = reversed_layer_map[(layer_info.layer, layer_info.datatype)]
        try:
            same_name_as_in_connections = next(iter(correct_layer_names & names))
        except StopIteration:
            same_name_as_in_connections = next(iter(names))
        l2n.connect(l2n.make_layer(l_idx, same_name_as_in_connections))
        if include_labels:
            l2n.connect(
                l2n.make_layer(l_idx, f"{same_name_as_in_connections}_LABELS"), labels
            )

    for layer_a, layer_via, layer_b in (
        (l2n.layer_by_name(layer) for layer in layers)
        for layers in layer_connection_iter
    ):
        # Don't try to connect Nones
        if all((layer_a, layer_via)):
            l2n.connect(layer_a, layer_via)
        if all((layer_b, layer_via)):
            l2n.connect(layer_via, layer_b)

    l2n.extract_netlist()
    return l2n


def get_netlist(
    gdspath: PathType,
    **kwargs: Any,
) -> kdb.Netlist:
    """Returns the SPICE netlist from a given GDS and klayout technology file.

    Args:
        gdspath: Path to the GDS file.
        kwargs: kwargs for get_l2n

    Returns:
        kdb.Netlist: The SPICE netlist of the GDS file.
    """
    l2n = get_l2n(gdspath=gdspath, **kwargs)
    netlist = l2n.netlist()
    return netlist.dup()


if __name__ == "__main__":
    from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

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
