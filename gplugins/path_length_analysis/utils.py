import numpy as np


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
    used = set([0])
    for _ in range(1, N):
        last = ordered[-1]
        dists = np.linalg.norm(points - last, axis=1)
        dists[list(used)] = np.inf
        next_idx = np.argmin(dists)
        ordered.append(points[next_idx])
        used.add(next_idx)
    return np.array(ordered)
