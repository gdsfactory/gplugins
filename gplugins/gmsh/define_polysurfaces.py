from typing import Any

from gdsfactory.technology import LayerStack
from meshwell.polysurface import PolySurface
from shapely.affinity import scale


def define_polysurfaces(
    polygons_dict: dict,
    layer_stack: LayerStack,
    model: Any,
    resolutions: dict,
    scale_factor: float = 1,
):
    """Define meshwell polysurfaces dimtags from gdsfactory information."""
    polysurfaces_list = []

    if resolutions is None:
        resolutions = {}

    for layername in polygons_dict.keys():
        if polygons_dict[layername].is_empty:
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
                mesh_order=layer_stack.layers.get(layername).mesh_order,
                physical_name=layername,
            )
        )

    return polysurfaces_list
