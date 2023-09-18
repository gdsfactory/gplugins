import copy

import gdsfactory as gf
from gdsfactory.typings import Component, LayerStack


def remove_empty_layerstack_layers(
    component: Component,
    layerstack: LayerStack,
) -> LayerStack:
    """Returns a new layerstack without layers that don't appear in the provided component.

    Arguments:
        component: to process.
        layerstack: to process.

    Returns:
        new_layerstack: without layers that do not appear in component
    """
    new_layerstack = layerstack.copy()

    layers_present = component.layers
    layernames_dict = new_layerstack.get_layer_to_layername()
    layernames_present = [
        name
        for sublist in [layernames_dict[layer] for layer in layers_present]
        for name in sublist
    ]
    for key in list(new_layerstack.layers.keys()):
        if key not in layernames_present:
            del new_layerstack.layers[key]

    return new_layerstack


def get_component_with_net_layers(
    component: Component,
    layerstack: LayerStack,
    portnames: list[str],
    delimiter: str = "#",
    new_layers_init: tuple[int, int] = (10010, 0),
    add_to_layerstack: bool = True,
) -> tuple[Component, LayerStack]:
    """Returns a component where polygons touching a port are put on new logical layers. Useful to quickly define boundary conditions from component ports in simulation. New layers are named "layername{delimiter}portname".

    Args:
        component: to process.
        layerstack: to process.
        portnames: list of portnames to process into new layers.
        delimiter: the new layer created is called "layername{delimiter}portname".
        new_layers_init: initial layer number for the temporary new layers.
        add_to_layerstack: if True, adds the new layers to net_layerstack.

    Returns:
        net_component: new component with port_polygons tagged on new layers
        net_layerstack: new layerstack with "layername{delimiter}portname" entries
    """
    import gdstk

    # Initialize returned component and layerstack
    net_component = component.copy()
    net_layerstack = layerstack.copy()

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
                    port_layernames = net_layerstack.get_layer_to_layername()[
                        port.layer
                    ]
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
                        new_layer = copy.deepcopy(net_layerstack.layers[old_layername])
                        new_layer.layer = (
                            new_layers_init[0] + i,
                            new_layers_init[1] + j,
                        )
                        net_layerstack.layers[
                            f"{old_layername}{delimiter}{portname}"
                        ] = new_layer
                    net_component.add_polygon(polygon, layer=new_layer_number)
            # Otherwise put the polygon back on the same layer
            else:
                net_component.add_polygon(polygon, layer=port.layer)

    net_component.name = f"{component.name}_net_layers"

    return net_component, net_layerstack
