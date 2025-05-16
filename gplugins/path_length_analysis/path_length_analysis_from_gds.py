# type: ignore
from collections.abc import Callable
from functools import partial

import gdsfactory as gf
import kfactory as kf
import matplotlib.pyplot as plt
import numpy as np
import shapely as sh
import shapely.ops as ops
from gdsfactory import logger
from klayout.db import DPoint, Polygon
from scipy.signal import savgol_filter
from scipy.spatial import distance

filter_savgol_filter = partial(savgol_filter, window_length=11, polyorder=3, axis=0)
fix_values = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8]


def _check_midpoint_found(inner_points, outer_points, port_list) -> bool:
    """Simple routine to check if the inner and outer points have been correctly found.

    This is necessary because sometimes the ordering of the points is not right
    and in that case the inner and outer points are mixed up.
    """
    coincident_points = False
    if (
        outer_points[0, 0] == inner_points[0, 0]
        and outer_points[-1, 0] == inner_points[-1, 0]
    ):
        coincident_points = True
    elif (
        outer_points[0, 0] == inner_points[0, 0]
        and outer_points[-1, 1] == inner_points[-1, 1]
    ):
        coincident_points = True
    elif (
        outer_points[0, 1] == inner_points[0, 1]
        and outer_points[-1, 1] == inner_points[-1, 1]
    ):
        coincident_points = True
    elif (
        outer_points[0, 1] == inner_points[0, 1]
        and outer_points[-1, 0] == inner_points[-1, 0]
    ):
        coincident_points = True

    if coincident_points:
        # Make sure initial point is close to one of the ports (1 um away)
        for port in port_list:
            if np.sqrt(np.sum(np.power(outer_points[0, :] - port.center, 2))) < 1e3:
                return True
        return False
    else:
        return False


def centerline_single_poly_2_ports(poly, under_sampling, port_list) -> np.ndarray:
    """Returns the centerline for a single polygon that has 2 ports.

    We assume that the ports are at min_x and max_x respectively.
    """
    # Simplify points that are too close to each other
    r = gf.kdb.Region(poly)
    r = r.smoothed(0.05, True)

    # Get polygon points from klayout DPolygon
    xs = [pt.x for pt in r[0].each_point_hull()]
    ys = [pt.y for pt in r[0].each_point_hull()]
    # For some reason there always seems to be a roll by 1 needed
    # to be closer to the right partition between inner and outer shell
    points = np.column_stack((xs, ys))
    points = np.roll(points, -1, axis=0)

    # Initially, assume the points are ordered and the first half is the outer curve,
    # the second half is the inner curve
    mid_index = len(points) // 2
    roll_val = 1
    mid_point_found = False

    outer_points = points[:mid_index, :]
    inner_points = points[mid_index:, :]
    inner_points = inner_points[::-1, :]

    # Check our assumption indeed makes it so that the inner and outer points
    # are correctly recognized
    mid_point_found = _check_midpoint_found(inner_points, outer_points, port_list)

    # ==== This is for debugging, keep until this is stable ====
    # logger.debug(len(outer_points))
    # logger.debug(len(inner_points))
    # input()

    # Relatively simple check to make sure that the first half is the outer curve and the
    # second half is the inner curve
    # plt.figure()
    # plt.plot(points[:, 0], points[:, 1], "x")
    # plt.plot(inner_points[:, 0], inner_points[:, 1], "x", label="inner points")
    # plt.plot(outer_points[:, 0], outer_points[:, 1], "x", label="outer points")
    # plt.show()
    # =================

    # If the midpoint was not found, do some complicated tests to try to find the
    # actual midpoint.
    n_rolls = 0
    n_fixes_tried = 0

    while not mid_point_found:
        points = np.roll(points, roll_val, axis=0)
        n_rolls += 1
        outer_points = points[: (mid_index + fix_values[n_fixes_tried]), :]
        inner_points = points[(mid_index + fix_values[n_fixes_tried]) :, :]
        inner_points = inner_points[::-1, :]

        # ==== This is for debugging, keep until this is stable ====
        # plt.figure()
        # plt.plot(points[:, 0],points[:, 1], 'x')
        # plt.plot(inner_points[:, 0],inner_points[:, 1], 'x', label="inner points")
        # plt.plot(outer_points[:, 0],outer_points[:, 1], 'x', label="outer points")
        # plt.show()

        # print(outer_points[0,:])
        # print(inner_points[0,:])
        # print(outer_points[-1,:])
        # print(inner_points[-1,:])
        # input()
        # =================

        mid_point_found = _check_midpoint_found(inner_points, outer_points, port_list)

        if n_rolls > points.shape[0] and n_fixes_tried < 10 and not mid_point_found:
            # Sometimes it is enough if we make the inner point be +-n elements longer
            n_fixes_tried += 1
            # logger.debug(f"Trying fix {n_fixes_tried}")
            n_rolls = 0

            outer_points = points[: (mid_index + fix_values[n_fixes_tried]), :]
            inner_points = points[(mid_index + fix_values[n_fixes_tried]) :, :]
            inner_points = inner_points[::-1]

            # ==== This is for debugging, keep until this is stable ====
            # plt.figure()
            # plt.plot(points[:, 0], points[:, 1], "x")
            # plt.plot(inner_points[:, 0], inner_points[:, 1], "x", label="inner points")
            # plt.plot(outer_points[:, 0], outer_points[:, 1], "x", label="outer points")
            # plt.show()
            # =================

            mid_point_found = _check_midpoint_found(
                inner_points, outer_points, port_list
            )

        elif n_rolls > points.shape[0] and not mid_point_found:
            # We could not find the right inner and outer points
            logger.error(f"We could not find the center line correctly for {port_list}")
            mid_point_found = True
            outer_points = points[:mid_index]
            inner_points = points[mid_index:]
            inner_points = inner_points[::-1]

    # Order points
    inds = np.argsort(inner_points[:, 0])
    inner_points = inner_points[inds, :]
    inds = np.argsort(outer_points[:, 0])
    outer_points = outer_points[inds, :]

    # # (OLD, keep juts in case for now) Apply undersampling if necessary
    # inner_points = np.append(
    #     inner_points[::under_sampling], np.array([inner_points[-1]]), axis=0
    # )
    # outer_points = np.append(
    #     outer_points[::under_sampling], np.array([outer_points[-1]]), axis=0
    # )

    # Apply undersampling if necessary, and add the last point if it is not there
    last_inner_pt = inner_points[-1]
    inner_points = inner_points[::under_sampling]
    if last_inner_pt not in inner_points:
        inner_points = np.append(inner_points, np.array([last_inner_pt]), axis=0)

    last_outer_pt = outer_points[-1]
    outer_points = outer_points[::under_sampling]
    if last_outer_pt not in outer_points:
        outer_points = np.append(outer_points, np.array([last_outer_pt]), axis=0)

    # There is a chance that the length of inner and outer is different
    # Interpolate if that's the case
    if inner_points.shape[0] != outer_points.shape[0]:
        # logger.debug('interpolating')
        if inner_points.shape[0] > outer_points.shape[0]:
            # More points in inner
            outer_pts_x = outer_points[:, 0]

            # add as many random points as necessary
            extra_pts = inner_points.shape[0] - outer_points.shape[0]
            extra_x = np.random.uniform(outer_pts_x[0], outer_pts_x[-1], size=extra_pts)

            interp_xs = np.hstack((outer_pts_x, extra_x))
            interp_xs = np.sort(interp_xs)
            inds = np.argsort(outer_pts_x)

            interp_outer_y = np.interp(
                interp_xs, outer_points[inds, 0], outer_points[inds, 1]
            )
            outer_points = np.hstack(
                (np.reshape(interp_xs, (-1, 1)), np.reshape(interp_outer_y, (-1, 1)))
            )

        else:
            # More points in outer
            inner_pts_x = inner_points[:, 0]

            # add as many random points as necessary
            extra_pts = outer_points.shape[0] - inner_points.shape[0]
            extra_x = np.random.uniform(inner_pts_x[0], inner_pts_x[-1], size=extra_pts)

            interp_xs = np.hstack((inner_pts_x, extra_x))
            interp_xs = np.sort(interp_xs)
            inds = np.argsort(inner_pts_x)

            interp_inner_y = np.interp(
                interp_xs, inner_points[inds, 0], inner_points[inds, 1]
            )
            inner_points = np.hstack(
                (np.reshape(interp_xs, (-1, 1)), np.reshape(interp_inner_y, (-1, 1)))
            )

    centerline = np.mean([outer_points, inner_points], axis=0) * 1e-3

    # ==== This is for debugging, keep until this is stable ====
    # plt.figure()
    # plt.plot(points[:, 0],points[:, 1], 'x')
    # plt.plot(inner_points[:, 0],inner_points[:, 1], 'x', label="inner points")
    # plt.plot(outer_points[:, 0],outer_points[:, 1], 'x', label="outer points")
    # plt.plot(centerline[:, 0], centerline[:, 1], "k--", label="Centerline")
    # plt.xlabel("X-coordinate")
    # plt.ylabel("Y-coordinate")
    # plt.grid(True)
    # plt.legend()
    # plt.show()
    # =================

    return centerline


def extract_paths(
    component: gf.Component | kf.DInstance,
    layer: tuple[int, int] = (1, 0),
    plot: bool = False,
    filter_function: Callable | None = None,
    under_sampling: int = 1,
    evanescent_coupling: bool = False,
    consider_ports: list[str] | None = None,
    port_positions: list[tuple[float, float]] | None = None,
) -> dict:
    """Extracts the centerline of a component or instance from a GDS file.

    Requires the components to have ports, and it returns a dictionary
    with {port1},{port2} as the key and a gf.Path as the value.

    Args:
        component: gdsfactory component or instance to extract from.
        layer: layer to extract the centerline from.
        plot: If True, we plot the extracted paths.
        filter_function: optional Function to filter the centerline.
        under_sampling: under sampling factor of the polygon points.
        evanescent_coupling: if True, it assumes that there is evanescent coupling
            between ports not physically connected.
        consider_ports: if specified, it only considers paths between the specified port names
            and ignores all other existing ports. Note - this will not work in cases where the
            specified ports are only coupled evanescently. In this case, it is better to
            run the function with consider_ports = None and then filter the returned dict.
        port_positions: if specified, we ignore the existing ports on the component and instead
            create new ports at the specified positions. Overrides the parameter consider_ports.
            Note - this will not work in cases where the specified port positions are only coupled
            evanescently. A workaround for this limitation is to specify one additional port that is
            physically connected to the ports of interest, for each port of interest.
    """
    ev_paths = None

    if port_positions is not None:
        # Create ports at the specified positions
        consider_ports = []
        new_component = component.copy()
        for i, pos in enumerate(port_positions):
            pname = f"pl{i}"
            # The port width and orientation are irrelevant but need to be specified
            new_component.add_port(
                name=pname, center=pos, layer=layer, width=0.3, orientation=0
            )
            consider_ports.append(pname)

        component = new_component

    if consider_ports is not None:
        # Only ports in the specified list
        ports_list = [component.ports[port_name] for port_name in consider_ports]
    else:
        # All ports
        ports_list = component.ports

    n_ports = len(ports_list)
    if n_ports == 0:
        raise ValueError(
            "The specified component does not have ports - path length extraction will not work."
        )

    # Perform over-under to merge all physically connected polygons
    polygons = gf.functions.get_polygons(component, layers=(layer,), by="tuple")[layer]
    r = gf.kdb.Region(polygons)
    r = r.sized(0.05)
    r = r.sized(-0.05)
    simplified_component = gf.Component()
    simplified_component.add_polygon(r, layer=layer)

    polys = gf.functions.get_polygons(simplified_component, merge=True, by="tuple")[
        layer
    ]

    paths: dict[str, gf.Path] = dict()

    if len(polys) == 1:
        # Single polygon - we need to act differently depending on the number
        # of ports
        poly = polys

        if n_ports == 2:
            # This is the simplest case - a straight or a bend

            if poly[0].is_box():  # only 4 points, no undersampling
                centerline = centerline_single_poly_2_ports(poly, 1, ports_list)
            else:
                centerline = centerline_single_poly_2_ports(
                    poly, under_sampling, ports_list
                )
            if filter_function is not None:
                centerline = filter_function(centerline)
            p = gf.Path(centerline)
            paths[f"{ports_list[0].name};{ports_list[1].name}"] = p

        else:
            # Single polygon and more than 2 ports - MMI

            # What we will do: assume that the component is symmetric along
            # the x axis, divide the single polygon into two, and use the
            # logic for MultiPolygons

            # Unfortunately klayout does not have an easy way to split, so
            # we will use shapely to do it and then go back to klayout

            y_val = (simplified_component.ymax + simplified_component.ymin) / 2
            slice = sh.LineString(
                [
                    [simplified_component.xmin, y_val],
                    [simplified_component.xmax, y_val],
                ]
            )

            pts = [(pt.x * 1e-3, pt.y * 1e-3) for pt in poly[0].each_point_hull()]
            poly = sh.Polygon(pts)
            split_polys = ops.split(sh.Polygon(poly), slice)

            polys = []
            # Convert the resulting polygons into klayout regions
            for poly in split_polys.geoms:
                pts = []
                for pt in poly.exterior.coords:
                    pts.append(DPoint(pt[0] * 1e3, pt[1] * 1e3))
                polys.append(Polygon(pts))

            # Here polys is a list of length 2, so the code that follows will be executed

    if len(polys) > 1:
        # Multiple polygons - iterate through each one

        all_ports: list[gf.Port] = []

        for poly in polys:
            # Need to check how many ports does that specific polygon contain

            ports_poly = [
                port
                for port in ports_list
                if poly.sized(0.005).inside(
                    DPoint(port.center[0], port.center[1]).to_itype(component.kcl.dbu)
                )
            ]
            if len(ports_poly) == 2:
                # Each polygon has two ports - simple case
                centerline = centerline_single_poly_2_ports(
                    poly, under_sampling, ports_poly
                )
                if filter_function is not None:
                    centerline = filter_function(centerline)
                p = gf.Path(centerline)
                paths[f"{ports_poly[0].name};{ports_poly[1].name}"] = p

            elif len(ports_poly) == 0:
                # No ports in the polygon - continue
                continue

            else:
                # More than 2 ports and multiple polygons
                # We will assume that means that we are trying to get path
                # length of a component that can be broken down into
                # subcomponents
                raise ValueError(
                    "The component for path length matching "
                    "has multiple polygons and each polygon has "
                    "more than 2 ports. This looks like a component "
                    "that can be broken into subcomponents"
                )
            all_ports.extend(ports_poly)

        # Deal with evanescent coupling
        if evanescent_coupling:
            ev_paths = dict()

            for port1p in all_ports:
                port1 = port1p.name
                for port2p in all_ports:
                    port2 = port2p.name
                    if port1 == port2:
                        # Same port - skip
                        continue
                    if (
                        f"{port1};{port2}" in paths
                        or f"{port2};{port1}" in paths
                        or f"{port1};{port2}" in ev_paths
                        or f"{port2};{port1}" in ev_paths
                    ):
                        # The path has already been computed
                        continue
                    else:
                        # We need to calculate the (evanescent) path

                        # First gather a connected path that contains each port
                        for key in paths.keys():
                            if port1 in key:
                                path1 = paths[key]
                                key1 = key
                            if port2 in key:
                                path2 = paths[key]
                                key2 = key

                        # Now calculate the closest point between the two paths
                        # We do so by iterating over the x points of path1
                        # and finding the point closest in x of path2, then calculating distance
                        distances = distance.cdist(path1.points, path2.points)
                        # ind = np.unravel_index(np.argmin(distances), distances.shape)

                        # What do we do if there are multiple points with the same minimum distance?
                        # Choose the one that's closer to the center of the component
                        ind_min_dist_pts = np.where(distances == distances.min())
                        min_dist_points1 = path1.points[
                            np.unique(ind_min_dist_pts[0]), :
                        ]
                        min_dist_points2 = path2.points[
                            np.unique(ind_min_dist_pts[1]), :
                        ]

                        # Find the point closest to the center of the polygon
                        center = np.array(
                            [
                                simplified_component.dcenter.x,
                                simplified_component.dcenter.y,
                            ]
                        )

                        distances2 = distance.cdist(
                            center.reshape(1, -1), min_dist_points1
                        )
                        ind = np.argmin(distances2)

                        # Now that we have the closest point we just start by one path and
                        # transition to the other at the closest point
                        ind_1 = np.where(
                            np.all(path1.points == min_dist_points1[ind, :], axis=1)
                        )[0][0]
                        ind_2 = np.where(
                            np.all(path2.points == min_dist_points2[ind, :], axis=1)
                        )[0][0]

                        # We can decide which part of the path we choose depending on the position
                        # of the port in the key
                        if f"{port1};" in key1:
                            part1 = path1.points[:ind_1, :]
                        else:
                            part1 = path1.points[ind_1:, :]
                        inds = np.argsort(part1[:, 0])
                        part1 = part1[inds, :]

                        if f"{port2};" in key2:
                            part2 = path2.points[:ind_2, :]
                        else:
                            part2 = path2.points[ind_2:, :]

                        # There is a chance that we need to flip the parts
                        d1 = np.sum(np.power(part1[-1, :] - part2[0, :], 2))
                        d2 = np.sum(np.power(part1[-1, :] - part2[-1, :], 2))
                        d3 = np.sum(np.power(part1[0, :] - part2[-1, :], 2))
                        d4 = np.sum(np.power(part1[0, :] - part2[0, :], 2))

                        if d1 == np.min([d1, d2, d3, d4]):
                            evan_path = np.vstack((part1, part2))
                        elif d2 == np.min([d1, d2, d3, d4]):
                            evan_path = np.vstack((part1, np.flipud(part2)))
                        elif d3 == np.min([d1, d2, d3, d4]):
                            evan_path = np.vstack((np.flipud(part1), np.flipud(part2)))
                        else:
                            evan_path = np.vstack((np.flipud(part1), part2))

                        # ==== This is for debugging, keep it until this is table ===
                        # plt.figure()
                        # plt.plot(path1.points[:, 0], path1.points[:, 1], "--")
                        # plt.plot(path2.points[:, 0], path2.points[:, 1], "--")
                        # plt.plot(evan_path[:, 0], evan_path[:, 1], "-o")
                        # plt.show()
                        # ========

                        if filter_function is not None:
                            evan_path = filter_function(evan_path)
                        ev_paths[f"{port1};{port2}"] = gf.Path(evan_path)

    if plot:
        points = gf.functions.get_polygons(
            simplified_component, merge=True, by="tuple"
        )[layer]
        plt.figure()
        for chunk in points:
            xs = [pt.x * 1e-3 for pt in chunk.each_point_hull()]
            ys = [pt.y * 1e-3 for pt in chunk.each_point_hull()]
            plt.plot(xs, ys, "x")
        for ports, centerline in paths.items():
            plt.plot(
                centerline.points[:, 0],
                centerline.points[:, 1],
                "--",
                label=ports,
            )
        plt.legend()
        plt.title("Direct paths")
        plt.xlabel("X-coordinate")
        plt.ylabel("Y-coordinate")
        plt.grid(True)

        if ev_paths is not None:
            plt.figure()
            for chunk in points:
                xs = [pt.x * 1e-3 for pt in chunk.each_point_hull()]
                ys = [pt.y * 1e-3 for pt in chunk.each_point_hull()]
                plt.plot(xs, ys, "x")
            for ports, centerline in ev_paths.items():
                plt.plot(
                    centerline.points[:, 0],
                    centerline.points[:, 1],
                    "--",
                    label=ports,
                )
            plt.legend()
            plt.title("Evanescent paths")
            plt.xlabel("X-coordinate")
            plt.ylabel("Y-coordinate")
            plt.grid(True)

        plt.show()

    return paths, ev_paths


def get_min_radius_and_length_path_dict(path_dict: dict) -> dict:
    """Get the minimum radius of curvature and the length of all paths in the dictionary."""
    curv_and_len_dict = {}
    for key, val in path_dict.items():
        curv_and_len_dict[key] = get_min_radius_and_length(val)

    return curv_and_len_dict


def get_min_radius_and_length(path: gf.Path) -> tuple[float, float]:
    """Get the minimum radius of curvature and the length of a path."""
    _, K = path.curvature()
    radius = 1 / K
    min_radius = np.nanmin(np.abs(radius))
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
    c.add_ports(right_ports)
    c.add_ports(left_ports)

    return c


if __name__ == "__main__":
    # c0 = gf.components.bend_euler(npoints=20)
    # c0 = gf.components.bend_euler(cross_section="xs_sc", with_arc_floorplan=True)
    c0 = gf.components.bend_circular()
    # c0 = gf.components.bend_s(npoints=50)
    # c0 = gf.components.mmi2x2()
    # c0 = gf.components.coupler()
    ev_coupling = True
    # c0 = _demo_routes()
    # ev_coupling = False

    # gdspath = c0.write_gds()
    # n = c0.get_netlist()
    c0.show()

    # c = gf.import_gds(gdspath)
    # p = extract_path(c, plot=False, window_length=None, polyorder=None)
    path_dict, ev_path_dict = extract_paths(
        c0,
        plot=True,
        under_sampling=1,
        evanescent_coupling=ev_coupling,
        consider_ports=["o1", "o2"],
        # port_positions=[(-10.0, -1.6), (30.0, -1.6)],
    )
    r_and_l_dict = get_min_radius_and_length_path_dict(path_dict)
    for ports, (min_radius, length) in r_and_l_dict.items():
        print(f"Ports: {ports}")
        print(f"Minimum radius of curvature: {min_radius:.2f}")
        print(f"Length: {length:.2f}")
        plot_curvature(path_dict[ports])
    print(c0.info)
    plt.show()
