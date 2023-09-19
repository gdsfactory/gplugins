import re
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx


def plot_nets(filepath: str | Path) -> None:
    """Plots the connectivity between the components in the GDS file."""
    filepath = Path(filepath)
    code = filepath.read_text()
    names = re.findall(r"name\('([\w,]+)'\)", code)

    # Creating a graph for the connectivity
    G_connectivity = nx.Graph()

    # Adding nodes and edges based on names
    for name_group in names:
        individual_names = name_group.split(",")
        for i in range(len(individual_names)):
            for j in range(i + 1, len(individual_names)):
                G_connectivity.add_edge(individual_names[i], individual_names[j])

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
