from collections.abc import Collection
from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
from gdsfactory.typings import PathType
from klayout.db import NetlistSpiceReaderDelegate
from matplotlib.figure import Figure

from gplugins.klayout.netlist_graph import networkx_from_spice
from gplugins.klayout.netlist_spice_reader import (
    GdsfactorySpiceReader,
)


def plot_nets(
    filepath: PathType,
    interactive: bool = False,
    include_labels: bool = True,
    top_cell: str | None = None,
    nodes_to_reduce: Collection[str] | None = None,
    spice_reader: type[NetlistSpiceReaderDelegate] = GdsfactorySpiceReader,
) -> None | Figure:
    """Plots the connectivity between the components in the KLayout LayoutToNetlist file from :func:`~get_l2n`.

    Args:
        filepath: Path to the KLayout LayoutToNetlist file or a SPICE netlist.
            File extensions should be `.l2n` and `.spice`, respectively.
        interactive: Whether to plot an interactive graph with `pyvis` or not.
        include_labels: Whether to include net labels in the graph connected to corresponding cells.
        top_cell: The name of the top cell to consider for the NetworkX graph. Defaults to all top cells.
        nodes_to_reduce: Nodes to reduce to a single edge. Comparison made with Python ``in`` operator.
            Helpful for reducing trivial waveguide elements.
        spice_reader: The KLayout Spice reader to use for parsing SPICE netlists.
    """
    G_connectivity = networkx_from_spice(
        filepath=filepath,
        include_labels=include_labels,
        top_cell=top_cell,
        spice_reader=spice_reader,
    )

    if nodes_to_reduce:

        def _removal_condition(node: str, degree: int) -> bool:
            return degree == 2 and any(e in node for e in nodes_to_reduce)

        while any(
            _removal_condition(node, degree) for node, degree in G_connectivity.degree
        ):
            G_connectivity_tmp = G_connectivity.copy()
            for node, degree in G_connectivity.degree:
                if _removal_condition(node, degree):
                    connected_to_node = [e[1] for e in G_connectivity.edges(node)]
                    node_pairs_to_connect = list(combinations(connected_to_node, r=2))
                    for pair in node_pairs_to_connect:
                        G_connectivity_tmp.add_edge(pair[0], pair[1])
                    G_connectivity_tmp.remove_node(node)
                    break
            G_connectivity = G_connectivity_tmp

    # Plotting the graph
    if interactive:
        try:
            from pyvis.network import Network
        except ModuleNotFoundError as e:
            raise UserWarning(
                "You need to `pip install pyvis<=0.3.1` or `gplugins[klayout]`"
            ) from e

        net = Network(
            select_menu=True,
            filter_menu=True,
        )
        net.show_buttons()
        net.from_nx(G_connectivity)
        net.show("connectivity.html")
    else:
        color_nets = [
            "lightblue"
            if G_connectivity.nodes[node].get("is_net", False)
            else "lightpink"
            for node in G_connectivity.nodes()
        ]

        fig = plt.figure(figsize=(8, 6))
        nx.draw(
            G_connectivity,
            with_labels=True,
            node_size=2000,
            node_color=color_nets,
            font_size=12,
        )
        return fig
    return


if __name__ == "__main__":
    from gdsfactory.config import PATH as GPATH
    from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

    from gplugins.common.config import PATH
    from gplugins.klayout.get_netlist import get_l2n

    c = pads_correct()
    c = pads_shorted()
    c.show()

    gdspath = c.write_gds(PATH.extra / "pads.gds")

    l2n = get_l2n(gdspath, klayout_tech_path=GPATH.klayout_lyt)
    path = PATH.extra / f"{c.name}.txt"
    l2n.write_l2n(str(path))

    plot_nets(path)
    plt.show()
