
import gdsfactory as gf
from meshwell.polyprism import PolyPrism
from meshwell.polysurface import PolySurface
from typing import List, Dict
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
import math
import kfactory as kf
from gdsfactory.add_padding import add_padding_container, add_padding
from functools import partial
from gdsfactory.generic_tech.layer_map import LAYER
from typing import Literal
import numpy as np
from gplugins.common.utils.geometry import region_to_shapely_polygons


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


def get_meshwell_cross_section(
        component: gf.Component,
        line: LineString,
        layer_stack: gf.technology.LayerStack,
        wafer_layer: gf.typings.Layer | None = LAYER.WAFER,
        wafer_padding: float | None = 0.0,
        name_by: Literal["layer", "material"] = "layer"
) -> List[PolySurface]:
    """Convert LayerStack + Component cross-section to meshwell PolySurface objects.

    Args:
        component: gdsfactory Component to take cross-section of
        line: shapely LineString defining the cross-section line in xy-plane
        layer_stack: LayerStack defining the z-direction layers
        wafer_layer: Optional wafer layer for padding
        wafer_padding: Optional padding around wafer layer
        name_by: How to name the physical entities ("layer" or "material")

    Returns:
        List of PolySurface objects representing the cross-section
    """
    surfaces = []

    if wafer_padding is not None and wafer_layer is not None:
        component = add_padding_container(component=component, function=partial(add_padding, layers=(wafer_layer,), default=wafer_padding))

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

        # Find intersections between polygons and the cross-section line
        cross_section_polygons = []

        for polygon in shapely_polygons.geoms if hasattr(shapely_polygons, 'geoms') else [shapely_polygons]:
            intersection = polygon.intersection(line)

            # Skip if no intersection
            if intersection.is_empty:
                continue

            # Handle different types of intersections
            if hasattr(intersection, 'geoms'):
                # Multiple intersections
                for geom in intersection.geoms:
                    if hasattr(geom, 'coords') and len(list(geom.coords)) >= 2:
                        # This is a line segment
                        cross_section_polygons.extend(_linestring_to_cross_section_polygon(geom, layer_level, line))
            else:
                # Single intersection
                if hasattr(intersection, 'coords') and len(list(intersection.coords)) >= 2:
                    # This is a line segment
                    cross_section_polygons.extend(_linestring_to_cross_section_polygon(intersection, layer_level, line))

        # Skip if no cross-section polygons found
        if not cross_section_polygons:
            continue

        # Create PolySurface object
        if name_by == "layer":
            physical_name = layer_name
        elif name_by == "material":
            physical_name = layer_level.material
        else:
            raise ValueError("name_by must be 'layer' or 'material'")

        surface = PolySurface(
            polygons=cross_section_polygons,
            physical_name=physical_name,
            mesh_order=layer_level.mesh_order,
            mesh_bool=True,
            additive=False
        )

        surfaces.append(surface)

    return surfaces


def _linestring_to_cross_section_polygon(linestring, layer_level: gf.technology.LayerLevel, cross_section_line: LineString) -> List[Polygon]:
    """Convert a linestring intersection to cross-section polygon(s) by extruding in z.

    Args:
        linestring: shapely LineString representing intersection
        layer_level: LayerLevel containing z-bounds information
        cross_section_line: The original cross-section line to project onto

    Returns:
        List of Polygon objects representing the cross-section
    """
    # Get z bounds
    zmin = layer_level.zmin
    zmax = zmin + layer_level.thickness

    # Get coordinates along the intersection linestring
    coords = list(linestring.coords)

    # Create cross-section polygons by extruding line segments in z
    polygons = []

    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]

        # Project the intersection points onto the cross-section line
        # to get their position along the line
        from shapely.geometry import Point
        point1 = Point(x1, y1)
        point2 = Point(x2, y2)

        dist1 = cross_section_line.project(point1)
        dist2 = cross_section_line.project(point2)

        if dist1 != dist2:
            # Create rectangle in the line-z plane
            # The x-coordinate is the distance along the cross-section line, y-coordinate is z
            rect_coords = [
                (dist1, zmin),
                (dist2, zmin),
                (dist2, zmax),
                (dist1, zmax),
                (dist1, zmin)
            ]

            polygon = Polygon(rect_coords)
            polygons.append(polygon)

    return polygons


if __name__ == "__main__":

    from gdsfactory.components import ge_detector_straight_si_contacts
    from gdsfactory.generic_tech.layer_stack import get_layer_stack
    from gdsfactory.generic_tech.layer_map import LAYER
    from meshwell.cad import cad
    from meshwell.mesh import mesh

    # Cross-section surfaces (new functionality)
    component = ge_detector_straight_si_contacts()
    component.show()

    # Define a cross-section line (e.g., horizontal line through center)
    cross_section_line = LineString([(4, -15), (4, 15)])

    surfaces = get_meshwell_cross_section(
        component=component,
        line=cross_section_line,
        layer_stack=get_layer_stack(sidewall_angle_wg=0),
        name_by="layer",
    )

    # Create CAD and mesh for cross-section
    cad(entities_list=surfaces, output_file="meshwell_cross_section_2D.xao")
    mesh(input_file="meshwell_cross_section_2D.xao",
         output_file="meshwell_cross_section_2D.msh",
         default_characteristic_length=1000,
         dim=2,
         verbosity=10
    )
