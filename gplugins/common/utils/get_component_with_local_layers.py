import copy
from dataclasses import dataclass

import gdsfactory as gf
import gdstk
from gdsfactory.component import Component
from gdsfactory.pdk import get_layer
from gdsfactory.typings import Layer
from gdstk import Polygon


@dataclass
class LocalMapping:
    """Dataclass to map polygons to new layers.

    Arguments:
        new_layer_name: new layer name for the updated LayerStack
        new_layer_number: new layer number for the updated LayerStack and GDS
        old_layer_name: original LayerStack key entry
        domains: list of gdstk polygons; Component polygons inside these domains are mapped to new_layer
    """

    new_layer_name: str
    new_layer_number: Layer
    old_layer_name: str
    domains: list[Polygon]


def get_component_with_local_layers(
    component,
    layer_stack,
    mappings: list[LocalMapping],
    precision: float = 1e-4,
) -> Component:
    """Returns a component where polygons within "domains" belonging to "old_layer_name" are remapped to "new_layer_name" (with layer details copied from old_layer), and polygons outside the domain are kept on "old_layer_name".

    Args:
        component: to process.
        layer_stack: to process.
        mappings: list of LocalMapping objects.
        precision: of the boolean operations.
    """
    # Initialize returned component and layerstack
    local_component = component.copy()
    local_component.flatten()
    local_layer_stack = layer_stack.model_copy()

    for mapping in mappings:
        # Create the new layer
        old_layer_number = layer_stack.layers[mapping.old_layer_name].layer
        new_layer = copy.deepcopy(layer_stack.layers[mapping.old_layer_name])
        new_layer.layer = mapping.new_layer_number
        local_layer_stack.layers[mapping.new_layer_name] = new_layer

        # Assign the polygons
        for domain in mapping.domains:
            layer_polygons = local_component.get_polygons(by_spec=True)[
                old_layer_number
            ]
            local_component.remove_layers([old_layer_number])
            gds_layer, gds_datatype = tuple(get_layer(old_layer_number))
            for layer_polygon in layer_polygons:
                # Polygons inside the domain
                p_inside = gdstk.boolean(
                    operand1=gdstk.Polygon(layer_polygon),
                    operand2=domain,
                    operation="and",
                    precision=precision,
                    layer=gds_layer,
                    datatype=gds_datatype,
                )
                # Outside the domain
                p_outside = gdstk.boolean(
                    operand1=gdstk.Polygon(layer_polygon),
                    operand2=domain,
                    operation="not",
                    precision=precision,
                    layer=gds_layer,
                    datatype=gds_datatype,
                )
                if p_inside:
                    local_component.add_polygon(
                        p_inside, layer=mapping.new_layer_number
                    )
                if p_outside:
                    local_component.add_polygon(p_outside, layer=old_layer_number)

    return local_component, local_layer_stack


if __name__ == "__main__":
    c = gf.components.spiral_racetrack_heater_metal()

    layer_stack = gf.generic_tech.LAYER_STACK

    mapping1 = LocalMapping(
        new_layer_name="test1",
        old_layer_name="heater",
        domains=[
            gdstk.rectangle(
                corner1=(0, -15),
                corner2=(10, -60),
            ),
            gdstk.rectangle(
                corner1=(20, -15),
                corner2=(30, -60),
            ),
        ],
        new_layer_number=(10002, 0),
    )

    mapping2 = LocalMapping(
        new_layer_name="test2",
        old_layer_name="heater",
        domains=[gdstk.ellipse(center=(30, 10), radius=10)],
        new_layer_number=(10003, 0),
    )

    c_local, layer_stack_local = get_component_with_local_layers(
        c,
        layer_stack,
        mappings=[mapping1, mapping2],
    )

    print(layer_stack_local.layers.keys())
    print(layer_stack_local.layers["test1"])

    c_local.show()
