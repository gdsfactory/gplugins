""" 
Parcirc: A parser leveraging Dan Fritchman's 
VLSIRTools for converting between 
Klayout's DB Netlist format and other 
electrical schematic file formats:
- SPICE
- Spectre
- Xyce
- Verilog (Not supported yet)

Author: Diogo Andre <das.dias@campus.fct.unl.pt>
Date: Sun, 03-09-2023

TODO:
    - Add support for Verilog
    - Thoroughly test the parser with more complex netlists
"""

import pathlib
from itertools import count

from io import StringIO
from typing import List

from gplugins.verification.get_netlist import get_netlist
from klayout.db import (
    #Pin, # Equivalent to Port
    Net, # Equivalent to Signal
    Netlist, # Equivalent to Package
    Circuit, # Equivalent to Module
    SubCircuit, # Equivalent to Instance witha Reference Module
)

from gdsfactory.typings import PathType

import vlsir.utils_pb2 as vutils
from vlsir.utils_pb2 import Reference, QualifiedName, ParamValue, Param
import vlsir.circuit_pb2 as vckt
from vlsir.circuit_pb2 import (
    ExternalModule,
    Module,
    Signal,
    Connection,
    ConnectionTarget,
    Port,
    Instance,
    Package,
    SpiceType,
)

import vlsir.spice_pb2 as vsp

import vlsirtools
from vlsirtools.spice import (
    SupportedSimulators,
    SimOptions,
    ResultFormat,
    sim,
)

__SUPPORTED_FORMATS = ["spice", "spectre", "xyce", "verilog"]

def _lref(name) -> Reference:
    """Create a local `Reference` to a local `Module` with the given name."""
    return Reference(local=name)

def _connections(**kwargs) -> List[Connection]:
    """Create a list of `Connection`s from keyword args of the form `portname=conn_target`, where `conn_target` is a `ConnectionTarget`."""
    return [Connection(portname=key, target=value) for key, value in kwargs.items()]

def _params(**kwargs) -> List[Param]:
    """Create a list of `Param`s from keyword args of the form
    `r=ParamValue(double_value=1e3)`"""
    return [Param(name=key, value=value) for key, value in kwargs.items()]

def _temp_net(counter) -> str:
    """Return a new unique net name, Used for naming temporary nets."""
    return f"__temp_net_{next(counter)}__"

def _net_name(net: Net, counter) -> str:
    """Get the name of a `Net`"""
    if net.name is None:
        return _temp_net(counter)
    net_name = net.expanded_name()
    return net_name.replace('$', '')

def _instance_name(instance: SubCircuit, counter) -> str:
    """Get the name of a `SubCircuit` instance"""
    if instance.name is None:
        return _temp_net(counter)
    instance_name = instance.expanded_name()
    return instance_name.replace('$', '')

def _subcircuit_instance(instance: SubCircuit, counter, **kwargs) -> Instance:
    """Create a new VLSIR Instance from the klayout.db SubCircuit and return it to include in the respective Module (SubCircuit)."""
    subckt_name = _instance_name(instance, counter)
    ref = instance.circuit_ref()
    num_pins = ref.pin_count()
    pin_nets = [instance.net_for_pin(pin_id) for pin_id in range(num_pins)]
    net_names = [_net_name(net, counter) for net in pin_nets]
    pin_names = [_net_name(ref.net_for_pin(pin_id), counter) for pin_id in range(num_pins)]
    #pin_names = [_pin_name(ref.net_by_id(pin_id), counter) for pin_id in range(num_pins)]
    # get all parent 
    # add the instance to the package's module
    inst = Instance(
        name=subckt_name,
        module=_lref(ref.name),
        parameters=_params(**{
            prop_name: instance.property(prop_name) for prop_name in instance.property_keys()
        }),
        connections=_connections(**{
            pin_name: ConnectionTarget(sig=net_name) for pin_name, net_name in zip(pin_names,net_names)
        })
    )
    return inst

def _circuit_module(circuit: Circuit, counter, verbose: bool = False, **kwargs)->Module:
    """Convert a Klayout DB `Circuit` to a VLSIR 'Module' and return it to include it in the package."""
    name = circuit.name
    num_pins = circuit.pin_count()
    pin_nets = [circuit.net_for_pin(pin_id) for pin_id in range(num_pins)]
    pin_names = [_net_name(pin_net,counter) for pin_net in pin_nets]
    # get all subcircuits of the circuit to form its instances
    instances = [_subcircuit_instance(instance, counter) for instance in circuit.each_subcircuit()]    
    # FIXME: ports should have a direction, but that info is not accounted for here, rendering verilog parsing impossible
    ports = [Port(direction="NONE", signal=pin_name) for pin_name in pin_names]
    # add the circutit module's nets as signals to the Module
    signals = [Signal(name=_net_name(net, counter), width=1) for net in circuit.each_net()]
    mod = Module(
        name=name,
        instances=instances,
        signals=signals,
        ports=ports,
        parameters=_params(**{
            prop_name: circuit.property(prop_name) for prop_name in circuit.property_keys()
        })
    )
    
    if verbose: print(mod)
    return mod

def kdb_vlsir(kdbnet: Netlist, domain: str, verbose:bool = False, **kwargs) -> Package:
    """Create a VLSIR `Package` circuit netlist from a KLayout DB `Netlist`"""
    _net_names_count = count() # count the number of unique net names
    modules = [_circuit_module(circuit, _net_names_count, verbose=verbose) for circuit in kdbnet.each_circuit_bottom_up()]
    return Package(domain=domain, modules=modules)
    
def export_netlist(pkg: Package, fmt: str = "spice", dest = None) -> str:
    """Export a VLSIR `Package` circuit netlist to a string in the specified format"""
    assert fmt in __SUPPORTED_FORMATS, f"Unsupported format {fmt}"
    if fmt == "verilog": raise NotImplementedError("Verilog export is not supported yet")
    if dest is None:
        dest = StringIO()
    return vlsirtools.netlist(pkg=pkg, dest=dest, fmt=fmt)

#! Example usage -----
if __name__ == "__main__":
    
    import argparse
    
    format_to_suffix = {
        "spice": ".sp",
        "spectre": ".scs",
        "xyce": ".cir",
        "verilog": ".v"
    }
    
    parser = argparse.ArgumentParser(description="Convert a GDS file's extracted Netlist to a Electrical Schematic netlist", prog="parcirc")
    parser.add_argument("gds", type=str, help="Path to the GDS file")
    parser.add_argument("-o", "--out", type=str, default=None, help="Path to the output file. If not specified, the netlist is printed to stdout.")
    parser.add_argument("-f", "--format", type=str, default="spice", help="Format of the output file. Supported formats are: " + ", ".join(__SUPPORTED_FORMATS))
    args = parser.parse_args()
    gds = args.gds
    outpath = args.out
    # freate file IO object for the output
    if outpath is None:
        out = StringIO()
    else:
        assert args.format in format_to_suffix, f"Unsupported format {args.format}"
        extension = pathlib.Path(outpath).suffix
        assert extension == format_to_suffix[args.format], f"Output file {outpath} does not have the correct extension for format {args.format}"
    fmt = args.format
    # get the netlist
    kdbnet = get_netlist(gds)
    # convert it to a VLSIR Package
    pkg = kdb_vlsir(kdbnet, domain="gplugins.verification.example")
    # export the netlist to the specified format
    with open(outpath, "w") as out:
        export_netlist(pkg, dest=out, fmt=fmt)
    print(f"Netlist exported to {outpath}")
    
