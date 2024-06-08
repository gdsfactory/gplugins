from collections.abc import Callable
from functools import partial

import gdsfactory as gf
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

filter_savgol_filter = partial(savgol_filter, window_length=11, polyorder=3, axis=0)


def extract_path(
    component: gf.Component,
    layer: gf.typings.LayerSpec = (1, 0),
    plot: bool = False,
    filter_function: Callable = None,
    under_sampling: int = 1,
) -> gf.Path:
    """Extracts the centerline of a component from a GDS file.

    Args:
        component: GDS component.
        layer: GDS layer to extract the centerline from.
        plot: Plot the centerline.
        filter_function: optional Function to filter the centerline.
        under_sampling: under sampling factor.
    """
    points = component.get_polygons(by_spec=layer)[0]

    # Assume the points are ordered and the first half is the outer curve, the second half is the inner curve
    # This assumption might need to be adjusted based on your specific geometry
    mid_index = len(points) // 2
    outer_points = points[:mid_index]
    inner_points = points[mid_index:]
    inner_points = inner_points[::-1]

    inner_points = inner_points[::under_sampling]
    outer_points = outer_points[::under_sampling]

    centerline = np.mean([outer_points, inner_points], axis=0)

    if filter_function is not None:
        centerline = filter_function(centerline)

    p = gf.Path(centerline)
    if plot:
        plt.figure()
        plt.plot(outer_points[:, 0], outer_points[:, 1], "o", label="Outer Points")
        plt.plot(inner_points[:, 0], inner_points[:, 1], "o", label="Inner Points")
        plt.plot(centerline[:, 0], centerline[:, 1], "k--", label="Centerline")
        plt.legend()
        plt.title("Curve with Spline Interpolation for Inner and Outer Edges")
        plt.xlabel("X-coordinate")
        plt.ylabel("Y-coordinate")
        plt.grid(True)
        plt.show()
    return p


def get_min_radius_and_length(path: gf.Path) -> tuple[float, float]:
    """Get the minimum radius of curvature and the length of a path."""
    _, K = path.curvature()
    radius = 1 / K
    min_radius = np.min(np.abs(radius))
    return min_radius, path.length()


def plot_curvature(path: gf.Path, rmax: int | float = 200) -> None:
    """Plot the curvature of a path.

    Args:
        path: Path object.
        rmax: Maximum radius of curvature to plot.
    """
    s, K = path.curvature()
    radius = 1 / K
    valid_indices = (radius > -rmax) & (radius < rmax)
    radius2 = radius[valid_indices]
    s2 = s[valid_indices]

    plt.figure(figsize=(10, 5))
    plt.plot(s2, radius2, ".-")
    plt.xlabel("Position along curve (arc length)")
    plt.ylabel("Radius of curvature")
    plt.show()


def plot_radius(path: gf.Path, rmax: float = 200) -> plt.Figure:
    """Plot the radius of curvature of a path.

    Args:
        path: Path object.
        rmax: Maximum radius of curvature to plot.
    """
    s, K = path.curvature()
    radius = 1 / K
    valid_indices = (radius > -rmax) & (radius < rmax)
    radius2 = radius[valid_indices]
    s2 = s[valid_indices]

    fig, ax = plt.subplots(1, 1, figsize=(15, 5))
    ax.plot(s2, radius2, ".-")
    ax.set_xlabel("Position along curve (arc length)")
    ax.set_ylabel("Radius of curvature")
    ax.grid(True)
    return fig


def _demo_routes():
    ys_right = [0, 10, 20, 40, 50, 80]
    pitch = 127.0
    N = len(ys_right)
    ys_left = [(i - N / 2) * pitch for i in range(N)]
    layer = (1, 0)

    right_ports = [
        gf.Port(
            f"R_{i}", center=(0, ys_right[i]), width=0.5, orientation=180, layer=layer
        )
        for i in range(N)
    ]
    left_ports = [
        gf.Port(
            f"L_{i}", center=(-200, ys_left[i]), width=0.5, orientation=0, layer=layer
        )
        for i in range(N)
    ]

    # you can also mess up the port order and it will sort them by default
    left_ports.reverse()

    c = gf.Component(name="connect_bundle_v2")
    routes = gf.routing.route_bundle(
        left_ports,
        right_ports,
        sort_ports=True,
        start_straight_length=100,
        enforce_port_ordering=False,
    )
    for route in routes:
        c.add(route.references)
    return c


if __name__ == "__main__":
    # c0 = gf.components.bend_euler(npoints=20)
    # c0 = gf.components.bend_euler(cross_section="strip", with_arc_floorplan=True)
    # c0 = gf.components.bend_circular()
    # c0 = gf.components.bend_s(npoints=7)
    # c0 = gf.components.coupler()
    c0 = _demo_routes()

    gdspath = c0.write_gds()
    n = c0.get_netlist()
    c0.show()

    c = gf.import_gds(gdspath)
    # p = extract_path(c, plot=False, window_length=None, polyorder=None)
    p = extract_path(c, plot=True, under_sampling=5)
    min_radius, length = get_min_radius_and_length(p)
    print(f"Minimum radius of curvature: {min_radius:.2f}")
    print(f"Length: {length:.2f}")
    print(c0.info)
    plot_radius(p)
