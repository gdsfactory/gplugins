"""Tests for the COMSOL result helpers shared by notebooks and scripts."""

import json
from pathlib import Path

import pytest

from gplugins.comsol.results import (
    exported_frequency_ghz,
    requested_frequency_grid,
    result_file,
    write_json_atomically,
)


def test_exported_frequency_reads_bare_and_named_annotations(tmp_path: Path) -> None:
    named = tmp_path / "named.txt"
    named.write_text("% @ freq=7.5\nV,E\n", encoding="utf-8")
    assert exported_frequency_ghz(named) == pytest.approx(7.5)

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
