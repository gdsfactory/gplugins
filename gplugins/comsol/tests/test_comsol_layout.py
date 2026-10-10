"""Tests for the PDK-neutral COMSOL layout extraction.

The components are drawn on the generic PDK with positive metal only, so these
tests pin the behaviour any PDK wrapper builds on: the layer argument, feed port
validation, cropping at the feed planes, and the containment check a wrapper
runs on its drawn layers before preparing them.
"""

from __future__ import annotations

import gdsfactory as gf
import pytest

from gplugins.comsol.layout import (
    ComsolFeedPort,
    CropPlanes,
    crop_planes,
    feed_port,
    prepare_comsol_layout,
    validate_crop_containment,
)

METAL = (1, 0)
GAP = (2, 0)


@pytest.fixture(autouse=True)
def _generic_pdk() -> None:
    gf.gpdk.PDK.activate()


def _ground_with_trace(length: float = 100.0, margin: float = 20.0) -> gf.Component:
    """A ground plane with a slot, a centre trace in it, and two feed ports.

    The ground extends ``margin`` past the feeds along x.

    Returns:
        The component.
    """
    c = gf.Component()
    width, gap = 10.0, 6.0
    half = width / 2 + gap
    c.add_polygon(
        [
            (-margin, half),
            (length + margin, half),
            (length + margin, 60),
            (-margin, 60),
        ],
        layer=METAL,
    )
    c.add_polygon(
        [
            (-margin, -60),
            (length + margin, -60),
            (length + margin, -half),
            (-margin, -half),
        ],
        layer=METAL,
    )
    c.add_polygon(
        [
            (-margin, -width / 2),
            (length + margin, -width / 2),
            (length + margin, width / 2),
            (-margin, width / 2),
        ],
        layer=METAL,
    )
    c.add_port("o1", center=(0, 0), width=width, orientation=180, layer=METAL)
    c.add_port("o2", center=(length, 0), width=width, orientation=0, layer=METAL)
    return c


def _ring() -> gf.Component:
    """A square of metal with a square hole in it.

    Returns:
        The component.
    """
    c = gf.Component()
    c.add_polygon([(0, 0), (40, 0), (40, 40), (0, 40)], layer=METAL)
    c.add_polygon([(10, 10), (30, 10), (30, 30), (10, 30)], layer=GAP)
    region = gf.kdb.Region(c.begin_shapes_rec(c.kcl.layer(*METAL))) - gf.kdb.Region(
        c.begin_shapes_rec(c.kcl.layer(*GAP))
    )
    out = gf.Component()
    out.add_polygon(region, layer=METAL)
    return out


def test_unfed_extraction_keeps_holes_and_bbox():
    layout = prepare_comsol_layout(_ring(), METAL)

    assert layout.feed_ports == ()
    assert len(layout.polygons) == 1
    assert len(layout.polygons[0].holes) == 1
    assert (layout.bbox.xmin, layout.bbox.ymin) == (0.0, 0.0)
    assert (layout.bbox.width, layout.bbox.height) == (40.0, 40.0)


def test_layer_spec_by_name_matches_tuple():
    by_tuple = prepare_comsol_layout(_ring(), METAL)
    by_name = prepare_comsol_layout(_ring(), "WG")

    assert by_name == by_tuple


def test_missing_metal_names_the_layer():
    with pytest.raises(ValueError, match=r"no metal on layer \(3, 0\)"):
        prepare_comsol_layout(_ring(), (3, 0))


def test_feed_ports_are_reported_without_cropping():
    layout = prepare_comsol_layout(_ground_with_trace(), METAL, ("o1", "o2"))

    assert [port.name for port in layout.feed_ports] == ["o1", "o2"]
    assert layout.feed_ports[0] == ComsolFeedPort(
        name="o1", center=(0.0, 0.0), width=10.0, orientation=180.0
    )
    assert layout.bbox.xmin == -20.0
    assert layout.bbox.xmax == 120.0


def test_crop_clips_metal_to_the_feed_planes():
    layout = prepare_comsol_layout(
        _ground_with_trace(), METAL, ("o1", "o2"), crop_to_feed_ports=True
    )

    assert (layout.bbox.xmin, layout.bbox.xmax) == (0.0, 100.0)
    assert len(layout.polygons) == 3
    for polygon in layout.polygons:
        xs = [x for x, _ in polygon.outline]
        assert min(xs) == 0.0
        assert max(xs) == 100.0


@pytest.mark.parametrize(
    ("feed_ports", "match"),
    [
        (("o1",), "exactly two"),
        (("o1", "o1"), "distinct"),
        (("o1", "nope"), "not available"),
    ],
)
def test_bad_feed_port_names_are_rejected(feed_ports, match):
    with pytest.raises(ValueError, match=match):
        prepare_comsol_layout(_ground_with_trace(), METAL, feed_ports)


def test_crop_needs_feed_ports():
    with pytest.raises(ValueError, match="needs two feed ports"):
        prepare_comsol_layout(_ring(), METAL, crop_to_feed_ports=True)


def test_feed_port_rejects_non_cardinal_orientation():
    c = _ground_with_trace()
    c.add_port("diag", center=(50, 50), width=5, orientation=45, layer=METAL)

    with pytest.raises(ValueError, match="not cardinal"):
        feed_port(c, "diag")


def _port(center: tuple[float, float], orientation: float) -> ComsolFeedPort:
    return ComsolFeedPort(name="p", center=center, width=1.0, orientation=orientation)


def test_crop_planes_orders_low_to_high():
    planes = crop_planes((_port((10, 0), 0), _port((-5, 0), 180)))

    assert planes == CropPlanes(axis=0, low=-5.0, high=10.0)


def test_crop_planes_along_y():
    planes = crop_planes((_port((0, 7), 90), _port((0, -3), 270)))

    assert planes == CropPlanes(axis=1, low=-3.0, high=7.0)


@pytest.mark.parametrize(
    ("ports", "match"),
    [
        ((_port((0, 0), 180), _port((10, 0), 90)), "same axis"),
        ((_port((0, 0), 0), _port((10, 0), 180)), "face outwards"),
        ((_port((0, 0), 180), _port((10, 1), 0)), "transverse"),
    ],
)
def test_crop_planes_rejects_invalid_pairs(ports, match):
    with pytest.raises(ValueError, match=match):
        crop_planes(ports)


def test_snap_rounds_outwards():
    planes = CropPlanes(axis=0, low=-0.0004, high=1.0004)

    assert planes.snap(0.001) == (-1, 1001)
    assert all(isinstance(value, int) for value in planes.snap(0.001))


def _drawn_cpw(device_overhang: float = 0.0) -> gf.Component:
    """A drawn CPW: a centre trace and two gap strips, before any ground fill.

    Returns:
        The component.
    """
    c = gf.Component()
    c.add_polygon(
        [(0, -5), (100 + device_overhang, -5), (100 + device_overhang, 5), (0, 5)],
        layer=METAL,
    )
    c.add_polygon([(0, 5), (100, 5), (100, 11), (0, 11)], layer=GAP)
    c.add_polygon([(0, -11), (100, -11), (100, -5), (0, -5)], layer=GAP)
    return c


def test_containment_accepts_geometry_between_the_planes():
    planes = CropPlanes(axis=0, low=0.0, high=100.0)

    validate_crop_containment(_drawn_cpw(), planes, layers=(METAL, GAP), gap_layer=GAP)


def test_containment_refuses_geometry_beyond_a_plane():
    planes = CropPlanes(axis=0, low=0.0, high=100.0)

    with pytest.raises(ValueError, match="would cut component geometry"):
        validate_crop_containment(_drawn_cpw(5.0), planes, layers=(METAL,))


def test_containment_requires_gaps_at_both_planes():
    planes = CropPlanes(axis=0, low=-10.0, high=100.0)

    with pytest.raises(ValueError, match="reach both feed"):
        validate_crop_containment(_drawn_cpw(), planes, layers=(METAL,), gap_layer=GAP)


def test_containment_requires_a_gap_layer_with_geometry():
    planes = CropPlanes(axis=0, low=0.0, high=100.0)

    with pytest.raises(ValueError, match="requires gaps"):
        validate_crop_containment(
            _drawn_cpw(), planes, layers=(METAL,), gap_layer=(3, 0)
        )
