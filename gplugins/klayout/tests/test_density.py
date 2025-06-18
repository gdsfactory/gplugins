from __future__ import annotations

import gdsfactory as gf
import numpy as np
import pytest
from gdsfactory.config import PATH

from gplugins.klayout.get_density import (
    calculate_density,
    density_data_to_meshgrid,
    get_gds_bbox,
)


@gf.cell
def component_test_density1():
    c = gf.Component("density_test1")
    large_rect = c << gf.components.rectangle(size=(100, 150), layer=(1, 0))
    _small_rect = c << gf.components.rectangle(size=(50, 50), layer=(2, 0))
    small_rect2 = c << gf.components.rectangle(size=(25, 25), layer=(2, 0))
    small_rect2.ymax = 100 - small_rect2.ysize
    small_rect2.xmax = large_rect.xmax - small_rect2.xsize
    return c


expected_densities = (
    [
        [0.765625, 0.875, 0.546875, 0, 0, 0],
        [0.875, 1, 0.625, 0, 0, 0],
        [0.546875, 0.625, 0.53125, 0.328125, 0, 0],
        [0, 0, 0.328125, 0.765625, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0],
    ],
    [[1, 1.0], [1, 1.0], [1, 1.0]],
)


@pytest.mark.parametrize(
    "layer, tile_size, expected_densities",
    [
        ((2, 0), (20, 20), expected_densities[0]),
        ((1, 0), (50, 50), expected_densities[1]),
        ((2, 0), (100, 100), None),
    ],
)
def test_calculate_density(layer, tile_size, expected_densities) -> None:
    gdspath = PATH.test_data / "test_gds_density1.gds"

    test_component = component_test_density1()
    test_component.write_gds(PATH.test_data / "test_gds_density1.gds")

    threads = gf.config.get_number_of_cores()

    bbox = get_gds_bbox(gdspath=gdspath)
    if expected_densities is None:
        with pytest.raises(ValueError) as e:
            calculate_density(
                gdspath=gdspath, layer=layer, tile_size=tile_size, threads=threads
            )
            assert (
                str(e.value)
                == f"Too large tile size {tile_size} for bbox {(bbox[0][0], bbox[0][1]), (bbox[1][0], bbox[1][1])}: reduce tile size (and merge later if needed)."
            )
            return
    else:
        density_data = calculate_density(
            gdspath=gdspath, layer=layer, tile_size=tile_size, threads=threads
        )

        # Get density meshgrid
        Xi, Yi, Zi = density_data_to_meshgrid(density_data=density_data, bbox=bbox)
        np.testing.assert_allclose(Zi, expected_densities, rtol=1e-3)
