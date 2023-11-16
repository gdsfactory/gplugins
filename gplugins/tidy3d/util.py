from typing import Literal

import tidy3d as td
from gdsfactory.port import Port
from gdsfactory.technology.layer_stack import LayerLevel
from tidy3d.plugins.mode import ModeSolver
from tidy3d.plugins.smatrix import ComponentModeler


def sort_layers(
    layers: dict[str, LayerLevel], sort_by: str, reverse: bool = False
) -> dict[str, LayerLevel]:
    """
    Sorts a dictionary of LayerLevel objects based on a specified attribute.

    Args:
        layers (dict[str, LayerLevel]): A dictionary where the keys are layer names and the values are LayerLevel objects.
        sort_by (str): The attribute of the LayerLevel objects to sort by. This can be 'zmin', 'zmax', 'zcenter', or 'thickness'.
        reverse (bool, optional): If True, the layers are sorted in descending order. Defaults to False.

    Returns:
        dict[str, LayerLevel]: A dictionary of LayerLevel objects, sorted by the specified attribute.
    """
    return dict(
        sorted(layers.items(), key=lambda x: getattr(x[1], sort_by), reverse=reverse)
    )


def get_port_normal(port: Port) -> tuple[int, Literal["+", "-"]]:
    """
    This function returns the index of the normal axis (x,y,z) and the tidy3d port orientation string.

    Args:
        port (Port): A gdsfactory Port object.

    Returns:
        tuple: A tuple containing the index of the normal axis and the tidy3d port orientation string.

    Raises:
        ValueError: If the orientation does not match any of the standard orientations.
    """
    match ort := port.orientation:
        case 0:
            return 0, "-"
        case 90:
            return 1, "-"
        case 180:
            return 0, "+"
        case 270:
            return 1, "+"
        case _:
            raise ValueError(f"Invalid port orientation: {ort}")


def get_mode_data(modeler: ComponentModeler, port_name: str) -> list[td.ModeSolverData]:
    """
    This function retrieves the mode data for a given port in a ComponentModeler.

    Args:
        modeler (ComponentModeler): The ComponentModeler object containing the port.
        port_name (str): The name of the port for which to retrieve the mode data.

    Returns:
        list[td.ModeSolverData]: A list of ModeSolverData objects containing the mode data for the port.

    Raises:
        ValueError: If the specified port does not exist in the ComponentModeler.
    """
    port = [p for p in modeler.ports if p.name == port_name]
    if not port:
        raise ValueError(f"Port {port_name} does not exist!")
    port = port[0]
    mode_data = []
    for sim in [s for name, s in modeler.sim_dict.items() if port_name in name]:
        ms = ModeSolver(
            simulation=sim,
            plane=port.geometry,
            mode_spec=port.mode_spec,
            freqs=modeler.freqs,
            direction=port.direction,
            colocate=True,
        )
        mode_data.append(ms.solve())
    return mode_data
