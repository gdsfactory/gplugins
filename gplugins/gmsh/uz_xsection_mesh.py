from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import gdsfactory as gf
import numpy as np
from gdsfactory.config import get_number_of_cores
from gdsfactory.technology import LayerStack
from gdsfactory.typings import ComponentOrReference
from meshwell.gmsh_entity import GMSH_entity
from meshwell.model import Model
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from gplugins.common.utils.parse_layer_stack import (
    list_unique_layer_stack_z,
    order_layer_stack,
)
from gplugins.gmsh.define_polysurfaces import define_polysurfaces
from gplugins.gmsh.parse_component import (
    process_buffers,
)
from gplugins.gmsh.parse_gds import cleanup_component, to_polygons


def get_u_bounds_polygons(
    polygons: MultiPolygon | list[Polygon],
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]],
    u_offset: float = 0.0,
):
    """Performs the bound extraction given a (Multi)Polygon or [Polygon] and cross-sectional line coordinates.

    Args:
        polygons: shapely MultiPolygon or list of Polygons.
        xsection_bounds: ( (x1,y1), (x2,y2) ), with x1,y1 beginning point of cross-sectional line and x2,y2 the end.
        u_offset: amount to offset the returned polygons in the lateral dimension.

    Returns: list of bounding box coordinates (u1,u2)) in xsection line coordinates (distance from xsection_bounds[0]).
    """
    line = LineString(xsection_bounds)
    linestart = Point(xsection_bounds[0])

    return_list = []
    for polygon in polygons.geoms if hasattr(polygons, "geoms") else [polygons]:
        initial_settings = np.seterr()
        np.seterr(invalid="ignore")
        intersection = polygon.intersection(line)
        np.seterr(**initial_settings)
        if intersection:
            for entry in (
                intersection.geoms if hasattr(intersection, "geoms") else [intersection]
            ):
                bounds = entry.bounds
                p1 = Point([bounds[0], bounds[1]])
                p2 = Point([bounds[2], bounds[3]])
                return_list.append(
                    [
                        linestart.distance(p1) + u_offset,
                        linestart.distance(p2) + u_offset,
                    ]
                )
    return return_list


def get_u_bounds_layers(
    layer_polygons_dict: dict[tuple(str, str, str), MultiPolygon],
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]],
):
    """Given a layer_polygons_dict and two coordinates (x1,y1), (x2,y2).

    Computes the bounding box(es) of each layer in the xsection coordinate system (u).

    Args:
        layer_polygons_dict: dict containing layernames: shapely polygons pairs
        xsection_bounds: ( (x1,y1), (x2,y2) ), with x1,y1 beginning point of cross-sectional line and x2,y2 the end.

    Returns: Dict containing layer(list pairs, with list a list of bounding box coordinates (u1,u2))
        in xsection line coordinates.
    """
    bounds_dict = {}
    for layername, (
        gds_layername,
        next_layername,
        polygons,
        next_polygons,
    ) in layer_polygons_dict.items():
        bounds_dict[layername] = []
        bounds = get_u_bounds_polygons(polygons, xsection_bounds)
        next_bounds = get_u_bounds_polygons(next_polygons, xsection_bounds)
        if bounds:
            bounds_dict[layername] = (
                gds_layername,
                next_layername,
                bounds,
                next_bounds,
            )

    return bounds_dict


def get_uz_bounds_layers(
    layer_polygons_dict: dict[str, tuple[str, MultiPolygon, MultiPolygon]],
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]],
    layer_stack: LayerStack,
    u_offset: float = 0.0,
    z_bounds: tuple[float, float] | None = None,
):
    """Given a component and layer stack, computes the bounding box(es).

    For each layer in the xsection coordinate system (u,z).

    Args:
        layer_polygons_dict: dict containing layernames: shapely polygons pairs.
        xsection_bounds: ( (x1,y1), (x2,y2) ), with x1,y1 beginning point of cross-sectional line and x2,y2 the end.
        layer_stack: LayerStack object containing layer information.
        u_offset: amount to offset the returned polygons in the lateral dimension.
        z_bounds: optional tuple containing the zmin and zmax of the simulation region.

    Returns: Dict containing layer: polygon pairs, with (u1,u2) in xsection line coordinates
    """
    if z_bounds is not None:
        z_min_sim = z_bounds[0]
        z_max_sim = z_bounds[1]
    else:
        z_min_sim = -np.inf
        z_max_sim = np.inf

    # Get in-plane cross-sections
    inplane_bounds_dict = get_u_bounds_layers(layer_polygons_dict, xsection_bounds)

    outplane_bounds_dict = {}

    layer_dict = layer_stack.to_dict()

    # Remove empty entries
    inplane_bounds_dict = {
        key: value for (key, value) in inplane_bounds_dict.items() if value
    }

    for layername, (
        gds_layername,
        next_layername,
        inplane_bounds_list,
        next_inplane_bounds_list,
    ) in inplane_bounds_dict.items():
        outplane_polygons_list = []
        for inplane_bounds, next_inplane_bounds in zip(
            inplane_bounds_list, next_inplane_bounds_list
        ):
            zmin = layer_dict[layername]["zmin"]
            zmax = layer_dict[next_layername]["zmin"]

            # Get bounding box
            umin_zmin = np.min(inplane_bounds) + u_offset
            umax_zmin = np.max(inplane_bounds) + u_offset
            umin_zmax = np.min(next_inplane_bounds) + u_offset
            umax_zmax = np.max(next_inplane_bounds) + u_offset

            # If layer thickness are negative, then zmin is actually zmax
            if zmin > zmax:
                foo = zmax
                zmax = zmin
                zmin = foo

                foo = umin_zmin
                umin_zmin = umin_zmax
                umin_zmax = foo

                foo = umax_zmax
                umax_zmax = umax_zmin
                umax_zmin = foo

            if zmax < z_min_sim or zmin > z_max_sim:
                # The whole polygon is outside of the simulation region
                continue

            # Check if we need to clip on top or bottom
            if zmin < z_min_sim:
                # Need to clip the bottom
                # Do a linear interpolation of the u coordinates
                umin_zmin = np.interp(z_min_sim, [zmin, zmax], [umin_zmin, umin_zmax])
                umax_zmin = np.interp(z_min_sim, [zmin, zmax], [umax_zmin, umax_zmax])
                zmin = z_min_sim

            if zmax > z_max_sim:
                # Need to clip the top
                umin_zmax = np.interp(z_max_sim, [zmin, zmax], [umin_zmin, umin_zmax])
                umax_zmax = np.interp(z_max_sim, [zmin, zmax], [umax_zmin, umax_zmax])
                zmax = z_max_sim

            points = [
                [umin_zmin, zmin],
                [umin_zmax, zmax],
                [umax_zmax, zmax],
                [umax_zmin, zmin],
            ]
            outplane_polygons_list.append(Polygon(points))

        outplane_bounds_dict[layername] = (gds_layername, outplane_polygons_list)

    return outplane_bounds_dict


def uz_xsection_mesh(
    component: ComponentOrReference,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]],
    layer_stack: LayerStack,
    layer_physical_map: dict[str, Any],
    layer_meshbool_map: dict[str, Any],
    resolutions: dict[str, Any] | None = None,
    default_characteristic_length: float = 0.5,
    background_tag: str | None = None,
    background_padding: Sequence[float] = (2.0,) * 6,
    background_mesh_order: int | float = 2**63 - 1,
    global_scaling: float = 1,
    global_scaling_premesh: float = 1,
    global_2D_algorithm: int = 6,
    filename: str | None = None,
    round_tol: int = 4,
    simplify_tol: float = 1e-4,
    u_offset: float = 0.0,
    left_right_periodic_bcs: bool = False,
    verbosity: int | None = 0,
    n_threads: int = get_number_of_cores(),
    gmsh_version: float | None = None,
    interface_delimiter: str = "___",
    background_remeshing_file: str | None = None,
    optimization_flags: tuple[tuple[str, int]] | None = None,
    **kwargs: Any,
):
    """Mesh uz cross-section of component along line u = [[x1,y1] , [x2,y2]].

    Args:
        component (Component): gdsfactory component to mesh
        xsection_bounds (Tuple): Tuple [[x1,y1] , [x2,y2]] parametrizing the line u
        layer_stack (LayerStack): gdsfactory LayerStack to parse
        layer_physical_map: map layer names to physical names
        layer_meshbool_map: map layer names to mesh_bool (True: mesh the prisms, False: don't mesh)
        resolutions (Dict): Pairs {"layername": {"resolution": float, "distance": "float}} to roughly control mesh refinement
        default_characteristic_length (float): default characteristic length to use in the mesh.
        background_tag (str): name of the background layer to add (default: no background added)
        background_padding (Tuple): [xleft, ydown, xright, yup] distances to add to the components and to fill with background_tag
        background_mesh_order (int, float): mesh order to assign to the background
        round_tol: during gds --> mesh conversion cleanup, number of decimal points at which to round the gdsfactory/shapely points before introducing to gmsh
        global_scaling: global scaling factor to apply to the mesh.
        global_scaling_premesh: global scaling factor to apply to the mesh before meshing.
        global_2D_algorithm: gmsh 2D meshing algorithm to use.
        filename: filename to save the mesh to.
        round_tol: during gds --> mesh conversion cleanup, number of decimal points at which to round the gdsfactory/shapely points before introducing to gmsh.
        simplify_tol: during gds --> mesh conversion cleanup, shapely "simplify" tolerance (make it so all points are at least separated by this amount)
        u_offset: quantity to add to the "u" coordinates, useful to convert back to x or y if parallel to those axes
        atol: tolerance used to establish equivalency between vertices
        left_right_periodic_bcs: if True, makes the left and right simulation edge meshes periodic
        verbosity: verbosity level of gmsh
        n_threads: number of threads to use in gmsh.
        gmsh_version: gmsh version to use.
        interface_delimiter: delimiter to use in the interface names
        background_remeshing_file: .pos file to use as a remeshing field. Overrides resolutions if not None.
        optimization_flags: list of tuples containing optimization flags to pass to gmsh.
        kwargs: additional arguments to pass to the meshing function.
    """
    # Fuse and cleanup polygons of same layer in case user overlapped them
    layer_polygons_dict = cleanup_component(
        component, layer_stack, round_tol, simplify_tol
    )

    # GDS polygons to simulation polygons
    buffered_layer_polygons_dict, buffered_layer_stack = process_buffers(
        layer_polygons_dict, layer_stack
    )

    # simulation polygons to u-z coordinates along cross-sectional line
    z_bounds = kwargs.get("z_bounds", None)
    bounds_dict = get_uz_bounds_layers(
        buffered_layer_polygons_dict,
        xsection_bounds,
        buffered_layer_stack,
        u_offset,
        z_bounds=z_bounds,
    )

    # u-z coordinates to gmsh-friendly polygons
    # Remove terminal layers and merge polygons
    layer_order = order_layer_stack(layer_stack)  # gds layers
    shapes = {}
    for layername in layer_order:
        current_shapes = []
        for gds_name, bounds in bounds_dict.values():
            if gds_name == layername:
                layer_shapes = list(bounds)
                current_shapes.append(MultiPolygon(to_polygons(layer_shapes)))
        shapes[layername] = unary_union(MultiPolygon(to_polygons(current_shapes)))

    # Define polysurfaces
    model = Model(n_threads=n_threads)
    polysurfaces_list = define_polysurfaces(
        polygons_dict=shapes,
        layer_stack=layer_stack,
        model=model,
        scale_factor=global_scaling_premesh,
        resolutions=resolutions,
        layer_physical_map=layer_physical_map,
        layer_meshbool_map=layer_meshbool_map,
    )

    # Add background polygon
    if background_tag is not None:
        # shapes[background_tag] = bounds.buffer(background_padding[0])
        # bounds = unary_union(list(shapes.values())).bounds
        zs = list_unique_layer_stack_z(buffered_layer_stack)
        zmin = np.min(zs) - background_padding[1]
        zmax = np.max(zs) + background_padding[3]
        umin = -1 * background_padding[0] + u_offset
        umax = (
            np.linalg.norm(np.array(xsection_bounds[1]) - np.array(xsection_bounds[0]))
            + background_padding[2]
            + u_offset
        )
        background_box = GMSH_entity(
            gmsh_function=model.occ.add_rectangle,
            gmsh_function_kwargs={
                "x": umin,
                "y": zmin,
                "z": 0,
                "dx": umax - umin,
                "dy": zmax - zmin,
            },
            dimension=2,
            model=model,
            mesh_order=background_mesh_order,
            physical_name=background_tag,
        )
        polysurfaces_list.append(background_box)

    # Create interface surfaces and boundaries
    minu = np.inf
    minz = np.inf
    maxu = -np.inf
    maxz = -np.inf
    if left_right_periodic_bcs:
        # Figure out bbox of simulation
        for polygon in shapes.values():
            if not polygon.is_empty:
                minx, miny, maxx, maxy = polygon.bounds
                minu = min(minx, minu)
                minz = min(miny, minz)
                maxu = max(maxx, maxu)
                maxz = max(maxy, maxz)
            minu += u_offset
            maxu += u_offset
            if background_tag:
                minu -= background_padding[0]
                maxu += background_padding[2]
                minz -= background_padding[1]
                maxz += background_padding[3]
        # Create boundary rectangles
        left_line_rectangle = GMSH_entity(
            gmsh_function=model.occ.add_rectangle,
            gmsh_function_kwargs={
                "x": minu - 1,
                "y": minz,
                "z": 0,
                "dx": 1,
                "dy": maxz - minz,
            },
            dimension=2,
            model=model,
            mesh_order=0,
            physical_name="left_line",
            mesh_bool=False,
        )
        right_line_rectangle = GMSH_entity(
            gmsh_function=model.occ.add_rectangle,
            gmsh_function_kwargs={
                "x": maxu,
                "y": minz,
                "z": 0,
                "dx": 1,
                "dy": maxz - minz,
            },
            dimension=2,
            model=model,
            mesh_order=0,
            physical_name="right_line",
            mesh_bool=False,
        )
        # Give meshwell all possible boundary interfaces
        periodic_entities = [
            (
                f"left_line{interface_delimiter}{entity.physical_name}",
                f"right_line{interface_delimiter}{entity.physical_name}",
            )
            for entity in polysurfaces_list
        ]
        polysurfaces_list.append(left_line_rectangle)
        polysurfaces_list.append(right_line_rectangle)

    # Mesh
    return model.mesh(
        entities_list=polysurfaces_list,
        default_characteristic_length=default_characteristic_length,
        periodic_entities=periodic_entities if left_right_periodic_bcs else None,
        global_scaling=global_scaling,
        global_2D_algorithm=global_2D_algorithm,
        gmsh_version=gmsh_version,
        filename=filename,
        verbosity=verbosity,
        interface_delimiter=interface_delimiter,
        background_remeshing_file=background_remeshing_file,
        optimization_flags=optimization_flags,
    )


if __name__ == "__main__":
    from gdsfactory.pdk import get_layer_stack

    c = gf.Component()

    waveguide = c << gf.get_component(gf.components.straight_pin(length=10, taper=None))
    undercut = c << gf.get_component(
        gf.components.rectangle(
            size=(5.0, 5.0),
            layer="UNDERCUT",
            centered=True,
        )
    )
    undercut.dmove((4, 0))
    c.show()

    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "via_contact",
                "undercut",
                "box",
                # "substrate",
                "clad",
                "metal1",
            )  # "slab90", "via_contact")#"via_contact") # "slab90", "core"
        }
    )

    resolutions = {}
    resolutions["si"] = {"resolution": 0.02, "distance": 0.1}
    resolutions["siInt"] = {"resolution": 0.0003, "distance": 0.1}
    # resolutions["sio2"] = {"resolution": 0.5, "distance": 1}
    resolutions["Aluminum"] = {"resolution": 0.1, "distance": 1}

    # resolutions = {}
    # resolutions["core"] = {"resolution": 0.02, "distance": 0.1}
    # resolutions["coreInt"] = {"resolution": 0.0001, "distance": 0.1}
    # resolutions["slab90"] = {"resolution": 0.05, "distance": 0.1}
    # # resolutions["sio2"] = {"resolution": 0.5, "distance": 1}
    # resolutions["via_contact"] = {"resolution": 0.1, "distance": 1}

    geometry = uz_xsection_mesh(
        c,
        [(4, -15), (4, 15)],
        filtered_layer_stack,
        resolutions=resolutions,
        layer_physical_map={},
        layer_meshbool_map={},
        background_tag="Oxide",
        background_padding=(0, 0, 0, 0),
        filename="mesh.msh",
        round_tol=3,
        simplify_tol=1e-3,
        u_offset=-15,
        left_right_periodic_bcs=True,
    )

    import meshio

    mesh_from_file = meshio.read("mesh.msh")

    def create_mesh(mesh, cell_type, prune_z=False):
        cells = mesh.get_cells_type(cell_type)
        cell_data = mesh.get_cell_data("gmsh:physical", cell_type)
        points = mesh.points[:, :2] if prune_z else mesh.points
        return meshio.Mesh(
            points=points,
            cells={cell_type: cells},
            cell_data={"name_to_read": [cell_data]},
        )

    line_mesh = create_mesh(mesh_from_file, "line", prune_z=True)
    meshio.write("facet_mesh.xdmf", line_mesh)

    triangle_mesh = create_mesh(mesh_from_file, "triangle", prune_z=True)
    meshio.write("mesh.xdmf", triangle_mesh)
