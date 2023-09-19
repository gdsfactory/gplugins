from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import gdsfactory as gf
import numpy as np
from gdsfactory.config import get_number_of_cores
from gdsfactory.geometry.union import union
from gdsfactory.technology import LayerLevel, LayerStack
from gdsfactory.typings import ComponentOrReference, List
from meshwell.gmsh_entity import GMSH_entity
from meshwell.model import Model
from meshwell.prism import Prism
from shapely.affinity import scale
from shapely.geometry import Polygon
from shapely.ops import unary_union

from gplugins.common.utils.parse_layerstack import (
    list_unique_layerstack_z,
)
from gplugins.gmsh.parse_component import bufferize
from gplugins.gmsh.parse_gds import cleanup_component


def define_edgeport(
    port,
    port_dict,
    model,
    layerlevel,
):
    """Creates an unmeshed box at the port location to tag the edge port surfaces in the final mesh."""
    zmin = port_dict.get("zmin") or layerlevel.zmin
    zmax = port_dict.get("zmax") or zmin + layerlevel.thickness

    dz = zmax - zmin
    x, y = port.center
    width_pad = port_dict.get("width_pad") or 0

    if port.orientation == 180:  # left of simulation
        dx = 1
        dy = port.width + 2 * width_pad
        x -= dx
        y -= dy / 2
    elif port.orientation == 0:  # right of simulation
        dx = 1
        dy = port.width + 2 * width_pad
        y -= dy / 2
    elif port.orientation == 90:  # top of simulation
        dx = port.width + 2 * width_pad
        dy = 1
        x -= dx / 2
    elif port.orientation == 270:  # bottom of simulation
        dx = port.width + 2 * width_pad
        dy = 1
        y -= dy
        x -= dx / 2

    box = GMSH_entity(
        gmsh_function=model.occ.add_box,
        gmsh_function_kwargs={"x": x, "y": y, "z": zmin, "dx": dx, "dy": dy, "dz": dz},
        dimension=3,
        model=model,
        resolution=port_dict.get("resolution", None),
        mesh_order=0,  # highest priority
        mesh_bool=False,
        physical_name=port_dict.get("physical_name", port.name),
    )

    return box


def define_prisms(
    layer_polygons_dict: dict,
    layerstack: LayerStack,
    model: Any,
    resolutions: dict,
    scale_factor: float = 1,
):
    """Define meshwell prism dimtags from gdsfactory information."""
    prisms_list = []
    buffered_layerstack = bufferize(layerstack)

    if resolutions is None:
        resolutions = {}

    for layername in buffered_layerstack.layers.keys():
        if layer_polygons_dict[layername].is_empty:
            continue

        coords = np.array(buffered_layerstack.layers[layername].z_to_bias[0])
        zs = (
            coords * buffered_layerstack.layers[layername].thickness * scale_factor
            + buffered_layerstack.layers[layername].zmin * scale_factor
        )
        buffers = (
            np.array(buffered_layerstack.layers[layername].z_to_bias[1]) * scale_factor
        )

        buffer_dict = dict(zip(zs, buffers))

        prisms_list.append(
            Prism(
                polygons=scale(
                    layer_polygons_dict[layername],
                    *(scale_factor,) * 2,
                    origin=(0, 0, 0),
                ),
                buffers=buffer_dict,
                model=model,
                resolution=resolutions.get(layername, None),
                mesh_order=buffered_layerstack.layers.get(layername).mesh_order,
                physical_name=layername,
            )
        )

    return prisms_list


def xyz_mesh(
    component: ComponentOrReference,
    layerstack: LayerStack,
    resolutions: dict | None = None,
    default_characteristic_length: float = 0.5,
    background_tag: str | None = None,
    background_padding: Sequence[float, float, float, float, float, float] = (2.0,) * 6,
    global_scaling: float = 1,
    global_scaling_premesh: float = 1,
    global_2D_algorithm: int = 6,
    global_3D_algorithm: int = 1,
    filename: str | None = None,
    verbosity: int | None = 0,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    n_threads: int = get_number_of_cores(),
    portnames: List[str] = None,
    edge_ports: List[str] = None,
    layer_portname_delimiter: str = "#",
    gmsh_version: float | None = None,
) -> bool:
    """Full 3D mesh of component.

    Args:
        component: gdsfactory component to mesh
        layerstack: gdsfactory LayerStack to parse
        resolutions: Pairs {"layername": {"resolution": float, "distance": "float}} to roughly control mesh refinement
            default_characteristic_length: gmsh maximum edge length
        background_tag: name of the background layer to add (default: no background added). This will be used as the material as well.
        background_padding: [-x, -y, -z, +x, +y, +z] distances to add to the components and to fill with ``background_tag``
        global_scaling: factor to scale all mesh coordinates by (e.g. 1E-6 to go from um to m)
        global_scaling_premesh: factor to scale all mesh coordinates by (e.g. 1E-6 to go from um to m).
            Instead of using a gmsh-option which is only applied to meshes, this parameter can scale cad-exported files, e.g. .step files
        global_2D_algorithm: gmsh surface default meshing algorithm, see https://gmsh.info/doc/texinfo/gmsh.html#Mesh-options
        global_3D_algorithm: gmsh volume default meshing algorithm, see https://gmsh.info/doc/texinfo/gmsh.html#Mesh-options
        filename: where to save the .msh file
        round_tol: during gds --> mesh conversion cleanup, number of decimal points at which to round the gdsfactory/shapely points before introducing to gmsh
        simplify_tol: during gds --> mesh conversion cleanup, shapely "simplify" tolerance (make it so all points are at least separated by this amount)
        n_threads: for gmsh parallelization
        portnames: list or port polygons to converts into new layers (useful for boundary conditions)
        edge_ports: dict of portnames to define as a 2D surface at the edge of the simulation.
            edge_ports = {
                "e1": {
                    physical_name: (str), # how to name the 2D surface in the GMSH mesh. Default {port_layer}{layer_portname_delimiter}{port_name}
                    width_pad: (float), # how much to extend the port width (default 0). Negative to shrink.
                    zmin: (float), # minimal z-value of the port (default to port layer zmin)
                    zmax: (float), # maximum z-value of the port (default to port layer zmin + thickness)
                    resolution: (float), # constant resolution to assign to the gmsh 2D entity
                },
                ...
            }
        layer_portname_delimiter: delimiter for the new layername/portname physicals, formatted as {layername}{delimiter}{portname}
        gmsh_version: Gmsh mesh format version. For example, Palace requires an older version of 2.2,
            see https://mfem.org/mesh-formats/#gmsh-mesh-formats.
    """
    if portnames:
        mesh_component = gf.Component()
        mesh_component << union(component, by_layer=True)
        mesh_component.add_ports(component.get_ports_list())
        component = layerstack.get_component_with_net_layers(
            mesh_component,
            portnames=portnames,
            delimiter=layer_portname_delimiter,
        )

    # Fuse and cleanup polygons of same layer in case user overlapped them
    # TODO: some duplication with union above, although this also does some useful offsetting
    layer_polygons_dict = cleanup_component(
        component, layerstack, round_tol, simplify_tol
    )

    # Add background polygon
    if background_tag is not None:
        bbox = unary_union(list(layer_polygons_dict.values()))
        bounds = bbox.bounds

        # get min and max z values in LayerStack
        zs = list_unique_layerstack_z(layerstack)
        zmin, zmax = np.min(zs), np.max(zs)

        # create Polygon encompassing simulation environment
        layer_polygons_dict[background_tag] = scale(
            Polygon(
                [
                    [
                        bounds[0] - background_padding[0],
                        bounds[1] - background_padding[1],
                    ],
                    [
                        bounds[0] - background_padding[0],
                        bounds[3] + background_padding[4],
                    ],
                    [
                        bounds[2] + background_padding[3],
                        bounds[3] + background_padding[4],
                    ],
                    [
                        bounds[2] + background_padding[3],
                        bounds[1] - background_padding[1],
                    ],
                ]
            ),
            *(global_scaling_premesh,) * 2,
            origin=(0, 0, 0),
        )
        layerstack = LayerStack(
            layers=layerstack.layers
            | {
                background_tag: LayerLevel(
                    layer=(9999, 0),  # TODO something like LAYERS.BACKGROUND?
                    thickness=(
                        (zmax + background_padding[5]) - (zmin - background_padding[2])
                    )
                    * global_scaling_premesh,
                    zmin=(zmin - background_padding[2]) * global_scaling_premesh,
                    material=background_tag,
                    mesh_order=2**63 - 1,
                )
            }
        )

    # Meshwell Prisms from gdsfactory polygons and layerstack
    model = Model(n_threads=n_threads)
    prisms_list = define_prisms(
        layer_polygons_dict=layer_polygons_dict,
        layerstack=layerstack,
        model=model,
        scale_factor=global_scaling_premesh,
        resolutions=resolutions,
    )

    # Add edgeports
    if edge_ports is not None:
        ports = component.get_ports_dict()
        port_layernames = layerstack.get_layer_to_layername()
        for portname, edge_ports_dict in edge_ports.items():
            port = ports[portname]
            prisms_list.append(
                define_edgeport(
                    port,
                    edge_ports_dict,
                    model,
                    layerlevel=layerstack.layers[port_layernames[port.layer][0]],
                )
            )

    import copy

    resolutions = copy.deepcopy(resolutions)

    if resolutions:
        for r in resolutions.values():
            r["resolution"] *= global_scaling_premesh
    else:
        resolutions = {}

    # Assign resolutions to derived logical layers
    for entry in prisms_list:
        key = entry.physical_name
        if layer_portname_delimiter in key:
            base_key = key.split(layer_portname_delimiter)[0]
            if key not in resolutions and base_key in resolutions:
                entry.resolution = resolutions[base_key]

    return model.mesh(
        entities_list=prisms_list,
        default_characteristic_length=default_characteristic_length,
        global_scaling=global_scaling,
        global_2D_algorithm=global_2D_algorithm,
        global_3D_algorithm=global_3D_algorithm,
        gmsh_version=gmsh_version,
        filename=filename,
        verbosity=verbosity,
    )


if __name__ == "__main__":
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.pdk import get_layer_stack

    # Choose some component
    c = gf.component.Component()
    waveguide = c << gf.get_component(gf.components.straight(length=40))
    c.add_ports(waveguide.get_ports_list())

    # Add wafer / vacuum (could be automated)
    wafer = c << gf.components.bbox(
        bbox=waveguide.bbox,
        layer=LAYER.WAFER,
        top=3,
        bottom=3,
    )

    # Generate a new component and layerstack with new logical layers
    layerstack = get_layer_stack()

    filtered_layerstack = LayerStack(
        layers={
            k: layerstack.layers[k]
            for k in (
                # "via1",
                "box",
                "clad",
                # "metal2",
                # "heater",
                # "via2",
                "core",
                # "metal3",
                # "via_contact",
                # "metal1"
            )
        }
    )

    filtered_layerstack.layers["core"].mesh_order = 1
    filtered_layerstack.layers["box"].thickness = 3
    filtered_layerstack.layers["box"].zmin = -3
    filtered_layerstack.layers["box"].mesh_order = 2
    filtered_layerstack.layers["clad"].thickness = 3
    filtered_layerstack.layers["clad"].zmin = 0
    filtered_layerstack.layers["clad"].mesh_order = 3

    resolutions = {
        "core": {"resolution": 0.3},
    }
    geometry = xyz_mesh(
        component=c,
        layerstack=filtered_layerstack,
        resolutions=resolutions,
        filename="mesh.msh",
        default_characteristic_length=5,
        verbosity=5,
        # portnames=["r_e2", "l_e4"],
        edge_ports={
            "o1": {
                "zmin": -1,
                "zmax": 1,
                "resolution": {"resolution": 0.1},
                "physical_name": "edgeport",
                "width_pad": 1,
            }
        },
    )
