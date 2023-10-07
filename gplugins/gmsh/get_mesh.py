import meshio
from gdsfactory import Component
from gdsfactory.typings import ComponentSpec, Layer, LayerStack

from gplugins.gmsh.uz_xsection_mesh import uz_xsection_mesh
from gplugins.gmsh.xy_xsection_mesh import xy_xsection_mesh
from gplugins.gmsh.xyz_mesh import xyz_mesh


def create_physical_mesh(mesh, cell_type) -> meshio.Mesh:
    cells = mesh.get_cells_type(cell_type)
    cell_data = mesh.get_cell_data("gmsh:physical", cell_type)
    points = mesh.points
    return meshio.Mesh(
        points=points,
        cells={cell_type: cells},
        cell_data={"name_to_read": [cell_data]},
    )


def get_mesh(
    component: ComponentSpec,
    type: str,
    layer_stack: LayerStack,
    z: float | None = None,
    xsection_bounds=None,
    wafer_padding: float = 0.0,
    wafer_layer: Layer = (99999, 0),
    default_characteristic_length=0.5,
    **kwargs,
):
    """Returns a gmsh mesh of the component for finite element simulation.

    Arguments:
        component: component
        type: one of "xy", "uz", or "3D". Determines the type of mesh to return.
        layer_stack: LayerStack object containing layer information.
        z: used to define z-slice for xy meshing.
        xsection_bounds: used to define in-plane line for uz meshing.
        wafer_padding: padding beyond bbox to add to WAFER layers.
        wafer_layer: layer to use for WAFER padding.

    Keyword Args:
        Arguments for the target meshing function in gplugins.gmsh


    TODO! make compatible with new unified plugins interface
    """

    # Add WAFER layer:
    padded_component = Component()
    _ = padded_component << component
    (xmin, ymin), (xmax, ymax) = component.bbox
    points = [
        [xmin - wafer_padding, ymin - wafer_padding],
        [xmax + wafer_padding, ymin - wafer_padding],
        [xmax + wafer_padding, ymax + wafer_padding],
        [xmin - wafer_padding, ymax + wafer_padding],
    ]
    padded_component.add_polygon(points, layer=wafer_layer)
    padded_component.add_ports(component.get_ports_list())

    # Parse the resolutions dict to set default size_max
    if "resolutions" in kwargs:
        new_resolutions = {}
        for layername, resolutions_dict in kwargs["resolutions"].items():
            if "SizeMax" not in resolutions_dict:
                resolutions_dict["SizeMax"] = default_characteristic_length
            if "distance" in resolutions_dict and "DistMax" not in resolutions_dict:
                resolutions_dict["DistMax"] = resolutions_dict["distance"]
            new_resolutions[layername] = resolutions_dict
        del kwargs["resolutions"]
    else:
        new_resolutions = None

    if type == "xy":
        if z is None:
            raise ValueError(
                'For xy-meshing, a z-value must be provided via the float argument "z".'
            )

        return xy_xsection_mesh(
            component=padded_component,
            z=z,
            layer_stack=layer_stack,
            default_characteristic_length=default_characteristic_length,
            resolutions=new_resolutions,
            **kwargs,
        )
    elif type == "uz":
        if xsection_bounds is None:
            raise ValueError(
                "For uz-meshing, you must provide a line in the xy-plane "
                "via the Tuple argument [[x1,y1], [x2,y2]] xsection_bounds."
            )

        return uz_xsection_mesh(
            component=padded_component,
            xsection_bounds=xsection_bounds,
            layer_stack=layer_stack,
            default_characteristic_length=default_characteristic_length,
            resolutions=new_resolutions,
            **kwargs,
        )
    elif type == "3D":
        return xyz_mesh(
            component=padded_component,
            layer_stack=layer_stack,
            default_characteristic_length=default_characteristic_length,
            resolutions=new_resolutions,
            **kwargs,
        )
    else:
        raise ValueError('Required argument "type" must be one of "xy", "uz", or "3D".')
