import pytest

from gplugins.klayout.netlist_spice_reader import CalibreSpiceReader


@pytest.mark.parametrize(
    "s,element,expected_name,expected_nets",
    [
        ("1 2 POS test_model", "X", "test_model", {"1", "2", "POS"}),
        (
            "2 3 NEG test_model2 $ This is a comment",
            "X",
            "test_model2",
            {"2", "3", "NEG"},
        ),
        (
            "5 4 some_elem some_variable=1 $ This is a comment",
            "X",
            "some_elem",
            {"5", "4"},
        ),
    ],
)
def test_CalibreSpiceReader(
    s: str, element: str, expected_name: str, expected_nets: set[str]
) -> None:
    reader = CalibreSpiceReader()
    parsed = reader.parse_element(s, element)
    assert set(parsed.net_names) == expected_nets
    assert parsed.model_name == expected_name.upper()
