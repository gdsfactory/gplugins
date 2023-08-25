from unittest.mock import MagicMock

import gdsfactory as gf
import pytest
from gdsfactory.generic_tech.layer_map import LAYER as l
from kfactory import kdb

import gplugins.klayout.dataprep.regions as dp


@pytest.fixture
def mock_region() -> kdb.Region:
    r = kdb.Region()

    r.insert(kdb.Box(0, 3000, 1000, 4000))

    points = [kdb.Point(0, 1000), kdb.Point(3000, 1000), kdb.Point(3000, 4000)]
    r.insert(kdb.Path(points, 2000))
    return r


@pytest.fixture
def region_collection() -> dp.RegionCollection:
    c = gf.Component()
    ring = c << gf.components.coupler_ring()
    c << gf.components.bbox(ring.bbox, layer=l.FLOORPLAN)
    gdspath = c.write_gds()
    return dp.RegionCollection(gdspath)


@pytest.fixture
def mock_library() -> kdb.Region:
    lib = MagicMock()
    lib.layer.return_value = MagicMock()
    lib.top_cells.return_value = [MagicMock(name="mock_top_cell")]
    return lib


def test_size(mock_region) -> None:
    region = mock_region
    result = dp.size(region, 1)
    assert isinstance(result, kdb.Region)


def test_boolean_or(mock_region) -> None:
    region1 = mock_region
    region2 = mock_region.dup()
    result = dp.boolean_or(region1, region2)
    assert isinstance(result, kdb.Region)


def test_boolean_not(mock_region) -> None:
    region1 = mock_region
    region2 = mock_region.dup()
    result = dp.boolean_not(region1, region2)
    assert isinstance(result, kdb.Region)


def test_copy(mock_region) -> None:
    result = dp.copy(mock_region)
    assert isinstance(result, kdb.Region)


def test_region_operations(mock_region) -> None:
    r = dp.Region()
    r += 5
    assert isinstance(r, kdb.Region)

    r -= 5
    assert isinstance(r, kdb.Region)

    with pytest.raises(ValueError):
        r + "invalid_type"

    r1 = r + mock_region
    assert isinstance(r1, kdb.Region)


def test_Region_iadd() -> None:
    region = dp.Region()
    result = region.__iadd__(10.0)
    assert isinstance(result, dp.Region)


def test_Region_isub() -> None:
    region = dp.Region()
    result = region.__isub__(10.0)
    assert isinstance(result, dp.Region)


def test_RegionCollection_init(region_collection) -> None:
    # Check if the RegionCollection was initialized properly
    assert region_collection[(1, 0)]


if __name__ == "__main__":
    import pathlib

    module = pathlib.Path(__file__).parent.absolute()

    pytest.main(["-v", "-s", module / "test_dataprep_regions.py"])
