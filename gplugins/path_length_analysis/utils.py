import numba
import numpy as np
import numpy.typing as npt
from scipy.interpolate import PchipInterpolator, PPoly
from scipy.interpolate._polyint import _Interpolator1D
from scipy.signal import savgol_filter


def resample_polygon_points_w_interpolator(
    points: npt.NDArray,
    n_samples_coeff: float | int = 1,
    interpolator: type[PPoly] | type[_Interpolator1D] = PchipInterpolator,
) -> npt.NDArray:
    """Resample polygon points equidistantly using PCHIP interpolation.

    Uses Piecewise Cubic Hermite Interpolating Polynomial because it preserves the shape (no overshoot).

    Args:
        points: (N, 2) array of points representing the polygon.
        n_samples_coeff: Coefficient to determine the number of samples. The number of samples will be
            ``int(max(len(points), 5) * n_samples_coeff)``.
        interpolator: SciPy :class:`Interpolator` to use for resampling. Defaults to PchipInterpolator.
    """
    # Parameterize the points by cumulative distance
    point_diffs = np.diff(points, axis=0)
    distances = np.linalg.norm(point_diffs, axis=1)
    cumulative_distance = np.insert(
        np.cumsum(distances), 0, 0
    )  # Insert 0 at the start for cumulative distance
    total_length = cumulative_distance[-1]
    # This is effectively arc-length parameterized
    pchip_x = interpolator(cumulative_distance, points[:, 0])
    pchip_y = interpolator(cumulative_distance, points[:, 1])

    # Interpolate the points with a higher resolution
    number_of_original_samples = max(len(points), 5)  # Ensure at least 5 samples
    arc_distance_samples = np.linspace(
        0,
        total_length,
        int(number_of_original_samples * n_samples_coeff),
        endpoint=True,
    )
    interpolated_points = np.column_stack(
        (pchip_x(arc_distance_samples), pchip_y(arc_distance_samples))
    )
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
