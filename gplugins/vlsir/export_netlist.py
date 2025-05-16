"""Uses VLSIRTools for converting between Klayout's DB Netlist format and other electrical schematic file formats.

- SPICE
- Spectre
- Xyce
- Verilog (Not supported yet).

Todo:
    - Add support for Verilog.
    - Thoroughly test the parser with more complex netlists.
"""

from collections.abc import Iterator
from io import StringIO
from itertools import count
from typing import Any

import vlsirtools
from klayout.db import (
    Circuit,  # Equivalent to Module
    # Pin, # Equivalent to Port
    Net,  # Equivalent to Signal
    Netlist,  # Equivalent to Package
    SubCircuit,  # Equivalent to Instance with a Reference Module
)
from vlsir.circuit_pb2 import (
    Connection,
    ConnectionTarget,
    Instance,
    Module,
    Package,
    Port,
    Signal,
)
from vlsir.utils_pb2 import Param, Reference

__SUPPORTED_FORMATS = ["spice", "spectre", "xyce", "verilog"]


def _lref(name: str) -> Reference:
    """Create a local `Reference` to a local `Module` with the given name."""
    return Reference(local=name)


def _connections(**kwargs: Any) -> list[Connection]:
    """Create a list of `Connection`s from keyword args of the form `portname=conn_target`, where `conn_target` is a `ConnectionTarget`."""
    return [Connection(portname=key, target=value) for key, value in kwargs.items()]


def _params(**kwargs: Any) -> list[Param]:
    """Create a list of `Param`s from keyword args of the form r=ParamValue(double_value=1e3)."""
    return [Param(name=key, value=value) for key, value in kwargs.items()]


def _temp_net(counter: Iterator[int]) -> str:
    """Return a new unique net name, Used for naming temporary nets."""
    return f"__temp_net_{next(counter)}__"


def _net_name(net: Net, counter: Iterator[int]) -> str:
    """Get the name of a `Net`."""
    if net.name is None:
        return _temp_net(counter)
    net_name = net.expanded_name()
    return net_name.replace("$", "")


def _instance_name(instance: SubCircuit, counter: Iterator[int]) -> str:
    """Get the name of a `SubCircuit` instance."""
    if instance.name is None:
        return _temp_net(counter)
    instance_name = instance.expanded_name()
    return instance_name.replace("$", "")


def _subcircuit_instance(
    instance: SubCircuit, counter: Iterator[int], **kwargs: Any
) -> Instance:
    """Create a new VLSIR Instance from the klayout.db SubCircuit and return it to include in the respective Module (SubCircuit)."""
    subckt_name = _instance_name(instance, counter)
    ref = instance.circuit_ref()
    num_pins = ref.pin_count()
    pin_nets = [instance.net_for_pin(pin_id) for pin_id in range(num_pins)]
    net_names = [_net_name(net, counter) for net in pin_nets]
    pin_names = [
        _net_name(ref.net_for_pin(pin_id), counter) for pin_id in range(num_pins)
    ]
    # pin_names = [_pin_name(ref.net_by_id(pin_id), counter) for pin_id in range(num_pins)]
    # get all parent
    # add the instance to the package's module
    return Instance(
        name=subckt_name,
        module=_lref(ref.name),
        parameters=_params(
            **{
                prop_name: instance.property(prop_name)
                for prop_name in instance.property_keys()
            }
        ),
        connections=_connections(
            **{
                pin_name: ConnectionTarget(sig=net_name)
                for pin_name, net_name in zip(pin_names, net_names)
            }
        ),
    )


def _circuit_module(
    circuit: Circuit, counter: Iterator[int], verbose: bool = False, **kwargs: Any
) -> Module:
    """Convert a Klayout DB `Circuit` to a VLSIR 'Module' and return it to include it in the package.

    Args:
        circuit: The Klayout DB `Circuit` to convert to a VLSIR `Module`.
        counter: A counter to keep track of the number of unique net names.
        verbose: Whether to print the generated VLSIR `Module` to stdout.
        **kwargs: Additional keyword arguments to pass to the VLSIR `Module` constructor.

    """
    name = circuit.name
    num_pins = circuit.pin_count()
    pin_nets = [circuit.net_for_pin(pin_id) for pin_id in range(num_pins)]
    pin_names = [_net_name(pin_net, counter) for pin_net in pin_nets]
    # get all subcircuits of the circuit to form its instances
    instances = [
        _subcircuit_instance(instance, counter)
        for instance in circuit.each_subcircuit()
    ]
    # FIXME: ports should have a direction, but that info is not accounted for here, rendering verilog parsing impossible
    ports = [Port(direction="NONE", signal=pin_name) for pin_name in pin_names]
    # add the circutit module's nets as signals to the Module
    signals = [
        Signal(name=_net_name(net, counter), width=1) for net in circuit.each_net()
    ]
    mod = Module(
        name=name,
        instances=instances,
        signals=signals,
        ports=ports,
        parameters=_params(
            **{
                prop_name: circuit.property(prop_name)
                for prop_name in circuit.property_keys()
            }
        ),
    )

    if verbose:
        print(mod)
    return mod


def kdb_vlsir(
    kdbnet: Netlist, domain: str, verbose: bool = False, **kwargs: Any
) -> Package:
    """Create a VLSIR `Package` circuit netlist from a KLayout DB `Netlist`.

    Args:
        kdbnet: The KLayout DB `Netlist` to convert to a VLSIR `Package`.
        domain: The domain of the VLSIR `Package`.
        verbose: Whether to print the generated VLSIR `Package` to stdout.
        **kwargs: Additional keyword arguments to pass to the VLSIR `Package` constructor.
    """
    _net_names_count = count()  # count the number of unique net names
    modules = [
        _circuit_module(circuit, _net_names_count, verbose=verbose)
        for circuit in kdbnet.each_circuit_bottom_up()
    ]
    return Package(domain=domain, modules=modules)


def export_netlist(pkg: Package, fmt: str = "spice", dest: Any = None) -> str:
    """Export a VLSIR `Package` circuit netlist to a string in the specified format.

    Args:
        pkg: The VLSIR `Package` to export.
        fmt: The format to export to. Supported formats are: "spice", "spectre", "xyce", "verilog".
        dest: The destination to write the exported netlist to. If None, a StringIO object is used.
    """
    if fmt not in __SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format {fmt} not in {__SUPPORTED_FORMATS}")
    if fmt == "verilog":
        raise NotImplementedError("Verilog export is not supported yet")
    if dest is None:
        dest = StringIO()
    return vlsirtools.netlist(pkg=pkg, dest=dest, fmt=fmt)


if __name__ == "__main__":
    from gdsfactory.samples.demo.lvs import pads_correct

    from gplugins.klayout.get_netlist import get_netlist

    format_to_suffix = {
        "spice": ".sp",
        "spectre": ".scs",
        "xyce": ".cir",
        "verilog": ".v",
    }

    c = pads_correct()
    gdspath = c.write_gds()

    # get the netlist
    kdbnetlist = get_netlist(gdspath)

    # convert it to a VLSIR Package
    pkg = kdb_vlsir(kdbnetlist, domain="gplugins.klayout.example")

    # export the netlist to the specified format
    out = StringIO()
    export_netlist(pkg, dest=out, fmt="spectre")
    print(out.getvalue())
