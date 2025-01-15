# type: ignore
import os
import pathlib
import re

import typer
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

app = typer.Typer()


def spice_to_yaml(
    netlist_path: str,
    mapping_path: str,
    picyaml_path: str,
    pdk: str,
    mode: str = "overwrite",
) -> None:
    """Handle the export of netlists based on the selected mode.

    Args:
        netlist_path: Path to SPICE netlist (.spi).
        mapping_path: Path to YAML mapping file (.yml).
        picyaml_path: Path to save the YAML netlist.
        pdk: Process design kit name.
        mode: Mode for netlist export (overwrite or update).
    """
    netlists = get_netlists(
        netlist_path, mapping_path, pdk=pdk, ignore_electrical=False, map_flag=False
    )

    for netlist in netlists:
        if mode == "overwrite" or not os.path.exists(picyaml_path):
            with open(picyaml_path, "w") as f:
                netlist["pdk"] = pdk
                yaml.dump(netlist, f)
            print(
                f"LOG: {'Overwrote' if mode == 'overwrite' else 'Created'} {picyaml_path}."
            )
        elif mode == "update":
            with open(picyaml_path, "r+") as f:
                existing_data = yaml.safe_load(f)
                existing_data.update(netlist)
                f.seek(0)
                f.truncate()
                yaml.dump(existing_data, f)
            print(f"LOG: Updated {picyaml_path}.")


@app.command()
def cli(
    mapping_file_name: str = typer.Option(
        "mapping", help="Mapping file name, defaults to 'mapping'."
    ),
    mode: str = typer.Option(
        "overwrite", help="Mode for netlist export (overwrite or update)."
    ),
    netlist_path: str = typer.Option(
        "netlist", help="Netlist file name, defaults to 'netlist'."
    ),
    picyaml_path: str = typer.Option("netlist", help="pic.yml path"),
) -> None:
    """Command Line Interface for processing netlists using Typer."""
    spice_to_yaml(netlist_path=netlist_path, mode=mode, picyaml_path=picyaml_path)


def get_netlists(
    netlist_path: str,
    mapping_path: str,
    pdk: str,
    ignore_electrical: bool,
    map_flag: str,
    ignored_info: tuple[str, ...] = ignored_info,
) -> list:
    """Get netlists from SPICE netlist and mapping file.

    Args:
        netlist_path: Path to SPICE netlist (.spi).
        mapping_path: Path to YAML mapping file (.yml).
        pdk: Process design kit name.
        ignore_electrical: Flag to ignore electrical routes and bundles.
        map_flag: Flag to create mapping from netlist.
        ignored_info: Ignored param names that will not be put into the 'settings' or 'info' fields (list of str).

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
            except (KeyError, TypeError):
                mapping = create_mapping_from_netlist(netlist_path, pdk)
    else:
        mapping = create_mapping_from_netlist(netlist_path, pdk)

    lines = pathlib.Path(netlist_path).read_text()
    # Get models
    models = get_models(netlist_path, ignored_info)

    # Find all matches in the input string
    pattern = r"\.subckt\s+(\w+)\s+(.*?)\s*\.ends\s+\1"
    matches = re.findall(pattern, lines, re.DOTALL)

    # Extract the strings between ".subckt" and ".ends"
    ctks = []
    for match in matches:
        instances = get_instances(match[1], models)
        ctk = {"name": match[0]}
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

    instances = get_instances(get_top_circuit(netlist_path), models)
    topctk = {
        "name": "TOP",
        "instances": get_instances_info(
            instances, mapping["models"], ignore_electrical, ignored_info
        ),
    }
    topctk["placements"] = get_placements(
        instances, mapping["models"], ignore_electrical
    )
    topctk["routes"] = get_routes(
        instances, mapping["models"], mapping["layers"], ignore_electrical
    )
    ctks.append(topctk)
    return ctks


def create_mapping_from_netlist(netlist_path: str, pdk: str) -> list:
    """Create the mapping dictionary from the netlist file.

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
    for j in range(len(lines)):
        if lines[j].strip().startswith("*#"):
            instance = lines[j].strip()[3:].split(" ")
            count = sum(
                1 for port in instance[1:] if ("opt_" in port) or ("port" in port)
            )
            if count > 0:
                name = instance[0]
                layout_cell = name
                ports = {}
                for port in instance[1:]:
                    pt = port[0:-5]
                    ports[pt] = pt
                model = {"layout_cell": layout_cell, "ports": ports}
                models[name] = model
    mapping["models"] = models

    ### REMOVE hardcode
    if pdk in {"ctpdk", "compoundtek_pdk_v3"}:
        mapping["layers"] = {
            "optical_route": {"layer": "HMWG", "params": {"radius": 15}},
            "electrical_route": {
                "layer": "PADAL",
                "params": {"width": 50, "separation": 20, "bend": "wire_corner"},
            },
        }
    if pdk in {"ubcpdk", "ebeam"}:
        mapping["layers"] = {
            "optical_route": {"layer": "Waveguide", "params": {"radius": 15}},
            "electrical_route": {
                "layer": "M2_ROUTER",
                "params": {"width": 50, "separation": 20, "bend": "wire_corner"},
            },
        }
    return mapping


def get_instances(netlist: str, models: dict) -> list:
    """Get instances with all info on instance.

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
    model_names = [str(model) for model in models]
    # Get params using regular expressions
    pattern = r'(\w+|"[^"]*")\s*=\s*({.*?}|-[0-9.]+|[0-9.]+|f+|y+|x+|"[^"]*")'
    for inst_line in grouped_instances:
        instance = {}
        # Get preamble before parameters (instance name, nets, model name)
        fields = inst_line.split(" ")
        instance["name"] = fields[0]

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
                        float(match[1]) * CONVERSION[match.group(2)]
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
    if non_pdk:
        print(
            "LOG: Non-PDK elements detected! Removing instances {"
            + ", ".join(non_pdk)
            + "} from netlist."
        )
    return instances


def get_instances_info(
    instances: list,
    mapping: dict,
    ignore_electrical: bool,
    ignored_info: list | None = None,
) -> dict:
    """Get instances data structure in the format of GDSFactory YAML instances.

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
        ignore_electrical: Flag to ignore electrical routes and bundles.
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
        instances_info[inst["name"]] = {
            "component": cell_name,
            "info": {},
            "settings": {},
        }
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
                    except KeyError as e:
                        raise KeyError(
                            f'Instance model "{inst["model"]}" not found in mapping file. Please check/update mapping file with model.'
                        ) from e
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
                name = f"X_PAD_0{i!s}_{pin}" if i < 10 else f"X_PAD_{i!s}_{pin}"
                instances_info[name] = {"component": cell_name}
    return instances_info


def get_var_name(string: str):
    """Get variable name by replacing %, spaces, and commas with other characters.

    Args:
        string: String to convert to a variable name

    Returns:
        string with replaced characters
    """
    return string.replace("%", "").replace(" ", "_").replace(",", "_")


def group_instance_str(netlist: str) -> list:
    """Group instance SPICE strings if they are extended by '+' and filter away lines that do not have params.

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
        i += 1

        while i < len(lines) and lines[i].strip().startswith("+") and instances:
            instances[-1] = instances[-1] + lines[i].strip()[1:-1]
            i += 1

    return [inst for inst in instances if "=" in inst]


def get_placements(instances: list, mapping: dict, ignore_electrical: bool) -> dict:
    """Get xy coordinates and orientation for each instance.

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
        if not ignore_electrical and connection_type == "electrical":
            for side1, side2 in connections.items():
                if side1 not in sides:
                    sides.append(side1)
                if side2 not in sides:
                    sides.append(side2)
            for i in range(len(sides)):
                pin = sides[i].split(",")[1]
                name = f"X_PAD_0{i!s}_{pin}" if i < 10 else f"X_PAD_{i!s}_{pin}"
                x += 1.20 * scale
                placements[name] = {
                    "x": x,
                    "y": 800.0,
                    "rotation": 0.0,
                    "mirror": False,
                }
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
    """Get circuit ports and their connectivity.

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
        for i in range(len(inst1["nets"])):
            # A net that only connects to other instances internally is detected when it has the '$' character.
            # 'connections' contains all sides that have a connection; this is used to prevent copies of a connection in different permutations
            # Ex. [a,o1: b,o1] is same as [b,o1: a,o1]; remove this permutation
            if (
                "$" not in inst1["nets"][i]
                and f"{inst1['name']},{inst1['ports'][i]}" not in connections
            ):
                side1 = f"{inst1['name']},{inst1['ports'][i]}"
                connections.append(side1)

                # Map instance port name to layout port name
                side1 = f"{inst1['name']},{mapping[inst1['model']]['ports'][inst1['ports'][i]]}"

                j = ctk_ports.index(inst1["nets"][i])
                ports[model["ports"][j]] = side1
    return ports


def get_connections(instances: list, mapping: dict) -> dict:
    """Get connections between instances based on their ports and nets.

    Args:
        instances (list): List of dictionaries where each dictionary describes an instance with model params, nets, ports, names, and models.
        mapping (dict): Mapping between models and layout cells, including port and parameter mappings.

    Returns:
        dict: Connectivity information categorized by 'electrical' and 'optical' connections.
    """
    connections = {"electrical": {}, "optical": {}}
    net_to_instance_port = {}

    # Create a mapping of nets to instances and ports
    for inst in instances:
        for port_index, net in enumerate(inst["nets"]):
            if "N$" in net or "PORT" in net:
                continue  # Skip internal nets and ports
            net_key = (net, inst["port_types"][port_index])
            if net_key not in net_to_instance_port:
                net_to_instance_port[net_key] = []
            net_to_instance_port[net_key].append(
                (inst["name"], inst["ports"][port_index])
            )

    # Build connections based on the net_to_instance_port mapping
    for (_, port_type), instance_ports in net_to_instance_port.items():
        if len(instance_ports) < 2:
            continue  # Skip if less than two instances are connected to the same net
        for i in range(len(instance_ports) - 1):
            inst1_name, inst1_port = instance_ports[i]
            inst2_name, inst2_port = instance_ports[i + 1]

            # Map instance ports to layout ports if possible
            port1 = (
                mapping.get(inst1_name, {}).get("ports", {}).get(inst1_port, inst1_port)
            )
            port2 = (
                mapping.get(inst2_name, {}).get("ports", {}).get(inst2_port, inst2_port)
            )

            side1 = f"{inst1_name},{port1}"
            side2 = f"{inst2_name},{port2}"
            connections[port_type][side1] = side2

    return connections


def create_bundle(connections, layer_params, bundle_type):
    """Creates a routing bundle dictionary with appropriate settings based on layer parameters."""
    routes = {}
    sides = set()
    for side_pair in connections.items():
        side1, side2 = side_pair
        if side1 not in sides and side2 not in sides:
            sides.update([side1, side2])
            index = len(routes)
            key = f"{bundle_type}_bundle_{index:02d}"
            routes[key] = {"links": {side1: side2}, "settings": layer_params}
    return routes


def get_routes(instances, mapping, layers, ignore_electrical):
    """Extract routing information from instances using provided mapping and layers.

    Args:
        instances: list of instance dictionaries with port and net information.
        mapping: dictionary mapping model names to layout cells and their properties.
        layers: dictionary defining parameters for different routing layers.
        ignore_electrical: boolean indicating whether to ignore electrical routes.

    Returns:
        - A dictionary of routes organized by bundle types.
    """
    all_connections = get_connections(instances, mapping)  # Stub, needs implementation

    routes = {}
    optical_params = {
        "layer": layers["optical_route"]["layer"],
        "radius": float(layers["optical_route"]["params"]["radius"]),
        "waypoints": [],
    }
    electrical_params = {
        "layer": layers["electrical_route"]["layer"],
        "separation": float(layers["electrical_route"]["params"]["separation"]),
        "width": float(layers["electrical_route"]["params"]["width"]),
        "bend": layers["electrical_route"]["params"]["bend"],
        "waypoints": [],
    }

    for connection_type, connections in all_connections.items():
        if connection_type == "electrical" and ignore_electrical:
            print("LOG: Electrical bundles were removed from the netlist.")
            continue

        if connection_type == "electrical":
            routes.update(
                create_bundle(connections, electrical_params, connection_type)
            )
            print(f"LOG: {len(routes)} electrical pads were added.")
        else:
            routes.update(create_bundle(connections, optical_params, connection_type))

    return routes


def parse_parameters(line):
    # Helper function to parse parameters from a line using regex
    pattern = r'(\w+|"[^"]*")\s*=\s*({.*?}|-[0-9.]+|[0-9.]+|f+|y+|x+|"[^"]*")'
    return {
        param: float(val) if val.replace(".", "", 1).isdigit() else val
        for param, val in re.findall(pattern, line)
        if param not in ignored_info
    }


def get_models(netlist_path: str, ignored_info: list | None = None) -> dict:
    """Extracts models and their information from a SPICE netlist file.

    Args:
        netlist_path: Path to SPICE netlist (.spi)
        ignored_info: List of parameter names to ignore in the output.

    Returns:
        Dictionary of models with their parameters, ports, port types, and expandability.
    """
    ignored_info = ignored_info or []

    # Reading the netlist file
    with open(netlist_path) as file:
        lines = file.readlines()

    models = {}
    current_model = None

    for line in lines:
        stripped_line = line.strip()

        # Start of a new model
        if stripped_line.startswith(".subckt"):
            parts = stripped_line.split()
            name = parts[1]
            ports = parts[2:]
            models[name] = {
                "ports": ports,
                "port_types": [],
                "expandable": True,
                "params": {},
            }
            current_model = name

        elif stripped_line.startswith("* Component pathname :"):
            if current_model:
                models[current_model]["expandable"] = (
                    stripped_line[23:].upper() in models
                )

        elif current_model and not stripped_line.startswith(".ends"):
            if stripped_line.startswith("+"):
                # Continuation of the previous line (parameters)
                models[current_model]["params"].update(
                    parse_parameters(stripped_line[1:])
                )
            else:
                # Regular line, possibly defining parameters or additional info
                models[current_model]["params"].update(parse_parameters(stripped_line))

        # Process model directives for additional parameters
        if stripped_line.startswith(".MODEL"):
            model_info = stripped_line.split(maxsplit=1)
            if len(model_info) > 1:
                model_name = model_info[0][7:]  # Remove '.MODEL ' prefix
                if model_name in models:
                    models[model_name]["params"].update(parse_parameters(model_info[1]))

    # Optionally filter out non-expandable models, or perform other final adjustments
    return models


def get_top_circuit(netlist_path: str) -> str:
    """Get top circuit information from a SPICE netlist by filtering out subcircuit definitions.

    Args:
        netlist_path: Path to SPICE netlist (.spi).

    Returns:
        cleaned_netlist (str): Cleaned netlist with only top level instances.
    """
    with open(netlist_path) as file:
        lines = file.readlines()

    cleaned_lines = []
    skip = False

    for line in lines:
        stripped_line = line.strip()

        if stripped_line.startswith(".subckt"):
            skip = True
        elif stripped_line.startswith(".ends"):
            skip = False
            continue  # Skip the ".ends" line as well

        if (
            not skip
            and not stripped_line.startswith("*")
            and not stripped_line.startswith(".end")
        ):
            cleaned_lines.append(stripped_line)

    return "\n".join(cleaned_lines)


if __name__ == "__main__":
    app()
