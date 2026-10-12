"""Java-API formatting helpers shared by the COMSOL builders.

Kept apart so the builders do not have to import one another for them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import mph

    from gplugins.comsol.layout import Point

#: Tags of the mesh sequence and study a study builder creates. They are fixed,
#: so a sheet model carries one study; the mesh helpers work on ``mesh1``.
MESH_TAG = "mesh1"
STUDY_TAG = "std1"


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


def _existing_tags(entity_list: Any) -> set[str]:
    """Return the tags a COMSOL entity list already holds.

    Returns:
        The tags, as Python strings.
    """
    return {str(tag) for tag in entity_list.tags()}


def _require_no_study(model: mph.Model, component: Any) -> None:
    """Refuse a model that already holds the mesh or study a builder creates.

    Raises:
        ValueError: If ``comp1`` already has ``mesh1`` or the model ``std1``,
            which means a study was already added to this model.
    """
    taken = [
        tag
        for tag, entity_list in (
            (MESH_TAG, component.mesh()),
            (STUDY_TAG, model.java.study()),
        )
        if tag in _existing_tags(entity_list)
    ]
    if taken:
        raise ValueError(
            f"the model already holds {taken}: a sheet model carries one study, "
            "so build a separate sheet model for the other study"
        )
