"""Preprocessing involving mostly the GDS polygons."""
from __future__ import annotations

import gdsfactory as gf
import shapely
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon


def round_coordinates(geom, ndigits=4):
    """Round coordinates to n_digits to eliminate floating point errors."""

    def _round_coords(x, y, z=None):
        x = round(x, ndigits)
        y = round(y, ndigits)

        if z is not None:
            z = round(x, ndigits)

        return [c for c in (x, y, z) if c is not None]

    return shapely.ops.transform(_round_coords, geom)


def fuse_polygons(
    component, layername, layer, round_tol=4, simplify_tol=1e-4, offset_tol=None
):
    """Take all polygons from a layer, and returns a single (Multi)Polygon shapely object."""

    layer_component = component.extract([layer])

    # gdstk union before shapely conversion helps with ill-formed polygons
    offset_tol = offset_tol or gf.get_active_pdk().grid_size
    layer_component = gf.geometry.offset(
        layer_component, distance=offset_tol, precision=1e-6, layer=layer
    )
    shapely_polygons = [
        round_coordinates(shapely.geometry.Polygon(polygon), round_tol)
        for polygon in layer_component.get_polygons()
    ]

    return shapely.ops.unary_union(shapely_polygons).simplify(
        simplify_tol, preserve_topology=True
    )


def cleanup_component(component, layer_stack, round_tol=2, simplify_tol=1e-2):
    """Process component polygons before meshing."""
    layer_stack_dict = layer_stack.to_dict()

    return {
        layername: fuse_polygons(
            component,
            layername,
            layer["layer"],
            round_tol=round_tol,
            simplify_tol=simplify_tol,
        )
        for layername, layer in layer_stack_dict.items()
        if layer["layer"] is not None
    }


def to_polygons(geometries):
    for geometry in geometries:
        if isinstance(geometry, Polygon):
            yield geometry
        else:
            yield from geometry.geoms


def to_lines(geometries):
    for geometry in geometries:
        if isinstance(geometry, LineString):
            yield geometry
        else:
            yield from geometry.geoms


def tile_shapes(shapes_dict):
    """Break up shapes in order so that plane is tiled with non-overlapping layers."""
    shapes_tiled_dict = {}

    for lower_index, (lower_name, lower_shapes) in reversed(
        list(enumerate(shapes_dict.items()))
    ):
        tiled_lower_shapes = []
        for lower_shape in (
            lower_shapes.geoms if hasattr(lower_shapes, "geoms") else [lower_shapes]
        ):
            diff_shape = lower_shape
            for _higher_index, (_higher_name, higher_shapes) in reversed(
                list(enumerate(shapes_dict.items()))[:lower_index]
            ):
                for higher_shape in (
                    higher_shapes.geoms
                    if hasattr(higher_shapes, "geoms")
                    else [higher_shapes]
                ):
                    diff_shape = diff_shape.difference(higher_shape)
            tiled_lower_shapes.append(diff_shape)
        if tiled_lower_shapes and tiled_lower_shapes[0].geom_type in [
            "Polygon",
            "MultiPolygon",
        ]:
            shapes_tiled_dict[lower_name] = MultiPolygon(
                to_polygons(tiled_lower_shapes)
            )
        else:
            shapes_tiled_dict[lower_name] = MultiLineString(tiled_lower_shapes)

    return shapes_tiled_dict


if __name__ == "__main__":
    from gdsfactory.generic_tech import LAYER_STACK

    from gplugins.gmsh.get_mesh import get_mesh

    c = gf.components.straight_heater_doped_rib()
    get_mesh(component=c, type="xy", layer_stack=LAYER_STACK, z=0)
    get_mesh(component=c, type="xy", layer_stack=LAYER_STACK, z=0)
