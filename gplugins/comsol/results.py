"""Read saved COMSOL exports without loading MPh or a solver."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

# Frequency units COMSOL may annotate an export header with, to GHz.
FREQUENCY_UNITS_GHZ = {"GHz": 1.0, "MHz": 1.0e-3, "kHz": 1.0e-6, "Hz": 1.0e-9}
# COMSOL exports use both ``@ freq=7.5`` and ``@ 7.2921 GHz`` headers.
_FREQUENCY_ANNOTATION = re.compile(
    r"@\s*freq\s*=\s*([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
)
_FREQUENCY_HEADER = re.compile(
    r"@\s*([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s*(GHz|MHz|kHz|Hz)\b"
)


def result_file(results_dir: Path | None, name: str) -> Path | None:
    """Return the path of an exported solver result, if one is available.

    Args:
        results_dir: Directory holding exported results, or ``None`` when the
            notebook has no results directory configured.
        name: File name to look for inside ``results_dir``.

    Returns:
        The path, or ``None`` when ``results_dir`` is unset or holds no such
        file.
    """
    if results_dir is None:
        return None
    path = results_dir / name
    return path if path.exists() else None


def explain_missing_results(results_dir: Path | None, name: str) -> str:
    """Explain how to supply a result file that is not on disk.

    Args:
        results_dir: Directory the file was looked for in.
        name: File name that was looked for inside ``results_dir``.

    Returns:
        A one-paragraph message naming the missing file and the two ways to
        supply it.
    """
    return (
        f"No {name} in RESULTS_DIR ({results_dir}). The figures on the "
        "documentation page are saved outputs of a licensed solve, and the cells "
        "here replot only from files on disk. To supply them, run with "
        "RUN_COMSOL = True on a licensed machine, which exports into MODEL_DIR, "
        "or set RESULTS_DIR to a directory that already holds an exported "
        f"{name}."
    )


def write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON through a sibling temporary file, then replace in place.

    A series writes on every row, so an interrupt partway through still leaves
    the rows already solved on disk. The temporary file is a sibling so the
    replace stays a same-filesystem rename, which is what makes it atomic.

    Args:
        path: The JSON file to write.
        payload: The object to serialise.
    """
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def exported_frequency_ghz(file: Path) -> float | None:
    """Read the frequency annotation COMSOL writes into a data export header.

    COMSOL writes either ``@ freq=<value>`` or a bare ``@ <value> <unit>`` line,
    and the live field exports use the second form, so both are parsed and the
    unit is applied explicitly rather than assumed to be GHz.

    Args:
        file: Exported text file to scan.

    Returns:
        The annotated frequency in GHz, or ``None`` when the export carries no
        frequency.
    """
    with file.open(encoding="utf-8") as handle:
        for line in handle:
            if (match := _FREQUENCY_ANNOTATION.search(line)) is not None:
                return float(match.group(1))
            if (match := _FREQUENCY_HEADER.search(line)) is not None:
                return float(match.group(1)) * FREQUENCY_UNITS_GHZ[match.group(2)]
    return None


def requested_frequency_grid(
    low_ghz: float, high_ghz: float, points: int
) -> tuple[str, np.ndarray]:
    """Return the COMSOL ``range`` for a requested grid, and that exact grid.

    The start and step are formatted once and the grid is rebuilt from those
    formatted tokens, so the grid checked here is the grid COMSOL will build.
    Formatting all three tokens independently is what goes wrong: a rounded step
    can make ``start + (points - 1) * step`` exceed a separately rounded stop by a
    few millihertz, and an inclusive range then returns only ``points - 1`` rows.
    The stop here is the intended last frequency plus half a step, so rounding
    cannot push the last point past it, while the point one step further is still
    beyond it, so the range returns exactly ``points`` frequencies.

    Args:
        low_ghz: Low end of the physical window, in GHz.
        high_ghz: High end of the physical window, in GHz.
        points: Number of grid points.

    Returns:
        The ``range`` expression, and the ``points``-long grid it should return.
    """
    step_ghz = (high_ghz - low_ghz) / (points - 1)
    start_token = f"{low_ghz:.12g}"
    step_token = f"{step_ghz:.12g}"
    start_ghz = float(start_token)
    step_rounded_ghz = float(step_token)
    grid_ghz = start_ghz + step_rounded_ghz * np.arange(points)
    stop_ghz = grid_ghz[-1] + 0.5 * step_rounded_ghz
    expression = f"range({start_token}[GHz],{step_token}[GHz],{stop_ghz:.12g}[GHz])"
    return expression, grid_ghz
