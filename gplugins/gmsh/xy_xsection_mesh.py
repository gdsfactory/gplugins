from __future__ import annotations

from collections import OrderedDict

import numpy as np
from gdsfactory.technology import LayerStack
from gdsfactory.typings import ComponentOrReference
from scipy.interpolate import NearestNDInterpolator
from shapely.geometry import Polygon
from shapely.ops import unary_union

from gplugins.gmsh.mesh import mesh_from_polygons
from gplugins.gmsh.parse_component import (
    merge_by_material_func,
)
from gplugins.gmsh.parse_gds import cleanup_component
from gplugins.utils.parse_layerstack import (
    get_layers_at_z,
)


def xy_xsection_mesh(
    component: ComponentOrReference,
    z: float,
    layerstack: LayerStack,
    resolutions: dict | None = None,
    mesh_scaling_factor: float = 1.0,
    default_resolution_min: float = 0.01,
    default_resolution_max: float = 0.5,
    background_tag: str | None = None,
    background_padding: tuple[float, float, float, float] = (2.0, 2.0, 2.0, 2.0),
    filename: str | None = None,
    global_meshsize_array: np.array | None = None,
    global_meshsize_interpolant_func: callable | None = NearestNDInterpolator,
    extra_shapes_dict: OrderedDict | None = None,
    merge_by_material: bool | None = False,
    round_tol: int = 4,
    simplify_tol: float = 1e-4,
    atol: float | None = 1e-5,
):
    """Mesh xy cross-section of component at height z.

    Args:
        component (Component): gdsfactory component to mesh
        z (float): z-coordinate at which to sample the LayerStack
        layerstack (LayerStack): gdsfactory LayerStack to parse
        resolutions (Dict): Pairs {"layername": {"resolution": float, "distance": "float}} to roughly control mesh refinement
        mesh_scaling_factor (float): factor multiply mesh geometry by
        default_resolution_min (float): gmsh minimal edge length
        default_resolution_max (float): gmsh maximal edge length
        background_tag (str): name of the background layer to add (default: no background added)
        background_padding (Tuple): [xleft, ydown, xright, yup] distances to add to the components and to fill with background_tag
        filename (str, path): where to save the .msh file
        global_meshsize_array: np array [x,y,z,lc] to parametrize the mesh
        global_meshsize_interpolant_func: interpolating function for global_meshsize_array
        extra_shapes_dict: Optional[OrderedDict] = OrderedDict of {key: geo} with key a label and geo a shapely (Multi)Polygon or (Multi)LineString of extra shapes to override component
        merge_by_material: boolean, if True will merge polygons from layers with the same layer.material. Physical keys will be material in this case.
        round_tol: during gds --> mesh conversion cleanup, number of decimal points at which to round the gdsfactory/shapely points before introducing to gmsh
        simplify_tol: during gds --> mesh conversion cleanup, shapely "simplify" tolerance (make it so all points are at least separated by this amount)
        atol: tolerance used to establish equivalency between vertices
    """
    # Fuse and cleanup polygons of same layer in case user overlapped them
    layer_polygons_dict = cleanup_component(
        component, layerstack, round_tol, simplify_tol
    )

    # Find layers present at this z-level
    layers = get_layers_at_z(layerstack, z)
    # Order the layers by their mesh_order in the layerstack
    layers = sorted(layers, key=lambda x: layerstack.layers[x].mesh_order)

    # Determine effective buffer (or even presence of layer) at this z-level
    shapes = OrderedDict()
    for layername in layers:
        polygons = layer_polygons_dict[layername]
        if layername in layers:
            # Calculate the buffer
            if layerstack.layers[layername].thickness < 0:
                zmin = (
                    layerstack.layers[layername].zmin
                    + layerstack.layers[layername].thickness
                )
                thickness = abs(layerstack.layers[layername].thickness)
            else:
                zmin = layerstack.layers[layername].zmin
                thickness = layerstack.layers[layername].thickness
            z_fraction = (z - zmin) / thickness
            if layerstack.layers[layername].z_to_bias:
                fractions, buffers = zip(*layerstack.layers[layername].z_to_bias)
                buffer = np.interp(z_fraction, fractions, buffers)
                shapes[layername] = polygons.buffer(buffer, join_style=2)
            else:
                shapes[layername] = polygons

    # Add background polygon
    if background_tag is not None:
        bounds = unary_union(list(shapes.values())).bounds
        shapes[background_tag] = Polygon(
            [
                [bounds[0] - background_padding[0], bounds[1] - background_padding[1]],
                [bounds[0] - background_padding[0], bounds[3] + background_padding[3]],
                [bounds[2] + background_padding[2], bounds[3] + background_padding[3]],
                [bounds[2] + background_padding[2], bounds[1] - background_padding[1]],
            ]
        )

    # Merge by material
    if merge_by_material:
        shapes = merge_by_material_func(shapes, layerstack)

    # Mesh
    return mesh_from_polygons(
        shapes,
        resolutions=resolutions,
        mesh_scaling_factor=mesh_scaling_factor,
        filename=filename,
        default_resolution_min=default_resolution_min,
        default_resolution_max=default_resolution_max,
        global_meshsize_array=global_meshsize_array,
        global_meshsize_interpolant_func=global_meshsize_interpolant_func,
        atol=atol,
    )


if __name__ == "__main__":
    import gdsfactory as gf

    c = gf.component.Component()
    waveguide = c << gf.get_component(gf.components.straight_pin(length=10, taper=None))
    undercut = c << gf.get_component(
        gf.components.rectangle(
            size=(5.0, 5.0),
            layer="UNDERCUT",
            centered=True,
        )
    ).move(destination=[4, 0])
    c.show()

    from gdsfactory.pdk import get_layer_stack

    filtered_layerstack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "via_contact",
                "undercut",
                "box",
                "substrate",
                # "clad",
                "metal1",
            )
        }
    )

    resolutions = {}
    resolutions["core"] = {"resolution": 0.05, "distance": 0.1}
    resolutions["via_contact"] = {"resolution": 0.1, "distance": 0}

    geometry = xy_xsection_mesh(
        component=c,
        z=-6,
        layerstack=filtered_layerstack,
        resolutions=resolutions,
        # background_tag="Oxide",
        filename="mesh.msh",
    )
    # print(geometry)

    # import gmsh

    # gmsh.write("mesh.msh")
    # gmsh.clear()
    # geometry.__exit__()

    import meshio

    mesh_from_file = meshio.read("mesh.msh")

    def create_mesh(mesh, cell_type):
        cells = mesh.get_cells_type(cell_type)
        cell_data = mesh.get_cell_data("gmsh:physical", cell_type)
        points = mesh.points
        return meshio.Mesh(
            points=points,
            cells={cell_type: cells},
            cell_data={"name_to_read": [cell_data]},
        )

    line_mesh = create_mesh(mesh_from_file, "line")
    meshio.write("facet_mesh.xdmf", line_mesh)

    triangle_mesh = create_mesh(mesh_from_file, "triangle")
    meshio.write("mesh.xdmf", triangle_mesh)

    # # for layer, polygons in heaters.get_polygons(by_spec=True).items():
    # #     print(layer, polygons)
