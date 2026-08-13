from types import SimpleNamespace

import gdsfactory as gf
from kfactory import kdb

from gplugins.lumerical.write_sparameters_lumerical import (
    _get_component_with_background_layers,
)


class _LayerStack:
    def __init__(self, level: SimpleNamespace) -> None:
        self.layers = {"background": level}

    def get_component_with_derived_layers(
        self, component: gf.Component
    ) -> gf.Component:
        return component.copy()


def test_materializes_background_layer_with_exclusions() -> None:
    component = gf.Component()
    component.add_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], layer=(3, 0))
    component.add_polygon([(2, 2), (8, 2), (8, 8), (2, 8)], layer=(2, 0))
    layer_stack = _LayerStack(
        SimpleNamespace(
            background=True,
            layer=(1, 0),
            background_exclude_layers=((2, 0),),
        )
    )

    result = _get_component_with_background_layers(component, layer_stack)
    region = kdb.Region(result.kdb_cell.begin_shapes_rec(result.kcl.layer(1, 0)))

    assert region.area() == 64_000_000
