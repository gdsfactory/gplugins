from typing import Literal

from gdsfactory.port import Port
from gdsfactory.technology.layer_stack import LayerLevel


def sort_layers(
    layers: dict[str, LayerLevel], sort_by: str, reverse: bool = False
) -> dict[str, LayerLevel]:
    return dict(
        sorted(layers.items(), key=lambda x: getattr(x[1], sort_by), reverse=reverse)
    )


def get_port_normal(port: Port) -> tuple[int, Literal["+", "-"]]:
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
