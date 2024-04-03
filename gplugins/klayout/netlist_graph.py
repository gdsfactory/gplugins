import itertools
from pathlib import Path
from typing import Optional, Type

import klayout.db as kdb
import networkx as nx
from gdsfactory.config import logger

from gplugins.klayout.netlist_spice_reader import CalibreSpiceReader


def _get_device_name(device: kdb.Device) -> str:
    """Get a unique name for a ``Device`` instance."""
    return f"{device.device_class().name}_{device.expanded_name()}"


def netlist_to_networkx(
    netlist: kdb.Netlist,
    include_labels: bool = True,
    only_most_complex: bool = False,
    spice_reader_instance: kdb.NetlistSpiceReaderDelegate | None = None,
) -> nx.Graph:
    """Convert a KLayout DB `Netlist` to a networkx graph.

    Args:
        netlist: The KLayout DB `Netlist` to convert to a networkx `Graph`.
        include_labels: Whether to include net labels in the graph connected to corresponding cells.
        only_most_complex: Whether to plot only the circuit with most connections or not.
            Helpful for not plotting subcircuits separately.
        spice_reader_instance: The KLayout Spice reader that was used for parsing SPICE netlists.
            Used for fetching string parameter values from a stored mapping.

    Returns:
        A networkx `Graph` representing the connectivity of the `Netlist`.
    """
    G = nx.Graph()

    top_circuits = list(
        itertools.islice(netlist.each_circuit_top_down(), netlist.top_circuit_count())
    )

    if only_most_complex:
        top_circuits = (max(top_circuits, key=lambda x: x.pin_count()),)

    all_used_nets = set()
    for circuit in top_circuits:
        for device in circuit.each_device():
            # Gather properties of Device class
            device_class = device.device_class()
            parameter_definitions = device_class.parameter_definitions()
            terminal_definitions = device_class.terminal_definitions()

            # Gather values for specific Device instance
            parameters = {
                parameter.name: (
                    device.parameter(parameter.name)
                    if not spice_reader_instance
                    else spice_reader_instance.integer_to_string_map.get(
                        device.parameter(parameter.name),
                        device.parameter(parameter.name),
                    )
                )
                for parameter in parameter_definitions
            }
            nets = [
                device.net_for_terminal(terminal.name)
                for terminal in terminal_definitions
            ]
            device_name = _get_device_name(device)

            # Create NetworkX representation
            G.add_node(device_name, **parameters)
            for net in nets:
                net_name = net.expanded_name()
                G.add_edge(device_name, net_name)
                all_used_nets.add(net_name)

    if not include_labels:
        for node in all_used_nets:
            connections = list(G.neighbors(node))
            G.add_edges_from(itertools.combinations(connections, r=2))
            G.remove_node(node)

    return G


def networkx_from_file(
    filepath: str | Path,
    include_labels: bool = True,
    only_most_complex: bool = False,
    spice_reader: type[kdb.NetlistSpiceReaderDelegate] = CalibreSpiceReader,
    **kwargs,
) -> nx.Graph:
    """Returns a networkx Graph from a SPICE netlist file or KLayout LayoutToNetlist.
    Args:
        filepath: Path to the KLayout LayoutToNetlist file or a SPICE netlist.
            File extensions should be `.l2n` and `.spice`, respectively.
        include_labels: Whether to include labels in the graph connected to corresponding cells.
        only_most_complex: Whether to plot only the circuit with most connections or not.
            Helpful for not plotting subcircuits separately.
        spice_reader: The KLayout Spice reader to use for parsing SPICE netlists.
    """
    spice_reader_instance = None
    match Path(filepath).suffix:
        case ".l2n" | ".txt":
            l2n = kdb.LayoutToNetlist()
            l2n.read(str(filepath))
            netlist = l2n.netlist()
        case ".cir" | ".sp" | ".spi" | ".spice":
            reader = kdb.NetlistSpiceReader(spice_reader_instance := spice_reader())
            netlist = kdb.Netlist()
            netlist.read(str(filepath), reader)
        case _:
            logger.warning("Assuming file is KLayout native LayoutToNetlist file")
            l2n = kdb.LayoutToNetlist()
            l2n.read(str(filepath))
            netlist = l2n.netlist()

    # Creating a graph for the connectivity
    return netlist_to_networkx(
        netlist,
        include_labels=include_labels,
        only_most_complex=only_most_complex,
        spice_reader_instance=spice_reader_instance,
    )
