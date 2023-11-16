"""
This module contains the Tidy3DComponent class which is used to model 3D components in the Tidy3D simulation environment.
It extends the LayeredComponentBase class and adds additional properties and methods specific to the Tidy3D environment.

Classes:
    Tidy3DComponent: Represents a 3D component in the Tidy3D simulation environment.

Functions:
    polyslabs: Returns a dictionary of PolySlab instances for each layer in the component.
    structures: Returns a list of Structure instances for each PolySlab in the component.
    get_ports: Returns a list of Port instances for each optical port in the component.
    get_simulation: Returns a Simulation instance for the component.
    get_component_modeler: Returns a ComponentModeler instance for the component.
    plot_slice: Plots a cross section of the component at a specified position.
"""

from functools import cached_property

import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td
from pydantic import NonNegativeFloat
from tidy3d.plugins.smatrix import ComponentModeler, Port

from gplugins.common.base_models.component import LayeredComponentBase

from .types import Tidy3DElementMapping, Tidy3DMedium
from .util import get_port_normal, sort_layers


class Tidy3DComponent(LayeredComponentBase):
    """
    Represents a 3D component in the Tidy3D simulation environment.

    Attributes:
        material_mapping (dict[str, Tidy3DMedium]): A mapping of material names to Tidy3DMedium instances.
        extend_ports (NonNegativeFloat): The extension length for ports.
        port_offset (float): The offset for ports.
        pad_xy_inner (NonNegativeFloat): The inner padding in the xy-plane.
        pad_xy_outer (NonNegativeFloat): The outer padding in the xy-plane.
        pad_z_inner (float): The inner padding in the z-direction.
        pad_z_outer (NonNegativeFloat): The outer padding in the z-direction.
    """

    material_mapping: dict[str, Tidy3DMedium]
    extend_ports: NonNegativeFloat = 1.0
    port_offset: float = 0.2
    pad_xy_inner: NonNegativeFloat = 1.0
    pad_xy_outer: NonNegativeFloat = 3.0
    pad_z_inner: float = 1.0
    pad_z_outer: NonNegativeFloat = 3.0

    @cached_property
    def polyslabs(self) -> dict[str, tuple[td.PolySlab, ...]]:
        """
        Returns a dictionary of PolySlab instances for each layer in the component.

        Returns:
            dict[str, tuple[td.PolySlab, ...]]: A dictionary mapping layer names to tuples of PolySlab instances.
        """
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
        """
        Returns a list of Structure instances for each PolySlab in the component.

        Returns:
            list[td.Structure]: A list of Structure instances.
        """
        structures = []
        for name, polys in self.polyslabs.items():
            structures.extend(
                [
                    td.Structure(
                        geometry=poly,
                        medium=self.material_mapping[
                            self.geometry_layers[name].material
                        ],
                        name=f"{name}_{idx}",
                    )
                    for idx, poly in enumerate(polys)
                ]
            )
        return structures

    def get_ports(
        self,
        mode_spec: td.ModeSpec,
        size_mult: float | tuple[float, float] = (4.0, 2.0),
        cz: float | None = None,
    ) -> list[Port]:
        """
        Returns a list of Port instances for each optical port in the component.

        Args:
            mode_spec (td.ModeSpec): The mode specification for the ports.
            size_mult (float | tuple[float, float], optional): The size multiplier for the ports. Defaults to (4.0, 2.0).
            cz (float | None, optional): The z-coordinate for the ports. If None, the z-coordinate of the component is used. Defaults to None.

        Returns:
            list[Port]: A list of Port instances.
        """
        ports = []
        for port in self.ports:
            if port.port_type != "optical":
                continue
            center = self.get_port_center(port)
            center = center if cz is None else (*center[:2], cz)
            axis, direction = get_port_normal(port)

            match size_mult:
                case float():
                    size = np.full(3, size_mult * port.width)
                case tuple():
                    size = np.full(3, size_mult[0] * port.width)
                    size[2] = size_mult[1] * port.width
            size[axis] = 0

            ports.append(
                Port(
                    center=center,
                    size=tuple(size),
                    direction=direction,
                    mode_spec=mode_spec,
                    name=port.name,
                )
            )
        return ports

    def get_simulation(
        self,
        grid_spec: td.GridSpec,
        center_z: float,
        sim_size_z: int,
        boundary_spec: td.BoundarySpec,
        run_time: float = 1e-12,
        shutoff: float = 1e-5,
    ) -> td.Simulation:
        """
        Returns a Simulation instance for the component.

        Args:
            grid_spec (td.GridSpec): The grid specification for the simulation.
            center_z (float): The z-coordinate for the center of the simulation.
            sim_size_z (int): The size of the simulation in the z-direction.
            boundary_spec (td.BoundarySpec): The boundary specification for the simulation.
            run_time (float, optional): The run time for the simulation. Defaults to 1e-12.
            shutoff (float, optional): The shutoff value for the simulation. Defaults to 1e-5.

        Returns:
            td.Simulation: A Simulation instance.
        """
        sim_center = (*self.center[:2], center_z)
        sim_size = (*self.size[:2], sim_size_z)
        sim = td.Simulation(
            size=sim_size,
            center=sim_center,
            structures=self.structures,
            grid_spec=grid_spec,
            boundary_spec=boundary_spec,
            run_time=run_time,
            shutoff=shutoff,
        )
        return sim

    def get_component_modeler(
        self,
        wavelength: float = 1.55,
        bandwidth: float = 0.2,
        num_freqs: int = 21,
        min_steps_per_wvl: int = 30,
        center_z: float | str | None = None,
        sim_size_z: int = 4,
        port_size_mult: float | tuple[float, float] = (4.0, 3.0),
        run_only: tuple[tuple[str, int], ...] | None = None,
        element_mappings: Tidy3DElementMapping = (),
        mode_spec: td.ModeSpec = td.ModeSpec(num_modes=1, filter_pol="te"),
        boundary_spec: td.BoundarySpec = td.BoundarySpec.all_sides(boundary=td.PML()),
        run_time: float = 1e-12,
        shutoff: float = 1e-5,
        folder_name: str = "default",
        path_dir: str = ".",
        verbose: bool = True,
    ) -> ComponentModeler:
        """
        Returns a ComponentModeler instance for the component.

        Args:
            wavelength (float, optional): The wavelength for the ComponentModeler. Defaults to 1.55.
            bandwidth (float, optional): The bandwidth for the ComponentModeler. Defaults to 0.2.
            num_freqs (int, optional): The number of frequencies for the ComponentModeler. Defaults to 21.
            min_steps_per_wvl (int, optional): The minimum number of steps per wavelength for the ComponentModeler. Defaults to 30.
            center_z (float | str | None, optional): The z-coordinate for the center of the ComponentModeler. If None, the z-coordinate of the component is used. Defaults to None.
            sim_size_z (int, optional): The size of the simulation in the z-direction for the ComponentModeler. Defaults to 4.
            port_size_mult (float | tuple[float, float], optional): The size multiplier for the ports in the ComponentModeler. Defaults to (4.0, 3.0).
            run_only (tuple[tuple[str, int], ...] | None, optional): The run only specification for the ComponentModeler. Defaults to None.
            element_mappings (Tidy3DElementMapping, optional): The element mappings for the ComponentModeler. Defaults to ().
            mode_spec (td.ModeSpec, optional): The mode specification for the ComponentModeler. Defaults to td.ModeSpec(num_modes=1, filter_pol="te").
            boundary_spec (td.BoundarySpec, optional): The boundary specification for the ComponentModeler. Defaults to td.BoundarySpec.all_sides(boundary=td.PML()).
            run_time (float, optional): The run time for the ComponentModeler. Defaults to 1e-12.
            shutoff (float, optional): The shutoff value for the ComponentModeler. Defaults to 1e-5.
            folder_name (str, optional): The folder name for the ComponentModeler. Defaults to "default".
            path_dir (str, optional): The directory path for the ComponentModeler. Defaults to ".".
            verbose (bool, optional): Whether to print verbose output for the ComponentModeler. Defaults to True.

        Returns:
            ComponentModeler: A ComponentModeler instance.
        """
        match center_z:
            case float():
                cz = center_z
            case str():
                cz = self.get_layer_center(center_z)[2]
            case None:
                cz = self.center[2]
            case _:
                raise ValueError(f"Invalid center_z: {center_z}")

        freqs = td.C_0 / np.linspace(
            wavelength - bandwidth / 2, wavelength + bandwidth / 2, num_freqs
        )

        grid_spec = td.GridSpec.auto(
            wavelength=wavelength, min_steps_per_wvl=min_steps_per_wvl
        )

        if sim_size_z == 0:
            boundary_spec = boundary_spec.updated_copy(z=td.Boundary.periodic())

        sim = self.get_simulation(
            grid_spec=grid_spec,
            center_z=cz,
            sim_size_z=sim_size_z,
            boundary_spec=boundary_spec,
            run_time=run_time,
            shutoff=shutoff,
        )

        ports = self.get_ports(mode_spec, port_size_mult, cz)

        modeler = ComponentModeler(
            simulation=sim,
            ports=ports,
            freqs=tuple(freqs),
            element_mappings=element_mappings,
            run_only=run_only,
            folder_name=folder_name,
            path_dir=path_dir,
            verbose=verbose,
        )

        return modeler

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
        """
        Plots a cross section of the component at a specified position.

        Args:
            x (float | str | None, optional): The x-coordinate for the cross section. If None, the x-coordinate of the component is used. Defaults to None.
            y (float | str | None, optional): The y-coordinate for the cross section. If None, the y-coordinate of the component is used. Defaults to None.
            z (float | str | None, optional): The z-coordinate for the cross section. If None, the z-coordinate of the component is used. Defaults to None.
            offset (float, optional): The offset for the cross section. Defaults to 0.0.
            ax (plt.Axes | None, optional): The Axes instance to plot on. If None, a new Axes instance is created. Defaults to None.
            legend (bool, optional): Whether to include a legend in the plot. Defaults to False.

        Returns:
            plt.Axes: The Axes instance with the plot.
        """
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
