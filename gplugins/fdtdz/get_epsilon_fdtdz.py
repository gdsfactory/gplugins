import jax.numpy as jnp
import matplotlib.pyplot as plt
import numpy as np
from gdsfactory.technology import LayerStack
from gdsfactory.typings import Float2
from pjz import _epsilon

from gplugins.common.utils.parse_layer_stack import (
    get_layer_overlaps_z,
    list_unique_layer_stack_z,
    order_layer_stack,
)

material_name_to_fdtdz = {
    "si": 3.45,
    "sio2": 1.44,
    "sin": 2.0,
}


def create_physical_grid(xmin, ymin, zmin, epsilon, nm_per_pixel):
    _, xinds, yinds, zinds = np.shape(epsilon)
    xmax = xmin + xinds * nm_per_pixel * 1e-3 * 2  # Factor of 2 from Yee grid?
    ymax = ymin + yinds * nm_per_pixel * 1e-3 * 2  # Factor of 2 from Yee grid?
    zmax = zmin + zinds * nm_per_pixel * 1e-3
    step = nm_per_pixel * 1e-3
    xarray = np.arange(xmin, xmax + step / 2, nm_per_pixel * 1e-3)
    yarray = np.arange(ymin, ymax + step / 2, nm_per_pixel * 1e-3)
    zarray = np.arange(zmin, zmax + step / 2, nm_per_pixel * 1e-3)
    return xarray, yarray, zarray


def component_to_epsilon_pjz(
    component,
    layer_stack,
    zmin: float | None = None,
    zz: int = 96,
    nm_per_pixel: float = 20,
    material_name_to_index=None,
    default_index=1.44,
):
    """Uses the layer profiles and vertical layer interfaces to compute epsilon sing pjz.

    Arguments:
        component: gdsfactory component.
        layer_stack: LayerStack object, with layers to consider.
        zmin: can be used to clip the layer_stack at the lower end; upper end determined by zz * num_per_pixel.
        zz: number of vertical grid points.
        nm_per_pixel: resolution (1 simulation pixel = nm_per_pixel nm).
        material_name_to_index: dict mapping LayerStack material names to a real refractive index.
        default_index: used to fill the epsilon array if a pixel is undefined.

    Returns:
        ``(3, xx, yy, zz)`` array of permittivity values with offsets and vector
        components according to the finite-difference Yee cell.
    """
    # Default materials if not provided
    material_name_to_index = material_name_to_index or material_name_to_fdtdz

    # Parse layerlevels
    z_values = sorted(list_unique_layer_stack_z(layer_stack))
    if zmin:
        z_values = [z for z in z_values if zmin <= z]
        z_values.append(zmin)
        z_values = sorted(set(z_values))
        # Patch layer mapping
        z_to_layername = get_layer_overlaps_z(layer_stack, include_zmax=False)
        missing_zs = set(z_to_layername.keys()) - set(z_values)
        z_to_layername[zmin] = z_to_layername[max(missing_zs)]
    else:
        zmin = min(z_values)
        z_to_layername = get_layer_overlaps_z(layer_stack, include_zmax=False)

    # For each vertical slice
    initialized = False
    interface_positions = []
    for level_index, z_value in enumerate(z_values[:-1]):
        # Add interface
        if level_index != 0:
            interface_positions.append(int((z_value - zmin) * 1e3 / nm_per_pixel))
        # Extract each layer number and material in the current level, in mesh order:
        level_layer_stack = LayerStack(
            layers={k: layer_stack.layers[k] for k in z_to_layername[z_value]}
        )
        current_layernames = order_layer_stack(level_layer_stack)[::-1]
        current_layers = [
            layer_stack.layers[layername].layer for layername in current_layernames
        ]
        current_indices = [
            material_name_to_index[layer_stack.layers[layername].material] ** 2
            for layername in current_layernames
        ]

        # Get the epsilon matrix
        i = component.to_np(
            nm_per_pixel=nm_per_pixel,
            layers=current_layers,
            values=current_indices,
            pad_width=0,
        )
        # FIX EDGES
        i[0, :] = i[1, :]
        i[:, 0] = i[:, 1]
        i[-1, :] = i[-2, :]
        i[:, -1] = i[:, -2]
        # Initialize the array if not initialized
        if not initialized:
            layers = np.zeros((len(z_values) - 1, *np.shape(i)))
            initialized = True
        # Populate the epsilon
        layers[level_index, :, :] = i

    # Set unassigned entries to some default
    layers[layers == 0] = default_index**2

    return _epsilon.epsilon(
        layers=jnp.array(layers),
        interface_positions=jnp.array(interface_positions),
        magnification=1,
        zz=zz,
    )


def component_to_epsilon_femwell():
    """TODO: Uses gdsfactory meshing + femwell physical tagging + export to a cartesian\
            grid to define the (3, xx, yy, zz) array of permittivity values"""
    return NotImplementedError


def plot_epsilon(
    epsilon: jnp.array,
    x: int | float = 0.0,
    y: int | float | None = None,
    z: int | float | None = None,
    xmin: float = 0,
    ymin: float = 0,
    zmin: float = 0,
    nm_per_pixel: float = 1000,
    figsize: Float2 = (11, 4),
):
    """Plot epsilon distribution.

    Args:
        epsilon: epsilon array.
        x: (index or coordinate). x-coordinate defining the yz plane to inspect
        y: (index or coordinate). y-coordinate defining the xz plane to inspect
        z: (index or coordinate). z-coordinate defining the xy plane to inspect \
                Only one of x,y, or z must be numeric. \
                By default with nm_per_pixel = 1000 and xmin = ymin = zmin = 0,\
                these are array indices or physical coordinate in um.
        xmin: (um) minimum x-coordinate (default to 0 for pixel index).
        ymin: (um) minimum y-coordinate (default to 0 for pixel index).
        zmin: (um) minimum z-coordinate (default to 0 for pixel index).
        nm_per_pixel: (int) resolution (default to 1000 for pixel index).
        figsize: figure size.
    """

    # Checks
    if (x and y) or (y and z) or (x and z):
        raise ValueError("Only one of x, y or z must be numeric!")

    # Create physical grid
    xarray, yarray, zarray = create_physical_grid(
        xmin, ymin, zmin, epsilon, nm_per_pixel
    )

    # Plot
    fig = plt.figure(figsize=figsize)
    if x is not None:
        x_index = int(
            np.where(np.isclose(xarray, x, atol=nm_per_pixel * 1e-3 / 2))[0][0] / 2
        )  # factor of 2 from Yee grid?
        im = plt.imshow(
            epsilon[0, x_index, :, :].transpose(),
            origin="lower",
            extent=[yarray[0], yarray[-1], zarray[0], zarray[-1]],
            vmin=np.min(epsilon),
            vmax=np.max(epsilon),
        )
        add_plot_labels("y", "z", "Epsilon Distribution at x = ", x)
    elif y is not None:
        y_index = int(
            np.where(np.isclose(yarray, y, atol=nm_per_pixel * 1e-3 / 2))[0][0] / 2
        )  # factor of 2 from Yee grid?
        im = plt.imshow(
            epsilon[1, :, y_index, :].transpose(),
            origin="lower",
            extent=[xarray[0], xarray[-1], zarray[0], zarray[-1]],
            vmin=np.min(epsilon),
            vmax=np.max(epsilon),
        )
        add_plot_labels("x", "z", "Epsilon Distribution at y = ", y)
    else:
        z_index = np.where(np.isclose(zarray, z, atol=nm_per_pixel * 1e-3 / 2))[0][0]
        im = plt.imshow(
            epsilon[0, :, :, z_index].transpose(),
            origin="lower",
            extent=[xarray[0], xarray[-1], yarray[0], yarray[-1]],
            vmin=np.min(epsilon),
            vmax=np.max(epsilon),
        )
        add_plot_labels("x", "y", "Epsilon Distribution at z = ", z)
    cbar = plt.colorbar(im)
    cbar.set_label("Epsilon")

    plt.show()
    return fig


def add_plot_labels(arg0, arg1, arg2, arg3):
    plt.xlabel(arg0)
    plt.ylabel(arg1)
    plt.title(f"{arg2}{arg3}")


if __name__ == "__main__":
    import gdsfactory as gf
    from gdsfactory.generic_tech import LAYER, LAYER_STACK

    length = 5

    c = gf.Component()
    waveguide = c << gf.components.straight(length=length, layer=LAYER.WG).extract(
        layers=(LAYER.WG,)
    )
    padding = c << gf.components.bbox(
        waveguide.bbox, top=2, bottom=2, layer=LAYER.WAFER
    )
    c.add_ports(gf.components.straight(length=length).get_ports_list())

    filtered_layer_stack = LayerStack(
        layers={k: LAYER_STACK.layers[k] for k in ["clad", "box", "core"]}
    )

    epsilon = component_to_epsilon_pjz(
        component=c, layer_stack=filtered_layer_stack, zmin=-0.75
    )

    fig = plot_epsilon(
        epsilon=epsilon,
        x=0.0,
        y=None,
        z=None,
        xmin=0,
        ymin=0,
        zmin=0,
        nm_per_pixel=1000,
        figsize=(11, 4),
    )
    plt.savefig("test_func.png")
