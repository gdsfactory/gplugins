"""Tests for the COMSOL result helpers shared by notebooks and scripts."""

import json
from pathlib import Path

import pytest

from gplugins.comsol.results import (
    explain_missing_results,
    exported_frequency_ghz,
    requested_frequency_grid,
    result_file,
    write_json_atomically,
)


def test_exported_frequency_reads_bare_and_named_annotations(tmp_path: Path) -> None:
    named = tmp_path / "named.txt"
    named.write_text("% @ freq=7.5\nV,E\n", encoding="utf-8")
    assert exported_frequency_ghz(named, bare_unit="GHz") == pytest.approx(7.5)
    assert exported_frequency_ghz(named, bare_unit="MHz") == pytest.approx(7.5e-3)

    bare = tmp_path / "bare.txt"
    bare.write_text("% @ 7.2921 GHz\nV,E\n", encoding="utf-8")
    assert exported_frequency_ghz(bare) == pytest.approx(7.2921)

    scaled = tmp_path / "scaled.txt"
    scaled.write_text("% @ 750 MHz\nV,E\n", encoding="utf-8")
    assert exported_frequency_ghz(scaled) == pytest.approx(0.75)

    silent = tmp_path / "silent.txt"
    silent.write_text("V,E\n0,1\n", encoding="utf-8")
    assert exported_frequency_ghz(silent) is None


def test_result_file_resolution(tmp_path: Path) -> None:
    present = tmp_path / "on_disk.txt"
    present.write_text("x\n", encoding="utf-8")

    assert result_file(tmp_path, "on_disk.txt") == present
    assert result_file(tmp_path, "absent.txt") is None
    assert result_file(None, "on_disk.txt") is None


def test_requested_grid_returns_the_exact_point_count() -> None:
    expression, grid_ghz = requested_frequency_grid(7.0, 7.002, 11)

    assert grid_ghz.size == 11
    assert grid_ghz[0] == pytest.approx(7.0)
    assert expression.startswith("range(")
    assert expression.endswith("[GHz])")


def test_write_json_atomically_leaves_no_temporary(tmp_path: Path) -> None:
    path = tmp_path / "series.json"
    write_json_atomically(path, {"rows": [1, 2]})
    write_json_atomically(path, {"rows": [1, 2, 3]})

    assert json.loads(path.read_text()) == {"rows": [1, 2, 3]}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["series.json"]


def test_a_unitless_frequency_is_not_assumed_to_be_ghz(tmp_path: Path) -> None:
    named = tmp_path / "named.txt"
    named.write_text("% @ freq=7.5E9\nV,E\n", encoding="utf-8")
    with pytest.raises(ValueError, match="without a unit"):
        exported_frequency_ghz(named)
    assert exported_frequency_ghz(named, bare_unit="Hz") == pytest.approx(7.5)
    with pytest.raises(ValueError, match="bare_unit must be one of"):
        exported_frequency_ghz(named, bare_unit="THz")


@pytest.mark.parametrize(
    ("low", "high", "points"),
    [(7.0, 8.0, 1), (7.0, 8.0, 0), (7.0, 8.0, 2.0), (8.0, 7.0, 3), (7.0, 7.0, 3)],
)
def test_requested_grid_rejects_a_degenerate_request(
    low: float, high: float, points: int
) -> None:
    with pytest.raises(ValueError):
        requested_frequency_grid(low, high, points)


def test_requested_grid_with_two_points_hits_both_ends() -> None:
    _, grid_ghz = requested_frequency_grid(7.0, 8.0, 2)
    assert grid_ghz == pytest.approx([7.0, 8.0])


def test_missing_results_message_names_no_notebook_globals(tmp_path: Path) -> None:
    for directory in (tmp_path, None):
        message = explain_missing_results(directory, "s21.txt")
        assert "s21.txt" in message
        for name in ("RESULTS_DIR", "MODEL_DIR", "RUN_COMSOL"):
            assert name not in message
    assert str(tmp_path) in explain_missing_results(tmp_path, "s21.txt")
