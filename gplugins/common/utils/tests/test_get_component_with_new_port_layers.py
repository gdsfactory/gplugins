from gdsfactory.components import straight_heater_metal
from gdsfactory.generic_tech import LAYER_STACK

from gplugins.common.utils.get_component_with_net_layers import (
    get_component_layer_stack,
    get_component_with_net_layers,
)

port_names = ("r_e2", "l_e4")
layernames_before = set(LAYER_STACK.layers.keys())
original_component = straight_heater_metal()


def test_component_with_new_port_layers() -> None:
    layer_stack = LAYER_STACK.model_copy()
    get_component_with_net_layers(
        component=original_component,
        layer_stack=layer_stack,
        port_names=port_names,
    )
    layernames_after = set(layer_stack.layers.keys())

    # Check we have two new layers in the LayerStack
    assert len(layernames_after - layernames_before) == 2, (
        "Two new layers should be added to the LayerStack"
    )

    # Check we have one new layer in Component (all metal3 is removed by these operations)
    # assert len(new_component.get_layers()) == len(original_component.get_layers()) + 1
    # print(new_component.get_layers())
    # print(original_component.get_layers())


def test_remove_empty_layer_stack_layers() -> None:
    layer_stack = LAYER_STACK.model_copy()
    new_component = get_component_with_net_layers(
        component=original_component,
        layer_stack=layer_stack,
        port_names=port_names,
    )

    new_layer_stack = get_component_layer_stack(
        component=new_component,
        layer_stack=layer_stack,
    )
    # Assert that "metal3" does not exist in the layers
    assert "metal3" not in new_layer_stack.layers
