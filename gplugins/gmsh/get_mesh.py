import importlib.util

from gdsfactory import Component
from gdsfactory.typings import ComponentSpec, Layer, LayerStack

from gplugins.gmsh.uz_xsection_mesh import uz_xsection_mesh
from gplugins.gmsh.xy_xsection_mesh import xy_xsection_mesh
from gplugins.gmsh.xyz_mesh import xyz_mesh


def get_mesh(
    component: ComponentSpec,
    type: str,
    layer_stack: LayerStack,
    z: float | None = None,
    xsection_bounds=None,
    wafer_padding: float = 0.0,
    wafer_layer: Layer = (99999, 0),
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
    padded_component << component
    (xmin, ymin), (xmax, ymax) = component.bbox
    points = [
        [xmin - wafer_padding, ymin - wafer_padding],
        [xmax + wafer_padding, ymin - wafer_padding],
        [xmax + wafer_padding, ymax + wafer_padding],
        [xmin - wafer_padding, ymax + wafer_padding],
    ]
    padded_component.add_polygon(points, layer=wafer_layer)
    padded_component.add_ports(component.get_ports_list())

    if type == "xy":
        if z is None:
            raise ValueError(
                'For xy-meshing, a z-value must be provided via the float argument "z".'
            )

        return xy_xsection_mesh(padded_component, z, layer_stack, **kwargs)
    elif type == "uz":
        if xsection_bounds is None:
            raise ValueError(
                "For uz-meshing, you must provide a line in the xy-plane "
                "via the Tuple argument [[x1,y1], [x2,y2]] xsection_bounds."
            )

        return uz_xsection_mesh(
            padded_component, xsection_bounds, layer_stack, **kwargs
        )
    elif type == "3D":
        spec = importlib.util.find_spec("meshwell")
        if spec is None:
            print(
                "3D meshing requires meshwell, see https://github.com/simbilod/meshwell or run pip install meshwell."
            )

        return xyz_mesh(padded_component, layer_stack, **kwargs)
    else:
        raise ValueError('Required argument "type" must be one of "xy", "uz", or "3D".')
