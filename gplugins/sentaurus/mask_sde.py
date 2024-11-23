import operator
from functools import reduce

import shapely
from gdsfactory.typings import Layer, LayerSpecs


def get_mask_polygons(
    layer_polygons_dict,
    layer,
    layers_or,
    layers_and,
    layers_diff,
    layers_xor,
    buffer_tol=1e-3,
):
    """(3D simulations) Returns mask polygons for the combination of layers."""
    layer_polygons = layer_polygons_dict[layer]

    for or_layer in layers_or:
        layer_polygons = layer_polygons | layer_polygons_dict[or_layer]
    for and_layer in layers_and:
        layer_polygons = layer_polygons & layer_polygons_dict[and_layer]
    for diff_layer in layers_diff:
        layer_polygons = layer_polygons - layer_polygons_dict[diff_layer]
    for xor_layer in layers_xor:
        layer_polygons = layer_polygons ^ layer_polygons_dict[xor_layer]

    return layer_polygons.buffer(-buffer_tol, join_style=2).buffer(
        buffer_tol, join_style=2
    )


def add_mask_polygons(layer_polygons):
    """Returns polygons strings for 3D masks."""
    return_str_lines = []
    for _i, polygon in enumerate(
        layer_polygons.geoms if hasattr(layer_polygons, "geoms") else [layer_polygons]
    ):
        if not polygon.is_empty:
            coordinates_x = [x for x, y in polygon.exterior.coords][:-1]
            coordinates_y = [y for x, y in polygon.exterior.coords][:-1]
            coordinates = reduce(operator.add, zip(coordinates_x, coordinates_y))
            segments = ""
            for coordinate in coordinates:
                segments += f"{coordinate:1.3f} "
            line = f"(list {segments})"
            return_str_lines.append(line)
    return return_str_lines


def get_sentaurus_mask_3D(
    layer_polygons_dict,
    name: str,
    layer: Layer = None,
    layers_or: LayerSpecs = None,
    layers_and: LayerSpecs = None,
    layers_diff: LayerSpecs = None,
    layers_xor: LayerSpecs = None,
) -> list[str]:
    """Returns the 3D Sentaurus mask script line for the given layer + extra layers.

    Arguments:
        layer_polygons_dict: dict of layernames --> shapely (multi)polygons
        name: name of the mask
        layer: main layer for this mask
        layers_or: other layers' polygons to union with layer polygons
        layers_diff: other layers' polygons to diff with layer polygons
        layers_and: other layers' polygons to intersect with layer polygons
        layers_xor: other layers' polygons to exclusive or with layer polygons
    """
    return_str = ""

    layers_or = layers_or or []
    layers_and = layers_and or []
    layers_diff = layers_diff or []
    layers_xor = layers_xor or []

    if layer is None:
        return []
    else:
        layer_polygons = get_mask_polygons(
            layer_polygons_dict=layer_polygons_dict,
            layer=layer,
            layers_or=layers_or,
            layers_and=layers_and,
            layers_diff=layers_diff,
            layers_xor=layers_xor,
        )

    # Add mask step
    return_str += f'(sdepe:generate-mask "{name}" (list\n'
    polygon_strings = add_mask_polygons(layer_polygons)
    for i, polygon_string in enumerate(polygon_strings):
        return_str += polygon_string
        if i < len(polygon_strings):
            return_str += "\n"
    return_str += "))\n"

    if layer_polygons:
        exists = True
    else:
        exists = False

    return return_str, exists


if __name__ == "__main__":
    test_polygon = shapely.Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])

    test_layer_polygons_dict = {}
    test_layer_polygons_dict[(10, 0)] = test_polygon

    print(
        get_sentaurus_mask_3D(
            test_layer_polygons_dict, layer=(10, 0), name="test_layer"
        )
    )
