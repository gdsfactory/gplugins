"""Preprocessing involving both the GDS and the LayerStack, or the resulting simulation polygons."""
from __future__ import annotations

import numpy as np
from gdsfactory.technology import LayerLevel, LayerStack
from shapely.affinity import scale
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union

from gplugins.gmsh.parse_gds import to_polygons


def bufferize(layer_stack: LayerStack):
    """Convert layers without a z_to_bias to an equivalent z_to_bias.

    Arguments:
        layer_stack: layer_stack to process
    """
    for layer in layer_stack.layers.values():
        if layer.z_to_bias is None:
            if layer.sidewall_angle is None:
                layer.z_to_bias = ([0, 1], [0, 0])
            else:
                buffer_magnitude = layer.thickness * np.tan(
                    np.radians(layer.sidewall_angle)
                )
                layer.z_to_bias = (
                    (
                        [0, layer.width_to_z, 1],
                        [
                            1 * buffer_magnitude * layer.width_to_z,
                            0,
                            -1 * buffer_magnitude * (1 - layer.width_to_z),
                        ],
                    )
                    if layer.width_to_z
                    else ([0, 1], [0, -1 * buffer_magnitude])
                )
    return layer_stack


def process_buffers(layer_polygons_dict: dict, layer_stack: LayerStack):
    """Break up layers into sub-layers according to z_to_bias.

    Arguments:
        layer_polygons_dict: dict of GDS layernames: shapely polygons
        layer_stack: original Layerstack

    Returns:
        extended_layer_polygons_dict: dict of simulation_layername: (gds_layername, next_simulation_layername, this_layer_polygons, next_layer_polygons)
        extended_layer_stack: LayerStack of simulation_layername: simulation layers
    """
    extended_layer_polygons_dict = {}
    extended_layer_stack_layers = {}

    layer_stack = bufferize(layer_stack)

    for layername, polygons in layer_polygons_dict.items():
        # Check for empty polygons
        if not polygons.is_empty:
            zs = layer_stack.layers[layername].z_to_bias[0]
            width_buffers = layer_stack.layers[layername].z_to_bias[1]

            for poly_ind, polygon in enumerate(
                polygons.geoms if hasattr(polygons, "geoms") else [polygons]
            ):
                for z_ind, (z, width_buffer) in enumerate(
                    zip(zs[:-1], width_buffers[:-1])
                ):
                    new_zmin = (
                        layer_stack.layers[layername].zmin
                        + layer_stack.layers[layername].thickness * z
                    )
                    new_thickness = (
                        layer_stack.layers[layername].thickness * zs[z_ind + 1]
                        - layer_stack.layers[layername].thickness * z
                    )
                    extended_layer_stack_layers[
                        f"{layername}_{poly_ind}_{z}"
                    ] = LayerLevel(
                        layer=layer_stack.layers[layername].layer,
                        thickness=new_thickness,
                        zmin=new_zmin,
                        material=layer_stack.layers[layername].material,
                        info=layer_stack.layers[layername].info,
                        mesh_order=layer_stack.layers[layername].mesh_order,
                    )
                    extended_layer_polygons_dict[f"{layername}_{poly_ind}_{z}"] = (
                        f"{layername}",
                        f"{layername}_{poly_ind}_{zs[z_ind+1]}",
                        polygon.buffer(width_buffer),
                        polygon.buffer(width_buffers[z_ind + 1]),
                    )
                extended_layer_stack_layers[
                    f"{layername}_{poly_ind}_{zs[-1]}"
                ] = LayerLevel(
                    layer=layer_stack.layers[layername].layer,
                    thickness=0,
                    zmin=layer_stack.layers[layername].zmin
                    + layer_stack.layers[layername].thickness,
                    material=layer_stack.layers[layername].material,
                    info=layer_stack.layers[layername].info,
                    mesh_order=layer_stack.layers[layername].mesh_order,
                )
    return extended_layer_polygons_dict, LayerStack(layers=extended_layer_stack_layers)


def buffers_to_lists(layer_polygons_dict: dict, layer_stack: LayerStack):
    """Break up polygons on each layer into lists of polygons:z tuples according to z_to_bias.

    Arguments:
        layer_polygons_dict: dict of GDS layernames: shapely polygons
        layer_stack: original Layerstack

    Returns:
        extended_layer_polygons_dict: dict of layername: List[(z, polygon_at_z)] for all polygons at z
    """
    extended_layer_polygons_dict = {}

    layer_stack = bufferize(layer_stack)

    xfactor, yfactor = 1, 1  # buffer_to_scaling(polygon, width_buffer)
    for layername, polygons in layer_polygons_dict.items():
        all_polygons_list = []
        for polygon in polygons.geoms if hasattr(polygons, "geoms") else [polygons]:
            zs = layer_stack.layers[layername].z_to_bias[0]
            width_buffers = layer_stack.layers[layername].z_to_bias[1]

            polygons_list = [
                (
                    z
                    * (
                        layer_stack.layers[layername].zmin
                        + layer_stack.layers[layername].thickness
                    )
                    + layer_stack.layers[layername].zmin,
                    scale(polygon, xfact=xfactor, yfact=yfactor),
                )
                for z, width_buffer in zip(zs, width_buffers)
            ]
            all_polygons_list.append(polygons_list)
        extended_layer_polygons_dict[layername] = all_polygons_list

    return extended_layer_polygons_dict


def merge_by_material_func(layer_polygons_dict: dict, layer_stack: LayerStack):
    """Merge polygons of layer_polygons_dict whose layer_stack keys share the same material in layer_stack values.

    Returns new layer_polygons_dict with merged polygons and materials as keys.
    """
    merged_layer_polygons_dict = {}
    for layername, polygons in layer_polygons_dict.items():
        material = layer_stack.layers[layername].material
        if material in merged_layer_polygons_dict:
            merged_layer_polygons_dict[material] = unary_union(
                MultiPolygon(
                    to_polygons([merged_layer_polygons_dict[material], polygons])
                )
            )
        else:
            merged_layer_polygons_dict[material] = polygons

    return merged_layer_polygons_dict


def create_2D_surface_interface(
    layer_polygons: MultiPolygon,
    thickness_min: float = 0.0,
    thickness_max: float = 0.01,
    simplify: float = 0.005,
):
    """Create 2D entity at the interface of two layers/materials.

    Arguments:
        layer_polygons: shapely polygons.
        thickness_min: distance to define the interfacial region towards the polygon.
        thickness_max: distance to define the interfacial region away from the polygon.
        simplify: simplification factor for over-parametrized geometries.

    Returns:
        shapely interface polygon
    """
    interfaces = layer_polygons.boundary
    interface_surface = layer_polygons.boundary
    left_hand_side = interfaces.buffer(thickness_max, single_sided=True)
    right_hand_side = interfaces.buffer(-thickness_min, single_sided=True)
    interface_surface = left_hand_side.union(right_hand_side)

    return interface_surface.simplify(simplify, preserve_topology=False)
