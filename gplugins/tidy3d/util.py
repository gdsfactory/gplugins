from typing import Literal

from gdsfactory.port import Port
from gdsfactory.technology.layer_stack import LayerLevel


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
