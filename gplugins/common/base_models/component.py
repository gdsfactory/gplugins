from functools import cached_property
from hashlib import md5

import gdsfactory as gf
import numpy as np
from gdsfactory.component import Component
from gdsfactory.technology import LayerLevel, LayerStack
from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    computed_field,
)
from shapely import MultiPolygon, Polygon

from gplugins.gmsh.parse_gds import cleanup_component

from ..types import AnyShapelyPolygon, GFComponent


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
    wafer_layer: tuple[int, int] = (99999, 0)
    slice_stack: tuple[int, int] = (0, -1)

    def __hash__(self):
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
        c = Component(name=f"sim_component_{self.component.name}")
        c << gf.components.extend_ports(
            self.component, length=self.extend_ports + self.pad_xy
        )
        c << gf.components.bbox(
            self._gds_bbox,
            layer=self.wafer_layer,
            top=self.pad_xy_outer,
            bottom=self.pad_xy_outer,
            left=self.pad_xy_outer,
            right=self.pad_xy_outer,
        )
        c.add_ports(self.gds_ports)
        c.copy_child_info(self.component)
        return c

    @cached_property
    def _gds_bbox(self) -> tuple[tuple[float, float], tuple[float, float]]:
        c = gf.components.extend_ports(
            self.component, length=self.extend_ports + self.pad_xy_inner
        ).ref()
        unchanged = np.isclose(np.abs(np.round(c.bbox - self.component.bbox, 3)), 0)
        bbox = c.bbox + unchanged * np.array([[-1, -1], [1, 1]]) * self.pad_xy_inner
        return tuple(map(tuple, bbox))

    @cached_property
    def gds_ports(self) -> dict[str, gf.Port]:
        return {
            n: p.move_polar_copy(self.extend_ports - self.port_offset, p.orientation)
            for n, p in self.component.ports.items()
        }

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
        }
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
    def port_centers(self) -> tuple[tuple[float, float, float], ...]:
        return tuple(self.get_port_center(p) for p in self.gds_ports.values())

    @cached_property
    def port_sizes(self):
        # TODO calculate maximum port sizes from neighbors
        for name, port in self.gds_ports.items():
            print(name, self.port_center(port))

    def get_port_center(self, port: gf.Port) -> tuple[float, float, float]:
        layer_czs = np.array(tuple(self.layer_centers.values()))
        return (
            *port.center,
            np.mean(
                [
                    layer_czs[idx, 2]
                    for idx, layer in enumerate(self.geometry_layers.values())
                    if layer.layer == port.layer
                ]
            ),
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

    def get_vertices(self, layer_name: str, buffer: float = 0.0):
        poly = self.polygons[layer_name].buffer(buffer, join_style="mitre")
        match poly:
            case MultiPolygon():
                verts = tuple(tuple(p.exterior.coords) for p in poly.geoms)
            case Polygon():
                verts = (tuple(poly.exterior.coords),)
            case _:
                raise TypeError(f"Invalid polygon type: {type(poly)}")
        return verts
