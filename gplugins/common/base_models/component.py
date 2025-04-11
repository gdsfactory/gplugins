from functools import cached_property
from hashlib import md5
from typing import TypeAlias

import gdsfactory as gf
import numpy as np
from gdsfactory.component import Component
from gdsfactory.technology import LayerLevel, LayerStack
from numpy.typing import NDArray
from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    computed_field,
)
from shapely import MultiPolygon, Polygon

from gplugins.gmsh.parse_gds import cleanup_component

from ..types import AnyShapelyPolygon, GFComponent

Coordinate: TypeAlias = tuple[float, float]


def move_polar_rad_copy(
    pos: Coordinate, angle: float, length: float
) -> NDArray[np.float64]:
    """Returns the points of a position (pos) with angle, shifted by length.

    Args:
        pos: position.
        angle: in radians.
        length: extension length in um.
    """
    c = np.cos(angle)
    s = np.sin(angle)
    return pos + length * np.array([c, s])


class LayeredComponentBase(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        allow_inf_nan=False,
        validate_return=True,
    )

    component: GFComponent
    layer_stack: LayerStack
    extend_ports: NonNegativeFloat = 0.0
    port_offset: float = 0.0
    pad_xy_inner: float = 0.0
    pad_xy_outer: NonNegativeFloat = 0.0
    pad_z_inner: float = 0.0
    pad_z_outer: NonNegativeFloat = 0.0
    wafer_layer: tuple[int, int] = (999, 0)
    slice_stack: tuple[int, int | None] = (0, None)

    def __hash__(self):
        """Returns a hash of the model dump."""
        if not hasattr(self, "_hash"):
            dump = str.encode(self.model_dump_json())
            self._hash = int(md5(dump).hexdigest()[:15], 16)
        return self._hash

    @property
    def pad_xy(self) -> float:
        return self.pad_xy_inner + self.pad_xy_outer

    @property
    def pad_z(self) -> float:
        return self.pad_z_inner + self.pad_z_outer

    @cached_property
    def gds_component(self) -> GFComponent:
        c = Component()
        c << gf.components.extend_ports(
            self.component, length=self.extend_ports + self.pad_xy
        )
        (xmin, ymin), (xmax, ymax) = self._gds_bbox
        delta = self.pad_xy_outer
        points = [
            [xmin - delta, ymin - delta],
            [xmax + delta, ymin - delta],
            [xmax + delta, ymax + delta],
            [xmin - delta, ymax + delta],
        ]
        c.add_polygon(points, layer=self.wafer_layer)
        c.add_ports(self.ports)
        c.copy_child_info(self.component)
        return c

    @cached_property
    def _gds_bbox(self) -> tuple[tuple[float, float], tuple[float, float]]:
        c = gf.components.extend_ports(
            self.component, length=self.extend_ports + self.pad_xy_inner
        )
        unchanged = np.isclose(
            np.abs(np.round(c.bbox_np() - self.component.bbox_np(), 3)), 0
        )
        bbox = (
            c.bbox_np() + unchanged * np.array([[-1, -1], [1, 1]]) * self.pad_xy_inner
        )
        return tuple(map(tuple, bbox))

    @cached_property
    def ports(self) -> tuple[gf.Port, ...]:
        p = tuple(
            p.copy_polar(
                self.extend_ports + self.pad_xy_inner - self.port_offset,
                orientation=p.orientation,
            )
            for p in self.component.ports
        )
        for pi, po in zip(self.component.ports, p):
            po.angle = pi.angle
        return p

    @computed_field
    @cached_property
    def polygons(self) -> dict[str, AnyShapelyPolygon]:
        return cleanup_component(
            self.gds_component, self.layer_stack, round_tol=3, simplify_tol=1e-3
        )

    @cached_property
    def geometry_layers(self) -> dict[str, LayerLevel]:
        layers = {
            k: v
            for k, v in self.layer_stack.layers.items()
            if not self.polygons[k].is_empty
            and v.zmin is not None
            and v.thickness is not None
        }

        layers = dict(sorted(layers.items(), key=lambda x: x[1].zmin + x[1].thickness))
        return dict(tuple(layers.items())[slice(*self.slice_stack)])

    @property
    def xmin(self) -> float:
        return self._gds_bbox[0][0]

    @property
    def xmax(self) -> float:
        return self._gds_bbox[1][0]

    @property
    def ymin(self) -> float:
        return self._gds_bbox[0][1]

    @property
    def ymax(self) -> float:
        return self._gds_bbox[1][1]

    @cached_property
    def zmin(self) -> float:
        return (
            min(
                min(layer.zmin, layer.zmin + layer.thickness)
                for layer in self.geometry_layers.values()
            )
            - self.pad_z_inner
        )

    @cached_property
    def zmax(self) -> float:
        return (
            max(
                max(layer.zmin, layer.zmin + layer.thickness)
                for layer in self.geometry_layers.values()
            )
            + self.pad_z_inner
        )

    @property
    def bbox(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        return (*self._gds_bbox[0], self.zmin), (*self._gds_bbox[1], self.zmax)

    @property
    def center(self) -> tuple[float, float, float]:
        return tuple(np.mean(self.bbox, axis=0))

    @property
    def size(self) -> tuple[float, float, float]:
        return tuple(np.squeeze(np.diff(self.bbox, axis=0)))

    @cached_property
    def bottom_layer(self) -> str:
        return min(
            self.geometry_layers.items(),
            key=lambda item: min([item[1].zmin, item[1].zmin + item[1].thickness]),
        )[0]

    @cached_property
    def top_layer(self) -> str:
        return max(
            self.geometry_layers.items(),
            key=lambda item: max([item[1].zmin, item[1].zmin + item[1].thickness]),
        )[0]

    @cached_property
    def device_layers(self) -> tuple[str, ...]:
        return tuple(
            k
            for k, v in self.layer_stack.layers.items()
            if v.layer in self.component.layers
        )

    @cached_property
    def port_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.ports)

    @cached_property
    def port_centers(self) -> tuple[tuple[float, float, float], ...]:
        return tuple(self.get_port_center(p) for p in self.ports)

    def get_port_center(self, port: gf.Port) -> tuple[float, float, float]:
        layers = self.get_port_layers(port)
        return (
            *port.dcenter,
            np.mean([self.get_layer_center(layer)[2] for layer in layers]),
        )

    def get_port_layers(self, port: gf.Port) -> tuple[str, ...]:
        # FIXME: extract actual layer
        # this needs to be a list of all layers and derived layers that are
        # associated with the port layer enum
        return ("core",)
        return tuple(
            k for k, v in self.layer_stack.layers.items() if port.layer in v.layer
        )

    def get_layer_bbox(
        self, layername: str
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        layer = self.layer_stack[layername]
        bounds_xy = self.polygons[layername].bounds
        zmin, zmax = sorted([layer.zmin, layer.zmin + layer.thickness])

        if layername == self.bottom_layer:
            zmin -= self.pad_z
        if layername == self.top_layer:
            zmax += self.pad_z

        return (*bounds_xy[:2], zmin), (*bounds_xy[2:], zmax)

    def get_layer_center(self, layername: str) -> tuple[float, float, float]:
        bbox = self.get_layer_bbox(layername)
        return tuple(np.mean(bbox, axis=0))
