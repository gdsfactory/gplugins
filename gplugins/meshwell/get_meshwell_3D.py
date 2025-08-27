
import gdsfactory as gf
from meshwell.prism import Prism
from typing import List, Dict
from shapely.geometry import Polygon, MultiPolygon
import math
import kfactory as kf


def region_to_shapely_polygons(region: kf.kdb.Region) -> List[Polygon]:
    """Convert a kfactory Region to a list of Shapely polygons."""
    polygons = []
    for polygon_kdb in region.each():
        # Extract exterior coordinates
        exterior_coords = []
        for point in polygon_kdb.each_point_hull():
            exterior_coords.append((gf.kcl.to_um(point.x), gf.kcl.to_um(point.y)))

        # Extract hole coordinates
        holes = []
        for hole_idx in range(polygon_kdb.holes()):
            hole_coords = []
            hole = polygon_kdb.hole(hole_idx)
            for point in hole.each_point():
                hole_coords.append((gf.kcl.to_um(point.x), gf.kcl.to_um(point.y)))
            holes.append(hole_coords)

        # Create Shapely polygon
        if holes:
            polygon = Polygon(exterior_coords, holes)
        else:
            polygon = Polygon(exterior_coords)
        polygons.append(polygon)

    return MultiPolygon(polygons)


def build_buffer_dict_from_layer_level(layer_level: gf.technology.LayerLevel) -> Dict[float, float]:
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
) -> List[Prism]:
    """Convert LayerStack + Component to meshwell Prism objects."""
    prisms = []

    # Iterate through each layer in the stack
    for layer_name, layer_level in layer_stack.layers.items():

        # Get shapes for this layer from the component
        region = layer_level.layer.get_shapes(component)

        # Skip if no shapes found
        if region.is_empty():
            continue

        # Convert kfactory Region to Shapely polygons
        shapely_polygons = region_to_shapely_polygons(region)

        print(shapely_polygons)

        # Skip if no valid polygons
        if not shapely_polygons:
            continue

        # Build buffer dictionary from layer level properties
        buffers = build_buffer_dict_from_layer_level(layer_level)

        # Create Prism object
        prism = Prism(
            polygons=shapely_polygons,
            buffers=buffers,
            physical_name=layer_level.material or layer_name,
            mesh_order=layer_level.mesh_order,
            mesh_bool=True,
            additive=False
        )

        prisms.append(prism)

    return prisms


if __name__ == "__main__":

    from gdsfactory.components import straight_pn
    from gdsfactory.generic_tech.layer_stack import get_layer_stack
    from meshwell.cad import cad
    from meshwell.mesh import mesh

    prisms = get_meshwell_prisms(component=straight_pn(length=10, taper=None),
                        layer_stack=get_layer_stack()
                        )

    cad(entities_list=prisms, output_file="meshwell_prisms_3D.xao")
    mesh(input_file="meshwell_prisms_3D.xao",
         output_file="meshwell_prisms_3D.msh",
         default_characteristic_length=1000,
         dim=3,
         verbosity=10
    )
