import kfactory as kf
import klayout.db as kdb
import matplotlib.pyplot as plt
import networkx as nx
from gdsfactory.typings import PathType


def netlist_to_graph(netlist: str) -> nx.Graph:
    """Converts a SPICE netlist to a networkx graph."""
    G = nx.Graph()

    # Split the netlist into lines
    lines = netlist.split("\n")

    # For each line, parse the component and nodes
    for line in lines:
        tokens = line.split()
        if len(tokens) < 4:  # A valid line has at least 4 tokens
            continue

        component_name = tokens[0]
        node1 = tokens[1]
        node2 = tokens[2]
        value = tokens[3]

        # Add nodes and edge to the graph
        G.add_node(node1)
        G.add_node(node2)
        G.add_edge(node1, node2, name=component_name, value=value)

    return G


def plot_graph(G) -> None:
    """Plots a graph."""
    # Create a plot
    plt.figure(figsize=(10, 6))

    # Draw the nodes
    pos = nx.spring_layout(G)  # This provides a "good" layout for the graph
    nx.draw_networkx_nodes(G, pos, node_color="skyblue")

    # Draw the edges
    nx.draw_networkx_edges(G, pos)

    # Label the nodes
    nx.draw_networkx_labels(G, pos)

    # Label the edges with the component names
    edge_labels = {(u, v): G[u][v]["name"] for u, v in G.edges()}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

    plt.title("SPICE Netlist Graph")
    plt.axis("off")  # Turn off the axis
    plt.show()


def get_netlist(gdspath, klayout_tech_path: PathType | None = None) -> str:
    """Returns the SPICE netlist of a GDS file.

    Args:
        gdspath: Path to the GDS file.
        klayout_tech_path: Path to the klayout technology file.

    TODO: use klayout python API to define connectivity through PDK.
    """
    lib = kf.kcell.KCLayout()
    lib.read(filename=str(gdspath))
    c = lib[0]

    if klayout_tech_path:
        technology = kdb.Technology()
        technology.load(str(klayout_tech_path))

    l2n = kf.kdb.LayoutToNetlist(c.begin_shapes_rec(0))
    for l_idx in c.kcl.layer_indices():
        l2n.connect(l2n.make_layer(l_idx, f"layer{l_idx}"))
    l2n.extract_netlist()
    return l2n.netlist().to_s()


if __name__ == "__main__":
    from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

    c = pads_correct()
    c = pads_shorted()
    gdspath = c.write_gds()
    netlist = get_netlist(gdspath)

    graph = netlist_to_graph(netlist)
    print(len(graph.nodes))
    c.show()

    # graph.edges(data=True)
    # plot_graph(graph)
