"""gdsfactory interface to EMode Photonix.

EMode is a commercial photonic simulation package with an electromagnetic
waveguide mode solver (FDM), eigenmode expansion propagation (EME), nonlinear
photonics, and thermal/electrical FEM solvers.
See https://docs.emodephotonix.com for the full API.

This module translates gdsfactory objects (:class:`~gdsfactory.CrossSection`,
:class:`~gdsfactory.technology.LayerStack`) into EMode geometry. The
translation itself is implemented as pure functions
(:func:`get_emode_settings`, :func:`get_shapes_from_layer_stack`) that only
require the pip-installable ``emodeconnection`` client. Creating an
:class:`EMode` session and running solvers requires a local EMode installation
and license.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import emodeconnection as emc
import gdsfactory as gf
from gdsfactory.technology import LayerStack
from gdsfactory.typings import CrossSectionSpec

UM_TO_NM = 1e3

DIMENSIONAL_SETTINGS = frozenset(
    {
        "wavelength",
        "x_resolution",
        "y_resolution",
        "window_width",
        "window_height",
        "bend_radius",
        "expansion_resolution",
        "expansion_size",
        "propagation_resolution",
    }
)


def get_emode_settings(**settings: Any) -> dict[str, Any]:
    """Convert gdsfactory-style settings to EMode units.

    gdsfactory uses microns for all dimensions while EMode defaults to
    nanometers. Settings named in ``DIMENSIONAL_SETTINGS`` are converted from
    um to nm; all other settings pass through unchanged.

    Args:
        settings: keyword arguments for EMode's ``settings()`` function,
            with dimensional values in um.

    Returns:
        The same settings with dimensional values converted to nm.
    """
    return {
        key: value * UM_TO_NM if key in DIMENSIONAL_SETTINGS else value
        for key, value in settings.items()
    }


def get_emode_material(material: str, materials: Sequence[str]) -> str:
    """Match a gdsfactory material name to the EMode material database.

    Matching is case-insensitive (e.g. gdsfactory's ``si`` matches EMode's
    ``Si``). If no match is found the name is returned unchanged so EMode can
    report an informative error for genuinely unknown materials.

    Args:
        material: gdsfactory material name.
        materials: available EMode material names, from ``EMode.get('materials')``.
    """
    return next((m for m in materials if m.lower() == material.lower()), material)


def get_shapes_from_layer_stack(
    cross_section: CrossSectionSpec,
    layer_stack: LayerStack,
    materials: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Translate a gdsfactory layer stack and cross-section into EMode shapes.

    Each :class:`~gdsfactory.technology.LayerLevel` becomes one EMode shape.
    Layers whose ``layer`` (or ``derived_layer``) appears as a section of the
    cross-section take their mask width and offset from that section. Vertical
    positions are referenced to the bottom of the layer stack, and gdsfactory
    mesh order (lower = higher priority) is converted to EMode shape priority
    (higher = higher priority).

    Args:
        cross_section: gdsfactory cross-section (or spec) defining mask
            widths and offsets.
        layer_stack: gdsfactory LayerStack defining layer materials,
            thicknesses, and vertical placement.
        materials: available EMode material names used to match gdsfactory
            material names case-insensitively, typically from
            ``EMode.get('materials')``.

    Returns:
        One dict of keyword arguments for EMode's ``shape()`` function per
        layer, in layer-stack order, with dimensions in nm.
    """
    if not layer_stack.layers:
        raise ValueError("layer_stack must contain at least one layer.")

    xs = gf.get_cross_section(cross_section)

    max_order = max(level.mesh_order for level in layer_stack.layers.values())
    min_zmin = min(level.zmin for level in layer_stack.layers.values())

    shapes: list[dict[str, Any]] = []
    for name, level in layer_stack.layers.items():
        shape: dict[str, Any] = {
            "name": name,
            "material": get_emode_material(level.material, materials),
            "height": level.thickness * UM_TO_NM,
            "mask": level.width_to_z * UM_TO_NM,
            "sidewall_angle": level.sidewall_angle,
            "etch_depth": level.thickness * UM_TO_NM if level.width_to_z > 0 else 0.0,
            "position": [0.0, (level.zmin - min_zmin + level.thickness / 2) * UM_TO_NM],
            "priority": max_order - level.mesh_order + 1,
        }

        section = next(
            (
                s
                for s in xs.sections
                if str(s.layer) in (str(level.layer), str(level.derived_layer))
            ),
            None,
        )
        if section is not None:
            shape["mask"] = section.width * UM_TO_NM
            shape["mask_offset"] = section.offset * UM_TO_NM

        shapes.append(shape)

    return shapes


class EMode(emc.EMode):
    """EMode session with gdsfactory geometry helpers.

    Creating an instance launches the EMode application and connects to it,
    so it requires a local EMode installation and license (the
    ``emodeconnection`` client alone is not enough). Any EMode function can
    be called as a method, e.g. ``FDM()``, ``EME()``, ``report()``,
    ``plot()``; see https://docs.emodephotonix.com for the full API.
    """

    def build_waveguide(
        self,
        cross_section: CrossSectionSpec,
        layer_stack: LayerStack,
        **settings: Any,
    ) -> None:
        """Build a waveguide in this EMode session from gdsfactory geometry.

        Args:
            cross_section: gdsfactory cross-section (or spec) defining mask
                widths and offsets.
            layer_stack: gdsfactory LayerStack defining layer materials,
                thicknesses, and vertical placement.
            settings: forwarded to EMode's ``settings()`` function, with
                dimensional values in um (see :func:`get_emode_settings`).
        """
        self.settings(**get_emode_settings(**settings))
        materials = self.get("materials")
        for shape in get_shapes_from_layer_stack(cross_section, layer_stack, materials):
            self.shape(**shape)


if __name__ == "__main__":
    # Silicon-on-insulator rib waveguide example.
    # Requires a local EMode installation and license.
    from gdsfactory.gpdk import LAYER_STACK

    layer_stack = LayerStack(
        layers={
            k: LAYER_STACK.layers[k].model_copy()
            for k in ("core", "clad", "slab90", "box")
        }
    )
    layer_stack.layers["core"].thickness = 0.22
    layer_stack.layers["core"].zmin = 0.0
    layer_stack.layers["slab90"].thickness = 0.09
    layer_stack.layers["slab90"].zmin = 0.0
    layer_stack.layers["box"].thickness = 1.5
    layer_stack.layers["box"].zmin = -1.5
    layer_stack.layers["clad"].thickness = 1.5
    layer_stack.layers["clad"].zmin = 0.0

    em = EMode()
    em.build_waveguide(
        cross_section=gf.cross_section.rib(width=0.6),
        layer_stack=layer_stack,
        wavelength=1.55,
        num_modes=1,
        x_resolution=0.010,
        y_resolution=0.010,
        window_width=3.0,
        window_height=3.0,
        background_material="Air",
        max_effective_index=2.631,
    )
    em.FDM()
    em.report()
    em.plot()
    em.close()
