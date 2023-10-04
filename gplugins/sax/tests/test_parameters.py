import gdsfactory as gf

from gplugins.sax.parameter import LithoParameter


def test_litho_parameters() -> None:
    layer1 = (1, 0)
    layer2 = (2, 0)

    c = gf.Component("myComponent")
    c.add_polygon(
        [[2.8, 3], [5, 3], [5, 0.8]],
        layer=layer1,
    )
    c.add_polygon(
        [
            [2, 0],
            [2, 2],
            [4, 2],
            [4, 0],
        ],
        layer=layer1,
    )
    c.add_polygon(
        [
            [0, 0.5],
            [0, 1.5],
            [3, 1.5],
            [3, 0.5],
        ],
        layer=layer1,
    )
    c.add_polygon(
        [
            [0, 0],
            [5, 0],
            [5, 3],
            [0, 3],
        ],
        layer=layer2,
    )
    c.add_polygon(
        [
            [2.5, -2],
            [3.5, -2],
            [3.5, -0.1],
            [2.5, -0.1],
        ],
        layer=layer1,
    )
    c.add_port(name="o1", center=(0, 1), width=1, orientation=0, layer=layer1)
    c.add_port(name="o2", center=(3, -2), width=1, orientation=90, layer=layer1)

    param = LithoParameter(layername="core")
    param.layer_dilation_erosion(c, 0.2)

    param = LithoParameter(layername="core")
    param.layer_dilation_erosion(c, -0.2)

    param = LithoParameter(layername="core")
    param.layer_x_offset(c, 0.5)

    param = LithoParameter(layername="core")
    param.layer_y_offset(c, 0.5)

    param = LithoParameter(layername="core")
    param.layer_round_corners(c, 0.2)
