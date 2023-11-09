import pytest

from gplugins.klayout.netlist_spice_reader import NoCommentReader


@pytest.mark.parametrize(
    "s,element,expected_name,expected_nets",
    [
        ("1 2 POS", "X", "POS_0", {"1", "2"}),
        ("2 3 NEG $ This is a comment", "X", "NEG_0", {"2", "3"}),
        (
            "5 4 some_elem some_variable=1 $ This is a comment",
            "X",
            "some_elem_0",
            {"5", "4"},
        ),
    ],
)
def test_NoCommentReader(
    s: str, element: str, expected_name: str, expected_nets: set[str]
) -> None:
    reader = NoCommentReader()
    parsed = reader.parse_element(s, element)
    assert set(parsed.net_names) == expected_nets
    assert parsed.model_name == expected_name.upper()
