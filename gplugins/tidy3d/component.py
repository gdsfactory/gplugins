from functools import cached_property

import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td
from pydantic import (
    NonNegativeFloat,
)

from .base import SimulationComponentBase
from .custom_types import Tidy3DMedium
from .util import sort_layers


class Tidy3DComponent(SimulationComponentBase):
    material_mapping: dict[str, Tidy3DMedium]
    extend_ports: NonNegativeFloat = 1.0
    port_offset: float = 0.2
    pad_xy_inner: NonNegativeFloat = 1.0
    pad_xy_outer: NonNegativeFloat = 3.0
    pad_z_inner: NonNegativeFloat = 1.0
    pad_z_outer: NonNegativeFloat = 3.0

    @cached_property
    def polyslabs(self) -> dict[str, tuple[td.PolySlab, ...]]:
        slabs = {}
        layers = sort_layers(self.geometry_layers, sort_by="mesh_order", reverse=True)
        for name, layer in layers.items():
            bbox = self.get_layer_bbox(name)
            slabs[name] = tuple(
                td.PolySlab(
                    vertices=v,
                    axis=2,
                    slab_bounds=(bbox[0][2], bbox[1][2]),
                    sidewall_angle=np.deg2rad(layer.sidewall_angle),
                    reference_plane="middle",
                )
                for v in self.get_vertices(name)
            )
        return slabs

    @cached_property
    def structures(self) -> list[td.Structure]:
        structures = []
        for name, polys in self.polyslabs.items():
            structures.extend(
                [
                    td.Structure(
                        geometry=poly,
                        medium=self.aterial_mapping[
                            self.geometry_layers[name].material
                        ],
                        name=name,
                    )
                    for poly in polys
                ]
            )
        return structures

    @td.components.viz.add_ax_if_none
    def plot_slice(
        self,
        x: float | str | None = None,
        y: float | str | None = None,
        z: float | str | None = None,
        offset: float = 0.0,
        ax: plt.Axes | None = None,
        legend: bool = False,
    ) -> plt.Axes:
        x, y, z = (
            self.get_layer_center(c)[i] if isinstance(c, str) else c
            for i, c in enumerate((x, y, z))
        )
        x, y, z = (c if c is None else c + offset for c in (x, y, z))

        colors = dict(
            zip(
                self.polyslabs.keys(),
                plt.colormaps.get_cmap("Spectral")(
                    np.linspace(0, 1, len(self.polyslabs))
                ),
            )
        )

        layers = sort_layers(self.geometry_layers, sort_by="zmin", reverse=True)
        meshorders = np.unique([v.mesh_order for v in layers.values()])
        order_map = dict(zip(meshorders, range(0, -len(meshorders), -1)))
        xmin, xmax = np.inf, -np.inf
        ymin, ymax = np.inf, -np.inf

        for name, layer in layers.items():
            if name not in self.polyslabs:
                continue
            polys = self.polyslabs[name]

            for idx, poly in enumerate(polys):
                axis, position = poly.parse_xyz_kwargs(x=x, y=y, z=z)
                xlim, ylim = poly._get_plot_limits(axis=axis, buffer=0)
                xmin, xmax = min(xmin, xlim[0]), max(xmax, xlim[1])
                ymin, ymax = min(ymin, ylim[0]), max(ymax, ylim[1])
                for shape in poly.intersections_plane(x=x, y=y, z=z):
                    _shape = td.Geometry.evaluate_inf_shape(shape)
                    patch = td.components.viz.polygon_patch(
                        _shape,
                        facecolor=colors[name],
                        edgecolor="k",
                        linewidth=0.5,
                        label=name if idx == 0 else None,
                        zorder=order_map[layer.mesh_order],
                    )
                    ax.add_artist(patch)

        size = list(self.size)
        cmin = list(self.bbox[0])
        size.pop(axis)
        cmin.pop(axis)

        sim_roi = plt.Rectangle(
            cmin,
            *size,
            facecolor="none",
            edgecolor="k",
            linestyle="--",
            linewidth=1,
            label="Simulation",
        )
        ax.add_patch(sim_roi)

        xlabel, ylabel = poly._get_plot_labels(axis=axis)
        ax.set_title(f"cross section at {'xyz'[axis]}={position:.2f}")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        if legend:
            ax.legend(fancybox=True, framealpha=1.0)

        return ax
