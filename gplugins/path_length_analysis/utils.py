import numpy as np
import numpy.typing as npt


def interpolate_polygon_points(
    points: list[tuple[int | float, int | float]] | npt.NDArray,
    min_resolution: int | float = 100,
) -> npt.NDArray:
    """Interpolates polygon points to ensure a minimum distance between consecutive points.

    This function keeps all original points and adds interpolated points where necessary
    for minimum distance resolution. The returned points are not guaranteed to be equidistant.

    Args:
        points: (N, 2) array of polygon points.
        min_resolution: minimum allowed distance between consecutive points.

    Returns:
        (M, 2) array of interpolated points, where M >= N.
    """
    # Ensure points is a numpy array
    points = np.asarray(points)

    # Compute distances between consecutive points
    diffs = np.diff(points, axis=0)
    dists = np.linalg.norm(diffs, axis=1)

    # For closed polygons, add the segment from last to first
    is_closed = np.allclose(points[0], points[-1])
    if is_closed:
        diffs = np.vstack([diffs, points[0] - points[-1]])
        dists = np.append(dists, np.linalg.norm(points[0] - points[-1]))

    new_points = [points[0]]
    for i in range(len(dists)):
        n_segments = max(int(np.ceil(dists[i] / min_resolution)), 1)
        for j in range(1, n_segments + 1):
            interp_point = points[i] + (diffs[i] * j / n_segments)
            # Only add interpolated points if not exactly at the next original point
            if n_segments > 1 and j < n_segments:
                new_points.append(interp_point)
        # Always add the next original point
        next_idx = (i + 1) % len(points) if is_closed else i + 1
        if next_idx < len(points):
            new_points.append(points[next_idx])
    # For open polygons, ensure last point is included only once
    if not is_closed and not np.allclose(new_points[-1], points[-1]):
        new_points.append(points[-1])
    # Remove possible duplicates (within tolerance)
    new_points = np.array(new_points)
    _, unique_indices = np.unique(
        np.round(new_points, decimals=8), axis=0, return_index=True
    )
    new_points = new_points[np.sort(unique_indices)]
    return new_points


def resample_polyline(
    points: list[tuple[int | float, int | float]],
    resolution: int | float,
    min_points: int = 5,
) -> np.ndarray:
    """Resample a polyline to have a specific resolution for points.

    The resampled polyline will have points spaced as evenly as possible along the polyline,
    but will not necessarily include the original points.

    Args:
        points (List[Tuple[float, float]]): List of (x, y) coordinates representing the polyline.
        resolution (float): Desired distance between consecutive points in the resampled polyline.
        min_points (int): Minimum number of points in the resampled polyline in case the resolution is too large.

    Returns:
        np.ndarray: Array of shape (num_points, 2) with resampled (x, y) coordinates.
    """
    points = np.asarray(points)
    # Calculate cumulative distance along the polyline
    deltas = np.diff(points, axis=0)
    seg_lengths = np.linalg.norm(deltas, axis=1)
    cumulative = np.insert(np.cumsum(seg_lengths), 0, 0)
    total_length = cumulative[-1]
    if total_length == 0:
        return points[[0]].copy()
    num_points = max(int(np.floor(total_length / resolution)) + 1, min_points)
    even_distances = np.linspace(0, total_length, num_points)
    resampled = np.empty((num_points, 2))
    for i, d in enumerate(even_distances):
        idx = np.searchsorted(cumulative, d) - 1
        idx = np.clip(idx, 0, len(points) - 2)
        seg_len = seg_lengths[idx]
        t = (d - cumulative[idx]) / seg_len if seg_len > 0 else 0.0
        resampled[i] = (1 - t) * points[idx] + t * points[idx + 1]
    return resampled


def sort_points_nearest_neighbor(points: np.ndarray) -> np.ndarray:
    """Sorts points so that each point is next to its Euclidean nearest neighbors.

    Args:
        points: (N, 2) array of unordered points.

    Returns:
        (N, 2) array of ordered points.
    """
    if len(points) <= 1:
        return points.copy()
    points = points.copy()
    N = len(points)
    ordered = [points[0]]
    used = set([0])  # noqa: C405
    for _ in range(1, N):
        last = ordered[-1]
        dists = np.linalg.norm(points - last, axis=1)
        dists[list(used)] = np.inf
        next_idx = np.argmin(dists)
        ordered.append(points[next_idx])
        used.add(next_idx)
    return np.array(ordered)
