import pytest

from gplugins.spice.spice_to_yaml import get_instances


# Define a fixture for the models and netlist to reuse in different test functions
@pytest.fixture
def setup_data():
    models = {
        "ebeam_dc_te1550": {
            "params": {"width": "0.5", "length": "1.5"},
            "ports": ["in", "out"],
            "port_types": ["optical", "optical"],
            "expandable": False,
        },
        "ebeam_bdc_te1550": {
            "params": {"ratio": "2", "loss": "0.5"},
            "ports": ["in1", "in2", "out"],
            "port_types": ["optical", "optical", "optical"],
            "expandable": True,
        },
    }
    netlist = """
    X_dc_0 1 2 ebeam_dc_te1550 width=0.5 length=1.5
    X_bdc_0 3 4 5 ebeam_bdc_te1550 ratio=2 loss=0.5
    """
    return models, netlist


# Test function for correct instance extraction
def test_instance_extraction_correct(setup_data) -> None:
    models, netlist = setup_data
    instances = get_instances(netlist, models)
    expected = [
        {
            "name": "X_dc_0",
            "model": "ebeam_dc_te1550",
            "ports": ["in", "out"],
            "port_types": ["optical", "optical"],
            "expandable": False,
            "nets": ["1", "2"],
            "params": {"width": 0.5, "length": 1.5},
        },
        {
            "name": "X_bdc_0",
            "model": "ebeam_bdc_te1550",
            "ports": ["in1", "in2", "out"],
            "port_types": ["optical", "optical", "optical"],
            "expandable": True,
            "nets": ["3", "4", "5"],
            "params": {"ratio": 2.0, "loss": 0.5},
        },
    ]
    assert instances == expected


# Test for handling non-PDK models
def test_non_pdk_handling(setup_data) -> None:
    models, netlist = setup_data
    # Adding a line with a model not in the models dictionary
    netlist += "\nX_dc_1 6 7 non_pdk_model param=3.0"
    instances = get_instances(netlist, models)
    non_pdk_names = [
        inst["name"] for inst in instances if inst["model"] == "non_pdk_model"
    ]
    assert "X_dc_1" not in non_pdk_names


# Test for correct parameter parsing and conversion
def test_parameter_parsing(setup_data) -> None:
    models, netlist = setup_data
    # Adjust netlist to include a unit in parameters
    netlist = "X_dc_0 1 2 ebeam_dc_te1550 width=0.5u length=1.5n"
    instances = get_instances(netlist, models)
    expected_params = {"width": 0.5, "length": 1.5}
    assert instances[0]["params"] == expected_params


if __name__ == "__main__":
    pytest.main(["-v", "test_netlist.py"])
