import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from .utils import filter_points_by_std_distance, sort_points_nearest_neighbor


def test_filter_points_empty_array():
    """Test that an empty array is returned as-is."""
    points = np.array([])
    result = filter_points_by_std_distance(points)
    assert len(result) == 0
    assert isinstance(result, np.ndarray)


def test_filter_points_single_point():
    """Test that a single point is returned as-is."""
    points = np.array([[1.0, 2.0]])
    result = filter_points_by_std_distance(points)
    assert len(result) == 1
    assert np.array_equal(result, points)


def test_filter_points_two_points():
    """Test that two points are returned as-is (no filtering)."""
    points = np.array([[1.0, 2.0], [3.0, 4.0]])
    result = filter_points_by_std_distance(points)
    assert len(result) == 2
    assert np.array_equal(result, points)


def test_filter_points_no_outliers():
    """Test that points with consistent distances are all kept."""
    # Points with equal distances
    points = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]])
    result = filter_points_by_std_distance(points)
    assert len(result) == 5
    assert np.array_equal(result, points)


def test_filter_points_with_outlier():
    """Test that outlier points are correctly filtered out."""
    # Regular points with one outlier (large jump from point 3 to 4)
    points = np.array([[0, 0], [1, 0], [2, 0], [10, 0], [11, 0]])
    result = filter_points_by_std_distance(points)

    # The point at index 3 (value [10, 0]) should be removed
    expected = np.array([[0, 0], [1, 0], [2, 0], [11, 0]])
    assert len(result) == 4
    assert np.array_equal(result, expected)


def test_filter_points_preserve_endpoints():
    """Test that the first and last points (ports) are always preserved."""
    # First and last points should be preserved even if they would be outliers
    points = np.array([[-10, 0], [1, 0], [2, 0], [3, 0], [20, 0]])
    result = filter_points_by_std_distance(points)

    # First and last points should be preserved
    assert result[0][0] == -10
    assert result[-1][0] == 20


def test_filter_points_std_multiplier():
    """Test that the std_multiplier parameter affects filtering threshold."""
    # With a very large std_multiplier, no points should be filtered
    points = np.array([[0, 0], [1, 0], [2, 0], [10, 0], [11, 0]])
    result = filter_points_by_std_distance(points, std_multiplier=10.0)
    assert len(result) == 5
    assert np.array_equal(result, points)

    # With a very small std_multiplier, more points might be filtered
    result = filter_points_by_std_distance(points, std_multiplier=0.1)
    assert len(result) < 5  # Some points should be filtered out


@given(
    st.lists(
        st.tuples(
            st.floats(
                min_value=-100, max_value=100, allow_nan=False, allow_infinity=False
            ),
            st.floats(
                min_value=-100, max_value=100, allow_nan=False, allow_infinity=False
            ),
        ),
        min_size=3,
        max_size=20,
    ).map(np.array)
)
@settings(deadline=None)
def test_filter_points_random(points):
    """Test point filtering with random arrays."""
    result = filter_points_by_std_distance(points)

    # Check basic properties
    assert isinstance(result, np.ndarray)
    assert len(result) <= len(points)  # Result should have fewer or equal points
    assert len(result) >= 2  # At minimum, first and last points should be preserved

    # Verify that first and last points are preserved
    assert np.array_equal(result[0], points[0])
    assert np.array_equal(result[-1], points[-1])


def test_nearest_neighbor_sort_empty_array():
    """Test with empty array should return empty array."""
    points = np.array([], dtype=np.float64).reshape(0, 2)
    result = sort_points_nearest_neighbor(points)
    assert result.shape == (0, 2)
    assert np.array_equal(result, points)


def test_nearest_neighbor_sort_single_point():
    """Test with single point should return the same point."""
    points = np.array([[1.0, 2.0]])
    result = sort_points_nearest_neighbor(points)
    assert np.array_equal(result, points)


def test_nearest_neighbor_sort_two_points():
    """Test with two points should return both points in order."""
    points = np.array([[1.0, 2.0], [3.0, 4.0]])
    result = sort_points_nearest_neighbor(points)
    assert len(result) == 2
    assert np.array_equal(
        result[0], points[0]
    )  # First point should be same as start_idx (default 0)


def test_nearest_neighbor_sort_custom_start_idx():
    """Test using a custom start index."""
    points = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    start_idx = 1
    result = sort_points_nearest_neighbor(points, start_idx)
    assert np.array_equal(result[0], points[start_idx])


def test_nearest_neighbor_sort_result_contains_all_points():
    """Test that the result contains all original points."""
    points = np.array([[1.0, 2.0], [5.0, 6.0], [3.0, 4.0], [7.0, 8.0]])
    result = sort_points_nearest_neighbor(points)

    # Check that all original points are in the result
    assert len(result) == len(points)
    for point in points:
        assert any(np.array_equal(point, res_point) for res_point in result)


def test_nearest_neighbor_sort_nearest_neighbor_property():
    """Test that each point is actually next to its nearest neighbor."""
    points = np.array([[0.0, 0.0], [1.0, 1.0], [10.0, 10.0], [11.0, 11.0]])
    result = sort_points_nearest_neighbor(points)

    # Verify that points that are close together stay close in the result
    # For this specific example, we expect pairs to stay together
    distances = []
    for i in range(len(result) - 1):
        dist = np.sum((result[i] - result[i + 1]) ** 2)
        distances.append(dist)

    # The closest pairs should be next to each other
    assert min(distances) == pytest.approx(2.0)  # Distance between [0,0] and [1,1]


@given(
    arrays(np.float64, (5, 2), elements=st.floats(min_value=-100.0, max_value=100.0))
)
@settings(deadline=None)
def test_nearest_neighbor_sort_hypothesis_random_points(points):
    """Test with randomly generated points using Hypothesis."""
    result = sort_points_nearest_neighbor(points)

    # Check that result has same shape as input
    assert result.shape == points.shape

    # Check that all original points are in the result
    for point in points:
        found = False
        for res_point in result:
            if np.allclose(point, res_point, rtol=1e-10, atol=1e-10):
                found = True
                break
        assert found, f"Point {point} not found in result"


@given(st.integers(min_value=0, max_value=9))
@settings(deadline=None)
def test_nearest_neighbor_sort_hypothesis_start_idx(start_idx):
    """Test with random start indices using Hypothesis."""
    points = np.array([[i, i] for i in range(10)], dtype=np.float64)
    result = sort_points_nearest_neighbor(points, start_idx)

    # First point should be the one at start_idx
    assert np.array_equal(result[0], points[start_idx])


def test_nearest_neighbor_sort_same_distance_stability():
    """Test with points that have the same distance to ensure stable behavior."""
    # Points in a perfect square - each point has two equidistant neighbors
    points = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    result = sort_points_nearest_neighbor(points)

    # Just verify we get a result without errors
    assert len(result) == 4
