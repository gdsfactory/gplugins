from __future__ import annotations

from gdsfactory import components

from gplugins.common.config import PATH
from gplugins.lumerical.read import read_sparameters_lumerical

factory = {
    i: getattr(components, i)
    for i in dir(components)
    if not i.startswith("_") and callable(getattr(components, i))
}


# component_types = [
#     "straight",
#     "bend_circular",
#     "bend_euler",
#     "coupler",
#     "mmi1x2",
#     "mmi2x2",
# ]
# component_types = []


# @pytest.mark.parametrize("component_type", component_types)
# def test_read_sparameters(
#     component_type: str, data_regression: DataRegressionFixture, check: bool = True
# ) -> None:
#     c = factory[component_type]()
#     sp = read_sparameters_lumerical(component=c)

#     port_names = sp[0]
#     f = list(sp[1])
#     s = sp[2]

#     lenf = s.shape[0]
#     rows = s.shape[1]
#     cols = s.shape[2]

#     assert rows == cols == len(c.ports)
#     assert len(port_names) == len(c.ports)
#     if check:
#         data_regression.check(dict(port_names=port_names))
#     assert lenf == len(f)


def test_read_sparameters_2port_bend() -> None:
    filepath = PATH.test_data / "sp" / "bend_circular_S220.dat"
    port_names, f, s = read_sparameters_lumerical(filepath=filepath, numports=2)
    assert port_names == ("N0", "W0"), port_names


def test_read_sparameters_2port_straight() -> None:
    filepath = PATH.test_data / "sp" / "straight_S220.dat"
    port_names, f, s = read_sparameters_lumerical(filepath=filepath, numports=2)
    assert len(f) == 500
    assert port_names == ("E0", "W0"), port_names


def test_read_sparameters_3port_mmi1x2() -> None:
    filepath = PATH.test_data / "sp" / "mmi1x2_si220n.dat"
    port_names, f, s = read_sparameters_lumerical(filepath=filepath, numports=3)
    assert len(f) == 500
    assert port_names == ("E0", "E1", "W0"), port_names


def test_read_sparameters_4port_mmi2x2() -> None:
    filepath = PATH.test_data / "sp" / "mmi2x2_si220n.dat"
    port_names, f, s = read_sparameters_lumerical(filepath=filepath, numports=4)
    assert len(f) == 500
    assert port_names == ("E0", "E1", "W0", "W1"), port_names


if __name__ == "__main__":
    # c = gf.components.straight(layer=(2, 0))
    # print(c.get_sparameters_path())
    # test_read_sparameters("straight", None, False)
    test_read_sparameters_2port_straight()
