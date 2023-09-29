import copy

import gdsfactory as gf
import gdstk
from gdsfactory.generic_tech import LAYER_STACK
from gdsfactory.pdk import get_layer
from gdsfactory.typings import Component, LayerSpecs, LayerStack


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
        for sublist in [layernames_dict[layer] for layer in layers_present]
        for name in sublist
    ]
    for key in list(new_layer_stack.layers.keys()):
        if key not in layernames_present:
            new_layer_stack.layers.pop(key)

    return new_layer_stack


@gf.cell
def get_component_with_new_port_layers(
    component: Component = gf.components.straight_heater_metal(),
    layer_stack: LayerStack = LAYER_STACK.model_copy(),
    port_names: tuple[str, ...] = ("l_e1",),
    new_layers: LayerSpecs | None = None,
    new_layer_names: tuple[str, ...] | None = None,
) -> Component:
    """Returns a component where polygons touching a port are put on new logical layers.

    Useful to quickly define boundary conditions from component ports in simulation.

    Args:
        component: to process.
        layer_stack: to process.
        port_names: list of port_names to process into new layers.
        new_layers: list of new layers to create.
        new_layer_names: list of new layer names to create.

    Returns:
        new component with port_polygons tagged on new layers.
    """

    if (
        new_layers
        and new_layer_names
        and len(port_names) != len(new_layers) != len(new_layer_names)
    ):
        raise ValueError(
            "port_names, new_layers and new_layer_names must have the same length"
        )

    new_layers = new_layers or [None] * len(port_names)
    new_layer_names = new_layer_names or [None] * len(port_names)

    # copy original component
    component = component.copy()

    # For each port to consider, convert relevant polygons
    for port_name, new_layer_spec, new_layer_name in zip(
        port_names, new_layers, new_layer_names
    ):
        port = component.ports[port_name]
        # Get original port layer polygons, and modify a new component without that layer
        polygons = component.extract(layers=[port.layer]).get_polygons()
        component = component.remove_layers(layers=[port.layer])

        if new_layer_spec is None:
            port_layer = get_layer(port.layer)
            new_layer_spec = (port_layer[0], port_layer[1] + 1)

        new_layer_name = new_layer_name or f"{port.name}_port"
        for polygon in polygons:
            # If polygon belongs to port, create a unique new layer based on the old one, and add the polygon to it

            offset_polygon = gdstk.offset(
                gdstk.Polygon(polygon), gf.get_active_pdk().grid_size
            )
            if gdstk.inside(
                [port.center],
                offset_polygon,
            )[0]:
                new_layer_number = get_layer(new_layer_spec)
                port_layername = layer_stack.get_layer_to_layername()[port.layer][0]
                new_layerlevel = layer_stack.layers[port_layername].model_copy()
                layer_stack.layers[new_layer_name] = new_layerlevel
                layer_stack.layers[new_layer_name].layer = new_layer_number
                component.add_polygon(polygon, layer=new_layer_number)

            # Otherwise put the polygon back on the same layer
            else:
                component.add_polygon(polygon, layer=port.layer)

    return component


def get_component_with_net_layers(
    layer_stack,
    component,
    portnames: list[str],
    delimiter: str = "#",
    new_layers_init: tuple[int, int] = (10010, 0),
    add_to_layerstack: bool = True,
):
    """Returns component with new layers that combine port names and original layers, and modifies the layerstack accordingly.
    Uses port's layer attribute to decide which polygons need to be renamed.
    New layers are named "layername{delimiter}portname".
    Args:
        component: to process.
        portnames: list of portnames to process into new layers.
        delimiter: the new layer created is called "layername{delimiter}portname".
        new_layers_init: initial layer number for the temporary new layers.
        add_to_layerstack: True by default, but can be set to False to disable parsing of the layerstack.
    """
    import gdstk

    # Initialize returned component
    net_component = component.copy()

    # For each port to consider, convert relevant polygons
    for i, portname in enumerate(portnames):
        port = component.ports[portname]
        # Get original port layer polygons, and modify a new component without that layer
        polygons = net_component.extract(layers=[port.layer]).get_polygons()
        net_component = net_component.remove_layers(layers=[port.layer])
        for polygon in polygons:
            # If polygon belongs to port, create a unique new layer, and add the polygon to it

            if gdstk.inside(
                [port.center],
                gdstk.offset(gdstk.Polygon(polygon), gf.get_active_pdk().grid_size),
            )[0]:
                try:
                    port_layernames = layer_stack.get_layer_to_layername()[port.layer]
                except KeyError as e:
                    raise KeyError(
                        "Make sure your `layer_stack` contains all layers with ports"
                    ) from e
                for j, old_layername in enumerate(port_layernames):
                    new_layer_number = (
                        new_layers_init[0] + i,
                        new_layers_init[1] + j,
                    )
                    if add_to_layerstack:
                        new_layer = copy.deepcopy(layer_stack.layers[old_layername])
                        new_layer.layer = (
                            new_layers_init[0] + i,
                            new_layers_init[1] + j,
                        )
                        layer_stack.layers[
                            f"{old_layername}{delimiter}{portname}"
                        ] = new_layer
                    net_component.add_polygon(polygon, layer=new_layer_number)
            # Otherwise put the polygon back on the same layer
            else:
                net_component.add_polygon(polygon, layer=port.layer)

    net_component.name = f"{component.name}_net_layers"

    return net_component


if __name__ == "__main__":
    c = get_component_with_new_port_layers()
    c.show()
