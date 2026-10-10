"""Base AEDT simulation utilities using PyAEDT.

This module provides shared helper functions and a base class for AEDT
simulations (HFSS, Q3D, Q2D) from gdsfactory components.

Layer stacks default to the active PDK's. Materials are looked up in a
``material_properties`` table mapping each layer stack material name to its
properties (``relative_permittivity``, optionally ``conductivity``); a material
with infinite relative permittivity is treated as a perfect conductor.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Collection, Generator, Mapping
from contextlib import contextmanager
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

import gdsfactory as gf
from gdsfactory.technology.layer_stack import LayerLevel

logger = gf.logger

MaterialProperties: TypeAlias = Mapping[str, Mapping[str, float]]

DEFAULT_MATERIAL_PROPERTIES: dict[str, dict[str, float]] = {
    "vacuum": {"relative_permittivity": 1.0},
    "air": {"relative_permittivity": 1.0},
    "si": {"relative_permittivity": 11.7},
    "Si": {"relative_permittivity": 11.7},
    "silicon": {"relative_permittivity": 11.7},
    "sio2": {"relative_permittivity": 3.9},
    "sin": {"relative_permittivity": 7.5},
    "ge": {"relative_permittivity": 16.0},
    "sapphire": {"relative_permittivity": 9.4},
    "Aluminum": {"relative_permittivity": float("inf")},
    "Al": {"relative_permittivity": float("inf")},
    "Copper": {"relative_permittivity": float("inf")},
    "Gold": {"relative_permittivity": float("inf")},
    "Tungsten": {"relative_permittivity": float("inf")},
    "TiN": {"relative_permittivity": float("inf")},
    "Nb": {"relative_permittivity": float("inf")},
    "NbTiN": {"relative_permittivity": float("inf")},
}
"""Relative permittivities for common layer stack material names.

Metals have infinite permittivity and become ``pec`` in AEDT. Pass your own table
through the ``material_properties`` arguments to override or extend it.
"""


def _resolve_layer_stack(layer_stack: LayerStack | None) -> LayerStack:
    """Return ``layer_stack``, or the active PDK's when it is None.

    Raises:
        ValueError: If no layer stack is given and the active PDK has none.
    """
    if layer_stack is not None:
        return layer_stack
    stack = gf.get_active_pdk().layer_stack
    if stack is None:
        raise ValueError(
            "No layer_stack given and the active PDK has none; pass a LayerStack."
        )
    return stack


def _is_conductor(props: Mapping[str, float]) -> bool:
    """Return whether a material's properties make it a perfect conductor."""
    return props.get("relative_permittivity") == float("inf")


def conductor_materials(
    material_properties: MaterialProperties | None = None,
) -> set[str]:
    """Return the names of the perfect-conductor materials in a material table.

    Args:
        material_properties: Material table. Defaults to
            :data:`DEFAULT_MATERIAL_PROPERTIES`.

    Returns:
        Material names with infinite relative permittivity.
    """
    return {
        name
        for name, props in _resolve_material_properties(material_properties).items()
        if _is_conductor(props)
    }


def _resolve_material_properties(
    material_properties: MaterialProperties | None,
) -> MaterialProperties:
    """Return ``material_properties``, or the defaults when it is None."""
    if material_properties is None:
        return DEFAULT_MATERIAL_PROPERTIES
    return material_properties


if TYPE_CHECKING:
    from ansys.aedt.core import Hfss, Q2d
    from ansys.aedt.core.q3d import Q3d
    from gdsfactory.component import Component
    from gdsfactory.technology import LayerStack


def _get_layer_number_from_level(layer_level: LayerLevel) -> int | None:
    """Extract layer number from a LayerLevel's layer definition.

    Returns:
        The GDS layer number if available, else None.
    """
    if hasattr(layer_level, "derived_layer") and layer_level.derived_layer is not None:
        derived = layer_level.derived_layer
        if hasattr(derived, "layer"):
            inner = derived.layer
            if hasattr(inner, "layer"):
                val = inner.layer
                if isinstance(val, tuple) and len(val) >= 1:
                    return int(val[0])
                return int(val)
            if isinstance(inner, tuple) and len(inner) >= 1:
                return int(inner[0])

    layer = layer_level.layer
    if isinstance(layer, tuple) and len(layer) >= 1:
        return int(layer[0])
    if hasattr(layer, "layer"):
        inner = layer.layer
        if isinstance(inner, tuple) and len(inner) >= 1:
            return int(inner[0])
        if hasattr(inner, "layer"):
            val = inner.layer
            if isinstance(val, tuple) and len(val) >= 1:
                return int(val[0])
            return int(val)
        return int(inner)
    return None


def layer_stack_to_gds_mapping(
    layer_stack: LayerStack | None = None,
    thickness_override: float | None = None,
    *,
    override_materials: Collection[str] | None = None,
) -> dict[int, tuple[float, float]]:
    """Convert a LayerStack to HFSS/Q3D GDS import mapping dictionary.

    Vacuum levels (``material == "vacuum"``) are skipped: the AEDT background
    region is already vacuum and any vacuum box is added explicitly with
    :meth:`gplugins.ansys.HFSS.add_air_region`, so importing vacuum as
    GDS geometry is redundant. This also resolves collisions between a
    vacuum level and a substrate drawn on the same simulation-area layer.

    pyaedt's ``import_gds_3d`` keys the mapping on GDS layer number only — the
    GDS datatype is not part of the key — so two levels sharing a layer number
    (e.g. an airbridge pad on (10, 0) and its via on (10, 1)) are merged
    into a single entry when they share a material and their z-spans join into
    one box; otherwise an error is raised rather than silently importing wrong
    geometry. Levels sharing a layer number are processed in ascending
    ``zmin`` order so the result does not depend on the layer stack's
    insertion order.

    Args:
        layer_stack: Layer stack to map. Defaults to the active PDK's.
        thickness_override: Thickness in µm, e.g. ``0.0`` to import sheets. None
            keeps each level's own thickness.
        override_materials: Apply ``thickness_override`` only to levels with one
            of these materials, e.g. the conductors, so dielectric levels keep
            their thickness. None applies it to every level.

    Returns:
        Dictionary mapping layer number to (elevation, thickness) tuple.

    Raises:
        ValueError: If two levels share a GDS layer number but cannot be merged
            into a single (elevation, thickness) entry because their materials
            differ (regardless of ``thickness_override``) or, for levels
            without a thickness override, their z-spans do not join into a
            single box.
    """
    layer_stack = _resolve_layer_stack(layer_stack)

    # Collect levels per layer number first, then process each number's levels
    # in zmin order so the result is independent of the layer stack's
    # insertion order.
    levels_by_number: dict[int, list[tuple[str, LayerLevel, float, float, bool]]] = {}
    for name, layer_level in layer_stack.layers.items():
        if layer_level.material == "vacuum":
            logger.info(
                f"Skipping layer level {name!r} in GDS import mapping: vacuum is"
                " already the AEDT background region."
            )
            continue

        layer_number = _get_layer_number_from_level(layer_level)
        if layer_number is None:
            logger.warning(
                f"Layer level {name!r} has no resolvable GDS layer number and is"
                " left out of the GDS import mapping, so its geometry is not"
                " imported."
            )
            continue

        elevation = layer_level.zmin if layer_level.zmin is not None else 0.0
        overridden = thickness_override is not None and (
            override_materials is None or layer_level.material in override_materials
        )
        thickness = (
            thickness_override
            if overridden and thickness_override is not None
            else (layer_level.thickness or 0.0)
        )
        levels_by_number.setdefault(layer_number, []).append(
            (name, layer_level, elevation, thickness, overridden)
        )

    mapping: dict[int, tuple[float, float]] = {}
    for layer_number, levels in levels_by_number.items():
        levels.sort(key=itemgetter(2))  # ascending zmin

        prev_name, prev_level, prev_elevation, prev_thickness, _ = levels[0]
        mapping[layer_number] = (prev_elevation, prev_thickness)

        for name, layer_level, elevation, thickness, overridden in levels[1:]:
            if prev_level.material != layer_level.material:
                raise ValueError(
                    f"Layer levels {prev_name!r} ({prev_level.material!r}) and"
                    f" {name!r} ({layer_level.material!r}) share GDS layer"
                    f" {layer_number} but have different materials. pyaedt"
                    f" import_gds_3d keys the mapping on GDS layer number only"
                    f" (the datatype is discarded), so both would be imported as"
                    f" one object with a single material. Give them distinct GDS"
                    f" layer numbers or pass a custom layer_stack to"
                    f" import_component."
                )

            # Union of the two z-spans (um)
            span_low = min(prev_elevation, elevation)
            span_high = max(prev_elevation + prev_thickness, elevation + thickness)
            # Overlapping or touching intervals join into a single box
            max_low = max(prev_elevation, elevation)
            min_high = min(prev_elevation + prev_thickness, elevation + thickness)

            if overridden:
                # Levels sharing a number share a material, so both are
                # overridden. Sheets/forced thickness: colliding levels cannot keep distinct
                # z-spans, so collapse to the lowest elevation and warn loudly.
                logger.warning(
                    f"Layer levels {prev_name!r} and {name!r} share GDS layer"
                    f" {layer_number} (pyaedt import_gds_3d keys on layer number"
                    f" only): collapsing to a single entry at elevation"
                    f" {span_low} um; the higher level's geometry is not"
                    f" represented separately."
                )
                mapping[layer_number] = (span_low, thickness)
            elif max_low > min_high + 1e-6:  # 1 pm tolerance in um
                raise ValueError(
                    f"Layer levels {prev_name!r} and {name!r} share GDS layer"
                    f" {layer_number} but their z-spans [{prev_elevation},"
                    f" {prev_elevation + prev_thickness}] and [{elevation},"
                    f" {elevation + thickness}] do not join into a single box."
                    f" pyaedt import_gds_3d keys the mapping on GDS layer number"
                    f" only (the datatype is discarded), so both would be imported"
                    f" with a single elevation and thickness. Give them distinct"
                    f" GDS layer numbers or pass a custom layer_stack to"
                    f" import_component."
                )
            else:
                logger.info(
                    f"Merging layer levels {prev_name!r} and {name!r}: both use"
                    f" GDS layer {layer_number} and their z-spans join into a"
                    f" single box (elevation {span_low} um, thickness"
                    f" {span_high - span_low} um)."
                )
                mapping[layer_number] = (span_low, span_high - span_low)

            prev_name = name
            prev_level = layer_level
            prev_elevation, prev_thickness = mapping[layer_number]

    return mapping


@contextmanager
def export_component_to_gds_temp(
    component: gf.Component,
    gds_path: str | Path | None = None,
    prefix: str = "gplugins_aedt_",
) -> Generator[Path, None, None]:
    """Context manager for exporting a component to a temporary GDS file.

    The GDS is written without the layout's context info, where gdsfactory keeps its
    ports, cross-sections and settings. AEDT needs the geometry only, and on AEDT
    2026 R1 the importer fails on a file that carries the info: the import returns
    success, the AEDT process is gone moments later, and every later call in the
    session reports a dead desktop. A consumer that reads the file back with
    gdsfactory rather than handing it to AEDT gets no ports from it.

    Yields:
        Path to the exported GDS file.
    """
    if gds_path is not None:
        path = Path(gds_path)
        component.write_gds(str(path), with_metadata=False)
        yield path
    else:
        with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
            path = Path(temp_dir) / "component.gds"
            component.write_gds(str(path), with_metadata=False)
            yield path


def _first_real_value(solution: Any) -> float | None:
    """Read the first real value of a solution's active expression.

    ``get_expression_data`` is awkward about missing data: an expression the report
    does not carry comes back as empty arrays, and a sweep with no row matching the
    requested variation returns ``None`` for both the values and the sweep, in both
    cases while the ``SolutionData`` object itself stays truthy.

    Args:
        solution: A PyAEDT ``SolutionData`` for a single expression.

    Returns:
        The value, or ``None`` when the expression has no data to read.
    """
    _, values = solution.get_expression_data(formula="real")
    if values is None or len(values) == 0:
        return None
    return float(values[0])


def _level_names_by_number(layer_stack: LayerStack) -> dict[int, str]:
    """Map each GDS layer number to the level the import mapping places on it.

    Vacuum levels are skipped, as :func:`layer_stack_to_gds_mapping` skips them,
    and of the levels sharing a number the lowest one names the imported object.

    Returns:
        Dictionary mapping GDS layer number to layer stack level name.
    """
    candidates: dict[int, list[tuple[float, str]]] = {}
    for name, level in layer_stack.layers.items():
        if level.material == "vacuum":
            continue
        layer_num = _get_layer_number_from_level(level)
        if layer_num is not None:
            zmin = level.zmin if level.zmin is not None else 0.0
            candidates.setdefault(layer_num, []).append((zmin, name))
    return {num: min(levels)[1] for num, levels in candidates.items()}


def rename_imported_objects(
    app: Any,
    new_objects: list[str],
    layer_stack: LayerStack,
) -> list[str]:
    """Rename imported ``signal<N>`` GDS objects after their layer stack level.

    An object whose rename AEDT refuses (PyAEDT only logs a warning when the name
    is taken) keeps its original name, which :func:`object_names_to_materials`
    still resolves. Errors from AEDT itself propagate.

    Returns:
        List of the objects' names after renaming, in input order.
    """
    num_to_name = _level_names_by_number(layer_stack)

    renamed_objects = []
    for obj_name in new_objects:
        match = re.match(r"^signal(\d+)(_.*)?$", obj_name)
        new_name = obj_name
        if match and int(match.group(1)) in num_to_name:
            obj = app.modeler[obj_name]
            if obj is None:
                logger.warning(f"Imported object {obj_name!r} not found; not renamed.")
            else:
                obj.name = f"{num_to_name[int(match.group(1))]}{match.group(2) or ''}"
                new_name = obj.name
        renamed_objects.append(new_name)

    return renamed_objects


def object_names_to_materials(
    object_names: list[str],
    layer_stack: LayerStack,
    material_properties: MaterialProperties | None = None,
) -> dict[str, str]:
    """Map imported object names to AEDT material names based on the layer stack.

    Resolves each object to its :class:`LayerLevel` either by parsing the
    ``signal<layer_number>`` GDS import names (same convention as
    :func:`rename_imported_objects`) or by matching the (renamed) object name
    against layer stack names. Metal levels (materials with infinite
    relative permittivity in ``material_properties``) map to ``"pec"``;
    dielectric levels map to their layer stack material name.

    Args:
        object_names: AEDT object names to resolve.
        layer_stack: Layer stack the objects were imported from.
        material_properties: Material table. Defaults to
            :data:`DEFAULT_MATERIAL_PROPERTIES`.

    Returns:
        Dictionary mapping object names to AEDT material names.

    Raises:
        ValueError: If an object cannot be resolved to a layer stack level,
            or its level material is not registered in ``material_properties``.
            Failing closed avoids silently leaving objects with the project
            default material, which would make extracted results wrong
            rather than failed.
    """
    material_properties = _resolve_material_properties(material_properties)
    num_to_name = _level_names_by_number(layer_stack)

    def find_level(obj_name: str) -> LayerLevel | None:
        match = re.match(r"^signal(\d+)(_.*)?$", obj_name)
        if match and int(match.group(1)) in num_to_name:
            return layer_stack.layers[num_to_name[int(match.group(1))]]
        # Exact name first, then prefix match (longest names first so that
        # e.g. "Airbridge_Via_1" is not matched by "Airbridge")
        for name in sorted(layer_stack.layers, key=len, reverse=True):
            if obj_name == name or obj_name.startswith(f"{name}_"):
                return layer_stack.layers[name]
        return None

    assignments: dict[str, str] = {}
    for obj_name in object_names:
        level = find_level(obj_name)
        material = level.material if level is not None else None
        if material is None:
            raise ValueError(
                f"Could not resolve AEDT object {obj_name!r} to a layer stack "
                "level with a material; refusing to leave it with the default "
                "material."
            )
        props = material_properties.get(material)
        if props is None:
            raise ValueError(
                f"Material {material!r} of AEDT object {obj_name!r} is not "
                "registered in material_properties; refusing to leave it with "
                "the default material."
            )
        assignments[obj_name] = "pec" if _is_conductor(props) else material
    return assignments


def add_materials_to_aedt(
    app: Hfss | Q2d | Q3d,
    material_properties: MaterialProperties | None = None,
) -> None:
    """Add materials to the PyAEDT application, skipping ones it already has.

    Args:
        app: The PyAEDT application.
        material_properties: Material table. Defaults to
            :data:`DEFAULT_MATERIAL_PROPERTIES`.
    """
    for name, props in _resolve_material_properties(material_properties).items():
        if app.materials.exists_material(name):
            continue

        mat = app.materials.add_material(name)

        for prop_name, prop_value in props.items():
            if prop_value == float("inf"):
                if prop_name == "relative_permittivity":
                    mat.conductivity = 1e30
                continue

            if prop_name == "relative_permittivity":
                mat.permittivity = prop_value
            elif prop_name == "conductivity":
                mat.conductivity = prop_value


class AEDTBase:
    """Base class for AEDT simulations."""

    def __init__(
        self,
        app: Hfss | Q2d | Q3d,
        *,
        layer_stack: LayerStack | None = None,
        material_properties: MaterialProperties | None = None,
    ):
        """Initialize the AEDT base class.

        Args:
            app: The PyAEDT application instance.
            layer_stack: Default layer stack for imports. None means the active
                PDK's, looked up when it is needed.
            material_properties: Material table. Defaults to
                :data:`DEFAULT_MATERIAL_PROPERTIES`.
        """
        self.app = app
        self.layer_stack = layer_stack
        self.material_properties = _resolve_material_properties(material_properties)

    def resolve_layer_stack(self, layer_stack: LayerStack | None = None) -> LayerStack:
        """Return ``layer_stack``, else this instance's, else the active PDK's.

        Returns:
            The layer stack to use.
        """
        return _resolve_layer_stack(
            layer_stack if layer_stack is not None else self.layer_stack
        )

    @property
    def modeler(self):
        """The AEDT modeler instance."""
        return self.app.modeler

    def add_materials(self) -> None:
        """Add this instance's materials to the AEDT project."""
        add_materials_to_aedt(self.app, self.material_properties)

    def add_substrate(
        self,
        component: Component,
        thickness: float = 500.0,
        material: str = "silicon",
        name: str = "Substrate",
    ) -> str:
        """Add a substrate box below the component geometry.

        The material table is added to the project first, so ``material`` may be
        any of its names.

        Returns:
            Name of the created substrate object.
        """
        self.add_materials()
        bounds = component.bbox()
        x_min, y_min = bounds.p1.x, bounds.p1.y
        dx, dy = bounds.p2.x - x_min, bounds.p2.y - y_min

        substrate = self.modeler.create_box(
            origin=[x_min, y_min, -thickness],
            sizes=[dx, dy, thickness],
            name=name,
            material=material,
        )
        return substrate.name

    def save(self) -> None:
        """Save the AEDT project."""
        self.app.save_project()


def fit_view(app: Any) -> None:
    """Frame the model in a graphical AEDT session, and do nothing when headless.

    ``modeler.fit_all`` is a view operation. A non-graphical session has no view, and
    on AEDT 2026 R1 the failed call loses the gRPC channel: the geometry is fine, but
    every later call in the session reports a dead desktop.

    The guard reads the flag the session was constructed with, not what the session
    itself reports, so attaching to an existing headless session still needs
    ``non_graphical`` set or ``PYAEDT_NON_GRAPHICAL`` exported. A released session has
    no desktop left and raises.

    Args:
        app: The AEDT application (an ``Hfss``, ``Q3d`` or ``Q2d`` instance).
    """
    if not app.desktop_class.non_graphical:
        app.modeler.fit_all()


def detach_desktop_logging(app: Any) -> None:
    """Stop PyAEDT reading the AEDT desktop on every log message.

    ``Logger._log_on_desktop`` tests the desktop before it tests
    ``settings.enable_desktop_logs``, so the setting PyAEDT turns off itself in
    non-graphical mode does not prevent the read. The read goes through
    ``Desktop.odesktop``, whose failure path releases the gRPC plugin's AEDT handle,
    so a stray log message can end a session that AEDT is still running. Dropping the
    logger's reference to the desktop is what ``Desktop.release_desktop`` does at the
    end of a session anyway.

    PyAEDT has one logger per process and every desktop construction points it back at
    that desktop, so this is process-global and needs calling after each ``Hfss``,
    ``Q3d`` or ``Q2d`` is built. Messages the logger reads out of the desktop, such as
    ``get_messages(aedt_messages=True)``, stop working afterwards.

    Args:
        app: The AEDT application (an ``Hfss``, ``Q3d`` or ``Q2d`` instance).
    """
    if hasattr(app.logger, "_desktop_class"):
        app.logger._desktop_class = None
    else:  # pragma: no cover - only where PyAEDT renamed the attribute
        logger.warning(
            "PyAEDT's logger has no _desktop_class, so it keeps reading the desktop on"
            " every log message. Check the PyAEDT version."
        )
