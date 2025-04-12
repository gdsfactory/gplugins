import itertools
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import klayout.db as kdb
import networkx as nx
from gdsfactory import logger
from gdsfactory.typings import PathType
from klayout.db import NetlistSpiceReaderDelegate

import gplugins.vlsir
from gplugins.klayout.netlist_spice_reader import (
    GdsfactorySpiceReader,
    NetlistSpiceReaderDelegateWithStrings,
)


def _get_device_name(device: kdb.Device) -> str:
    """Get a unique name for a ``Device`` instance."""
    return f"{device.device_class().name}_{device.expanded_name()}"


def netlist_to_networkx(
    netlist: kdb.Netlist,
    include_labels: bool = True,
    top_cell: str | None = None,
    spice_reader_instance: NetlistSpiceReaderDelegateWithStrings | None = None,
) -> nx.Graph:
    """Convert a KLayout DB `Netlist` to a networkx graph.

    Args:
        netlist: The KLayout DB `Netlist` to convert to a NetworkX `Graph`.
        include_labels: Whether to include net labels in the graph connected to corresponding cells.
        top_cell: The name of the top cell to consider for the NetworkX graph. Defaults to all top cells.
        spice_reader_instance: The KLayout Spice reader that was used for parsing SPICE netlists.
            Used for fetching string parameter values from a stored mapping.

    Returns:
        A networkx `Graph` representing the connectivity of the `Netlist`.
    """
    G = nx.Graph()
    netlist.flatten()

    top_circuits = list(
        itertools.islice(netlist.each_circuit_top_down(), netlist.top_circuit_count())
    )

    if top_cell:
        try:
            top_circuits = (
                next(
                    c for c in top_circuits if c.name.casefold() == top_cell.casefold()
                ),
            )
        except StopIteration as e:
            available_top_cells = [cell.name for cell in top_circuits]
            raise ValueError(
                f"{top_cell=!r} not found in the netlist. Available top cells: {available_top_cells!r}"
            ) from e

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
                    spice_reader_instance.integer_to_string_map.get(
                        int(device.parameter(parameter.name)),
                        device.parameter(parameter.name),
                    )
                    if spice_reader_instance
                    else device.parameter(parameter.name)
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

    # Easier to set different colors for nets
    for net in all_used_nets:
        G.nodes[net]["is_net"] = True

    if not include_labels:
        for node in all_used_nets:
            connections = list(G.neighbors(node))
            G.add_edges_from(itertools.combinations(connections, r=2))
            G.remove_node(node)

    return G


def networkx_from_spice(
    filepath: PathType,
    include_labels: bool = True,
    top_cell: str | None = None,
    spice_reader: type[NetlistSpiceReaderDelegate]
    | NetlistSpiceReaderDelegate = GdsfactorySpiceReader,
    **kwargs: Any,
) -> nx.Graph:
    """Returns a networkx Graph from a SPICE netlist file or KLayout LayoutToNetlist.

    Args:
        filepath: Path to the KLayout LayoutToNetlist file or a SPICE netlist.
            File extensions should be `.l2n` and `.spice`, respectively.
        include_labels: Whether to include labels in the graph connected to corresponding cells.
        top_cell: The name of the top cell to consider for the NetworkX graph. Defaults to all top cells.
        spice_reader: The KLayout Spice reader to use for parsing SPICE netlists.
        kwargs: kwargs for spice_reader
    """
    spice_reader_instance = None
    match Path(filepath).suffix:
        case ".l2n" | ".txt":
            l2n = kdb.LayoutToNetlist()
            l2n.read(str(filepath))
            netlist = l2n.netlist()

            # Parsing is done for SPICE so first we export to SPICE with VLSIR
            pkg = gplugins.vlsir.kdb_vlsir(netlist, domain="gplugins.klayout.example")
            with NamedTemporaryFile("w+", suffix=".sp") as fp:
                gplugins.vlsir.export_netlist(pkg, dest=fp, fmt="spice")
                return networkx_from_spice(
                    fp.name,
                    include_labels=include_labels,
                    top_cell=top_cell,
                    spice_reader=spice_reader,
                    **kwargs,
                )

        case ".cir" | ".sp" | ".spi" | ".spice":
            reader = kdb.NetlistSpiceReader(
                spice_reader_instance := spice_reader()
                if isinstance(spice_reader, Callable)
                else spice_reader
            )
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
        top_cell=top_cell,
        spice_reader_instance=spice_reader_instance,
    )
