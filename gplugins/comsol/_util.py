"""Java-API formatting helpers shared by the COMSOL builders.

Kept apart so the builders do not have to import one another for them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gplugins.comsol.layout import Point


def _format_number(value: float) -> str:
    """Format a length for the COMSOL Java API.

    Returns:
        The value as a plain decimal string.
    """
    return f"{value:.12g}"


def _add_polygon(work_plane: Any, tag: str, points: tuple[Point, ...]) -> None:
    """Add one solid polygon to a work plane geometry sequence.

    Args:
        work_plane: The work plane's geometry sequence (``feature.geom()``).
        tag: Feature tag for the polygon.
        points: Vertices in µm, first vertex not repeated.
    """
    work_plane.create(tag, "Polygon")
    polygon = work_plane.feature(tag)
    polygon.set("x", ",".join(_format_number(point[0]) for point in points))
    polygon.set("y", ",".join(_format_number(point[1]) for point in points))
