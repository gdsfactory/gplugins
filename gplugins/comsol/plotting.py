"""Matplotlib helpers shared by the COMSOL notebooks.

Matplotlib and numpy only: importing this module needs neither MPh nor a COMSOL
license, so the result cells still draw saved exports where no solver is
installed.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import axes as mpl_axes
from matplotlib.colors import LogNorm
from matplotlib.patches import Polygon as MplPolygon


def draw_layout_polygons(ax: mpl_axes.Axes, polygons: Iterable[Any]) -> None:
    """Draw prepared metal polygons as filled patches, largest first.

    Largest first keeps the small pads and the ground plane visible whichever
    order the layout hands them back in.

    Args:
        ax: Axes to draw on.
        polygons: Polygons with ``outline`` points and ``holes``, as a prepared
            layout stores them.
    """

    def area(polygon: Any) -> float:
        xs = [x for x, _ in polygon.outline]
        ys = [y for _, y in polygon.outline]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    for polygon in sorted(polygons, key=lambda item: -area(item)):
        ax.add_patch(
            MplPolygon(
                polygon.outline,
                closed=True,
                facecolor="0.78",
                edgecolor="0.35",
                linewidth=0.6,
                zorder=1,
            )
        )
        for hole in polygon.holes:
            ax.add_patch(
                MplPolygon(
                    hole,
                    closed=True,
                    facecolor="white",
                    edgecolor="0.35",
                    linewidth=0.6,
                    zorder=1,
                )
            )


def draw_cut_plane_field(
    file: Path,
    title: str,
    *,
    view_um: tuple[float, float, float, float],
    contour_levels: int = 30,
) -> None:
    """Draw a cropped ``emw.normE`` map from a COMSOL cut-plane export.

    The export holds field values at mesh nodes but not the mesh, so the plot
    triangulates the nodes and then crops to ``view_um`` with the axis limits.
    It triangulates the nodes within one window size of ``view_um`` on every
    side, not only the nodes inside it: those alone would leave the window
    corners outside their convex hull, and the corners would draw blank. Nodes
    that share a position, as on a metal edge where the field jumps, are drawn
    with their largest value. The colour limits are percentiles of the
    positive field inside the window.

    Args:
        file: A ``emw.normE`` export on the cut plane, columns x, y, z, E.
        title: Figure title.
        view_um: ``(xmin, xmax, ymin, ymax)`` crop window, in µm.
        contour_levels: Number of contour levels.

    Raises:
        ValueError: If the crop window holds no exported node, or no node with
            a positive field.
    """
    field = np.loadtxt(file, comments="%", ndmin=2)
    # COMSOL writes NaN where it cannot evaluate the expression. The
    # triangulation reaches past the window, so a NaN node just outside it
    # would still blank the triangles that cross its edge.
    field = field[np.isfinite(field[:, [0, 1, 3]]).all(axis=1)]
    xmin, xmax, ymin, ymax = view_um
    margin = max(xmax - xmin, ymax - ymin)
    near = (
        (field[:, 0] >= xmin - margin)
        & (field[:, 0] <= xmax + margin)
        & (field[:, 1] >= ymin - margin)
        & (field[:, 1] <= ymax + margin)
    )
    # The triangulation keeps one node per position and would drop the rest
    # silently, in export order.
    positions, node = np.unique(field[near][:, :2], axis=0, return_inverse=True)
    field_x, field_y = positions[:, 0], positions[:, 1]
    field_e = np.full(len(positions), -np.inf)
    np.maximum.at(field_e, node.ravel(), field[near][:, 3])
    inside = (
        (field_x >= xmin) & (field_x <= xmax) & (field_y >= ymin) & (field_y <= ymax)
    )
    view_e = field_e[inside]
    if view_e.size == 0:
        raise ValueError(f"No exported field nodes inside {view_um}")

    # Colour limits from the data in the window rather than the full-domain
    # maximum, which sits far outside it and flattens everything on the scale.
    # The scale is logarithmic, so the limits come from the positive nodes only:
    # an export with more than 1% zero-field nodes would put the 1st percentile
    # at 0, which a log scale cannot take.
    positive_e = view_e[view_e > 0.0]
    if positive_e.size == 0:
        raise ValueError(f"No positive field values inside {view_um} to draw")
    color_min, color_max = (
        float(value) for value in np.percentile(positive_e, [1, 99])
    )
    if color_max <= color_min:
        # A uniform window would give a single contour level; widen it so the
        # levels still increase.
        color_max = color_min * 10.0

    print(
        f"Field nodes: {view_e.size} inside the view, {field_e.size} "
        f"triangulated; range {view_e.min():.3g} to {view_e.max():.3g} V/m, "
        f"1st to 99th percentile {color_min:.3g} to {color_max:.3g} V/m"
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    # Zero and below-range nodes are drawn in the lowest colour, not left blank.
    contour = ax.tricontourf(
        field_x,
        field_y,
        np.maximum(field_e, color_min),
        levels=np.geomspace(color_min, color_max, contour_levels),
        norm=LogNorm(vmin=color_min, vmax=color_max),
        cmap="inferno",
        extend="both",
    )
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    ax.set_title(title)
    fig.colorbar(contour, ax=ax, label=r"$|\mathbf{E}|$ (V/m)")
    plt.tight_layout()
    plt.show()
