import itertools
import re
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx


def plot_nets(filepath: str | Path, fully_connected: bool = False) -> None:
    """Plots the connectivity between the components in the GDS file.

    Args:
        filepath: Path to the GDS file.
        fully_connected: Whether to plot the graph as elements fully connected to all other ones (True) or
            going through other elements (False).
    """
    filepath = Path(filepath)
    code = filepath.read_text()
    names = re.findall(r"name\('([\w,]+)'\)", code)

    # Creating a graph for the connectivity
    G_connectivity = nx.Graph()

    # Adding nodes and edges based on names
    for name_group in names:
        individual_names = name_group.split(",")
        if fully_connected:
            G_connectivity.add_edges_from(itertools.combinations(individual_names, 2))
        else:
            G_connectivity.add_edges_from(
                zip(individual_names[:-1], individual_names[1:])
            )

    # Plotting the graph
    plt.figure(figsize=(8, 6))
    nx.draw(
        G_connectivity,
        with_labels=True,
        node_size=2000,
        node_color="lightpink",
        font_size=12,
    )
    plt.title("Connectivity")
    plt.show()


if __name__ == "__main__":
    from gdsfactory.samples.demo.lvs import pads_correct, pads_shorted

    from gplugins.common.config import PATH

    c = pads_correct()
    c = pads_shorted()
    c.show()

    path = PATH.extra / f"{c.name}.txt"
    plot_nets(path)
