# type: ignore
from collections.abc import Callable
from functools import partial

import gdsfactory as gf
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

filter_savgol_filter = partial(savgol_filter, window_length=11, polyorder=3, axis=0)


def extract_paths(
    component: gf.Component,
    layer: gf.typings.LayerSpec = (1, 0),
    plot: bool = False,
    filter_function: Callable = None,
    under_sampling: int = 1,
) -> list[gf.Path]:
    """Extracts the centerlines of a component from a GDS file.

    Args:
        component: GDS component.
        layer: GDS layer to extract the centerline from.
        plot: Plot the centerline.
        filter_function: optional Function to filter the centerline.
        under_sampling: under sampling factor.

    Returns:
        List of gf.Path: Centerlines of the paths.
    """
    layer = gf.get_layer(layer)

    polygons_by_layer = component.get_polygons_points(merge=True)

    if layer not in polygons_by_layer:
        raise ValueError(f"Layer {layer} not found in component")

    points_list = polygons_by_layer[layer]

    paths = []
    for points in points_list:
        points = np.array(points)

        # Ensure the points are ordered and split them into outer and inner points
        if len(points) % 2 != 0:
            raise ValueError(
                "The number of points should be even to separate into outer and inner points"
            )

        mid_index = len(points) // 2
        outer_points = points[:mid_index]
        inner_points = points[mid_index:]
        inner_points = inner_points[::-1]

        # Ensure outer_points and inner_points have the same length
        min_length = min(len(outer_points), len(inner_points))
        outer_points = outer_points[:min_length]
        inner_points = inner_points[:min_length]

        # Remove the first and last points
        outer_points = outer_points[1:-1]
        inner_points = inner_points[1:-1]

        # Apply under-sampling
        outer_points = np.array(outer_points[::under_sampling])
        inner_points = np.array(inner_points[::under_sampling])

        # Calculate the centerline
        centerline = np.mean([outer_points, inner_points], axis=0)

        if filter_function is not None:
            centerline = filter_function(centerline)

        path = gf.Path(centerline)
        paths.append(path)

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

    return paths


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
    gf.routing.route_bundle(
        c,
        left_ports,
        right_ports,
        sort_ports=True,
        start_straight_length=100,
    )
    return c


if __name__ == "__main__":
    # c0 = gf.components.bend_euler(npoints=20)
    # c0 = gf.components.bend_euler(cross_section="strip", with_arc_floorplan=True)
    # c0 = gf.components.bend_circular()
    # c0 = gf.components.bend_s()
    c0 = gf.components.coupler()
    # c0 = _demo_routes()

    gdspath = c0.write_gds()
    n = c0.get_netlist()
    c0.show()

    c = gf.import_gds(gdspath)
    paths = extract_paths(c, plot=True, under_sampling=1)
    for path in paths:
        min_radius, length = get_min_radius_and_length(path)
        print(f"Minimum radius of curvature: {min_radius:.2f}")
        print(f"Length: {length:.2f}")
    # min_radius, length = get_min_radius_and_length(p)
    # print(f"Minimum radius of curvature: {min_radius:.2f}")
    # print(f"Length: {length:.2f}")
    # print(c0.info)
    # plot_radius(p)
    plt.show()
