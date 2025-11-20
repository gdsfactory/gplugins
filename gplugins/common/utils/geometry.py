from typing import List
import gdsfactory as gf
import kfactory as kf
from shapely.geometry import Polygon, MultiPolygon

def region_to_shapely_polygons(region: kf.kdb.Region) -> MultiPolygon:
    """Convert a kfactory Region to a list of Shapely polygons."""
    polygons = []
    for polygon_kdb in region.each():
        exterior_coords = [
            (gf.kcl.to_um(point.x), gf.kcl.to_um(point.y))
            for point in polygon_kdb.each_point_hull()
        ]
        # Extract hole coordinates
        holes = []
        num_holes = polygon_kdb.holes()
        for hole_idx in range(num_holes):
            hole_coords = []
            for point in polygon_kdb.each_point_hole(hole_idx):
                hole_coords.append((gf.kcl.to_um(point.x), gf.kcl.to_um(point.y)))
            holes.append(hole_coords)


        # Create Shapely polygon
        if holes:
            polygon = Polygon(exterior_coords, holes)
        else:
            polygon = Polygon(exterior_coords)
        polygons.append(polygon)

    return MultiPolygon(polygons)
