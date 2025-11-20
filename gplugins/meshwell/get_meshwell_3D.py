import gdsfactory as gf
from meshwell.polyprism import PolyPrism
from typing import List, Dict, Literal
from shapely.geometry import Polygon, MultiPolygon
import math
import kfactory as kf
from gdsfactory.add_padding import add_padding_container, add_padding
from functools import partial
from gdsfactory.generic_tech.layer_map import LAYER
from gplugins.common.utils.geometry import region_to_shapely_polygons


def build_buffer_dict_from_layer_level(
    layer_level: gf.technology.LayerLevel,
) -> Dict[float, float]:
    """Build buffer dictionary from LayerLevel properties."""
    zmin = layer_level.zmin
    zmax = zmin + layer_level.thickness

    # Priority 1: z_to_bias if available
    if layer_level.z_to_bias is not None:
        z_values, bias_values = layer_level.z_to_bias
        return dict(zip(z_values, bias_values))

    # Priority 2: Handle sidewall angle
    if layer_level.sidewall_angle != 0.0:
        angle_rad = math.radians(layer_level.sidewall_angle)
        height = layer_level.thickness
        width_to_z = layer_level.width_to_z

        # Calculate buffer change due to sidewall angle
        # Positive angle means outward sloping, negative means inward
        buffer_change = height * math.tan(angle_rad)

        if width_to_z == 0.0:  # Reference at bottom
            bottom_buffer = 0.0
            top_buffer = buffer_change
        elif width_to_z == 1.0:  # Reference at top
            bottom_buffer = -buffer_change
            top_buffer = 0.0
        else:  # Reference somewhere in middle
            ref_height = height * width_to_z
            bottom_buffer = -ref_height * math.tan(angle_rad)
            top_buffer = (height - ref_height) * math.tan(angle_rad)

        return {zmin: bottom_buffer, zmax: top_buffer}

    # Default: Simple extrusion
    return {zmin: 0.0, zmax: 0.0}


def get_meshwell_prisms(
    component: gf.Component,
    layer_stack: gf.technology.LayerStack,
    wafer_layer: gf.typings.Layer | None = LAYER.WAFER,
    wafer_padding: float | None = 0.0,
    name_by: Literal["layer", "material"] = "layer",
) -> List[PolyPrism]:
    """Convert LayerStack + Component to meshwell PolyPrism objects."""
    prisms = []

    if wafer_padding is not None and wafer_layer is not None:
        component = add_padding_container(
            component=component,
            function=partial(add_padding, layers=(wafer_layer,), default=wafer_padding),
        )

    # Iterate through each layer in the stack
    for layer_name, layer_level in layer_stack.layers.items():
        # Get shapes for this layer from the component
        region = layer_level.layer.get_shapes(component)

        # Skip if no shapes found
        if region.is_empty():
            continue

        # Convert kfactory Region to Shapely polygons
        shapely_polygons = region_to_shapely_polygons(region)

        # Skip if no valid polygons
        if not shapely_polygons:
            continue

        # Build buffer dictionary from layer level properties
        buffers = build_buffer_dict_from_layer_level(layer_level)

        # Create PolyPrism object
        if name_by == "layer":
            physical_name = layer_name
        elif name_by == "material":
            physical_name = layer_level.material
        else:
            raise ValueError("name_by must be 'layer' or 'material'")
        prism = PolyPrism(
            polygons=shapely_polygons,
            buffers=buffers,
            physical_name=physical_name,
            mesh_order=layer_level.mesh_order,
            mesh_bool=True,
            additive=False,
        )

        prisms.append(prism)

    return prisms

if __name__ == "__main__":
    from gdsfactory.components import ge_detector_straight_si_contacts, add_frame
    from gdsfactory.generic_tech.layer_stack import get_layer_stack
    from gdsfactory.generic_tech.layer_map import LAYER
    from meshwell.cad import cad
    from meshwell.mesh import mesh


    for component in [ge_detector_straight_si_contacts, add_frame]:
        c = component()
        prisms = get_meshwell_prisms(
            component=c,
            layer_stack=get_layer_stack(sidewall_angle_wg=0),
            name_by="layer",
        )

        cad(entities_list=prisms, output_file=f"meshwell_prisms_3D_{c.name}.xao")
        mesh(
            input_file=f"meshwell_prisms_3D_{c.name}.xao",
            output_file=f"meshwell_prisms_3D_{c.name}.msh",
            default_characteristic_length=1000,
            dim=3,
            verbosity=10,
        )
