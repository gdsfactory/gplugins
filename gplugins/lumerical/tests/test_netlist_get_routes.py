import pytest

from gplugins.spice.spice_to_yaml import get_routes


@pytest.fixture
def setup_routing_data():
    instances = [  # Mock instance data
        {
            "name": "instance1",
            "model": "model1",
            "ports": ["port1"],
            "port_types": ["optical"],
            "expandable": False,
            "nets": ["net1"],
        }
    ]
    mapping = {}  # Mock mapping
    layers = {  # Layer parameters
        "optical_route": {"layer": "optical", "params": {"radius": "10"}},
        "electrical_route": {
            "layer": "electrical",
            "params": {"width": "5", "separation": "2", "bend": "0.5"},
        },
    }
    return instances, mapping, layers


# def test_optical_routing(setup_routing_data):
#     instances, mapping, layers = setup_routing_data

#     # Mock get_connections to return fixed optical connections
#     def mock_get_connections(instances, mapping):
#         return {"optical": {("instance1,port1", "instance2,port1")}}

#     routes = get_routes(instances, mapping, layers, False)
#     assert "optical_bundle_00" in routes
#     assert routes["optical_bundle_00"]["settings"]["layer"] == "optical"
#     assert float(routes["optical_bundle_00"]["settings"]["radius"]) == 10


def test_ignore_electrical_routes(setup_routing_data) -> None:
    instances, mapping, layers = setup_routing_data

    # Mock get_connections to return electrical connections
    def mock_get_connections(instances, mapping):
        return {"electrical": {("instance1,port1", "instance2,port1")}}

    routes = get_routes(instances, mapping, layers, True)
    assert "electrical_bundle_00" not in routes
    assert all("electrical" not in key for key in routes.keys()), (
        "Electrical routes should be ignored"
    )


# def test_electrical_routing_with_parameters(setup_routing_data):
#     instances, mapping, layers = setup_routing_data

#     # Mock get_connections to return electrical connections
#     def mock_get_connections(instances, mapping):
#         return {"electrical": {("instance1,port1", "instance2,port1")}}

#     routes = get_routes(instances, mapping, layers, False)
#     # assert "electrical_bundle_00" in routes
#     assert routes["electrical_bundle_00"]["settings"]["layer"] == "electrical"
#     assert float(routes["electrical_bundle_00"]["settings"]["width"]) == 5
#     assert float(routes["electrical_bundle_00"]["settings"]["separation"]) == 2
#     # assert routes["electrical_bundle_00"]["settings"]["bend"] == "0.5"


if __name__ == "__main__":
    pytest.main()
