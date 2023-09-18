from gdsfactory.components import straight_heater_metal
from gdsfactory.generic_tech import LAYER_STACK

from gplugins.utils.get_component_with_net_layers import (
    get_component_with_net_layers,
    remove_empty_layer_stack_layers,
)


def test_component_with_net_layers():
    # Hardcoded settings for now
    delimiter = "#"
    portnames_to_test = ["r_e2", "l_e4"]
    layernames_before = set(LAYER_STACK.layers.keys())
    original_component = straight_heater_metal()

    # Run the function
    net_component, net_layer_stack = get_component_with_net_layers(
        original_component,
        LAYER_STACK,
        portnames=portnames_to_test,
        delimiter=delimiter,
    )
    layernames_after = set(net_layer_stack.layers.keys())

    # Check we have two new layers in the LayerStack
    assert len(layernames_after - layernames_before) == 2

    # Check we have one new layer in Component (all metal3 is removed by these operations)
    assert len(net_component.get_layers()) == len(original_component.get_layers()) + 1

    # Check new layer is the same as old layer, apart from layer number and name
    old_layer = net_layer_stack.layers["metal3"]
    new_layer = net_layer_stack.layers[f"metal3{delimiter}{portnames_to_test[0]}"]

    for varname in vars(net_layer_stack.layers["metal3"]):
        if varname == "layer":
            continue
        else:
            assert getattr(old_layer, varname) == getattr(new_layer, varname)


def test_remove_empty_layer_stack_layers():
    # Hardcoded settings for now
    delimiter = "#"
    portnames_to_test = ["r_e2", "l_e4"]
    original_component = straight_heater_metal()

    # Run the function
    net_component, net_layer_stack = get_component_with_net_layers(
        original_component,
        LAYER_STACK,
        portnames=portnames_to_test,
        delimiter=delimiter,
    )

    # Test remove old layers
    new_layer_stack = remove_empty_layer_stack_layers(
        net_component,
        net_layer_stack,
    )
    # Assert that "metal3" does not exist in the layers
    assert "metal3" not in new_layer_stack.layers


if __name__ == "__main__":
    test_component_with_net_layers()
    test_remove_empty_layer_stack_layers()
