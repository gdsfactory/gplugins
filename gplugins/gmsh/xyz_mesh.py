from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence

import numpy as np
from gdsfactory.config import get_number_of_cores
from gdsfactory.technology import LayerLevel, LayerStack
from gdsfactory.typings import ComponentOrReference
from meshwell.model import Model
from meshwell.prism import Prism
from shapely.affinity import scale
from shapely.geometry import Polygon
from shapely.ops import unary_union

from gplugins.gmsh.parse_component import bufferize
from gplugins.gmsh.parse_gds import cleanup_component
from gplugins.gmsh.parse_layerstack import (
    list_unique_layerstack_z,
    order_layerstack,
)


def define_prisms(layer_polygons_dict, layerstack, model, scale_factor):
    """Define meshwell prism dimtags from gdsfactory information."""
    prisms_dict = OrderedDict()
    buffered_layerstack = bufferize(layerstack)
    ordered_layerstack = order_layerstack(layerstack)

    for layername in ordered_layerstack:
        coords = np.array(buffered_layerstack.layers[layername].z_to_bias[0])
        zs = (
            coords * buffered_layerstack.layers[layername].thickness * scale_factor
            + buffered_layerstack.layers[layername].zmin * scale_factor
        )
        buffers = (
            np.array(buffered_layerstack.layers[layername].z_to_bias[1]) * scale_factor
        )

        buffer_dict = dict(zip(zs, buffers))

        prisms_dict[layername] = Prism(
            polygons=scale(
                layer_polygons_dict[layername], *(scale_factor,) * 2, origin=(0, 0, 0)
            ),
            buffers=buffer_dict,
            model=model,
        )

    return prisms_dict


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
        global_2D_algorithm: gmsh surface default meshing algorithm, see https://gmsh.info/doc/texinfo/gmsh.html#Mesh-options
        global_3D_algorithm: gmsh volume default meshing algorithm, see https://gmsh.info/doc/texinfo/gmsh.html#Mesh-options
        filename: where to save the .msh file
        round_tol: during gds --> mesh conversion cleanup, number of decimal points at which to round the gdsfactory/shapely points before introducing to gmsh
        simplify_tol: during gds --> mesh conversion cleanup, shapely "simplify" tolerance (make it so all points are at least separated by this amount)
    """
    # Fuse and cleanup polygons of same layer in case user overlapped them
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
    prisms_dict = define_prisms(
        layer_polygons_dict, layerstack, model, global_scaling_premesh
    )

    import copy

    resolutions = copy.deepcopy(resolutions)

    if resolutions:
        for r in resolutions.values():
            r["resolution"] *= global_scaling_premesh

    # Mesh
    mesh_out = model.mesh(
        entities_dict=prisms_dict,
        resolutions=resolutions,
        default_characteristic_length=default_characteristic_length,
        global_scaling=global_scaling,
        global_2D_algorithm=global_2D_algorithm,
        global_3D_algorithm=global_3D_algorithm,
        filename=filename,
        verbosity=verbosity,
    )

    return mesh_out


if __name__ == "__main__":
    import gdsfactory as gf
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.pdk import get_layer_stack

    # Choose some component
    c = gf.component.Component()
    waveguide = c << gf.get_component(gf.components.straight_heater_metal(length=40))
    c.add_ports(waveguide.get_ports_list())

    # Add wafer / vacuum (could be automated)
    wafer = c << gf.components.bbox(bbox=waveguide.bbox, layer=LAYER.WAFER)

    # Generate a new component and layerstack with new logical layers
    layerstack = get_layer_stack()
    c = layerstack.get_component_with_net_layers(
        c,
        portnames=["r_e2", "l_e4"],
        delimiter="#",
    )

    # FIXME: .filtered returns all layers
    # filtered_layerstack = layerstack.filtered_from_layerspec(layerspecs=c.get_layers())
    filtered_layerstack = LayerStack(
        layers={
            k: layerstack.layers[k]
            for k in (
                # "via1",
                "box",
                "clad",
                # "metal2",
                "metal3#l_e4",
                "heater",
                "via2",
                "core",
                "metal3#r_e2",
                # "metal3",
                # "via_contact",
                # "metal1"
            )
        }
    )

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
    )
