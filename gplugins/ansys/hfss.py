"""HFSS simulation utilities using PyAEDT."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import numpy as np
import polars as pl

from gplugins.ansys.base import (
    AEDTBase,
    _first_real_value,
    conductor_materials,
    export_component_to_gds_temp,
    layer_stack_to_gds_mapping,
    logger,
    object_names_to_materials,
    rename_imported_objects,
)

if TYPE_CHECKING:
    from ansys.aedt.core import Hfss
    from gdsfactory.component import Component
    from gdsfactory.technology import LayerStack
    from gdsfactory.typings import Ports

    from gplugins.ansys.base import MaterialProperties


_FREQUENCY_TO_GHZ = {
    "Hz": 1e-9,
    "kHz": 1e-6,
    "MHz": 1e-3,
    "GHz": 1.0,
    "THz": 1e3,
}


def _to_ghz(unit: str | None, what: str, default: str) -> float:
    """Return the factor converting a frequency in ``unit`` to GHz.

    Args:
        unit: Unit AEDT reported. None or empty means ``default``.
        what: What the unit belongs to, for the error message.
        default: Unit to assume when AEDT reports none.

    Raises:
        ValueError: If the unit is not a known frequency unit.
    """
    unit = (unit or "").strip() or default
    if unit not in _FREQUENCY_TO_GHZ:
        raise ValueError(
            f"Unknown frequency unit {unit!r} for {what}; expected one of"
            f" {sorted(_FREQUENCY_TO_GHZ)}"
        )
    return _FREQUENCY_TO_GHZ[unit]


class LumpedPortConfig(TypedDict):
    """Configuration for defining a lumped port rectangle in HFSS."""

    origin: list[float]
    sizes: list[float]
    integration_line: list[list[float]]


def lumped_port_rectangle_from_cpw(
    center: tuple[float, float, float] | tuple[float, float],
    orientation: float | None,
    cpw_gap: float,
    cpw_width: float,
) -> LumpedPortConfig:
    """Calculates parameters for a lumped port based on its orientation.

    Args:
        center: [x, y, z] coordinates of the port face center. A 2D center is
            placed at z = 0.
        orientation: Angle in degrees (must be a multiple of 90).
        cpw_gap: The length of the port along the axis of propagation.
        cpw_width: The width of the port perpendicular to propagation.

    Returns:
        A dictionary containing 'origin', 'sizes', and 'integration_line' for HFSS.

    Raises:
        ValueError: If port orientation is None or not a multiple of 90 degrees.
    """
    if orientation is None:
        raise ValueError("Port has no orientation; a lumped port needs one")
    if orientation % 90 != 0:
        raise ValueError(f"Unsupported port orientation: {orientation}°")

    cx, cy = center[0], center[1]
    cz = float(center[2]) if len(center) > 2 else 0.0
    theta = np.deg2rad(orientation)
    c = np.round(np.cos(theta))
    s = np.round(np.sin(theta))

    size_x = cpw_gap * np.abs(c) + cpw_width * np.abs(s)
    size_y = cpw_width * np.abs(c) + cpw_gap * np.abs(s)

    rect_cx = cx + (cpw_gap / 2) * c
    rect_cy = cy + (cpw_gap / 2) * s

    origin = [rect_cx - size_x / 2, rect_cy - size_y / 2, cz]
    int_line = [[cx + cpw_gap * c, cy + cpw_gap * s, cz], [cx, cy, cz]]

    return {"origin": origin, "sizes": [size_x, size_y], "integration_line": int_line}


class HFSS(AEDTBase):
    """HFSS simulation wrapper.

    Provides high-level methods for importing components into HFSS,
    setting up simulation regions, and extracting results.
    """

    def __init__(
        self,
        hfss: Hfss,
        *,
        layer_stack: LayerStack | None = None,
        material_properties: MaterialProperties | None = None,
    ):
        """Initialize the HFSS wrapper.

        Args:
            hfss: The PyAEDT Hfss application instance.
            layer_stack: Default layer stack for imports. None means the active
                PDK's.
            material_properties: Material table. Defaults to
                :data:`gplugins.ansys.DEFAULT_MATERIAL_PROPERTIES`.
        """
        super().__init__(
            hfss, layer_stack=layer_stack, material_properties=material_properties
        )
        self.hfss = hfss

    def import_component(
        self,
        component: Component,
        layer_stack: LayerStack | None = None,
        *,
        import_as_sheets: bool = False,
        units: str = "um",
        gds_path: str | Path | None = None,
    ) -> bool:
        """Import a gdsfactory component into HFSS.

        Conductor levels (materials with infinite permittivity) get a PerfectE
        boundary; every other level gets its layer stack material, after the
        material table is added to the project.

        Args:
            component: The gdsfactory component to import.
            layer_stack: LayerStack defining thickness and elevation for each layer.
                If None, uses the wrapper's, else the active PDK's.
            import_as_sheets: If True, imports conductor levels as 2D sheets (zero
                thickness) and assigns a PerfectE boundary to them; dielectric
                levels keep their thickness. If False, imports everything as 3D
                objects with thickness from layer_stack and assigns PerfectE to
                the conductors.
            units: Length units of the geometry. Only ``"um"`` is supported, as
                the layer stack is in µm.
            gds_path: Optional path to write the GDS file. If None, uses a temporary file.

        Returns:
            True. Failures raise.

        Raises:
            ValueError: If ``units`` is not ``"um"``.
            RuntimeError: If the GDS import fails.
        """
        if units != "um":
            raise ValueError(
                f"HFSS import expects units='um' (the layer stack is in µm), got {units!r}"
            )
        stack = self.resolve_layer_stack(layer_stack)
        mapping_layers = layer_stack_to_gds_mapping(
            stack,
            thickness_override=0.0 if import_as_sheets else None,
            override_materials=conductor_materials(self.material_properties),
        )

        with export_component_to_gds_temp(
            component, gds_path, prefix="gplugins_hfss_"
        ) as path:
            self.modeler.model_units = units
            existing_objects = set(self.modeler.object_names)

            result = self.hfss.import_gds_3d(
                input_file=str(path),
                mapping_layers=mapping_layers,
                units=units,
                import_method=0,
            )
            if not result:
                raise RuntimeError("HFSS GDS import failed")

            new_objects = list(set(self.modeler.object_names) - existing_objects)
            renamed_objects = rename_imported_objects(self.hfss, new_objects, stack)

            self.add_materials()
            by_material: dict[str, list[str]] = {}
            for obj_name, material in object_names_to_materials(
                renamed_objects, stack, self.material_properties
            ).items():
                by_material.setdefault(material, []).append(obj_name)

            # PerfectE is a conductor boundary: conductors get it instead of a
            # material, dielectrics such as the substrate get their material.
            conductor_objects = by_material.pop("pec", [])
            for material, objects in by_material.items():
                self.hfss.assign_material(objects, material)

            if conductor_objects:
                if import_as_sheets:
                    self.hfss.assign_perfecte_to_sheets(
                        conductor_objects, name="PEC_Sheets"
                    )
                else:
                    self.hfss.assign_perfect_e(conductor_objects, name="PEC_3D")

        return True

    def add_lumped_ports(
        self,
        ports: Ports,
        cpw_gap: float,
        cpw_width: float,
        *,
        elevation: float = 0.0,
    ) -> None:
        """Add lumped ports to HFSS at given port locations.

        Args:
            ports: Collection of gdsfactory ports defining signal locations.
            cpw_gap: The length of the port along the axis of propagation.
            cpw_width: The width of the port perpendicular to propagation.
            elevation: z of the port sheets in µm, i.e. the conductor's plane.

        Raises:
            ValueError: If a port has no orientation or one that is not a
                multiple of 90 degrees.
        """
        for port in ports:
            try:
                params = lumped_port_rectangle_from_cpw(
                    (*port.center, elevation), port.orientation, cpw_gap, cpw_width
                )
            except ValueError as error:
                raise ValueError(f"Port {port.name!r}: {error}") from error
            port_rect = self.modeler.create_rectangle(
                orientation="XY",
                origin=params["origin"],
                sizes=params["sizes"],
                name=f"{port.name}_face",
            )
            self.hfss.lumped_port(
                assignment=port_rect.name,
                name=port.name,
                create_port_sheet=False,
                integration_line=params["integration_line"],
            )

    def add_air_region(
        self,
        component: Component,
        height: float = 500.0,
        substrate_thickness: float = 500.0,
        pec_boundary: bool = False,
        name: str = "AirRegion",
        *,
        lateral_margin: float = 0.0,
    ) -> str:
        """Add an air region (vacuum box) around the component.

        Args:
            component: The component to create air region around.
            height: Height above the component in micrometers.
            substrate_thickness: Depth below surface for the region.
            pec_boundary: If True, assign PerfectE boundary conditions to outer faces.
            name: Name of the created region object.
            lateral_margin: Clearance in µm added on every side of the component's
                bounding box, so a radiation boundary on the box does not touch
                the geometry.

        Returns:
            Name of the created region object.

        Raises:
            ValueError: If ``lateral_margin`` is negative.
        """
        if lateral_margin < 0:
            raise ValueError(f"lateral_margin must be >= 0, got {lateral_margin}")
        bounds = component.bbox()
        x_min, y_min = bounds.p1.x - lateral_margin, bounds.p1.y - lateral_margin
        dx = bounds.p2.x + lateral_margin - x_min
        dy = bounds.p2.y + lateral_margin - y_min

        region = self.modeler.create_box(
            origin=[x_min, y_min, -substrate_thickness],
            sizes=[dx, dy, height + substrate_thickness],
            name=name,
            material="vacuum",
        )

        if pec_boundary:
            self.hfss.assign_perfect_e(
                assignment=[face.id for face in region.faces],
                name="PEC_Boundary",
            )
        return region.name

    def get_eigenmode_results(self, setup_name: str = "EigenmodeSetup") -> dict:
        """Extract eigenmode simulation results.

        Args:
            setup_name: Name of the setup to get results from.

        Returns:
            Dictionary containing:
            - frequencies: List of eigenmode frequencies in GHz
            - q_factors: List of Q factors for each mode
        """
        # Get frequency values
        freq_names = self.hfss.post.available_report_quantities(
            quantities_category="Eigen Modes"
        )
        q_names = self.hfss.post.available_report_quantities(
            quantities_category="Eigen Q"
        )

        results = {"frequencies": [], "q_factors": [], "setup": setup_name}

        for f_name in freq_names:
            solution = self.hfss.post.get_solution_data(
                expressions=f_name, report_category="Eigenmode"
            )
            if solution and (freq_hz := _first_real_value(solution)) is not None:
                results["frequencies"].append(freq_hz / 1e9)

        for q_name in q_names:
            solution = self.hfss.post.get_solution_data(
                expressions=q_name, report_category="Eigenmode"
            )
            if solution and (q := _first_real_value(solution)) is not None:
                results["q_factors"].append(q)

        return results

    def get_sparameter_results(
        self, setup_name: str = "DrivenSetup", sweep_name: str = "FrequencySweep"
    ) -> pl.DataFrame:
        """Extract complex S-parameters from a driven simulation.

        Polars has no complex dtype, so each S-parameter is returned as two
        float columns, its real and imaginary parts.

        Args:
            setup_name: Name of the setup.
            sweep_name: Name of the frequency sweep.

        Returns:
            DataFrame with a ``frequency_ghz`` column and, for each S-parameter
            ``S(i,j)``, Float64 columns ``re(S(i,j))`` and ``im(S(i,j))``. Rebuild
            the complex value with ``df["re(S(i,j))"] + 1j * df["im(S(i,j))"]``
            on the NumPy arrays. Traces without samples are skipped with a
            warning.

        Raises:
            ValueError: If the sweep is in an unknown frequency unit, or traces
                have different numbers of samples.
        """
        traces = self.hfss.get_traces_for_plot(category="S")
        data: dict[str, np.ndarray] = {}

        for trace in traces:
            solution = self.hfss.post.get_solution_data(
                expressions=trace,
                setup_sweep_name=f"{setup_name} : {sweep_name}",
            )
            if not solution:
                logger.warning(f"No solution data for {trace}; skipping it.")
                continue

            _, real = solution.get_expression_data(expression=trace, formula="real")
            _, imag = solution.get_expression_data(expression=trace, formula="imag")
            if real is None or imag is None or len(real) == 0:
                logger.warning(f"{trace} has no samples; skipping it.")
                continue

            if "frequency_ghz" not in data:
                sweep_unit = solution.units_sweeps.get(solution.primary_sweep)
                data["frequency_ghz"] = np.asarray(
                    solution.primary_sweep_values, dtype=float
                ) * _to_ghz(sweep_unit, f"sweep {sweep_name!r}", "GHz")

            real = np.asarray(real, dtype=float)
            imag = np.asarray(imag, dtype=float)
            n = len(data["frequency_ghz"])
            if len(real) != n or len(imag) != n:
                raise ValueError(
                    f"{trace} has {len(real)} real and {len(imag)} imaginary samples"
                    f" for {n} sweep points"
                )
            data[f"re({trace})"] = real
            data[f"im({trace})"] = imag

        return pl.DataFrame(data)
