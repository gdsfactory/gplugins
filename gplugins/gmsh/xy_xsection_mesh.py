from __future__ import annotations

from collections import OrderedDict
from typing import Any

import gdsfactory as gf
import numpy as np
from gdsfactory.config import get_number_of_cores
from gdsfactory.technology import LayerLevel, LayerStack, LogicalLayer
from gdsfactory.typings import ComponentOrReference
from meshwell.model import Model
from shapely.geometry import Polygon
from shapely.ops import unary_union

from gplugins.common.utils.get_component_with_net_layers import (
    get_component_with_net_layers,
)
from gplugins.common.utils.parse_layer_stack import (
    get_layers_at_z,
    list_unique_layer_stack_z,
)
from gplugins.gmsh.define_polysurfaces import define_polysurfaces
from gplugins.gmsh.parse_gds import cleanup_component


def apply_effective_buffers(layer_polygons_dict, layer_stack, z):
    # Find layers present at this z-level
    layers = get_layers_at_z(layer_stack, z)
    # Order the layers by their mesh_order in the layer_stack
    layers = sorted(layers, key=lambda x: layer_stack.layers[x].mesh_order)

    # Determine effective buffer (or even presence of layer) at this z-level
    shapes = OrderedDict()
    for layername in layers:
        if layername in layers:
            # Calculate the buffer
            if layer_stack.layers[layername].thickness < 0:
                zmin = (
                    layer_stack.layers[layername].zmin
                    + layer_stack.layers[layername].thickness
                )
                thickness = abs(layer_stack.layers[layername].thickness)
            else:
                zmin = layer_stack.layers[layername].zmin
                thickness = layer_stack.layers[layername].thickness
            z_fraction = (z - zmin) / thickness
            polygons = layer_polygons_dict[layername]
            if layer_stack.layers[layername].z_to_bias:
                fractions, buffers = layer_stack.layers[layername].z_to_bias
                buffer = np.interp(z_fraction, fractions, buffers)
                shapes[layername] = polygons.buffer(buffer, join_style=2)
            else:
                shapes[layername] = polygons

    return shapes


def xy_xsection_mesh(
    component: ComponentOrReference,
    z: float,
    layer_stack: LayerStack,
    layer_physical_map: dict,
    layer_meshbool_map: dict,
    resolutions: dict | None = None,
    default_characteristic_length: float = 0.5,
    background_tag: str | None = None,
    background_padding: tuple[float, float, float, float, float, float] = (2.0,) * 6,
    background_mesh_order: int | float = 2**63 - 1,
    global_scaling: float = 1,
    global_scaling_premesh: float = 1,
    global_2D_algorithm: int = 6,
    filename: str | None = None,
    verbosity: int | None = 0,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    n_threads: int = get_number_of_cores(),
    port_names: list[str] | None = None,
    gmsh_version: float | None = None,
    interface_delimiter: str = "___",
    layer_port_delimiter: str | None = None,
    background_remeshing_file: str | None = None,
    optimization_flags: tuple[tuple[str, int]] | None = None,
    **kwargs: Any,
):
    """Mesh xy cross-section of component at height z.

    Args:
        component (Component): gdsfactory component to mesh
        z (float): z-coordinate at which to sample the LayerStack
        layer_stack (LayerStack): gdsfactory LayerStack to parse
        layer_physical_map: map layer names to physical names
        layer_meshbool_map: map layer names to mesh_bool (True: mesh the prisms, False: don't mesh)
        resolutions (Dict): Pairs {"layername": {"resolution": float, "distance": "float}} to roughly control mesh refinement
        default_characteristic_length: default characteristic length for the mesh
        background_tag (str): name of the background layer to add (default: no background added)
        background_padding (Tuple): [xleft, ydown, xright, yup] distances to add to the components and to fill with background_tag
        background_mesh_order (int, float): mesh order to assign to the background
        global_scaling: scaling factor for the mesh
        global_scaling_premesh: scaling factor for the mesh before meshing
        global_2D_algorithm: gmsh 2D algorithm to use
        filename (str, path): where to save the .msh file
        verbosity: verbosity level for gmsh
        round_tol: during gds --> mesh conversion cleanup, number of decimal points at which to round the gdsfactory/shapely points before introducing to gmsh
        simplify_tol: during gds --> mesh conversion cleanup, shapely "simplify" tolerance (make it so all points are at least separated by this amount)
        n_threads: number of threads to use for mesh generation
        port_names: list of port names to mesh
        gmsh_version: gmsh version to use
        interface_delimiter: delimiter to use for new layers generated for interfaces: "layer{interface_delimiter}interface_name".
        layer_port_delimiter: Delimiter to use for new layers generated for ports: "layer{delimiter}port_name".
        background_remeshing_file: filename to load background remeshing from.
        optimization_flags: flags for Model.mesh
        kwargs: kwargs for Model.mesh
    """
    if port_names:
        mesh_component = gf.Component()
        ref = mesh_component << component
        mesh_component.add_ports(ref.ports)
        component = get_component_with_net_layers(
            component=mesh_component,
            port_names=port_names,
            layer_stack=layer_stack,
            **(dict(delimiter=layer_port_delimiter) if layer_port_delimiter else {}),
        )

    # Fuse and cleanup polygons of same layer in case user overlapped them
    layer_polygons_dict = cleanup_component(
        component, layer_stack, round_tol, simplify_tol
    )

    # Determine effective buffer (or even presence of layer) at this z-level
    shapes_dict = apply_effective_buffers(layer_polygons_dict, layer_stack, z)

    # Add background polygon
    if background_tag is not None:
        # get min and max z values in LayerStack
        zs = list_unique_layer_stack_z(layer_stack)
        zmin, zmax = np.min(zs), np.max(zs)

        bounds = unary_union(list(shapes_dict.values())).bounds
        shapes_dict[background_tag] = Polygon(
            [
                [bounds[0] - background_padding[0], bounds[1] - background_padding[1]],
                [bounds[0] - background_padding[0], bounds[3] + background_padding[3]],
                [bounds[2] + background_padding[2], bounds[3] + background_padding[3]],
                [bounds[2] + background_padding[2], bounds[1] - background_padding[1]],
            ]
        )
        layer_stack = LayerStack(
            layers=layer_stack.layers
            | {
                background_tag: LayerLevel(
                    layer=LogicalLayer(
                        layer=(999, 0)
                    ),  # TODO something like LAYERS.BACKGROUND?
                    thickness=(
                        (zmax + background_padding[5]) - (zmin - background_padding[2])
                    )
                    * global_scaling_premesh,
                    zmin=(zmin - background_padding[2]) * global_scaling_premesh,
                    material=background_tag,
                    mesh_order=background_mesh_order,
                )
            }
        )

    # Define polysurfaces
    model = Model(n_threads=n_threads)
    polysurfaces_list = define_polysurfaces(
        polygons_dict=shapes_dict,
        layer_stack=layer_stack,
        model=model,
        scale_factor=global_scaling_premesh,
        resolutions=resolutions,
        layer_physical_map=layer_physical_map,
        layer_meshbool_map=layer_meshbool_map,
    )

    # Mesh
    return model.mesh(
        entities_list=polysurfaces_list,
        default_characteristic_length=default_characteristic_length,
        global_scaling=global_scaling,
        global_2D_algorithm=global_2D_algorithm,
        gmsh_version=gmsh_version,
        filename=filename,
        verbosity=verbosity,
        background_remeshing_file=background_remeshing_file,
        optimization_flags=optimization_flags,
        interface_delimiter=interface_delimiter,
        **kwargs,
    )


if __name__ == "__main__":
    import gdsfactory as gf

    c = gf.Component()
    waveguide = c << gf.get_component(gf.components.straight_pin(length=10, taper=None))

    from gdsfactory.pdk import get_layer_stack

    filtered_layer_stack = LayerStack(
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
        z=0.11,
        layer_stack=filtered_layer_stack,
        layer_physical_map={},
        layer_meshbool_map={},
        resolutions=resolutions,
        background_tag="Oxide",
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
