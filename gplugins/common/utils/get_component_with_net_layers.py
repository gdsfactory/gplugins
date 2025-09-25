import copy

import gdsfactory as gf
from gdsfactory.technology.layer_stack import DerivedLayer, LayerLevel
from gdsfactory.typings import Port
import klayout.db as kdb
from gdsfactory import Component, LayerEnum
from gdsfactory.technology import LayerStack, LogicalLayer


def get_component_layer_stack(
    component: Component,
    layer_stack: LayerStack,
) -> LayerStack:
    """Returns a new layer_stack only with layers that appear in the provided component.

    Arguments:
        component: to process.
        layer_stack: to process.

    Returns:
        new_layer_stack: without layers that do not appear in component.
    """
    new_layer_stack = layer_stack.model_copy()

    layers_present = component.layers
    layernames_dict = new_layer_stack.get_layer_to_layername()
    layernames_present = [
        name
        for sublist in [
            layernames_dict[LogicalLayer(layer=layer)] for layer in layers_present
        ]
        for name in sublist
    ]
    for key in list(new_layer_stack.layers.keys()):
        if key not in layernames_present:
            new_layer_stack.layers.pop(key)

    return new_layer_stack


def compare_layerlevel_and_port_layers(layer_level: LayerLevel, port: Port) -> bool:
    """Compare the layer information between a :class:`~LayerLevel` and a :class:`~Port`.

    Note:
        If ``layer_level.layer`` is :class:`~LogicalLayer`, ``layer_level.layer`` is used.
        If ``layer_level.layer`` is :class:`~DerivedLayer`, ``layer_level.derived_layer`` is used.

    Args:
        layer_level: The LayerLevel object containing layer information
        port: The Port object containing layer_info with layer and datatype

    Returns:
        bool: True if the layer and datatype match between both objects
    """

    port_layer_tuple = (
        port.layer_info.layer,
        port.layer_info.datatype,
    )

    is_derived_layer = isinstance(layer_level.layer, DerivedLayer)
    if is_derived_layer:
        layer_level_tuple = (layer_level.derived_layer.layer.layer, layer_level.derived_layer.layer.datatype)
        return layer_level_tuple == port_layer_tuple

    layer_enum_or_tuple = layer_level.layer.layer
    if isinstance(layer_enum_or_tuple, tuple):
        layer_level_tuple = layer_enum_or_tuple
    else:
        layer_level_tuple = (
            layer_enum_or_tuple.layer,
            layer_enum_or_tuple.datatype,
        )

    return layer_level_tuple == port_layer_tuple


def get_component_with_net_layers(
    component: Component,
    layer_stack: LayerStack,
    port_names: list[str],
    delimiter: str = "#",
    new_layers_init: tuple[int, int] = (10010, 0),
    add_to_layerstack: bool = True,
) -> Component:
    """Returns a component where polygons touching a port are put on new logical layers.

    Uses port's layer attribute to decide which polygons need to be renamed.
    New layers are named "layername{delimiter}portname".

    Args:
        component: to process.
        layer_stack: to process.
        port_names: list of port_names to process into new layers.
        delimiter: the new layer created is called "layername{delimiter}portname".
        new_layers_init: initial layer number for the temporary new layers.
        add_to_layerstack: True by default, but can be set to False to disable parsing of the layerstack.
    """

    # Initialize returned component
    net_component = component.copy()

    new_layerlevels = []
    # For each port to consider, convert relevant polygons
    for i, port_name in enumerate(port_names):
        port = component.ports[port_name]
        # Get original port layer polygons, and modify a new component without that layer
        polygons = (
            net_component.extract(layers=(port.layer,))
            .get_polygons()
            .get(port.layer, [])
        )
        net_component = net_component.remove_layers(
            layers=(port.layer,), recursive=False
        )
        for polygon in polygons:
            # If polygon belongs to port, create a unique new layer, and add the polygon to it
            if polygon.sized(int(3 * gf.kcl.dbu)).inside(
                kdb.Point(*port.to_itype().center)
            ):
                try:
                    derived_layerlevels_touching_port = [
                        e
                        for e in layer_stack.layers.values()
                        if e.derived_layer is not None
                        and e not in new_layerlevels
                        and compare_layerlevel_and_port_layers(e, port)
                    ]
                    logical_layerlevels_touching_port = [
                        e
                        for e in layer_stack.layers.values()
                        if not isinstance(
                            e.layer, gf.technology.layer_stack.DerivedLayer
                        )
                        and e not in new_layerlevels
                        and compare_layerlevel_and_port_layers(e, port)
                    ]

                    layerlevels_touching_port = (
                        derived_layerlevels_touching_port
                        + logical_layerlevels_touching_port
                    )
                except KeyError as e:
                    raise KeyError(
                        "Make sure your `layer_stack` contains all layers with ports"
                    ) from e

                for j, old_layerlevel in enumerate(layerlevels_touching_port):
                    new_layer_number = (
                        new_layers_init[0] + i,
                        new_layers_init[1] + j,
                    )
                    if add_to_layerstack:
                        # new_layer = copy.deepcopy(layer_stack.layers[old_layerlevel])
                        new_layerlevel = copy.deepcopy(old_layerlevel)
                        new_layerlevel.layer = LogicalLayer(
                            layer=(
                                new_layers_init[0] + i,
                                new_layers_init[1] + j,
                            )
                        )
                        new_layerlevel.name = (
                            f"{old_layerlevel.name}{delimiter}{port_name}"
                        )
                        # Increase mesh order to ensure new layer is on top old
                        new_layerlevel.mesh_order = old_layerlevel.mesh_order - 1
                        layer_stack.layers[
                            f"{old_layerlevel.name}{delimiter}{port_name}"
                        ] = new_layerlevel
                        new_layerlevels.append(new_layerlevel)
                    net_component.add_polygon(polygon, layer=new_layer_number)
            # Otherwise put the polygon back on the same layer
            else:
                net_component.add_polygon(polygon, layer=port.layer)

    net_component.name = f"{component.name}_net_layers"
    return net_component
