"""Read saved COMSOL exports without loading MPh or a solver."""

from __future__ import annotations

import json
import math
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
        results_dir: Directory the file was looked for in, or ``None`` when no
            results directory is configured.
        name: File name that was looked for inside ``results_dir``.

    Returns:
        A one-paragraph message naming the missing file and the two ways to
        supply it.
    """
    where = (
        "no results directory is configured"
        if results_dir is None
        else f"{results_dir} holds no such file"
    )
    return (
        f"No exported {name}: {where}. Saved results come from a licensed solve, "
        "so either solve on a machine with COMSOL and export the file into the "
        "results directory, or point the results directory at one that already "
        f"holds an exported {name}."
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


def exported_frequency_ghz(file: Path, *, bare_unit: str | None = None) -> float | None:
    """Read the frequency annotation COMSOL writes into a data export header.

    COMSOL writes either ``@ freq=<value>`` or a ``@ <value> <unit>`` line. The
    second form carries its unit and is converted. The first carries none, and
    which unit COMSOL writes it in is not established here, so it is only read
    when the caller names that unit with ``bare_unit``.

    Args:
        file: Exported text file to scan.
        bare_unit: Unit of a unit-less ``@ freq=`` value, one of
            :data:`FREQUENCY_UNITS_GHZ`. ``None`` refuses such a value rather
            than guessing.

    Returns:
        The annotated frequency in GHz, or ``None`` when the export carries no
        frequency.

    Raises:
        ValueError: If ``bare_unit`` is not a known unit, or if the export
            carries a unit-less ``@ freq=`` value and ``bare_unit`` is ``None``.
    """
    if bare_unit is not None and bare_unit not in FREQUENCY_UNITS_GHZ:
        raise ValueError(
            f"bare_unit must be one of {sorted(FREQUENCY_UNITS_GHZ)}, got {bare_unit!r}"
        )
    with file.open(encoding="utf-8") as handle:
        for line in handle:
            if (match := _FREQUENCY_ANNOTATION.search(line)) is not None:
                if bare_unit is None:
                    raise ValueError(
                        f"{file} annotates freq={match.group(1)} without a unit; "
                        "pass bare_unit to say which unit it is in"
                    )
                return float(match.group(1)) * FREQUENCY_UNITS_GHZ[bare_unit]
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

    Raises:
        ValueError: If ``points`` is not an integer of at least 2, or if the
            window is not finite with ``high_ghz`` above ``low_ghz``.
    """
    if isinstance(points, bool) or not isinstance(points, int) or points < 2:
        raise ValueError(f"points must be an integer of at least 2, got {points!r}")
    if not (math.isfinite(low_ghz) and math.isfinite(high_ghz)) or high_ghz <= low_ghz:
        raise ValueError(
            f"the window must be finite with high_ghz > low_ghz, got {low_ghz!r} "
            f"to {high_ghz!r}"
        )
    step_ghz = (high_ghz - low_ghz) / (points - 1)
    start_token = f"{low_ghz:.12g}"
    step_token = f"{step_ghz:.12g}"
    start_ghz = float(start_token)
    step_rounded_ghz = float(step_token)
    grid_ghz = start_ghz + step_rounded_ghz * np.arange(points)
    stop_ghz = grid_ghz[-1] + 0.5 * step_rounded_ghz
    expression = f"range({start_token}[GHz],{step_token}[GHz],{stop_ghz:.12g}[GHz])"
    return expression, grid_ghz
