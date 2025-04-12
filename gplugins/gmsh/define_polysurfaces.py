from typing import Any

from gdsfactory.technology import LayerStack
from meshwell.polysurface import PolySurface
from shapely.affinity import scale


def define_polysurfaces(
    polygons_dict: dict[str, Any],
    layer_stack: LayerStack,
    layer_physical_map: dict[str, Any],
    layer_meshbool_map: dict[str, Any],
    model: Any,
    resolutions: dict[str, Any] | None = None,
    scale_factor: float = 1,
) -> list[PolySurface]:
    """Define meshwell polysurfaces dimtags from gdsfactory information."""
    polysurfaces_list: list[PolySurface] = []

    if resolutions is None:
        resolutions = {}

    for layername in polygons_dict.keys():
        if polygons_dict[layername].is_empty:
            continue

        layer_stack_ = layer_stack.layers.get(layername)

        if layer_stack_ is None:
            continue

        polysurfaces_list.append(
            PolySurface(
                polygons=scale(
                    polygons_dict[layername],
                    *(scale_factor,) * 2,
                    origin=(0, 0, 0),
                ),
                model=model,
                resolution=resolutions.get(layername, None),
                mesh_order=layer_stack_.mesh_order,
                physical_name=layer_physical_map[layername]
                if layername in layer_physical_map
                else layername,
                mesh_bool=layer_meshbool_map[layername]
                if layername in layer_meshbool_map
                else True,
            )
        )

    return polysurfaces_list
