import numba
import numpy as np
import numpy.typing as npt
from scipy.interpolate import PchipInterpolator, PPoly
from scipy.interpolate._polyint import _Interpolator1D
from scipy.signal import savgol_filter


def resample_polygon_points_w_interpolator(
    points: np.ndarray,
    n_samples_coeff: float | int = 1,
    interpolator: type[PPoly] | type[_Interpolator1D] = PchipInterpolator,
) -> np.ndarray:
    """Resample polygon points equidistantly using PCHIP interpolation.

    Uses Piecewise Cubic Hermite Interpolating Polynomial because it preserves the shape (no overshoot).

    Args:
        points: (N, 2) array of points representing the polygon.
        n_samples_coeff: Coefficient to determine the number of samples. The number of samples will be
            ``int(max(len(points), 5) * n_samples_coeff)``.
        interpolator: SciPy :class:`Interpolator` to use for resampling. Defaults to PchipInterpolator.
    """
    # Convert to numpy array if not already
    points_array = np.asarray(points, dtype=np.float64)

    # Parameterize the points by cumulative distance
    point_diffs = np.diff(points, axis=0)
    distances = np.linalg.norm(point_diffs, axis=1)
    cumulative_distance = np.zeros(len(points_array))
    np.cumsum(distances, out=cumulative_distance[1:])
    total_length = cumulative_distance[-1]

    # This is effectively arc-length parameterized
    pchip_x = interpolator(cumulative_distance, points_array[:, 0])
    pchip_y = interpolator(cumulative_distance, points_array[:, 1])

    # Interpolate the points with a higher resolution
    number_of_original_samples = max(len(points_array), 5)  # Ensure at least 5 samples
    num_samples = int(number_of_original_samples * n_samples_coeff)

    # Pre-allocate result array
    interpolated_points = np.empty((num_samples, 2), dtype=np.float64)

    # Generate sample points
    arc_distance_samples = np.linspace(0, total_length, num_samples, endpoint=True)

    interpolated_points[:, 0] = pchip_x(arc_distance_samples)
    interpolated_points[:, 1] = pchip_y(arc_distance_samples)

    return interpolated_points


def smoothed_savgol_filter(
    data: npt.NDArray, window_length: int = 11, polyorder: int = 3
) -> np.ndarray:
    """Simple wrapper on SciPy Savitzky-Golay filter that handles data not long enough.

    Also ensures that the end points are not affected by the filter.
    """
    # Ensure window_length is odd
    if window_length % 2 == 0:
        window_length += 1

    # Adjust window_length if it is larger than the data size
    data_length = data.shape[0]
    if data_length < window_length:
        # Make window_length smaller than data_length and ensure it is odd
        window_length = min(data_length - (data_length % 2 == 0), 5)

        # Ensure window_length is at least 3
        window_length = max(window_length, 3)

        # Adjust polyorder if needed (must be less than window_length)
        polyorder = min(polyorder, window_length - 2)

    # Apply the filter
    filtered_data = savgol_filter(
        data, window_length=window_length, polyorder=polyorder, axis=0, mode="nearest"
    )

    # Preserve the original end points to ensure they are not affected by the filter
    # filtered_data = np.insert(filtered_data, 0, data[0], axis=0)
    # filtered_data = np.append(filtered_data, [data[-1]], axis=0)
    # filtered_data[0] = data[0]
    # filtered_data[-1] = data[-1]

    return filtered_data


@numba.njit(parallel=True)
def sort_points_nearest_neighbor(points: np.ndarray, start_idx: int = 0) -> np.ndarray:
    """Sorts points so that each point is next to its Euclidean nearest neighbors.

    Args:
        points: (N, 2) array of unordered points.
        start_idx: Index of the starting point.

    Returns:
        (N, 2) array of ordered points.
    """
    n = len(points)
    if n <= 1:
        return points.copy()

    # Initialize result array and mask for remaining points
    result = np.zeros_like(points)
    remaining = np.ones(n, dtype=np.bool_)

    # Start with the leftmost point (smallest x-coordinate)
    result[0] = points[start_idx]
    remaining[start_idx] = False

    # Iteratively find the nearest neighbor
    for i in range(1, n):
        last_point = result[i - 1]
        remaining_points = points[remaining]

        if len(remaining_points) == 0:
            break

        # Calculate distances to the last point in parallel
        distances = np.zeros(len(remaining_points))
        for j in numba.prange(len(remaining_points)):
            distances[j] = np.sum((remaining_points[j] - last_point) ** 2)

        # Find the index of the closest point in the remaining set
        min_idx = np.argmin(distances)

        # Convert from index in remaining_points to index in original points
        original_indices = np.where(remaining)[0]
        next_idx = original_indices[min_idx]

        # Add to result and mark as used
        result[i] = points[next_idx]
        remaining[next_idx] = False

    return result


@numba.njit(parallel=True)
def _filter_points_by_std_distance(
    points: np.ndarray, std_multiplier: float | int = 1
) -> np.ndarray:
    """Inner implementation of filter_points_by_std_distance for Numba JIT compilation."""
    # Calculate distances between consecutive points
    point_diffs = points[1:] - points[:-1]
    point_distances = np.sqrt(np.sum(np.power(point_diffs, 2), axis=1))
    # point_distances = np.linalg.norm(point_diffs, axis=1)

    # Calculate mean and standard deviation of distances
    mean_distance = np.mean(point_distances)
    std_distance = np.std(point_distances)

    # Identify outliers - points where distance to next point is > mean + std_multiplier*std
    threshold = mean_distance + std_multiplier * std_distance

    # Create a mask of points to keep (all True initially)
    keep_mask = np.ones(len(points), dtype=np.bool_)

    # Mark outlier points for removal - skip first and last points
    for i in range(len(point_distances)):
        if point_distances[i] > threshold and 0 < i + 1 < len(points) - 1:
            keep_mask[i + 1] = False

    # Apply the mask to filter the points
    return points[keep_mask]


def filter_points_by_std_distance(
    points: np.ndarray, std_multiplier: float | int = 1
) -> np.ndarray:
    """Filters out points that are outliers based on the distance to their neighbors.

    Warning:
        Assumes that the points are ordered in a way that makes sense (e.g., sorted or nearest neighbor).

    Args:
        points: (N, 2) array of points representing the path.
        std_multiplier: Multiplier for the standard deviation to determine outlier threshold.

    Returns:
        (M, 2) array of filtered points, where M ≤ N.
    """
    # Early return for small arrays
    if len(points) <= 2:
        return points

    return _filter_points_by_std_distance(points, std_multiplier=std_multiplier)
