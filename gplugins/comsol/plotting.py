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
    stride: int = 4,
    contour_levels: int = 30,
) -> None:
    """Draw a cropped ``emw.normE`` map from a COMSOL cut-plane export.

    The export covers the whole prepared box, so the nodes are cropped to
    ``view_um`` and, for display only, drawn on a fixed-stride subset with
    percentiles of the cropped data as the colour limits. The stride changes what
    is drawn, not what was solved.

    Args:
        file: A ``emw.normE`` export on the cut plane, columns x, y, z, E.
        title: Figure title.
        view_um: ``(xmin, xmax, ymin, ymax)`` crop window, in µm.
        stride: Drawing stride over the cropped nodes.
        contour_levels: Number of contour levels.

    Raises:
        ValueError: If the crop window holds no exported node.
    """
    field = np.loadtxt(file, comments="%")
    field_x, field_y, field_e = field[:, 0], field[:, 1], field[:, 3]
    inside = (
        (field_x >= view_um[0])
        & (field_x <= view_um[1])
        & (field_y >= view_um[2])
        & (field_y <= view_um[3])
    )
    view_x, view_y, view_e = field_x[inside], field_y[inside], field_e[inside]
    if view_e.size == 0:
        raise ValueError(f"No exported field nodes inside {view_um}")

    # Colour limits from the data in the window rather than the full-domain
    # maximum, which sits far outside it and flattens everything on the scale.
    color_min, color_max = (float(value) for value in np.percentile(view_e, [1, 99]))
    draw_x, draw_y, draw_e = view_x, view_y, view_e
    if stride > 1 and view_e.size // stride >= 10:
        draw_x = view_x[::stride]
        draw_y = view_y[::stride]
        draw_e = view_e[::stride]
    print(  # ruff: ignore[print]
        f"Field nodes: {view_e.size} of {field_e.size} inside the view; "
        f"{draw_e.size} drawn at stride {stride}; "
        f"range {view_e.min():.3g} to {view_e.max():.3g} V/m, "
        f"1st to 99th percentile {color_min:.3g} to {color_max:.3g} V/m"
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    contour = ax.tricontourf(
        draw_x,
        draw_y,
        draw_e,
        levels=np.geomspace(color_min, color_max, contour_levels),
        norm=LogNorm(vmin=color_min, vmax=color_max),
        cmap="inferno",
        extend="both",
    )
    ax.set_xlim(view_um[0], view_um[1])
    ax.set_ylim(view_um[2], view_um[3])
    ax.set_aspect("equal")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    ax.set_title(title)
    fig.colorbar(contour, ax=ax, label=r"$|\mathbf{E}|$ (V/m)")
    plt.tight_layout()
    plt.show()
