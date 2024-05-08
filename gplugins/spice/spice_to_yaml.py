import argparse
import os
import re
from pathlib import Path

import yaml

# DEFINITIONS
BASE_UNIT = "um"
if BASE_UNIT == "um":
    CONVERSION = {"u": 1, "n": 1e-3}
if BASE_UNIT == "nm":
    CONVERSION = {"u": 1e3, "n": 1}

ignored_info = (
    "sch_x",
    "sch_y",
    "sch_r",
    "sch_f",
    "lay_x",
    "lay_y",
    "MC_non_uniform",
    "MC_grid",
    "MC_resolution_x",
    "MC_resolution_y",
    "MC_uniformity_thickness",
    "MC_uniformity_width",
)


def main():
    # Turn this Python script into a command line tool that requires certain arguments
    parser = argparse.ArgumentParser(
        description="Lumerical INTERCONNECT to GDSFactory YAML netlist generator."
    )

    parser.add_argument(
        "working_directory",
        type=str,
        help="Working directory where YAML netlist will be saved.",
    )
    parser.add_argument(
        "mapping_file_name",
        type=str,
        help="Mapping file that maps models to layout cells [.yml].",
        default="mapping",
    )
    parser.add_argument(
        "mode",
        type=str,
        help="Mode for netlist export (overwrite or update), where overwrite is the [default]",
        nargs="?",
        default="overwrite",
    )
    parser.add_argument(
        "netlist_file_name",
        type=str,
        help="Netlist file name exported from INTC [.spi].",
        nargs="?",
        default="netlist",
    )
    args = parser.parse_args()

    ignore_electrical = False  # This flag ignores electrical routes and bundles

    # Error Handling for the python arguments
    map_flag = False
    try:
        netlist_path = os.path.join(
            args.working_directory, args.netlist_file_name + ".spi"
        )
        my_file = Path(netlist_path)
        if my_file.is_file():
            print(
                "LOG: "
                + args.netlist_file_name
                + ".spi file exists in the provided working directory."
            )
        else:
            raise Exception()
    except Exception:
        print(
            "LOG: Netlist file "
            + args.netlist_file_name
            + ".spi does not exist in the provided working directory. Flow will exit."
        )
        quit()
    try:
        mapping_path = os.path.join(
            args.working_directory, args.mapping_file_name + ".yml"
        )
        my_file = Path(mapping_path)
        if my_file.is_file():
            print(
                "LOG: "
                + args.mapping_file_name
                + ".yml file exists in the provided working directory."
            )
        else:
            raise Exception()
    except Exception:
        print(
            "LOG: YAML mapping file "
            + args.mapping_file_name
            + " does not exist in the provided path. Flow will use netlist to create mapping."
        )
        map_flag = True
        mapping_path = None
    try:
        mode = args.mode
        if (mode == "update") or (mode == "overwrite"):
            print("LOG: Mode is " + mode + ".")
        else:
            raise Exception()
    except Exception:
        print(
            "LOG: Mode should be either overwrite (default) or update. Flow will use default."
        )
        mode = "overwrite"

    if map_flag:
        libraries = []
        with open(netlist_path) as f:
            lines = f.readlines()
        for j in range(0, len(lines)):
            cmds = lines[j].strip().split(" ")
            for cmd in cmds:
                if cmd.startswith("library="):
                    libraries.append(cmd)
        libraries = list(dict.fromkeys(libraries))
        pdks = []
        if len(libraries) > 1:
            for libs in libraries:
                d_pdk = libs.strip()[11:-1]
                pdk = d_pdk.split("/")[1]
                pdks.append(pdk)
        else:
            d_pdk = libraries[0].strip()[11:-1]
            pdk = d_pdk.split("/")[1]
            pdks.append(pdk)
        print("LOG: PDKs are: " + ", ".join(str(x) for x in pdks))

        # Get netlists
        netlists = get_netlists(
            netlist_path, mapping_path, pdks[0], ignore_electrical, map_flag
        )
    else:
        # Get PDK from mapping file
        with open(mapping_path) as f:
            data = yaml.safe_load(f)
            try:
                pdk = data.get("pdk", "")
                print("LOG: PDKs are: " + pdk)

                # Get netlists
                netlists = get_netlists(
                    netlist_path, mapping_path, pdk, ignore_electrical, map_flag
                )
            except AttributeError:
                print("LOG: No PDKs available in mapping file. Checking the netlist.")
                libraries = []
                with open(netlist_path) as f:
                    lines = f.readlines()
                for j in range(0, len(lines)):
                    cmds = lines[j].strip().split(" ")
                    for cmd in cmds:
                        if cmd.startswith("library="):
                            libraries.append(cmd)
                libraries = list(dict.fromkeys(libraries))
                pdks = []
                if len(libraries) > 1:
                    for libs in libraries:
                        d_pdk = libs.strip()[11:-1]
                        pdk = d_pdk.split("/")[1]
                        pdks.append(pdk)
                else:
                    d_pdk = libraries[0].strip()[11:-1]
                    pdk = d_pdk.split("/")[1]
                    pdks.append(pdk)
                print("LOG: PDKs are: " + ", ".join(str(x) for x in pdks))

                # Get netlists
                netlists = get_netlists(
                    netlist_path, mapping_path, pdks[0], ignore_electrical, map_flag
                )
    # Export netlists
    if mode == "overwrite":
        # This mode overwrites all YAML files in working directory
        for netlist in netlists:
            if pdk:
                netlist["pdk"] = pdk
            with open(
                os.path.join(os.path.dirname(__file__), f'{netlist["name"]}.pic.yml'),
                "w",
            ) as f:
                yaml.dump(netlist, f)
        print("LOG: overwrite done.")
    elif mode == "update":
        # This mode updates YAML files in working directory and leaves the placement of the cells intact
        for netlist in netlists:
            filename = os.path.join(
                args.working_directory, f'{netlist["name"]}.pic.yml'
            )
            if os.path.exists(filename):
                with open(filename, "w") as f:
                    # Get existing netlist
                    file_netlist = yaml.safe_load(f)
                    # Overwrite pdk, name, instances, routes, default settings, and info
                    if pdk:
                        file_netlist["pdk"] = pdk
                    file_netlist["name"] = netlist["name"]
                    if netlist.get("default_settings", {}):
                        file_netlist["default_settings"] = netlist["default_settings"]
                    if netlist.get("info", {}):
                        file_netlist["info"] = netlist["info"]
                    file_netlist["instances"] = netlist["instances"]
                    file_netlist["routes"] = netlist["routes"]
                    if "ports" in netlist:
                        file_netlist["ports"] = netlist["ports"]
                    # Overwrite part of placements if new instance(s) are created
                    for inst, placement in netlist["placements"].items():
                        if inst not in file_netlist["placements"]:
                            file_netlist["placements"][inst] = placement
                    # Write to file
                    yaml.dump(file_netlist, f)
        print("LOG: update done.")


def get_netlists(
    netlist_path: str,
    mapping_path: str,
    pdk: str,
    ignore_electrical: bool,
    map_flag: str,
    ignored_info: tuple[str, ...] = ignored_info,
) -> list:
    """
    Get netlists from SPICE netlist and mapping file

    Args:
        netlist_path: Path to SPICE netlist (.spi).
        mapping_path: Path to YAML mapping file (.yml).
        pdk: Process design kit name.
        ignore_electrical: Flag to ignore electrical routes and bundles.
        map_flag: Flag to create mapping from netlist.

    Returns:
        ctks: YAML ready netlists. Example of data structure:
                [
                    {
                        'name': 'TOP' (str),
                        'pdk': 'ubcpdk' (str),
                        'instances':
                        {
                            'instance_name_0' (str):
                            {
                                'component': 'layout_cell_name_0' (str),
                                'settings':
                                {
                                    'param_name_0': param_val_0 (float or int),
                                    'param_name_1': param_val_1 (float or int)
                                }
                                'info':
                                {
                                    'info_name_0': info_0 (any type),
                                    'info_name_1': info_1 (any type)
                                }
                            },
                            .
                            .
                        },
                        'placements':
                        {
                            'instance_name_0' (str):
                            {
                                'rotation': 0.0 (float),
                                'mirror': False (bool),
                                'x': 75.0 (float),
                                'y': 0.0 (float)
                            },
                            .
                            .
                        }
                        'routes':
                        {
                            'electrical_bundle_0':
                            {
                                'links':
                                {
                                    'instance_name_0,port1': 'instance_name_1,port1',
                                    'instance_name_0,port2': 'instance_name_1,port2'
                                }
                            },
                            'optical_bundle_0':
                            {
                                'links':
                                {
                                    'instance_name_0,port4': 'instance_name_1,port4',
                                    'instance_name_0,port5': 'instance_name_1,port5'
                                }
                            },
                            .
                            .
                        }

                    },
                    {
                        'name': 'COMPOUND_1'
                        'pdk': 'ubcpdk' (str),
                        'default_settings':
                        {
                            'param_name_0':
                            {
                                'value': param_val_0 (float)
                            },
                            .
                            .
                        }
                        'info':
                        {
                            'info_0': info (any type),
                            .
                            .
                        }
                        'instances':
                        {
                            'instance_name_0' (str):
                            {
                                'component': 'layout_cell_name_0' (str),
                                'settings':
                                {
                                    'param_name_0': param_val_0 (float or int),
                                    'param_name_1': param_val_1 (float or int)
                                }
                                'info':
                                {
                                    'info_name_0': info_0 (any type),
                                    'info_name_1': info_1 (any type)
                                }
                            },
                            .
                            .
                        },
                        'placements':
                        {
                            'instance_name_0' (str):
                            {
                                'rotation': 0.0 (float),
                                'mirror': False (bool),
                                'x': 75.0 (float),
                                'y': 0.0 (float)
                            },
                            .
                            .
                        },
                        'ports':
                        {
                            'port 1': 'instance_name_0,port1',
                            'port 2': 'instance_name_1,port2',
                            .
                            .
                        }
                        'routes':
                        {
                            'electrical_bundle_0':
                            {
                                'links':
                                {
                                    'instance_name_0,port1': 'instance_name_1,port1',
                                    'instance_name_0,port2': 'instance_name_1,port2'
                                }
                            },
                            'optical_bundle_0':
                            {
                                'links':
                                {
                                    'instance_name_0,port4': 'instance_name_1,port4',
                                    'instance_name_0,port5': 'instance_name_1,port5'
                                }
                            },
                            .
                            .
                        }
                    },
                    .
                    .
                ]
    """
    if not map_flag:
        with open(mapping_path) as f:
            mapping = yaml.safe_load(f)
            try:
                mapping["models"]
            except KeyError:
                mapping = create_mapping_from_netlist(netlist_path, pdk)
            except TypeError:
                mapping = create_mapping_from_netlist(netlist_path, pdk)
    else:
        mapping = create_mapping_from_netlist(netlist_path, pdk)

    with open(netlist_path) as f:
        lines = f.read()

    # Get models
    models = get_models(netlist_path, ignored_info)

    # Find all matches in the input string
    pattern = r"\.subckt\s+(\w+)\s+(.*?)\s*\.ends\s+\1"
    matches = re.findall(pattern, lines, re.DOTALL)

    # Extract the strings between ".subckt" and ".ends"
    ctks = []
    for match in matches:
        # Build subcircuit dicts
        ctk = {}
        instances = get_instances(match[1], models)
        ctk["name"] = match[0]
        if ctk["name"] in models and models[ctk["name"]]["expandable"]:
            ctk["default_settings"] = {
                param_name: {"value": param_val}
                for param_name, param_val in models[ctk["name"]]["params"].items()
                if param_name not in ignored_info
            }
            ctk["info"] = {
                param_name: {"value": param_val}
                for param_name, param_val in models[ctk["name"]]["params"].items()
                if param_name not in ignored_info
                and param_name not in ctk["default_settings"]
            }
        ctk["instances"] = get_instances_info(
            instances, mapping["models"], ignore_electrical, ignored_info
        )
        ctk["placements"] = get_placements(
            instances, mapping["models"], ignore_electrical
        )
        ctk["ports"] = get_ports(
            match[1], instances, models[match[0]], mapping["models"]
        )
        ctk["routes"] = get_routes(
            instances, mapping["models"], mapping["layers"], ignore_electrical
        )
        ctks.append(ctk)

    # Get top circuit
    topctk = {}
    instances = get_instances(get_topctk(netlist_path), models)
    topctk["name"] = "TOP"
    topctk["instances"] = get_instances_info(
        instances, mapping["models"], ignore_electrical, ignored_info
    )
    topctk["placements"] = get_placements(
        instances, mapping["models"], ignore_electrical
    )
    topctk["routes"] = get_routes(
        instances, mapping["models"], mapping["layers"], ignore_electrical
    )
    ctks.append(topctk)
    return ctks


def create_mapping_from_netlist(netlist_path: str, pdk: str) -> list:
    """
    Create the mapping dictionary from the netlist file

    Args:
        netlist_path: Path to SPICE netlist (.spi).
        pdk: Process design kit name.

    Returns:
        mapping: Mapping between models and layout cells. Example data structure:
                    {
                        'pdk': 'name_of_pdk',
                        'models':
                        {
                            'compact_model_name_0':
                            {
                                'layout_cell': 'layout_cell_name_0',
                                'ports':
                                {
                                    'compact_model_port_0': 'layout_cell_port_0',
                                    'compact_model_port_1': 'layout_cell_port_1',
                                    .
                                    .
                                }
                            },
                            .
                            .
                        }
                    }
    """
    mapping = {}
    mapping["pdk"] = pdk
    with open(netlist_path) as f:
        lines = f.readlines()
    models = {}
    for j in range(0, len(lines)):
        count = 0
        model = {}
        ports = {}
        if lines[j].strip().startswith("*#"):
            instance = lines[j].strip()[3:].split(" ")
            for port in instance[1:]:
                if ("opt_" in port) or ("port" in port):
                    count += 1
            if count > 0:
                name = instance[0]
                layout_cell = name
                for port in instance[1:]:
                    pt = port[0:-5]
                    ports[pt] = pt
                model["layout_cell"] = layout_cell
                model["ports"] = ports
                models[name] = model
    mapping["models"] = models

    ### REMOVE hardcode
    if pdk == "ctpdk" or pdk == "compoundtek_pdk_v3":
        mapping["layers"] = {
            "optical_route": {"layer": "HMWG", "params": {"radius": 15}},
            "electrical_route": {
                "layer": "PADAL",
                "params": {"width": 50, "separation": 20, "bend": "wire_corner"},
            },
        }
    if pdk == "ubcpdk" or pdk == "ebeam":
        mapping["layers"] = {
            "optical_route": {"layer": "Waveguide", "params": {"radius": 15}},
            "electrical_route": {
                "layer": "M2_ROUTER",
                "params": {"width": 50, "separation": 20, "bend": "wire_corner"},
            },
        }
    return mapping


def get_instances(netlist: str, models: dict) -> list:
    """
    Get instances with all info on instance

    Args:
        netlist: SPICE netlist
        models: Models with associated model info
                Ex. {'model_name1':
                        {
                            'params': {'param_name1': param_val1, 'param_name2': param_val2, ...},
                            'ports': ['port1', 'port2', ...],
                            'port_types: ['optical', 'electrical', ...],
                            'expandable': True or False,
                        }
                        .
                        .
                    }

    Returns:
        instances: Instances with model params, nets, ports, names, and models. Each entry in list has instance data structure:
                    {
                        'name': 'X_dc_0' instance_name (str),
                        'model': 'ebeam_dc_te1550' compact model name (str),
                        'ports': ['port 1', 'port 2', port 3'] name of ports ordered in a list (list of str),
                        'port_types': ['optical', 'electrical', 'optical']type of port i.e. electrical or optical, ordered in a list (list of str),
                        'expandable': True if instance is compound element, else False (bool)
                        'nets': ['PORT 1', 'N$1', 'N$2'] nets connected to ports in this order (list of str)
                        'params':
                        {
                            'param_name_0': param_val (any type),
                            'param_name_1': param_val (any type)
                            .
                            .
                        }
                    }
    """
    grouped_instances = group_instance_str(netlist)
    instances = []
    non_pdk = []
    model_names = []
    for model in models:
        model_names.append(str(model))
    for inst_line in grouped_instances:
        instance = {}
        # Get preamble before parameters (instance name, nets, model name)
        fields = inst_line.split(" ")
        instance["name"] = fields[0]

        # Get params using regular expressions
        pattern = r'(\w+|"[^"]*")\s*=\s*({.*?}|-[0-9.]+|[0-9.]+|f+|y+|x+|"[^"]*")'
        matches = re.findall(pattern, inst_line)

        # Get fields before params
        preamble = inst_line.split(matches[0][0])[0].strip().split(" ")

        # Get model name
        model_name = preamble[-1]
        if model_name not in model_names:
            a = inst_line.find('"') + 1
            b = inst_line.find('"', a)
            model_name = inst_line[a - 1 : b + 1]
            if a == 0:
                model_name = preamble[-1]
        instance["model"] = model_name
        # print(model_name)
        # Filtering the non-PDK elements from the instances - the approach here is that models[] only contains the PDK (CML) library elements
        # when models[instance['models']] tries to find non-PDK elements, this will raise a KeyError
        try:
            instance["ports"] = models[instance["model"]]["ports"]
            instance["port_types"] = models[instance["model"]]["port_types"]
            instance["expandable"] = bool(models[instance["model"]]["expandable"])
            instance["nets"] = [preamble[i] for i in range(1, len(preamble) - 1)]
            instance["params"] = {}

            for param, value in matches:
                match = re.match(r"([\d.]+)([un])", value)
                if match:
                    instance["params"][param] = (
                        float(match.group(1)) * CONVERSION[match.group(2)]
                    )
                else:
                    try:
                        instance["params"][param] = float(value)
                    except (ValueError, TypeError, KeyError):
                        instance["params"][param] = value

            for param_name, param_val in (
                models[instance["model"]].get("params", {}).items()
            ):
                try:
                    instance["params"][param_name] = float(param_val)
                except ValueError:
                    instance["params"][param_name] = param_val
            instances.append(instance)
        except KeyError:
            non_pdk.append(instance["name"])
            pass

    if len(non_pdk) > 0:
        print(
            "LOG: Non-PDK elements detected! Removing instances {"
            + ", ".join(x for x in non_pdk)
            + "} from netlist."
        )
    return instances


def get_instances_info(
    instances: list,
    mapping: dict,
    ignore_electrical: bool,
    ignored_info: list | None = None,
) -> dict:
    """
    Get instances data structure in the format of GDSFactory YAML instances

    Args:
        instances: Instances with model params, nets, ports, names, and models
                    {
                        'name': 'X_dc_0' instance_name (str),
                        'model': 'ebeam_dc_te1550' compact model name (str),
                        'ports': ['port 1', 'port 2', port 3'] name of ports ordered in a list (list of str),
                        'port_types': ['optical', 'electrical', 'optical']type of port i.e. electrical or optical, ordered in a list (list of str),
                        'expandable': True if instance is compound element, else False (bool)
                        'nets': ['PORT 1', 'N$1', 'N$2'] nets connected to ports in this order (list of str)
                        'params':
                        {
                            'param_name_0': param_val (any type),
                            'param_name_1': param_val (any type)
                            .
                            .
                        }
                    }
        mapping: Mapping between models and layout cells. Example data structure:
                    {
                        'pdk': 'name_of_pdk',
                        'models':
                        {
                            'compact_model_name_0':
                            {
                                'layout_cell': 'layout_cell_name_0',
                                'ports':
                                {
                                    'compact_model_port_0': 'layout_cell_port_0',
                                    'compact_model_port_1': 'layout_cell_port_1',
                                    .
                                    .
                                },
                                'params'
                                {
                                    'compact_model_param_name_0': 'layout_cell_param_name_0',
                                    'compact_model_param_name_1': 'layout_cell_param_name_1',
                                    .
                                    .
                                }
                            },
                            .
                            .
                        }
                    }
        ignored_info: Ignored param names that will not be put into the 'settings' or 'info' fields (list of str)

    Returns:
        instances_info: Instances in GDSFactory YAML ready format. Ex.
                            {
                                'instance_name_0' (str):
                                {
                                    'component': 'layout_cell_name_0' (str),
                                    'info':
                                    {
                                        'info_name_0': info_0 (any type),
                                        .
                                        .
                                    },
                                    'settings':
                                    {
                                        'layout_cell_param_name_0': param_val (float or int),
                                        .
                                        .
                                    }
                                }
                            }
    """
    instances_info = {}
    ignored_info = ignored_info or ()
    for inst in instances:
        # Get layout cell
        try:
            cell_name = mapping[inst["model"]]["layout_cell"]
        except KeyError:
            cell_name = inst["model"]

        # Add instance and map model to component and params
        instances_info[inst["name"]] = {"component": cell_name}
        instances_info[inst["name"]]["info"] = {}
        instances_info[inst["name"]]["settings"] = {}
        for param_name, param_val in inst["params"].items():
            # Ignore specified params
            if param_name not in ignored_info:
                # If param is dependent on another parameter, create an equation
                if (
                    isinstance(param_val, str)
                    and "%" in param_val
                    and "{" in param_val
                    and "}" in param_val
                ):
                    param_val = f"{{{get_var_name(param_val)}}}"

                # Compound elements are handled differently
                if inst.get("expandable", False):
                    # Assume that params of float, int, and bool types or have equations are settings parameters that affect lower hierarchies, meaning these parameters live in 'settings' field
                    if isinstance(param_val, str | float | int | bool) or (
                        "{" in param_val and "}" in param_val
                    ):
                        instances_info[inst["name"]]["settings"][param_name] = param_val
                    else:
                        instances_info[inst["name"]]["info"][param_name] = param_val
                else:
                    try:
                        supported_params = mapping[inst["model"]].get("params", {})
                    except KeyError:
                        raise KeyError(
                            f'Instance model "{inst["model"]}" not found in mapping file. Please check/update mapping file with model.'
                        )
                    if param_name in supported_params:
                        instances_info[inst["name"]]["settings"][
                            supported_params[param_name]
                        ] = param_val
                    else:
                        # Place param in info field as meta data
                        instances_info[inst["name"]]["info"][param_name] = param_val

        if instances_info[inst["name"]]["settings"] == {}:
            del instances_info[inst["name"]]["settings"]
        if instances_info[inst["name"]]["info"] == {}:
            del instances_info[inst["name"]]["info"]
        sides = []

    # Add electrical routing information
    try:
        cell_name = mapping["PAD"]["layout_cell"]
    except KeyError:
        print("LOG: Ensure mapping.yml file has electrical pad information.")
        cell_name = "pad"
    all_connections = get_connections(instances, mapping)
    for connection_type, connections in all_connections.items():
        if not ignore_electrical and connection_type == "electrical":
            for side1, side2 in connections.items():
                if side1 not in sides:
                    sides.append(side1)
                if side2 not in sides:
                    sides.append(side2)
            for i in range(len(sides)):
                pin = sides[i].split(",")[1]
                if i < 10:
                    name = "X_PAD_0" + str(i) + "_" + pin
                else:
                    name = "X_PAD_" + str(i) + "_" + pin
                instances_info[name] = {"component": cell_name}
        else:
            pass
    return instances_info


def get_var_name(string: str):
    """
    Get variable name by replacing %, spaces, and commas with other characters

    Args:
        string: String to convert to a variable name

    Returns:
        string with replaced characters
    """
    return string.replace("%", "").replace(" ", "_").replace(",", "_")


def group_instance_str(netlist: str) -> list:
    """
    Group instance SPICE strings if they are extended by '+' and filter away lines that do not have params

    Args:
        netlist: SPICE netlist

    Returns:
        instances: Instances with params in '+' grouped together in single string
    """
    lines = netlist.split("\n")
    i = 0
    instances = []
    while i < len(lines):
        if not lines[i].strip().startswith(".MODEL") and not lines[
            i
        ].strip().startswith("+"):
            instances.append(lines[i].strip())
        i = i + 1

        while i < len(lines) and lines[i].strip().startswith("+") and instances:
            instances[-1] = instances[-1] + lines[i].strip()[1:-1]
            i = i + 1

    # Check that each instance has params. If not, remove them
    filtered_instances = []
    for inst in instances:
        if "=" in inst:
            filtered_instances.append(inst)

    return filtered_instances


def get_placements(instances: list, mapping: dict, ignore_electrical: bool) -> dict:
    """
    Get xy coordinates and orientation for each instance

    Args:
        instances: Instances with model params, nets, ports, names, and models
                    {
                        'name': 'X_dc_0' instance_name (str),
                        'model': 'ebeam_dc_te1550' compact model name (str),
                        'ports': ['port 1', 'port 2', port 3'] name of ports ordered in a list (list of str),
                        'port_types': ['optical', 'electrical', 'optical']type of port i.e. electrical or optical, ordered in a list (list of str),
                        'expandable': True if instance is compound element, else False (bool)
                        'nets': ['PORT 1', 'N$1', 'N$2'] nets connected to ports in this order (list of str)
                        'params':
                        {
                            'param_name_0': param_val (any type),
                            'param_name_1': param_val (any type)
                            .
                            .
                        }
                    }

    Returns:
        placements: Location and orientation of each instance in GDSFactory YAML ready format. Ex.
                    {
                        'instance_name_0':
                        {
                            'rotation': 180.0 (float),
                            'x': 0.0 (float),
                            'y': 75.0 (float)
                        },
                        .
                        .
                    }

    """
    scale = 1e2
    x = 0
    placements = {}
    sides = []
    all_connections = get_connections(instances, mapping)

    for connection_type, connections in all_connections.items():
        if (ignore_electrical == False) and (connection_type == "electrical"):
            for side1, side2 in connections.items():
                if side1 not in sides:
                    sides.append(side1)
                if side2 not in sides:
                    sides.append(side2)
            for i in range(len(sides)):
                pin = sides[i].split(",")[1]
                if i < 10:
                    name = "X_PAD_0" + str(i) + "_" + pin
                else:
                    name = "X_PAD_" + str(i) + "_" + pin
                x += 1.20 * scale
                placements[name] = {
                    "x": x,
                    "y": 800.0,
                    "rotation": 0.0,
                    "mirror": False,
                }
        else:
            pass
    for inst in instances:
        rotation = float(inst["params"]["sch_r"])
        if inst["params"]["sch_f"] == "f":
            mirror = False
        elif inst["params"]["sch_f"] == "x":
            mirror = True
            rotation = 180.0
        elif inst["params"]["sch_f"] == "y":
            mirror = True
        placements[inst["name"]] = {
            "x": float(inst["params"]["sch_x"]) * scale,
            "y": float(inst["params"]["sch_y"]) * scale,
            "rotation": rotation,
            "mirror": mirror,
        }

    return placements


def get_ports(netlist: str, instances: list, model: dict, mapping: dict) -> dict:
    """
    Get circuit ports and their connectivity

    Args:
        netlist: SPICE netlist
        instances: Instances with model params, nets, ports, names, and models
                    {
                        'name': 'X_dc_0' instance_name (str),
                        'model': 'ebeam_dc_te1550' compact model name (str),
                        'ports': ['port 1', 'port 2', port 3'] name of ports ordered in a list (list of str),
                        'port_types': ['optical', 'electrical', 'optical']type of port i.e. electrical or optical, ordered in a list (list of str),
                        'expandable': True if instance is compound element, else False (bool)
                        'nets': ['PORT 1', 'N$1', 'N$2'] nets connected to ports in this order (list of str)
                        'params':
                        {
                            'param_name_0': param_val (any type),
                            'param_name_1': param_val (any type)
                            .
                            .
                        }
                    }
        model: Model with port and param info
                Ex. {'model_name1':
                        {
                            'params': {'param_name1': param_val1, 'param_name2': param_val2, ...},
                            'ports': ['port1', 'port2', ...],
                            'port_types: ['optical', 'electrical', ...],
                            'expandable': True or False,
                        }
                    }
        mapping: Mapping between models and layout cells
                    {
                        'pdk': 'name_of_pdk',
                        'models':
                        {
                            'compact_model_name_0':
                            {
                                'layout_cell': 'layout_cell_name_0',
                                'ports':
                                {
                                    'compact_model_port_0': 'layout_cell_port_0',
                                    'compact_model_port_1': 'layout_cell_port_1',
                                    .
                                    .
                                },
                                'params'
                                {
                                    'compact_model_param_name_0': 'layout_cell_param_name_0',
                                    'compact_model_param_name_1': 'layout_cell_param_name_1',
                                    .
                                    .
                                }
                            },
                            .
                            .
                        }
                    }

    Returns:
        ports: Circuit ports and connections to instances in GDSFactory YAML ready format. Ex.
                {
                    'port_name_0': 'instance_name_0,instance_port_name_0',
                    'port_name_1': 'instance_name_0,instance_port_name_1',
                    .
                    .
                }

    """
    lines = netlist.split("\n")
    ctk_ports = lines[0].split(" ")
    ports = {}
    connections = []
    for inst1 in instances:
        for i in range(0, len(inst1["nets"])):
            # A net that only connects to other instances internally is detected when it has the '$' character.
            # 'connections' contains all sides that have a connection; this is used to prevent copies of a connection in different permutations
            # Ex. [a,o1: b,o1] is same as [b,o1: a,o1]; remove this permutation
            if (
                "$" not in inst1["nets"][i]
                and f'{inst1["name"]},{inst1["ports"][i]}' not in connections
            ):
                side1 = f'{inst1["name"]},{inst1["ports"][i]}'
                connections.append(side1)

                # Map instance port name to layout port name
                side1 = f'{inst1["name"]},{mapping[inst1["model"]]["ports"][inst1["ports"][i]]}'

                j = ctk_ports.index(inst1["nets"][i])
                ports[model["ports"][j]] = side1
    return ports


def get_connections(instances: list, mapping: dict) -> dict:
    """
    Get connections between instances

    Args:
        instances: Instances with model params, nets, ports, names, and models
                    {
                        'name': 'X_dc_0' instance_name (str),
                        'model': 'ebeam_dc_te1550' compact model name (str),
                        'ports': ['port 1', 'port 2', port 3'] name of ports ordered in a list (list of str),
                        'port_types': ['optical', 'electrical', 'optical']type of port i.e. electrical or optical, ordered in a list (list of str),
                        'expandable': True if instance is compound element, else False (bool)
                        'nets': ['PORT 1', 'N$1', 'N$2'] nets connected to ports in this order (list of str)
                        'params':
                        {
                            'param_name_0': param_val (any type),
                            'param_name_1': param_val (any type)
                            .
                            .
                        }
                    }
        mapping: Mapping between models and layout cells
                    {
                        'pdk': 'name_of_pdk',
                        'models':
                        {
                            'compact_model_name_0':
                            {
                                'layout_cell': 'layout_cell_name_0',
                                'ports':
                                {
                                    'compact_model_port_0': 'layout_cell_port_0',
                                    'compact_model_port_1': 'layout_cell_port_1',
                                    .
                                    .
                                },
                                'params'
                                {
                                    'compact_model_param_name_0': 'layout_cell_param_name_0',
                                    'compact_model_param_name_1': 'layout_cell_param_name_1',
                                    .
                                    .
                                }
                            },
                            .
                            .
                        }
                    }

    Returns:
        connections: Connectivity information between instances. Ex.
                        {
                            'electrical':
                            {
                                'instance_name_0,port1': 'instance_name_1,port1',
                                'instance_name_0,port2': 'instance_name_1,port2',
                                .
                                .
                            },
                            'optical':
                            {
                                'instance_name_2,port1': 'instance_name_3,port1',
                                'instance_name_2,port2': 'instance_name_3,port2',
                                .
                                .
                            }
                        }
    """
    connections = {"electrical": {}, "optical": {}}
    sides = []

    for port_type in connections:
        for inst1 in instances:
            try:
                for i in range(0, len(inst1["nets"])):
                    if ("N$" not in inst1["nets"][i]) and (
                        "PORT" not in inst1["nets"][i]
                    ):
                        print(
                            "LOG: "
                            + inst1["nets"][i]
                            + " is not a net name. Please check the netlist and make sure no whitespaces exist in the instance names. i.e. "
                            + inst1["name"]
                            + "_"
                            + inst1["nets"][i]
                        )
                        inst1["nets"].remove(inst1["nets"][i])
                    if (
                        "$" in inst1["nets"][i]
                        and f'{inst1["name"]},{inst1["ports"][i]}' not in sides
                        and port_type == inst1["port_types"][i]
                    ):
                        side1 = f'{inst1["name"]},{inst1["ports"][i]}'
                        sides.append(side1)
                        # Map port on instance 1
                        try:
                            ## Map instance port name to layout port name
                            side1 = f'{inst1["name"]},{mapping[inst1["model"]]["ports"][inst1["ports"][i]]}'
                        except KeyError:
                            side1 = f'{inst1["name"]},{inst1["ports"][i]}'
                        for inst2 in instances:
                            found = False
                            for j in range(0, len(inst2["nets"])):
                                if inst2["nets"][j] == inst1["nets"][i] and (
                                    not inst1["name"] == inst2["name"] or not i == j
                                ):
                                    side2 = f'{inst2["name"]},{inst2["ports"][j]}'
                                    sides.append(side2)
                                    # Map port on instance 2
                                    try:
                                        side2 = f'{inst2["name"]},{mapping[inst2["model"]]["ports"][inst2["ports"][j]]}'
                                    except KeyError:
                                        side2 = f'{inst2["name"]},{inst2["ports"][j]}'
                                    found = True
                                    break
                            if found:
                                break
                        try:
                            connections[port_type][side1] = side2
                        except UnboundLocalError:
                            connections[port_type][side1] = side1
            except IndexError:
                pass
    return connections


def get_routes(
    instances: list, mapping: dict, layers: dict, ignore_electrical: bool
) -> dict:
    """
    Get routes in GDSFactory YAML ready format

    Args:
        instances: Instances with model params, nets, ports, names, and models
                    {
                        'name': 'X_dc_0' instance_name (str),
                        'model': 'ebeam_dc_te1550' compact model name (str),
                        'ports': ['port 1', 'port 2', port 3'] name of ports ordered in a list (list of str),
                        'port_types': ['optical', 'electrical', 'optical']type of port i.e. electrical or optical, ordered in a list (list of str),
                        'expandable': True if instance is compound element, else False (bool)
                        'nets': ['PORT 1', 'N$1', 'N$2'] nets connected to ports in this order (list of str)
                        'params':
                        {
                            'param_name_0': param_val (any type),
                            'param_name_1': param_val (any type)
                            .
                            .
                        }
                    }
        mapping: Mapping between models and layout cells
                    {
                        'pdk': 'name_of_pdk',
                        'models':
                        {
                            'compact_model_name_0':
                            {
                                'layout_cell': 'layout_cell_name_0',
                                'ports':
                                {
                                    'compact_model_port_0': 'layout_cell_port_0',
                                    'compact_model_port_1': 'layout_cell_port_1',
                                    .
                                    .
                                },
                                'params'
                                {
                                    'compact_model_param_name_0': 'layout_cell_param_name_0',
                                    'compact_model_param_name_1': 'layout_cell_param_name_1',
                                    .
                                    .
                                }
                            },
                            .
                            .
                        }
                    }

    Returns:
        routes: Routes in GDSFactory YAML ready format. Ex.
                        {
                            'electrical_bundle_0':
                            {
                                'links':
                                {
                                    'instance_name_0,port1': 'instance_name_1,port1',
                                    'instance_name_0,port2': 'instance_name_1,port2',
                                    .
                                    .
                                }
                            },
                            'optical_bundle_0':
                            {
                                'links':
                                {
                                    'instance_name_2,port1': 'instance_name_3,port1',
                                    'instance_name_2,port2': 'instance_name_3,port2',
                                    .
                                    .
                                }
                            },
                            .
                            .
                        }
    """
    all_connections = get_connections(instances, mapping)
    sides = []
    routes = {}
    count = 0
    count2 = 0
    # Optical routing params
    optical = layers["optical_route"]["layer"]
    radius = layers["optical_route"]["params"]["radius"]
    # Electrical routing params
    electrical = layers["electrical_route"]["layer"]
    width = layers["electrical_route"]["params"]["width"]
    separation = layers["electrical_route"]["params"]["separation"]
    bend = layers["electrical_route"]["params"]["bend"]

    for connection_type, connections in all_connections.items():
        if (ignore_electrical == True) and (connection_type == "electrical"):
            count += 1
            pass
        elif (ignore_electrical == False) and (connection_type == "electrical"):
            for side1, side2 in connections.items():
                if side1 not in sides:
                    sides.append(side1)
                if side2 not in sides:
                    sides.append(side2)
            for i in range(len(sides)):
                pin = sides[i].split(",")[1]
                if i < 10:
                    routes[f"{connection_type}_bundle_0{i}"] = {"links": {}}
                    side2 = "X_PAD_0" + str(i) + "_" + pin + ",e1"
                    bundle = {sides[i]: side2}
                    routes[f"{connection_type}_bundle_0{i}"]["links"] = bundle
                    routes[f"{connection_type}_bundle_0{i}"]["settings"] = {
                        "layer": electrical,
                        "separation": float(separation),
                        "width": float(width),
                        "bend": bend,
                        "waypoints": [],
                    }
                else:
                    routes[f"{connection_type}_bundle_{i}"] = {"links": {}}
                    side2 = "X_PAD_" + str(i) + "_" + pin + ",e1"
                    bundle = {sides[i]: side2}
                    routes[f"{connection_type}_bundle_{i}"]["links"] = bundle
                    routes[f"{connection_type}_bundle_{i}"]["settings"] = {
                        "layer": electrical,
                        "separation": float(separation),
                        "width": float(width),
                        "bend": bend,
                        "waypoints": [],
                    }
                count2 += 1
        else:
            i = 0
            for side1, side2 in connections.items():
                if side1 not in sides and side2 not in sides:
                    sides.append(side1)
                    sides.append(side2)
                    bundle = {side1: side2}
                    # Get candidate connections that have the same components on side1 and side2
                    component1 = side1.split(",")[0]
                    component2 = side2.split(",")[0]
                    i = i + 1
                    for s1, s2 in connections.items():
                        if s1 not in sides and s2 not in sides:
                            c1 = s1.split(",")[0]
                            c2 = s2.split(",")[0]
                            if component1 == c1 and component2 == c2:
                                bundle[s1] = s2
                                sides.append(s1)
                                sides.append(s2)
                            elif component2 == c1 and component1 == c2:
                                bundle[s2] = s1
                                sides.append(s1)
                                sides.append(s2)
                    if i < 10:
                        routes[f"{connection_type}_bundle_0{i}"] = {"links": {}}
                        routes[f"{connection_type}_bundle_0{i}"]["links"] = bundle
                        routes[f"{connection_type}_bundle_0{i}"]["settings"] = {
                            "layer": optical,
                            "radius": float(radius),
                            "waypoints": [],
                        }
                    else:
                        routes[f"{connection_type}_bundle_{i}"] = {"links": {}}
                        routes[f"{connection_type}_bundle_{i}"]["links"] = bundle
                        routes[f"{connection_type}_bundle_{i}"]["settings"] = {
                            "layer": optical,
                            "radius": float(radius),
                            "waypoints": [],
                        }
    if count > 0:
        print("LOG: Electrical bundles were removed from the netlist.")
    if count2 > 0:
        print("LOG: " + str(count2) + " electrical pads were added.")
    return routes


def get_models(netlist_path: str, ignored_info: list = []) -> dict:
    """
    Get models from SPICE netlist

    Args:
        netlist_path: Path to SPICE netlist (.spi)
        ignored_info: Ignored param names that will not be put into the 'settings' or 'info' fields

    Returns:
        models: Models with associated model info
                Ex. {'model_name1':
                        {
                            'params': {'param_name1': param_val1, 'param_name2': param_val2, ...},
                            'ports': ['port1', 'port2', ...],
                            'port_types: ['optical', 'electrical', ...],
                            'expandable': True or False,
                        }
                        .
                        .
                    }
    """
    # Get port names in order
    with open(netlist_path) as f:
        lines = f.readlines()
    models = []
    subcircuits = []
    names = []
    for j in range(0, len(lines)):
        if lines[j].strip().startswith(".subckt"):
            models.append(lines[j].strip()[8:])
        if lines[j].strip().startswith("* Component pathname :"):
            subcircuits.append((lines[j].strip()[23:]).upper())
        if lines[j].strip().startswith("*#"):
            models.append(lines[j].strip()[3:])
    data = []
    for i in range(0, len(models)):
        net_model = {}
        a = models[i].find('"') + 1
        b = models[i].find('"', a)
        name = models[i][a - 1 : b + 1]
        if a == 0:
            model = models[i].split(" ")
            name = model.pop(0)
        names.append(name)
        ports = models[i].replace(name, "")
        if name in subcircuits:
            net_model.update({"expandable": 1})
        else:
            net_model.update({"expandable": 0})
        net_model.update({"name": name})
        model = ports.split(" ")
        model.pop(0)

        ports = []
        port_types = []
        for j in range(0, len(model)):
            port = model[j]
            if "(opt)" in port:
                port_types.append("optical")
                ports.append(port[:-5])
            elif "(ele)" in port:
                port_types.append("electrical")
                ports.append(port[:-5])
            else:
                port_types.append("optical")
                ports.append(port)
        net_model.update({"ports": ports})
        net_model.update({"port_types": port_types})
        data.append(net_model)
    models = {}
    for i in range(0, len(data)):
        models[data[i]["name"]] = {
            "ports": data[i]["ports"],
            "port_types": data[i]["port_types"],
            "expandable": data[i]["expandable"],
        }

        # If compound elements have parameters, get their parameter value and save it to its model
        if data[i]["expandable"]:
            # Get compound element info
            with open(netlist_path) as f:
                lines = f.readlines()
            for j in range(0, len(lines)):
                if (
                    f' {data[i]["name"]} ' in lines[j]
                    and not lines[j].strip().startswith(".subckt")
                    and not lines[j].strip().startswith(".ends")
                ):
                    k = 1
                    compound_line = lines[j].strip()
                    while lines[j + k].strip().startswith("+"):
                        compound_line = compound_line + lines[j + k].strip()[1:-1]
                        k = k + 1
                    break

            # Get params from compound element info
            pattern = r'(\w+|"[^"]*")\s*=\s*({.*?}|-[0-9.]+|[0-9.]+|f+|y+|x+|"[^"]*")'
            matches = re.findall(pattern, compound_line)
            params = {}
            for param_name, param_val in matches:
                # Ignore specified params
                if param_name not in ignored_info:
                    try:
                        params[param_name] = float(param_val)
                    except ValueError:
                        params[param_name] = param_val

            models[data[i]["name"]]["params"] = params

    # Get additional model info from .MODEL directive
    top_ctk_netlist = get_topctk(netlist_path)
    lines = top_ctk_netlist.split("\n")
    model_directives = []
    for i in range(0, len(lines)):
        if (lines[i].startswith(".MODEL")) or (lines[i].startswith("X_")):
            model_directive = lines[i]
            i = i + 1
            while i < len(lines) and lines[i].startswith("+"):
                model_directive = model_directive + lines[i]
                i = i + 1
            for model_name in names:
                if "library=" in model_directive:
                    model_directives.append(model_directive)
                    break
    # Extract model params
    for model_directive in model_directives:
        # Get model name
        a = model_directive.find('"') + 1
        b = model_directive.find('"', a)
        model_name = model_directive[a - 1 : b + 1]
        if model_name not in names:
            model = model_directive.split(" ")
            for m in model:
                model_name = m
                if model_name in names:
                    break
        f = model_directive.replace(model_name, "")

        # Get params using regular expressions
        pattern = r'(\w+|"[^"]*")\s*=\s*([0-9.]+|"[^"]*")'
        matches = re.findall(pattern, model_directive)
        model_params = {}
        for param, value in matches:
            match = re.match(r"([\d.]+)([un])", value)
            if match:
                model_params[param] = float(match.group(1)) * CONVERSION[match.group(2)]
            else:
                try:
                    model_params[param] = float(value)
                except:
                    model_params[param] = value

        # Add model params
        models[model_name]["params"] = model_params
    pdk = []
    models_f = {}
    # Filtering the non-PDK models
    for model_name in models:
        try:
            if "library" in models[model_name]["params"]:
                pdk.append(model_name)
                models_f[model_name] = models[model_name]
            elif model_name in subcircuits:
                pdk.append(model_name)
                models_f[model_name] = models[model_name]
        except KeyError:
            pass
    if len(pdk) > 0:
        print(
            "LOG: PDK elements {" + ", ".join(x for x in pdk) + "} used in the netlist."
        )
    return models_f


def get_topctk(netlist_path: str):
    """Get top circuit information from SPICE netlist.

    Args:
        netlist_path: Path to SPICE netlist (.spi).

    Returns:
        cleaned_netlist (str): Cleaned netlist with only top level instances
    """
    with open(netlist_path) as f:
        lines = f.readlines()
    cleaned_lines = []

    i = 0
    while i < len(lines):
        if lines[i].strip().startswith(".subckt"):
            # Skip this line and the following lines until .ends is encountered
            while not lines[i].strip().startswith(".ends"):
                line = lines.pop(i)
                if not lines:
                    break
            line = lines.pop(i)
        elif lines[i].strip().startswith("*") or lines[i].strip().startswith(".end"):
            i = i + 1
            continue
        else:
            cleaned_lines.append(lines[i].strip())
        i = i + 1

    cleaned_netlist = "\n".join(cleaned_lines).strip()
    return cleaned_netlist


if __name__ == "__main__":
    main()
