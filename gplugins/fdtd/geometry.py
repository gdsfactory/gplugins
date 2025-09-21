"""This module contains the Geometry class which is used to model 3D components in the Tidy3D simulation environment.

It extends the LayeredComponentBase class and adds additional properties and methods specific to the Tidy3D environment.

Classes:
    Geometry: Represents a 3D component in the Tidy3D simulation environment.

Functions:
    polyslabs: Returns a dictionary of PolySlab instances for each layer in the component.
    structures: Returns a list of Structure instances for each PolySlab in the component.
    get_ports: Returns a list of Port instances for each optical port in the component.
    get_simulation: Returns a Simulation instance for the component.
    get_component_modeler: Returns a ComponentModeler instance for the component.
    plot_slice: Plots a cross section of the component at a specified position.
"""

import pathlib
import time
from functools import cached_property
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td
from gdsfactory.component import Component
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from pydantic import NonNegativeFloat
from tidy3d.components.geometry.base import from_shapely
from tidy3d.components.types import Symmetry
from tidy3d.plugins.smatrix import ComponentModeler, Port

from gplugins.common.base_models.component import LayeredComponentBase
from gplugins.fdtd.render2d import plot_prism_slices
from gplugins.tidy3d.types import (
    Sparameters,
    Tidy3DElementMapping,
    Tidy3DMedium,
)
from gplugins.tidy3d.util import get_mode_solvers, get_port_normal, sort_layers

from gplugins.fdtd.render3d import plot_prisms_3d, plot_prisms_3d_open3d, export_3d_mesh, create_web_export, serve_threejs_visualization

PathType = pathlib.Path | str

material_name_to_medium = {
    "si": td.Medium(name="Si", permittivity=3.47**2),
    "sio2": td.Medium(name="SiO2", permittivity=1.47**2),
    "sin": td.Medium(name="SiN", permittivity=2.0**2),
}

home = pathlib.Path.home()
dirpath_default = home / ".gdsfactory" / "sparameters"


class Geometry(LayeredComponentBase):
    """Represents a 3D component in the Tidy3D simulation environment.

    Attributes:
        component: GDS component (can be None for initialization)
        layer_stack: LayerStack (can be None for initialization)
        extend_ports (NonNegativeFloat): The extension length for ports.
        port_offset (float): The offset for ports.
        pad_xy_inner (NonNegativeFloat): The inner padding in the xy-plane.
        pad_xy_outer (NonNegativeFloat): The outer padding in the xy-plane.
        pad_z_inner (float): The inner padding in the z-direction.
        pad_z_outer (NonNegativeFloat): The outer padding in the z-direction.
        dilation (float): Dilation of the polygon in the base by shifting each edge along its
            normal outwards direction by a distance;
            a negative value corresponds to erosion. Defaults to zero.
       reference_plane (Literal["bottom", "middle", "top"]): the reference plane
           used by tidy3d's PolySlab when applying sidewall_angle to a layer
    """
    extend_ports: NonNegativeFloat = 0.5  # TODO: Move to Physics or Solver class
    port_offset: float = 0.2  # TODO: Move to Physics or Solver class
    pad_xy_inner: NonNegativeFloat = 3.0
    pad_xy_outer: NonNegativeFloat = 3.0
    pad_z_inner: float = 3.0
    pad_z_outer: NonNegativeFloat = 3.0
    dilation: float = 0.0
    reference_plane: Literal["bottom", "middle", "top"] = "middle"

    @cached_property
    def bbox(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Override bbox to use core layer bounds plus padding."""
        try:
            core_bbox = self.get_layer_bbox("core")
            # core_bbox = ((xmin, ymin, zmin), (xmax, ymax, zmax))

            # Apply padding to core layer bbox
            xmin = core_bbox[0][0] - self.pad_xy_outer
            ymin = core_bbox[0][1] - self.pad_xy_outer
            zmin = core_bbox[0][2] - self.pad_z_outer

            xmax = core_bbox[1][0] + self.pad_xy_outer
            ymax = core_bbox[1][1] + self.pad_xy_outer
            zmax = core_bbox[1][2] + self.pad_z_outer

            return ((xmin, ymin, zmin), (xmax, ymax, zmax))
        except KeyError:
            # Fallback to parent implementation if no "core" layer
            return super().bbox

    @cached_property
    def polyslabs(self) -> dict[str, tuple[td.Geometry, ...]]:
        """Returns a dictionary of PolySlab instances for each layer in the component.

        Returns:
            dict[str, tuple[td.PolySlab, ...]]: A dictionary mapping layer names to tuples of PolySlab instances.
        """
        slabs = {}
        layers = sort_layers(self.geometry_layers, sort_by="mesh_order", reverse=True)
        for name, layer in layers.items():
            bbox = self.get_layer_bbox(name)
            shape = self.polygons[name].buffer(distance=0.0, join_style="mitre")
            geom = from_shapely(
                shape,
                axis=2,
                slab_bounds=(bbox[0][2], bbox[1][2]),
                dilation=self.dilation,
                sidewall_angle=np.deg2rad(layer.sidewall_angle),
                reference_plane=self.reference_plane,
            )
            slabs[name] = geom

        return slabs

    @cached_property
    def meep_prisms(self) -> dict[str, list]:
        """Returns MEEP Prism instances for each layer, alternative to Tidy3D PolySlabs.

        Key differences from Tidy3D implementation:
        - Tidy3D uses Shapely for polygon operations (buffering, boolean ops) before conversion
        - MEEP directly accepts polygon vertices, no Shapely preprocessing needed
        - Tidy3D returns one PolySlab per layer (handles multiple polygons internally)
        - MEEP returns list of Prisms per layer (one Prism per polygon)

        Similarities:
        - Both support 3D extrusion with sidewall angles
        - Both use layer thickness for vertical dimensions (zmin, zmax)
        - Both maintain layer ordering via mesh_order

        MEEP implementation details:
        - Uses mp.Vector3 for 3D vertex coordinates
        - Requires explicit height parameter (thickness)
        - Sidewall angle in radians (converted from degrees)
        - Materials NOT assigned here - can be added later via prism.material = mp.Medium(...)

        Returns:
            dict[str, list[mp.Prism]]: Layer names mapped to lists of MEEP Prism objects.
                Each polygon in a layer becomes a separate Prism.
        """
        import meep as mp

        prisms = {}
        layers = sort_layers(self.geometry_layers, sort_by="mesh_order", reverse=True)

        for name, layer in layers.items():
            bbox = self.get_layer_bbox(name)
            zmin = bbox[0][2]
            height = bbox[1][2] - bbox[0][2]

            # Get polygons for this layer
            shape = self.polygons[name]

            # Convert each polygon to MEEP Prism
            layer_prisms = []

            # Handle both single polygon and MultiPolygon
            if hasattr(shape, 'geoms'):  # MultiPolygon
                polygons = shape.geoms
            else:  # Single Polygon
                polygons = [shape]

            for polygon in polygons:
                # Skip if not a valid polygon
                if polygon.is_empty or not polygon.is_valid:
                    continue

                # Check if polygon has holes - if so, triangulate it
                if hasattr(polygon, 'interiors') and polygon.interiors:
                    # Triangulate polygon with holes into multiple small prisms
                    triangular_prisms = self._create_triangulated_prisms(
                        polygon, height, zmin, layer.sidewall_angle
                    )
                    layer_prisms.extend(triangular_prisms)
                else:
                    # Simple polygon without holes - create single prism as before
                    vertices = [mp.Vector3(p[0], p[1], zmin) for p in polygon.exterior.coords[:-1]]

                    prism = mp.Prism(
                        vertices=vertices,
                        height=height,
                        sidewall_angle=np.deg2rad(layer.sidewall_angle) if layer.sidewall_angle else 0,
                    )

                    # Store original Shapely polygon for 3D rendering
                    prism._original_polygon = polygon
                    layer_prisms.append(prism)

            prisms[name] = layer_prisms

        return prisms

    def _create_triangulated_prisms(self, polygon, height: float, zmin: float, sidewall_angle: float = 0):
        """Create multiple triangular MEEP prisms from a polygon with holes.

        Args:
            polygon: Shapely polygon with holes
            height: Extrusion height for prisms
            zmin: Z-coordinate for base of prisms
            sidewall_angle: Sidewall angle in degrees

        Returns:
            List of MEEP Prism objects representing triangulated polygon
        """
        import meep as mp
        try:
            import numpy as np
            from scipy.spatial import Delaunay
            import shapely.geometry as sg
        except ImportError:
            # Fallback to single prism if triangulation libraries not available
            print("Warning: scipy not available, falling back to exterior-only prism")
            vertices = [mp.Vector3(p[0], p[1], zmin) for p in polygon.exterior.coords[:-1]]
            prism = mp.Prism(
                vertices=vertices,
                height=height,
                sidewall_angle=np.deg2rad(sidewall_angle) if sidewall_angle else 0,
            )
            prism._original_polygon = polygon
            return [prism]

        # Extract all boundary points (exterior + holes)
        all_points = []

        # Add exterior boundary points
        all_points.extend(list(polygon.exterior.coords[:-1]))  # Remove duplicate last point

        # Add interior boundary points (holes)
        for interior in polygon.interiors:
            all_points.extend(list(interior.coords[:-1]))  # Remove duplicate last point

        if len(all_points) < 3:
            # Not enough points for triangulation - fallback
            vertices = [mp.Vector3(p[0], p[1], zmin) for p in polygon.exterior.coords[:-1]]
            prism = mp.Prism(
                vertices=vertices,
                height=height,
                sidewall_angle=np.deg2rad(sidewall_angle) if sidewall_angle else 0,
            )
            prism._original_polygon = polygon
            return [prism]

        # Use efficient ring-specific triangulation instead of full Delaunay
        triangular_prisms = []

        # Check if this is a simple ring (1 hole, similar vertex counts)
        if (len(polygon.interiors) == 1 and
            len(all_points) < 200 and  # Reasonable size limit
            abs(len(list(polygon.exterior.coords)) - len(list(polygon.interiors[0].coords))) < 10):

            # Efficient ring triangulation
            triangular_prisms = self._create_ring_triangulation(
                polygon, height, zmin, sidewall_angle
            )

        else:
            # Fall back to Delaunay for complex polygons
            points_2d = np.array(all_points)
            tri = Delaunay(points_2d)

            # Filter triangles to keep only those inside the polygon (not in holes)
            for triangle_indices in tri.simplices:
                # Calculate triangle centroid
                triangle_points = points_2d[triangle_indices]
                centroid = np.mean(triangle_points, axis=0)
                centroid_point = sg.Point(centroid[0], centroid[1])

                # Check if centroid is inside the polygon (and not in any hole)
                if polygon.contains(centroid_point):
                    # Create triangular MEEP prism
                    triangle_vertices = [
                        mp.Vector3(triangle_points[0][0], triangle_points[0][1], zmin),
                        mp.Vector3(triangle_points[1][0], triangle_points[1][1], zmin),
                        mp.Vector3(triangle_points[2][0], triangle_points[2][1], zmin),
                    ]

                    triangle_prism = mp.Prism(
                        vertices=triangle_vertices,
                        height=height,
                        sidewall_angle=np.deg2rad(sidewall_angle) if sidewall_angle else 0,
                    )

                    # Store reference to original polygon
                    triangle_prism._original_polygon = polygon
                    triangular_prisms.append(triangle_prism)

        if not triangular_prisms:
            # Fallback if no valid triangles found
            print("Warning: No valid triangles found, falling back to exterior-only prism")
            vertices = [mp.Vector3(p[0], p[1], zmin) for p in polygon.exterior.coords[:-1]]
            prism = mp.Prism(
                vertices=vertices,
                height=height,
                sidewall_angle=np.deg2rad(sidewall_angle) if sidewall_angle else 0,
            )
            prism._original_polygon = polygon
            return [prism]

        print(f"Created {len(triangular_prisms)} triangular prisms for polygon with {len(polygon.interiors)} holes")
        return triangular_prisms

    def _create_ring_triangulation(self, polygon, height: float, zmin: float, sidewall_angle: float = 0):
        """Create efficient triangulation for simple polygons with one hole.

        Optimized for simple cases like rings, disks with holes, or similar structures.
        Creates triangular strips between outer and inner boundaries - much faster than
        full Delaunay triangulation. Creates ~2N triangles instead of filling entire area.
        """
        import meep as mp
        import numpy as np

        exterior_coords = list(polygon.exterior.coords[:-1])  # Remove duplicate
        interior_coords = list(polygon.interiors[0].coords[:-1])  # Remove duplicate

        n_outer = len(exterior_coords)
        n_inner = len(interior_coords)

        triangular_prisms = []

        # Create triangular strips connecting outer and inner boundaries
        for i in range(n_outer):
            next_i = (i + 1) % n_outer

            # Map to corresponding inner vertices
            # Use proportional mapping in case vertex counts differ slightly
            inner_i = int(i * n_inner / n_outer) % n_inner
            inner_next = int(next_i * n_inner / n_outer) % n_inner

            # Create two triangles for this segment
            # Triangle 1: outer[i] -> outer[i+1] -> inner[i]
            triangle1_vertices = [
                mp.Vector3(exterior_coords[i][0], exterior_coords[i][1], zmin),
                mp.Vector3(exterior_coords[next_i][0], exterior_coords[next_i][1], zmin),
                mp.Vector3(interior_coords[inner_i][0], interior_coords[inner_i][1], zmin),
            ]

            triangle1_prism = mp.Prism(
                vertices=triangle1_vertices,
                height=height,
                sidewall_angle=np.deg2rad(sidewall_angle) if sidewall_angle else 0,
            )
            triangle1_prism._original_polygon = polygon
            triangular_prisms.append(triangle1_prism)

            # Triangle 2: outer[i+1] -> inner[i+1] -> inner[i]
            triangle2_vertices = [
                mp.Vector3(exterior_coords[next_i][0], exterior_coords[next_i][1], zmin),
                mp.Vector3(interior_coords[inner_next][0], interior_coords[inner_next][1], zmin),
                mp.Vector3(interior_coords[inner_i][0], interior_coords[inner_i][1], zmin),
            ]

            triangle2_prism = mp.Prism(
                vertices=triangle2_vertices,
                height=height,
                sidewall_angle=np.deg2rad(sidewall_angle) if sidewall_angle else 0,
            )
            triangle2_prism._original_polygon = polygon
            triangular_prisms.append(triangle2_prism)

        print(f"Efficient polygon triangulation: {len(triangular_prisms)} triangular prisms (was {n_outer + n_inner} boundary points)")
        return triangular_prisms

    # @cached_property
    # def structures(self) -> list[td.Structure]:
    #     """Returns a list of Structure instances for each PolySlab in the component.

    #     Returns:
    #         list[td.Structure]: A list of Structure instances.
    #     """
    #     # TODO: material_mapping removed from Geometry - need to get materials from Material class
    #     structures = []
    #     for name, poly in self.polyslabs.items():
    #         structure = td.Structure(
    #             geometry=poly,
    #             medium=self.material_mapping[self.geometry_layers[name].material],  # TODO: Fix this
    #             name=name,
    #         )
    #         structures.append(structure)

    #     return structures

    # # def get_ports(
    # #     self,
    # #     mode_spec: td.ModeSpec,
    # #     size_mult: float | tuple[float, float] = (4.0, 2.0),
    # #     cz: float | None = None,
    # #     grid_eps: float | None = None,
    # # ) -> list[Port]:
    # #     """Returns a list of Port instances for each optical port in the component.

    # #     Args:
    # #         mode_spec (td.ModeSpec): The mode specification for the ports.
    # #         size_mult (float | tuple[float, float], optional): The size multiplier for the ports. Defaults to (4.0, 2.0).
    # #         cz (float | None, optional): The z-coordinate for the ports. If None, the z-coordinate of the component is used. Defaults to None.
    # #         grid_eps (float | None, optional): Rounding tolerance for port coordinates. If None, the coordinates are not rounded. Defaults to None.

    # #     Returns:
    # #         list[Port]: A list of Port instances.
    # #     """
    # #     ports = []
    # #     for port in self.ports:
    # #         if port.port_type != "optical":
    # #             continue
    # #         center = self.get_port_center(port)
    # #         center = center if cz is None else (*center[:2], cz)
    # #         axis, direction = get_port_normal(port)

    # #         match size_mult:
    # #             case float():
    # #                 size = np.full(3, size_mult * port.dwidth)
    # #             case tuple():
    # #                 size = np.full(3, size_mult[0] * port.dwidth)
    # #                 size[2] = size_mult[1] * port.dwidth
    # #         size[axis] = 0

    # #         if grid_eps is not None:
    # #             center = np.round(center, abs(int(np.log10(grid_eps))))

    # #         ports.append(
    # #             Port(
    # #                 center=tuple(center),
    # #                 size=tuple(size),
    # #                 direction=direction,
    # #                 mode_spec=mode_spec,
    # #                 name=port.name,
    # #             )
    # #         )
    # #     return ports

    # def get_simulation(
    #     self,
    #     grid_spec: td.GridSpec,
    #     center_z: float,
    #     sim_size_z: int,
    #     boundary_spec: td.BoundarySpec,
    #     monitors: tuple[Any, ...] | None = None,
    #     run_time: float = 10e-12,
    #     shutoff: float = 1e-5,
    #     symmetry: tuple[Symmetry, Symmetry, Symmetry] = (0, 0, 0),
    #     **kwargs,
    # ) -> td.Simulation:
    #     """Returns a Simulation instance for the component.

    #     Args:
    #         grid_spec (td.GridSpec): The grid specification for the simulation.
    #         center_z (float): The z-coordinate for the center of the simulation.
    #         sim_size_z (int): The size of the simulation in the z-direction.
    #         boundary_spec (td.BoundarySpec): The boundary specification for the simulation.
    #         monitors (tuple[Any, ...] | None, optional): The monitors for the simulation. If None, no monitors are used. Defaults to None.
    #         run_time (float, optional): The run time for the simulation. Defaults to 1e-12.
    #         shutoff (float, optional): The shutoff value for the simulation. Defaults to 1e-5.
    #         symmetry (tuple[Symmetry, Symmetry, Symmetry], optional): The symmetry for the simulation. Defaults to (0,0,0).

    #     Keyword Args:
    #         **kwargs: Additional keyword arguments for the Simulation constructor.

    #     Returns:
    #         td.Simulation: A Simulation instance.
    #     """
    #     sim_center = (*self.center[:2], center_z)
    #     sim_size = (*self.size[:2], sim_size_z)
    #     return td.Simulation(
    #         size=sim_size,
    #         center=sim_center,
    #         structures=self.structures,
    #         grid_spec=grid_spec,
    #         monitors=[] if monitors is None else monitors,
    #         boundary_spec=boundary_spec,
    #         run_time=run_time,
    #         shutoff=shutoff,
    #         symmetry=symmetry,
    #         **kwargs,
    #     )

    # def get_component_modeler(
    #     self,
    #     wavelength: float = 1.55,
    #     bandwidth: float = 0.2,
    #     num_freqs: int = 6,
    #     min_steps_per_wvl: int = 30,
    #     center_z: float | str | None = None,
    #     sim_size_z: float = 4.0,
    #     port_size_mult: float | tuple[float, float] = (4.0, 3.0),
    #     run_only: tuple[tuple[str, int], ...] | None = None,
    #     element_mappings: Tidy3DElementMapping = (),
    #     extra_monitors: tuple[Any, ...] | None = None,
    #     mode_spec: td.ModeSpec = td.ModeSpec(num_modes=1, filter_pol="te"),
    #     boundary_spec: td.BoundarySpec = td.BoundarySpec.all_sides(boundary=td.PML()),
    #     run_time: float = 10e-12,
    #     shutoff: float = 1e-5,
    #     grid_eps: float = 1e-6,
    #     folder_name: str = "default",
    #     path_dir: str = ".",
    #     verbose: bool = True,
    #     symmetry: tuple[Symmetry, Symmetry, Symmetry] = (0, 0, 0),
    #     **kwargs,
    # ) -> ComponentModeler:
    #     """Returns a ComponentModeler instance for the component.

    #     Args:
    #         wavelength: The wavelength for the ComponentModeler. Defaults to 1.55.
    #         bandwidth: The bandwidth for the ComponentModeler. Defaults to 0.2.
    #         num_freqs: The number of frequencies for the ComponentModeler. Defaults to 21.
    #         min_steps_per_wvl: The minimum number of steps per wavelength for the ComponentModeler. Defaults to 30.
    #         center_z: The z-coordinate for the center of the ComponentModeler. If None, the z-coordinate of the component is used. Defaults to None.
    #         sim_size_z: simulation size um in the z-direction for the ComponentModeler. Defaults to 4.
    #         port_size_mult: The size multiplier for the ports in the ComponentModeler. Defaults to (4.0, 3.0).
    #         run_only: The run only specification for the ComponentModeler. Defaults to None.
    #         element_mappings: The element mappings for the ComponentModeler. Defaults to ().
    #         extra_monitors: The extra monitors for the ComponentModeler. Defaults to None.
    #         mode_spec: The mode specification for the ComponentModeler. Defaults to td.ModeSpec(num_modes=1, filter_pol="te").
    #         boundary_spec: The boundary specification for the ComponentModeler. Defaults to td.BoundarySpec.all_sides(boundary=td.PML()).
    #         run_time: The run time for the ComponentModeler.
    #         shutoff: The shutoff value for the ComponentModeler. Defaults to 1e-5.
    #         grid_eps: Rounding tolerance for coordinates, e.g. port locations and layer centers (μm).
    #         folder_name: The folder name for the ComponentModeler. Defaults to "default".
    #         path_dir: The directory path for the ComponentModeler. Defaults to ".".
    #         verbose: Whether to print verbose output for the ComponentModeler. Defaults to True.
    #         symmetry (tuple[Symmetry, Symmetry, Symmetry], optional): The symmetry for the simulation. Defaults to (0,0,0).
    #         kwargs: Additional keyword arguments for the Simulation constructor.

    #     Returns:
    #         ComponentModeler: A ComponentModeler instance.
    #     """
    #     match center_z:
    #         case float():
    #             cz = center_z
    #         case str():
    #             cz = self.get_layer_center(center_z)[2]
    #         case None:
    #             cz = np.mean(list({c[2] for c in self.port_centers}))
    #         case _:
    #             raise ValueError(f"Invalid center_z: {center_z}")

    #     cz = np.round(cz, abs(int(np.log10(grid_eps)))).item()

    #     freqs = td.C_0 / np.linspace(
    #         wavelength - bandwidth / 2, wavelength + bandwidth / 2, num_freqs
    #     )

    #     grid_spec = td.GridSpec.auto(
    #         wavelength=wavelength, min_steps_per_wvl=min_steps_per_wvl
    #     )

    #     if sim_size_z == 0:
    #         boundary_spec = boundary_spec.updated_copy(z=td.Boundary.periodic())

    #     sim = self.get_simulation(
    #         grid_spec=grid_spec,
    #         center_z=cz,
    #         sim_size_z=sim_size_z,
    #         boundary_spec=boundary_spec,
    #         monitors=extra_monitors,
    #         run_time=run_time,
    #         shutoff=shutoff,
    #         symmetry=symmetry,
    #         **kwargs,
    #     )

    #     ports = self.get_ports(mode_spec, port_size_mult, grid_eps=grid_eps)

    #     return ComponentModeler(
    #         simulation=sim,
    #         ports=ports,
    #         freqs=tuple(freqs),
    #         element_mappings=element_mappings,
    #         run_only=run_only,
    #         folder_name=folder_name,
    #         path_dir=path_dir,
    #         verbose=verbose,
    #     )

    def plot_prism(
        self,
        x: float | str | None = None,
        y: float | str | None = None,
        z: float | str = "core",
        ax: plt.Axes | None = None,
        legend: bool = True,
        slices: str = "z",
    ) -> plt.Axes | None:
        """Plot cross sections of MEEP prisms with multi-view support.

        Args:
            x: The x-coordinate for the cross section. If str, uses layer name.
            y: The y-coordinate for the cross section. If str, uses layer name.
            z: The z-coordinate for the cross section. If str, uses layer name. Defaults to "core".
            ax: The Axes instance to plot on. If None, creates new figure.
            legend: Whether to include a legend in the plot. Defaults to True.
            slices: Which slice(s) to plot. Can be single ("x", "y", "z") or any combination
                ("xy", "xz", "yz", "xyz", etc.). Creates subplots with legend panel on the side.

        Returns:
            plt.Axes or None: Returns None when creating new figure (displays directly),
                returns Axes if ax was provided.
        """
        return plot_prism_slices(self, x, y, z, ax, legend, slices)

    def plot_3d(self, backend: str = "open3d", **kwargs) -> Any:
        """Create interactive 3D visualization of the geometry.

        Args:
            backend: Rendering backend ("open3d" for Jupyter/VS Code, "pyvista" for desktop)
            **kwargs: Additional arguments passed to the backend renderer

        Note:
            - Use "open3d" (default) for VS Code and Jupyter notebooks
            - Use "pyvista" for desktop applications with full interactivity
            - For web browser visualization, use serve_3d() instead
        """
        if backend == "pyvista":
            return plot_prisms_3d(self, **kwargs)
        elif backend == "open3d":
            return plot_prisms_3d_open3d(self, **kwargs)
        else:
            raise ValueError(f"Unsupported backend: {backend}. Use 'open3d' or 'pyvista'")

    def export_3d(self, filename: str, format: str = "auto") -> None:
        """Export 3D geometry to mesh file."""
        return export_3d_mesh(self, filename, format)

    def serve_3d(self, port: int = 8000, auto_open: bool = True, **kwargs) -> str:
        """Start FastAPI server to display Three.js visualization in browser.

        Args:
            port: Port to serve on (default 8000)
            auto_open: Whether to automatically open browser
            **kwargs: Additional Three.js options

        Returns:
            URL of the running server
        """
        return serve_threejs_visualization(self, port=port, auto_open=auto_open, **kwargs)

    def export_web_3d(self, filename: str = "geometry_3d.html", title: str = "3D Geometry Visualization") -> str:
        """Export 3D visualization as standalone HTML file."""
        return create_web_export(self, filename, title)

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
        """Plots a cross section of the component at a specified position.

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
            poly = self.polyslabs[name]

            axis, position = poly.parse_xyz_kwargs(x=x, y=y, z=z)
            xlim, ylim = poly._get_plot_limits(axis=axis, buffer=0)
            xmin, xmax = min(xmin, xlim[0]), max(xmax, xlim[1])
            ymin, ymax = min(ymin, ylim[0]), max(ymax, ylim[1])
            for idx, shape in enumerate(poly.intersections_plane(x=x, y=y, z=z)):
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


def write_sparameters(
    component: Component,
    layer_stack: LayerStack | None = None,
    material_mapping: dict[str, Tidy3DMedium] = material_name_to_medium,  # TODO: Consider removing, use Material class instead
    extend_ports: NonNegativeFloat = 0.5,
    port_offset: float = 0.2,
    pad_xy_inner: NonNegativeFloat = 2.0,
    pad_xy_outer: NonNegativeFloat = 2.0,
    pad_z_inner: float = 0.0,
    pad_z_outer: NonNegativeFloat = 0.0,
    dilation: float = 0.0,
    wavelength: float = 1.55,
    bandwidth: float = 0.2,
    num_freqs: int = 21,
    min_steps_per_wvl: int = 30,
    center_z: float | str | None = None,
    sim_size_z: float = 4.0,
    port_size_mult: float | tuple[float, float] = (4.0, 3.0),
    run_only: tuple[tuple[str, int], ...] | None = None,
    element_mappings: Tidy3DElementMapping = (),
    extra_monitors: tuple[Any, ...] | None = None,
    mode_spec: td.ModeSpec = td.ModeSpec(num_modes=1, filter_pol="te"),
    boundary_spec: td.BoundarySpec = td.BoundarySpec.all_sides(boundary=td.PML()),
    symmetry: tuple[Symmetry, Symmetry, Symmetry] = (0, 0, 0),
    run_time: float = 1e-12,
    shutoff: float = 1e-5,
    folder_name: str = "default",
    dirpath: PathType = dirpath_default,
    verbose: bool = True,
    plot_simulation_layer_name: str | None = None,
    plot_simulation_port_index: int = 0,
    plot_simulation_z: float | None = None,
    plot_simulation_x: float | None = None,
    plot_mode_index: int | None = 0,
    plot_mode_port_name: str | None = None,
    plot_epsilon: bool = False,
    filepath: PathType | None = None,
    overwrite: bool = False,
    **kwargs: Any,
) -> Sparameters:
    """Writes the S-parameters for a component.

    .. deprecated::
        This function represents the legacy monolithic approach.
        Use the new modular FDTDSimulation class instead:

        sim = FDTDSimulation()
        sim.geometry = Geometry(component=component, layer_stack=layer_stack)
        sim.material = Material(mapping=material_mapping)
        result = sim.run()

        This function will be removed in a future version.

    Args:
        component: gdsfactory component to write the S-parameters for.
        layer_stack: The layer stack for the component. If None, uses active pdk layer_stack.
        material_mapping: A mapping of material names to Tidy3DMedium instances. Defaults to material_name_to_medium.
        extend_ports: The extension length for ports.
        port_offset: The offset for ports. Defaults to 0.2.
        pad_xy_inner: The inner padding in the xy-plane. Defaults to 2.0.
        pad_xy_outer: The outer padding in the xy-plane. Defaults to 2.0.
        pad_z_inner: The inner padding in the z-direction. Defaults to 0.0.
        pad_z_outer: The outer padding in the z-direction. Defaults to 0.0.
        dilation: Dilation of the polygon in the base by shifting each edge along its normal outwards direction by a distance;
        wavelength: The wavelength for the ComponentModeler. Defaults to 1.55.
        bandwidth: The bandwidth for the ComponentModeler. Defaults to 0.2.
        num_freqs: The number of frequencies for the ComponentModeler. Defaults to 21.
        min_steps_per_wvl: The minimum number of steps per wavelength for the ComponentModeler. Defaults to 30.
        center_z: The z-coordinate for the center of the ComponentModeler.
            If None, the z-coordinate of the component is used. Defaults to None.
        sim_size_z: simulation size um in the z-direction for the ComponentModeler. Defaults to 4.
        port_size_mult: The size multiplier for the ports in the ComponentModeler. Defaults to (4.0, 3.0).
        run_only: The run only specification for the ComponentModeler. Defaults to None.
        element_mappings: The element mappings for the ComponentModeler. Defaults to ().
        extra_monitors: The extra monitors for the ComponentModeler. Defaults to None.
        mode_spec: The mode specification for the ComponentModeler. Defaults to td.ModeSpec(num_modes=1, filter_pol="te").
        boundary_spec: The boundary specification for the ComponentModeler.
            Defaults to td.BoundarySpec.all_sides(boundary=td.PML()).
        symmetry (tuple[Symmetry, Symmetry, Symmetry], optional): The symmetry for the simulation. Defaults to (0,0,0).
        run_time: The run time for the ComponentModeler.
        shutoff: The shutoff value for the ComponentModeler. Defaults to 1e-5.
        folder_name: The folder name for the ComponentModeler in flexcompute website. Defaults to "default".
        dirpath: Optional directory path for writing the Sparameters. Defaults to "~/.gdsfactory/sparameters".
        verbose: Whether to print verbose output for the ComponentModeler. Defaults to True.
        plot_simulation_layer_name: Optional layer name to plot. Defaults to None.
        plot_simulation_port_index: which port index to plot. Defaults to 0.
        plot_simulation_z: which z coordinate to plot. Defaults to None.
        plot_simulation_x: which x coordinate to plot. Defaults to None.
        plot_mode_index: which mode index to plot. Defaults to 0.
        plot_mode_port_name: which port name to plot. Defaults to None.
        plot_epsilon: whether to plot epsilon. Defaults to False.
        filepath: Optional file path for the S-parameters. If None, uses hash of simulation.
        overwrite: Whether to overwrite existing S-parameters. Defaults to False.
        kwargs: Additional keyword arguments for the tidy3d Simulation constructor.

    """
    layer_stack = layer_stack or get_layer_stack()

    c = Geometry(
        component=component,
        layer_stack=layer_stack,
        material_mapping=material_mapping,
        extend_ports=extend_ports,
        port_offset=port_offset,
        pad_xy_inner=pad_xy_inner,
        pad_xy_outer=pad_xy_outer,
        pad_z_inner=pad_z_inner,
        pad_z_outer=pad_z_outer,
        dilation=dilation,
    )

    modeler = c.get_component_modeler(
        wavelength=wavelength,
        bandwidth=bandwidth,
        num_freqs=num_freqs,
        min_steps_per_wvl=min_steps_per_wvl,
        center_z=center_z,
        sim_size_z=sim_size_z,
        port_size_mult=port_size_mult,
        run_only=run_only,
        element_mappings=element_mappings,
        extra_monitors=extra_monitors,
        mode_spec=mode_spec,
        boundary_spec=boundary_spec,
        run_time=run_time,
        shutoff=shutoff,
        folder_name=folder_name,
        verbose=verbose,
        symmetry=symmetry,
        **kwargs,
    )

    path_dir = pathlib.Path(dirpath) / modeler._hash_self()
    modeler = modeler.updated_copy(path_dir=str(path_dir))

    sp = {}

    if plot_simulation_layer_name or plot_simulation_z or plot_simulation_x:
        if plot_simulation_layer_name is None and plot_simulation_z is None:
            raise ValueError(
                "You need to specify plot_simulation_z or plot_simulation_layer_name"
            )
        z = plot_simulation_z or c.get_layer_center(plot_simulation_layer_name)[2]
        x = plot_simulation_x or c.ports[plot_simulation_port_index].dcenter[0]

        modeler = c.get_component_modeler(
            center_z=plot_simulation_layer_name,
            port_size_mult=port_size_mult,
            sim_size_z=sim_size_z,
        )
        _, ax = plt.subplots(2, 1)
        if plot_epsilon:
            modeler.plot_sim_eps(z=z, ax=ax[0])
            modeler.plot_sim_eps(x=x, ax=ax[1])

        else:
            modeler.plot_sim(z=z, ax=ax[0])
            modeler.plot_sim(x=x, ax=ax[1])
        plt.show()
        return sp

    elif plot_mode_index is not None and plot_mode_port_name:
        modes = get_mode_solvers(modeler, port_name=plot_mode_port_name)
        mode_solver = modes[f"smatrix_{plot_mode_port_name}_{plot_mode_index}"]
        mode_data = mode_solver.solve()

        _, ax = plt.subplots(1, 3, tight_layout=True, figsize=(10, 3))
        abs(mode_data.Ex.isel(mode_index=plot_mode_index, f=0)).plot(
            x="y", y="z", ax=ax[0], cmap="magma"
        )
        abs(mode_data.Ey.isel(mode_index=plot_mode_index, f=0)).plot(
            x="y", y="z", ax=ax[1], cmap="magma"
        )
        abs(mode_data.Ez.isel(mode_index=plot_mode_index, f=0)).plot(
            x="y", y="z", ax=ax[2], cmap="magma"
        )
        ax[0].set_title("|Ex(x, y)|")
        ax[1].set_title("|Ey(x, y)|")
        ax[2].set_title("|Ez(x, y)|")
        plt.setp(ax, aspect="equal")
        plt.show()
        return sp

    dirpath = pathlib.Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    filepath = filepath or dirpath / f"{modeler._hash_self()}.npz"
    filepath = pathlib.Path(filepath)
    if filepath.suffix != ".npz":
        filepath = filepath.with_suffix(".npz")

    if filepath.exists() and not overwrite:
        print(f"Simulation loaded from {filepath!r}")
        return dict(np.load(filepath))
    else:
        time.sleep(0.2)
        s = modeler.run()
        for port_in in s.port_in.values:
            for port_out in s.port_out.values:
                for mode_index_in in s.mode_index_in.values:
                    for mode_index_out in s.mode_index_out.values:
                        sp[f"{port_in}@{mode_index_in},{port_out}@{mode_index_out}"] = (
                            s.sel(
                                port_in=port_in,
                                port_out=port_out,
                                mode_index_in=mode_index_in,
                                mode_index_out=mode_index_out,
                            ).values
                        )

        frequency = s.f.values
        sp["wavelengths"] = td.constants.C_0 / frequency
        np.savez_compressed(filepath, **sp)
        print(f"Simulation saved to {filepath!r}")
        return sp
