import operator
from functools import reduce

import shapely
from gdsfactory.typings import Layer, LayerSpecs

from gplugins.gmsh.uz_xsection_mesh import get_u_bounds_polygons


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


def add_mask_polygons(layer_polygons, name):
    """Returns polygons strings for 3D masks."""
    return_str_lines = []
    polygon_names = ""
    for i, polygon in enumerate(
        layer_polygons.geoms if hasattr(layer_polygons, "geoms") else [layer_polygons]
    ):
        if not polygon.is_empty:
            coordinates_x = [x for x, y in polygon.exterior.coords][:-1]
            coordinates_y = [y for x, y in polygon.exterior.coords][:-1]
            coordinates = reduce(operator.add, zip(coordinates_x, coordinates_y))
            segments = ""
            for coordinate in coordinates:
                segments += f"{coordinate:1.3f} "
            polygon_name = f"{name}_{i}"
            polygon_names += f"{polygon_name}" if i == 0 else f" {polygon_name}"
            line = f"polygon name={polygon_name} segments= {{ {segments}}}\n"
            return_str_lines.append(line)
    return return_str_lines, polygon_names


def get_mask_segments_xsection(
    layer_polygons_dict,
    xsection_bounds,
    layer,
    layers_or,
    layers_and,
    layers_diff,
    layers_xor,
    u_offset: float = 0.0,
):
    """(2D simulations) Returns mask polygons for the combination of layers, and cross-sectional line."""
    polygons = get_mask_polygons(
        layer_polygons_dict=layer_polygons_dict,
        layer=layer,
        layers_or=layers_or,
        layers_and=layers_and,
        layers_diff=layers_diff,
        layers_xor=layers_xor,
    )

    bounds_list = get_u_bounds_polygons(
        polygons=polygons,
        xsection_bounds=xsection_bounds,
        u_offset=u_offset,
    )

    segments_str = ""
    for x in [item for sublist in bounds_list for item in sublist]:
        segments_str += f"{x:1.3f} "

    return segments_str


def get_sentaurus_mask_3D(
    layer_polygons_dict,
    name: str,
    layer: Layer = None,
    layers_or: LayerSpecs = None,
    layers_and: LayerSpecs = None,
    layers_diff: LayerSpecs = None,
    layers_xor: LayerSpecs = None,
    positive_tone: bool = True,
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
        positive_tone: whether to invert the resulting mask (False) or not (True)
    """
    return_str_lines = []

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

    # Add polygons
    polygon_strings, polygon_names = add_mask_polygons(layer_polygons, name)
    return_str_lines += polygon_strings

    # Add mask step
    tone = "" if positive_tone else "negative"
    line = f"mask name={name} polygons= {{ {polygon_names}}} {tone}\n"
    return_str_lines.append(line)

    if layer_polygons:
        exists = True
    else:
        exists = False

    return return_str_lines, exists


def get_sentaurus_mask_2D(
    layer_polygons_dict,
    name: str,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None,
    u_offset: float = 0.0,
    layer: Layer = None,
    layers_or: LayerSpecs = None,
    layers_and: LayerSpecs = None,
    layers_diff: LayerSpecs = None,
    layers_xor: LayerSpecs = None,
    positive_tone: bool = True,
) -> list[str]:
    """Returns the 2D Sentaurus mask script line for the given layer + extra layers.

    Arguments:
        layer_polygons_dict: dict of layernames --> shapely (multi)polygons.
        name: name of the mask.
        xsection_bounds: cross-sectional line bounds (only for 2D simulations).
        u_offset: offset for the cross-sectional line.
        layer: main layer for this mask.
        layers_or: other layers' polygons to union with layer polygons.
        layers_and: other layers' polygons to intersect with layer polygons.
        layers_diff: other layers' polygons to diff with layer polygons.
        layers_xor: other layers' polygons to exclusive or with layer polygons.
        positive_tone: whether to invert the resulting mask (False) or not (True).
    """
    layers_or = layers_or or []
    layers_and = layers_and or []
    layers_diff = layers_diff or []
    layers_xor = layers_xor or []

    if layer is None:
        return []
    else:
        layer_bounds = get_mask_segments_xsection(
            layer_polygons_dict=layer_polygons_dict,
            xsection_bounds=xsection_bounds,
            layer=layer,
            layers_or=layers_or,
            layers_and=layers_and,
            layers_diff=layers_diff,
            layers_xor=layers_xor,
            u_offset=u_offset,
        )

    # Add mask step
    tone = "" if positive_tone else "negative"

    if layer_bounds:
        exists = True
    else:
        exists = False

    return f"mask name={name} segments= {{ {layer_bounds}}} {tone}\n", exists


if __name__ == "__main__":
    test_polygon = shapely.Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])

    test_layer_polygons_dict = {}
    test_layer_polygons_dict[(10, 0)] = test_polygon

    print(
        get_sentaurus_mask_3D(
            test_layer_polygons_dict, layer=(10, 0), name="test_layer"
        )
    )

    print(
        get_sentaurus_mask_2D(
            test_layer_polygons_dict,
            xsection_bounds=((0, 0), (0.5, 0.5)),
            layer=(10, 0),
            name="test_layer",
        )
    )
