"""Q3D and Q2D simulation utilities using PyAEDT."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, cast

import gdsfactory as gf
import polars as pl

from gplugins.ansys.base import (
    AEDTBase,
    _first_real_value,
    export_component_to_gds_temp,
    layer_stack_to_gds_mapping,
    object_names_to_materials,
    rename_imported_objects,
)

if TYPE_CHECKING:
    from ansys.aedt.core import Q2d
    from ansys.aedt.core.q3d import Q3d
    from gdsfactory.component import Component
    from gdsfactory.technology import LayerStack
    from gdsfactory.technology.layer_stack import LayerLevel
    from gdsfactory.typings import Ports

    from gplugins.ansys.base import MaterialProperties


class Q3D(AEDTBase):
    """Q3D Extractor simulation wrapper.

    Provides methods for importing components into Q3D and performing
    parasitic capacitance/inductance extraction.
    """

    def __init__(
        self,
        q3d: Q3d,
        *,
        layer_stack: LayerStack | None = None,
        material_properties: MaterialProperties | None = None,
    ):
        """Initialize the Q3D wrapper.

        Args:
            q3d: The PyAEDT Q3d application instance.
            layer_stack: Default layer stack. None means the active PDK's.
            material_properties: Material table. Defaults to
                :data:`gplugins.ansys.DEFAULT_MATERIAL_PROPERTIES`.
        """
        super().__init__(
            q3d, layer_stack=layer_stack, material_properties=material_properties
        )
        self.q3d = q3d

    def import_component(
        self,
        component: Component,
        layer_stack: LayerStack | None = None,
        *,
        units: str = "um",
        gds_path: str | Path | None = None,
    ) -> list[str]:
        """Import a gdsfactory component into Q3D Extractor.

        Imports the component's GDS geometry into a Q3D Extractor project,
        mapping each GDS layer to a 3D conductor at the appropriate elevation
        and thickness from the layer stack.

        Args:
            component: The gdsfactory component to import.
            layer_stack: LayerStack defining thickness and elevation for each layer.
                If None, uses the wrapper's, else the active PDK's.
            units: Length units for the geometry (default: "um" for micrometers).
            gds_path: Optional path to write the GDS file. If None, uses a temporary file.

        Returns:
            List of newly created conductor object names in Q3D.

        Raises:
            RuntimeError: If GDS import fails.
        """
        stack = self.resolve_layer_stack(layer_stack)
        mapping_layers = layer_stack_to_gds_mapping(stack)

        with export_component_to_gds_temp(
            component, gds_path, prefix="gplugins_q3d_"
        ) as path:
            self.modeler.model_units = units
            existing_objects = set(self.modeler.object_names)

            result = self.q3d.import_gds_3d(
                input_file=str(path),
                mapping_layers=mapping_layers,
                units=units,
                import_method=0,
            )
            if not result:
                raise RuntimeError("Q3D GDS import failed")

            new_objects = list(set(self.modeler.object_names) - existing_objects)

            renamed_objects = rename_imported_objects(self.q3d, new_objects, stack)

            # Assign materials from the layer stack: metals become "pec",
            # substrate/etch objects get their real dielectric materials.
            # Batched per material to keep AEDT round trips minimal.
            self.add_materials()
            objects_to_materials = object_names_to_materials(
                renamed_objects, stack, self.material_properties
            )
            by_material: dict[str, list[str]] = {}
            for obj_name, material in objects_to_materials.items():
                by_material.setdefault(material, []).append(obj_name)
            for material, objects in by_material.items():
                self.q3d.assign_material(objects, material)

            # Only conductors are meaningful downstream (e.g. net assignment).
            return [
                obj_name
                for obj_name, material in objects_to_materials.items()
                if material == "pec"
            ]

    def assign_nets_from_ports(
        self,
        ports: Ports,
        conductor_objects: list[str],
    ) -> list[str]:
        """Assign Q3D signal nets based on gdsfactory port locations.

        For each gdsfactory port, finds the conductor object whose bounding-box
        center is nearest to the port center and assigns it as a Q3D signal net.

        Args:
            ports: Collection of gdsfactory ports defining signal locations.
            conductor_objects: List of conductor object names created by
                :meth:`import_component`.

        Returns:
            List of assigned signal net names (one per port).
        """
        self.q3d.auto_identify_nets()

        assigned_nets: list[str] = []
        used_objects: set[str] = set()

        if not ports or not conductor_objects:
            return assigned_nets

        bboxes = {}
        for obj_name in conductor_objects:
            obj = self.modeler.get_object_from_name(obj_name)
            if obj:
                bboxes[obj_name] = obj.bounding_box

        if not bboxes:
            return assigned_nets

        first_port = next(iter(ports))
        px0, py0 = float(first_port.center[0]), float(first_port.center[1])

        def dist_to_bbox(
            px: float, py: float, bbox: list[float], s: float = 1.0
        ) -> float:
            dx = max(bbox[0] * s - px, 0, px - bbox[3] * s)
            dy = max(bbox[1] * s - py, 0, py - bbox[4] * s)
            return math.hypot(dx, dy)

        scale_factor = min(
            (10**p for p in range(-3, 5)),
            key=lambda s: min(dist_to_bbox(px0, py0, b, s) for b in bboxes.values()),
        )

        for port in ports:
            px, py = float(port.center[0]), float(port.center[1])
            available_objs = [obj for obj in bboxes if obj not in used_objects]
            if not available_objs:
                break

            def port_metric(
                obj_name: str, px: float = px, py: float = py
            ) -> tuple[float, float]:
                b = bboxes[obj_name]
                dist = dist_to_bbox(px, py, b, scale_factor)
                area = (b[3] - b[0]) * (b[4] - b[1]) * scale_factor**2
                return max(0.0, dist - 1.0), area

            best_obj = min(available_objs, key=port_metric)
            net_to_rename = next(
                (
                    b
                    for b in self.q3d.boundaries
                    if b.type == "SignalNet" and best_obj in b.props.get("Objects", [])
                ),
                None,
            )

            if net_to_rename is not None:
                net_to_rename.name = port.name
            else:
                self.q3d.assign_net(
                    assignment=[best_obj], net_name=port.name, net_type="Signal"
                )

            assigned_nets.append(port.name)
            used_objects.add(best_obj)

        return assigned_nets

    def get_capacitance_matrix(self, setup_name: str = "Q3DSetup") -> pl.DataFrame:
        """Extract the capacitance matrix from a Q3D Extractor simulation.

        Retrieves all capacitance matrix entries (e.g. ``C(o1,o1)``, ``C(o1,o2)``)
        from the solved Q3D setup.

        Args:
            setup_name: Name of the analysis setup.

        Returns:
            DataFrame with one column per capacitance expression containing
            the extracted values in Farads.
        """
        nets = [b.name for b in self.q3d.boundaries if b.type == "SignalNet"]
        expressions = [f"C({n1},{n2})" for i, n1 in enumerate(nets) for n2 in nets[i:]]
        data: dict[str, list[float]] = {}

        for expr in expressions:
            solution = self.q3d.post.get_solution_data(
                expressions=expr,
                setup_sweep_name=f"{setup_name} : LastAdaptive",
            )
            if solution and (val := _first_real_value(solution)) is not None:
                unit = solution.units_data.get(expr, "pF")
                multiplier = {
                    "fF": 1e-15,
                    "pF": 1e-12,
                    "nF": 1e-9,
                    "uF": 1e-6,
                    "mF": 1e-3,
                    "F": 1.0,
                }.get(str(unit), 1e-12)
                data[expr] = [val * multiplier]

        return pl.DataFrame(data)


def _get_level(layer_stack: LayerStack, name: str) -> LayerLevel:
    """Look up a level by name, requiring a thickness and a material.

    Returns:
        The layer level.

    Raises:
        ValueError: If the level is missing or has no thickness or material.
    """
    if name not in layer_stack.layers:
        raise ValueError(
            f"Layer stack has no level {name!r}; available: {sorted(layer_stack.layers)}"
        )
    level = layer_stack.layers[name]
    if not level.thickness or level.material is None:
        raise ValueError(f"Layer level {name!r} needs a thickness and a material")
    return level


class Q2D(AEDTBase):
    """Q2D simulation wrapper.

    Provides methods for 2D cross-sectional impedance extraction.
    """

    def __init__(
        self,
        q2d: Q2d,
        *,
        layer_stack: LayerStack | None = None,
        material_properties: MaterialProperties | None = None,
    ):
        """Initialize the Q2D wrapper.

        Args:
            q2d: The PyAEDT Q2d application instance.
            layer_stack: Default layer stack. None means the active PDK's.
            material_properties: Material table. Defaults to
                :data:`gplugins.ansys.DEFAULT_MATERIAL_PROPERTIES`.
        """
        super().__init__(
            q2d, layer_stack=layer_stack, material_properties=material_properties
        )
        self.q2d = q2d

    def create_2d_cpw(
        self,
        cpw_width: float,
        cpw_gap: float,
        layer_stack: LayerStack | None = None,
        *,
        substrate_level: str,
        conductor_level: str,
        ground_width: float | None = None,
        units: str = "um",
    ) -> dict[str, str]:
        """Create a 2D coplanar waveguide model for impedance extraction.

        Builds the cross-sectional geometry of a coplanar waveguide in Ansys Q2D
        (2D Extractor): a signal trace between two ground planes on top of a
        substrate, with the conductors assigned as signal line and reference
        ground.

        Args:
            cpw_width: Width of the centre conductor in µm.
            cpw_gap: Gap between the centre conductor and each ground in µm.
            layer_stack: LayerStack holding the substrate and conductor levels.
                If None, uses the wrapper's, else the active PDK's.
            substrate_level: Name of the substrate level in ``layer_stack``.
            conductor_level: Name of the conductor level in ``layer_stack``.
            ground_width: Width of each coplanar ground plane in µm. If None,
                defaults to 10 times the CPW gap.
            units: Length units for the Q2D geometry (default ``"um"``).

        Returns:
            Dictionary with keys ``"signal"``, ``"gnd_left"``, ``"gnd_right"``,
            ``"substrate"`` mapping to the created Q2D object names.

        Raises:
            ValueError: If the units are not ``"um"``, the dimensions are not
                positive, or a level is missing from the layer stack or has no
                thickness or material.
        """
        if units != "um":
            raise ValueError("Q2D cross-section expects units='um'")
        if cpw_width <= 0 or cpw_gap <= 0:
            raise ValueError(
                f"cpw_width and cpw_gap must be positive, got {cpw_width} and {cpw_gap}"
            )

        stack = self.resolve_layer_stack(layer_stack)
        substrate = _get_level(stack, substrate_level)
        substrate_thickness = float(substrate.thickness)
        substrate_material = cast(str, substrate.material)

        conductor = _get_level(stack, conductor_level)
        conductor_thickness = float(conductor.thickness)
        if conductor_thickness < 2.0:
            gf.logger.warning(
                "Setting conductor_thickness to 2.0 um for Q2D stability."
            )
            conductor_thickness = 2.0
        conductor_material = cast(str, conductor.material)

        if ground_width is None:
            ground_width = 10.0 * cpw_gap

        self.add_materials()
        self.modeler.model_units = units

        total_width = 2 * ground_width + 2 * cpw_gap + cpw_width
        substrate_margin = 50.0

        parts = [
            {
                "name": "signal",
                "origin": [ground_width + cpw_gap, 0, 0],
                "sizes": [cpw_width, conductor_thickness],
                "material": conductor_material,
            },
            {
                "name": "gnd_left",
                "origin": [0, 0, 0],
                "sizes": [ground_width, conductor_thickness],
                "material": conductor_material,
            },
            {
                "name": "gnd_right",
                "origin": [ground_width + cpw_gap + cpw_width + cpw_gap, 0, 0],
                "sizes": [ground_width, conductor_thickness],
                "material": conductor_material,
            },
            {
                "name": "substrate",
                "origin": [-substrate_margin, -substrate_thickness, 0],
                "sizes": [total_width + 2 * substrate_margin, substrate_thickness],
                "material": substrate_material,
            },
        ]

        objects = {
            part["name"]: self.modeler.create_rectangle(**part) for part in parts
        }

        self.q2d.assign_single_conductor(
            name="signal",
            assignment=[objects["signal"]],
            conductor_type="SignalLine",
            units=units,
        )
        self.q2d.assign_single_conductor(
            name="gnd",
            assignment=[objects["gnd_left"], objects["gnd_right"]],
            conductor_type="ReferenceGround",
            units=units,
        )

        self.app.mesh.assign_length_mesh(
            assignment=[objects["signal"], objects["gnd_left"], objects["gnd_right"]],
            maximum_length=2.0,
            maximum_elements=10000,
            name="thin_trace_mesh",
        )

        return {str(name): obj.name for name, obj in objects.items()}
