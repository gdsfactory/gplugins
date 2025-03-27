import matplotlib.pyplot as plt
import numpy as np
from gdsfactory.technology import LayerStack
from gdsfactory.typings import Float2
from pjz._mode import mode

from gplugins.fdtdz.get_epsilon_fdtdz import create_physical_grid


def get_epsilon_port(
    port,
    epsilon,
    xmin,
    ymin,
    zmin=0,
    nm_per_pixel: int = 20,
    port_extent_xy: float = 1,
    port_offset: int = 0,
):
    """This function extracts a xz or yz slice of the epsilon distribution at the location of the port to mode solve.

    Parameters:
        port (Port): The port object from the component.
        epsilon (array): The epsilon distribution of the component.
        xmin (array): The x-coordinates of the epsilon distribution.
        ymin (array): The y-coordinates of the epsilon distribution.
        port_extent_xy (float): The size of the port in the xy-plane. \
                Used to isolate the mode to a given waveguide.
        port_offset (pixels): FIXME need to move the port towards the simulation a bit

    Returns:
        port_slice (array): The slice of the epsilon distribution at the location of the port.
    """
    xarray, yarray, zarray = create_physical_grid(
        xmin, ymin, zmin, epsilon, nm_per_pixel
    )

    x, y = port.center
    # z_range_indices = np.where((zcoords >= (z - port_size_z)) & (zcoords <= (z + port_size_z)))
    sgn = 1 if port.orientation in [180, 270] else -1
    x_index = (
        int(np.where(np.isclose(xarray, x, atol=nm_per_pixel * 1e-3 / 2))[0][0] / 2)
        + sgn * port_offset
    )  # factor of 2 from Yee grid?
    port_slice = (
        epsilon[:, x_index : x_index + 1, :, :]
        if sgn == 1
        else epsilon[:, x_index - 1 : x_index, :, :]
    )
    y_range_indices = np.where(
        (yarray <= (y - port_extent_xy)) & (yarray >= (y + port_extent_xy))
    )
    port_slice = port_slice.at[:, 0, y_range_indices, :].set(np.min(port_slice))
    return port_slice


def get_mode_port(
    omega,
    port,
    epsilon,
    xmin,
    ymin,
    zmin=0,
    nm_per_pixel: int = 20,
    port_extent_xy=1,
):
    # Physical grid
    xarray, yarray, _zarray = create_physical_grid(
        xmin, ymin, zmin, epsilon, nm_per_pixel
    )

    # Epsilon of the cross section
    epsilon_port = get_epsilon_port(
        port=port,
        epsilon=epsilon,
        xmin=xmin,
        ymin=ymin,
        zmin=zmin,
        nm_per_pixel=nm_per_pixel,
        port_extent_xy=port_extent_xy,
    )

    # Excitation profile
    _wavevector, excitation, _err, _iters = mode(
        epsilon=epsilon_port,
        omega=omega,
        num_modes=1,
    )

    # Position
    if port.orientation in [0, 180]:
        pos = int(np.where(np.isclose(xarray, port.x, atol=nm_per_pixel / 2))[0][0] / 2)
    else:
        pos = int(np.where(np.isclose(yarray, port.y, atol=nm_per_pixel / 2))[0][0] / 2)

    return excitation[:, :, :, :, 0], pos, epsilon_port


def plot_mode(
    port,
    excitation,
    epsilon_port=None,
    xmin: float = 0,
    ymin: float = 0,
    zmin: float = 0,
    nm_per_pixel: int = 1000,
    figsize: Float2 = (11, 4),
):
    """Plot mode profile.

    Args:
        epsilon: epsilon array.
        excitation: mode profile.
        xmin: (um) minimum x-coordinate (default to 0 for pixel index)
        ymin: (um) minimum y-coordinate (default to 0 for pixel index)
        zmin: (um) minimum z-coordinate (default to 0 for pixel index)
        nm_per_pixel: (int) resolution (default to 1000 for pixel index)
        figsize: figure size.
    """
    # Create physical grid
    xarray, yarray, zarray = create_physical_grid(
        xmin, ymin, zmin, epsilon_port, nm_per_pixel
    )

    # Plot
    fig = plt.figure(figsize=figsize)
    if port.orientation in [0, 180]:
        fig, axs = plt.subplots(1, 3, figsize=figsize)
        im0 = axs[0].imshow(
            epsilon_port[0, 0, :, :].transpose(),
            origin="lower",
            extent=[yarray[0], yarray[-1], zarray[0], zarray[-1]],
        )
        axs[0].set_title("Permittivity")
        axs[0].set_xlabel("y")
        axs[0].set_ylabel("z")
        fig.colorbar(im0, ax=axs[0])

        im1 = axs[1].imshow(
            np.abs(excitation[0, 0, :, :]).transpose(),
            origin="lower",
            extent=[yarray[0], yarray[-1], zarray[0], zarray[-1]],
        )
        axs[1].set_title("|Ey|")
        axs[1].set_xlabel("y")
        axs[1].set_ylabel("z")
        fig.colorbar(im1, ax=axs[1])

        im2 = axs[2].imshow(
            np.abs(excitation[1, 0, :, :]).transpose(),
            origin="lower",
            extent=[yarray[0], yarray[-1], zarray[0], zarray[-1]],
        )
        axs[2].set_title("|Ez|")
        axs[2].set_xlabel("y")
    else:
        fig, axs = plt.subplots(1, 3, figsize=figsize)
        im0 = axs[0].imshow(
            epsilon_port[0, :, 0, :].transpose(),
            origin="lower",
            extent=[xarray[0], xarray[-1], zarray[0], zarray[-1]],
        )
        axs[0].set_title("Permittivity")
        axs[0].set_xlabel("x")
        axs[0].set_ylabel("z")
        fig.colorbar(im0, ax=axs[0])

        im1 = axs[1].imshow(
            np.abs(excitation[0, :, 0, :]).transpose(),
            origin="lower",
            extent=[xarray[0], xarray[-1], zarray[0], zarray[-1]],
        )
        axs[1].set_title("|Ex|")
        axs[1].set_xlabel("x")
        axs[1].set_ylabel("z")
        fig.colorbar(im1, ax=axs[1])

        im2 = axs[2].imshow(
            np.abs(excitation[1, :, 0, :]).transpose(),
            origin="lower",
            extent=[xarray[0], xarray[-1], zarray[0], zarray[-1]],
        )
        axs[2].set_title("|Ez|")
        axs[2].set_xlabel("x")
    axs[2].set_ylabel("z")
    fig.colorbar(im2, ax=axs[2])
    plt.show()
    return fig


if __name__ == "__main__":
    import gdsfactory as gf
    from gdsfactory.generic_tech import LAYER, LAYER_STACK

    from gplugins.fdtdz.get_epsilon_fdtdz import component_to_epsilon_pjz

    length = 5

    c = gf.Component()
    waveguide = c << gf.components.straight(length=length, layer=LAYER.WG).extract(
        layers=(LAYER.WG,)
    )
    padding = c << gf.components.bbox(
        waveguide.bbox, top=2, bottom=2, layer=LAYER.WAFER
    )
    c.add_ports(gf.components.straight(length=length).ports)

    filtered_layer_stack = LayerStack(
        layers={k: LAYER_STACK.layers[k] for k in ["clad", "box", "core"]}
    )

    nm_per_pixel = 20
    zmin = -0.75

    epsilon = component_to_epsilon_pjz(
        component=c,
        layer_stack=filtered_layer_stack,
        zmin=zmin,
        nm_per_pixel=nm_per_pixel,
    )

    omega = 0.3
    excitation, pos, epsilon_port = get_mode_port(
        omega=omega,
        port=c.ports["o1"],
        epsilon=epsilon,
        xmin=c.xmin,
        ymin=c.ymin,
        nm_per_pixel=nm_per_pixel,
        port_extent_xy=1,
    )

    fig = plot_mode(
        port=c.ports["o1"],
        epsilon_port=epsilon_port,
        excitation=excitation,
        xmin=c.xmin,
        ymin=c.ymin,
        zmin=zmin,
        nm_per_pixel=1000,
        figsize=(11, 4),
    )
    plt.savefig("test_mode.png")
