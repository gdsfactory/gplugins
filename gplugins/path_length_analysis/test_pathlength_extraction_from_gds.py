from pathlib import Path
from typing import Callable
import pytest
import numpy as np
import gdsfactory as gf
import matplotlib.pyplot as plt
import tempfile

from gplugins.path_length_analysis.utils import (
    smoothed_savgol_filter,
)
from gplugins.path_length_analysis.path_length_analysis_from_gds import extract_paths


@pytest.fixture
def simple_straight():
    """Create a simple straight waveguide component."""
    return gf.components.straight(length=10, width=0.5)


@pytest.fixture
def simple_bend():
    """Create a simple bend component."""
    return gf.components.bend_circular(radius=5, width=0.5)


@pytest.fixture
def filter_function() -> Callable:
    """Create a simple filter function."""
    return smoothed_savgol_filter


def test_extract_paths_straight(simple_straight):
    """Test extracting paths from a straight waveguide."""
    paths, ev_paths = extract_paths(simple_straight)

    # Check that we got a single path
    assert len(paths) == 1

    # Check that the evanescent paths are None
    assert ev_paths is None

    # Check that the key has the right format
    key = list(paths.keys())[0]
    assert ";" in key

    # Check that the path has the right length
    path = paths[key]
    length = path.length()
    assert np.isclose(length, 10.0, rtol=0.05)  # Within 5% of expected length


def test_extract_paths_bend(simple_bend):
    """Test extracting paths from a bend."""
    paths, ev_paths = extract_paths(simple_bend)

    # Check that we got a single path
    assert len(paths) == 1

    # Check that the key has the right format
    key = list(paths.keys())[0]
    assert ";" in key

    # Check path length approximately matches the arc length of the bend
    path = paths[key]
    length = path.length()
    expected_length = np.pi * 5 / 2  # quarter circle with radius 5
    assert np.isclose(
        length, expected_length, rtol=0.2
    )  # Allow 20% tolerance for approximation


def test_extract_paths_with_filter(simple_bend, filter_function):
    """Test extracting paths with a filter function."""
    paths_without_filter, _ = extract_paths(simple_bend)
    paths_with_filter, _ = extract_paths(simple_bend, filter_function=filter_function)

    # Both should return a path
    assert len(paths_without_filter) == len(paths_with_filter) == 1

    key = list(paths_without_filter.keys())[0]

    # The filtered path should have fewer or equal points
    assert len(paths_with_filter[key].points) <= len(paths_without_filter[key].points)


def test_extract_paths_with_port_positions(simple_straight):
    """Test extracting paths with custom port positions."""
    # Define custom port positions
    port_positions = [(-5, 0), (5, 0)]
    paths, _ = extract_paths(simple_straight, port_positions=port_positions)

    # Should have a path between the custom ports
    assert len(paths) == 1

    # The key should contain "pl0" and "pl1" (the auto-generated port names)
    key = list(paths.keys())[0]
    assert "pl0" in key and "pl1" in key


def test_extract_paths_plot(simple_bend, tmp_path):
    """Test the plotting functionality of extract_paths."""
    # Generate plot file
    plt.ioff()  # Turn off interactive mode

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        plot_path = Path(temp_file.name)

    # Extract paths with plotting
    def save_plot_and_close(*args, **kwargs):
        plt.savefig(plot_path)
        plt.close("all")

    # Patch plt.show to save the figure instead
    original_show = plt.show
    plt.show = save_plot_and_close

    try:
        extract_paths(simple_bend, plot=True)
        # Check that the plot file was created
        assert plot_path.exists()
        assert plot_path.stat().st_size > 0
    finally:
        # Restore original plt.show
        plt.show = original_show
        # Clean up
        if plot_path.exists():
            plot_path.unlink()


def test_extract_paths_error_no_ports():
    """Test that extract_paths raises an error when component has no ports."""
    # Create a component without ports
    c = gf.Component("no_ports")
    c.add_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], layer=(1, 0))

    # Should raise ValueError
    with pytest.raises(ValueError) as excinfo:
        extract_paths(c)

    assert "does not have ports" in str(excinfo.value)


def test_extract_paths_under_sampling(simple_bend):
    """Test extracting paths with under_sampling."""
    paths1, _ = extract_paths(simple_bend, under_sampling=1)
    paths2, _ = extract_paths(simple_bend, under_sampling=2)

    key = list(paths1.keys())[0]

    # The path with under_sampling=2 should have fewer points
    assert len(paths2[key].points) <= len(paths1[key].points)
