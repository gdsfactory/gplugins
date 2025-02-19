from __future__ import annotations

import gdsfactory as gf
import numpy as np
import pytest
from gdsfactory.config import PATH

from gplugins.klayout.get_density import (
    calculate_density,
    density_data_to_meshgrid,
    estimate_weighted_global_density,
    get_gds_bbox,
)


@gf.cell
def component_test_density1(
    large_rect_size: tuple[float, float] = (125, 125),
    small_rect1_size: tuple[float, float] = (50, 50),
    small_rect1_offset: tuple[float, float] = (-25, -25),
    small_rect2_size: tuple[float, float] = (50, 50),
    small_rect2_offset: tuple[float, float] = (25, 25),
) -> gf.Component:
    c = gf.Component()
    _ = c << gf.components.rectangle(size=large_rect_size, layer=(1, 0), centered=True)
    small_rect1 = c << gf.components.rectangle(
        size=small_rect1_size, layer=(2, 0), centered=True
    )
    small_rect2 = c << gf.components.rectangle(
        size=small_rect2_size, layer=(2, 0), centered=True
    )
    small_rect1.dmove(small_rect1_offset)
    small_rect2.dmove(small_rect2_offset)
    return c


def manual_density_calculation(
    large_rect_size: tuple[float, float],
    small_rect1_size: tuple[float, float],
    small_rect2_size: tuple[float, float],
) -> float:
    large_rect_area = large_rect_size[0] * large_rect_size[1]
    small_rect1_area = small_rect1_size[0] * small_rect1_size[1]
    small_rect2_area = small_rect2_size[0] * small_rect2_size[1]
    return (small_rect1_area + small_rect2_area) / large_rect_area


# Some cases
large_rect_sizes = [(4, 4)] * 3 + [(1, 1)]
small_rect1_sizes = [(1, 1)] * 4
small_rect2_sizes = [(1, 1)] * 4
small_rect1_offsets = [(1, 1)] * 2 + [(1.5, 1.5)] + [(0.5, 0.5)]
small_rect2_offsets = [(-1, -1)] * 2 + [(-1.5, -1.5)] + [(-0.5, -0.5)]
tile_sizes = [(1, 1), (0.75, 0.25), (1, 1), (1, 1)]
expected_global_densities = [
    manual_density_calculation(
        large_rect_size=large_rect_sizes[0],
        small_rect1_size=small_rect1_sizes[0],
        small_rect2_size=small_rect2_sizes[0],
    ),
] * 3 + [0.5]


@pytest.mark.parametrize(
    "large_rect_size, small_rect1_size, small_rect2_size, small_rect1_offset, small_rect2_offset, tile_size, expected_global_density",
    [
        (
            large_rect_sizes[i],
            small_rect1_sizes[i],
            small_rect2_sizes[i],
            small_rect1_offsets[i],
            small_rect2_offsets[i],
            tile_sizes[i],
            expected_global_densities[i],
        )
        for i in range(len(expected_global_densities))
    ],
)
def test_estimate_weighted_global_density(
    large_rect_size: tuple[float, float],
    small_rect1_size: tuple[float, float],
    small_rect2_size: tuple[float, float],
    small_rect1_offset: tuple[float, float],
    small_rect2_offset: tuple[float, float],
    tile_size: tuple[float, float],
    expected_global_density: float,
) -> None:
    gdspath = PATH.test_data / "test_gds_global_density.gds"
    test_component = component_test_density1(
        large_rect_size=large_rect_size,
        small_rect1_size=small_rect1_size,
        small_rect2_size=small_rect2_size,
        small_rect1_offset=small_rect1_offset,
        small_rect2_offset=small_rect2_offset,
    )
    test_component.write_gds(gdspath)

    density_data = calculate_density(gdspath=gdspath, layer=(2, 0), tile_size=tile_size)

    Xi, Yi, Zi = density_data_to_meshgrid(
        density_data=density_data,
        bbox=get_gds_bbox(gdspath),
    )

    estimated_density = estimate_weighted_global_density(
        Xi=Xi, Yi=Yi, Zi=Zi, bbox=get_gds_bbox(gdspath)
    )
    assert np.isclose(estimated_density, expected_global_density), (
        f"{estimated_density=}, {expected_global_density=}"
    )
