"""HFSS simulation utilities using PyAEDT."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import numpy as np
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
    from ansys.aedt.core import Hfss
    from gdsfactory.component import Component
    from gdsfactory.technology import LayerStack
    from gdsfactory.typings import Ports

    from gplugins.ansys.base import MaterialProperties


class LumpedPortConfig(TypedDict):
    """Configuration for defining a lumped port rectangle in HFSS."""

    origin: list[float]
    sizes: list[float]
    integration_line: list[list[float]]


def lumped_port_rectangle_from_cpw(
    center: tuple[float, float, float],
    orientation: float,
    cpw_gap: float,
    cpw_width: float,
) -> LumpedPortConfig:
    """Calculates parameters for a lumped port based on its orientation.

    Args:
        center: [x, y, z] coordinates of the port face center.
        orientation: Angle in degrees (must be a multiple of 90).
        cpw_gap: The length of the port along the axis of propagation.
        cpw_width: The width of the port perpendicular to propagation.

    Returns:
        A dictionary containing 'origin', 'sizes', and 'integration_line' for HFSS.

    Raises:
        ValueError: If port orientation is not a multiple of 90 degrees.
    """
    if orientation % 90 != 0:
        raise ValueError(f"Unsupported port orientation: {orientation}°")

    cx, cy = center[0], center[1]
    theta = np.deg2rad(orientation)
    c = np.round(np.cos(theta))
    s = np.round(np.sin(theta))

    size_x = cpw_gap * np.abs(c) + cpw_width * np.abs(s)
    size_y = cpw_width * np.abs(c) + cpw_gap * np.abs(s)

    rect_cx = cx + (cpw_gap / 2) * c
    rect_cy = cy + (cpw_gap / 2) * s

    origin = [rect_cx - size_x / 2, rect_cy - size_y / 2, 0]
    int_line = [[cx + cpw_gap * c, cy + cpw_gap * s, 0], [cx, cy, 0]]

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

        Args:
            component: The gdsfactory component to import.
            layer_stack: LayerStack defining thickness and elevation for each layer.
                If None, uses the wrapper's, else the active PDK's.
            import_as_sheets: If True, imports metals as 2D sheets (zero thickness)
                and assigns PerfectE boundary to them. If False, imports as 3D
                objects with thickness from layer_stack and assigns PerfectE
                boundary to their surfaces.
            units: Length units for the geometry (default: "um" for micrometers).
            gds_path: Optional path to write the GDS file. If None, uses a temporary file.

        Returns:
            True if import was successful, False otherwise.
        """
        stack = self.resolve_layer_stack(layer_stack)
        thickness_override = 0.0 if import_as_sheets else None
        mapping_layers = layer_stack_to_gds_mapping(
            stack, thickness_override=thickness_override
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

            if result:
                new_objects = list(set(self.modeler.object_names) - existing_objects)

                renamed_objects = rename_imported_objects(self.hfss, new_objects, stack)

                # PerfectE is a conductor boundary: assign it only to metal
                # levels, not to dielectric objects such as the substrate.
                conductor_objects = [
                    obj_name
                    for obj_name, material in object_names_to_materials(
                        renamed_objects, stack, self.material_properties
                    ).items()
                    if material == "pec"
                ]

                if conductor_objects:
                    if import_as_sheets:
                        self.hfss.assign_perfecte_to_sheets(
                            conductor_objects, name="PEC_Sheets"
                        )
                    else:
                        self.hfss.assign_perfect_e(conductor_objects, name="PEC_3D")

        return result

    def add_lumped_ports(self, ports: Ports, cpw_gap: float, cpw_width: float) -> None:
        """Add lumped ports to HFSS at given port locations.

        Args:
            ports: Collection of gdsfactory ports defining signal locations.
            cpw_gap: The length of the port along the axis of propagation.
            cpw_width: The width of the port perpendicular to propagation.
        """
        for port in ports:
            params = lumped_port_rectangle_from_cpw(
                port.center, port.orientation, cpw_gap, cpw_width
            )
            port_rect = self.modeler.create_rectangle(
                orientation="XY", name=f"{port.name}_face", **params
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
    ) -> str:
        """Add an air region (vacuum box) around the component.

        Args:
            component: The component to create air region around.
            height: Height above the component in micrometers.
            substrate_thickness: Depth below surface for the region.
            pec_boundary: If True, assign PerfectE boundary conditions to outer faces.
            name: Name of the created region object.

        Returns:
            Name of the created region object.
        """
        bounds = component.bbox()
        x_min, y_min = bounds.p1.x, bounds.p1.y
        dx, dy = bounds.p2.x - x_min, bounds.p2.y - y_min

        region = self.modeler.create_box(
            origin=[x_min, y_min, -substrate_thickness],
            sizes=[dx, dy, height + substrate_thickness],
            name=name,
            material="vacuum",
        )
        region.mesh_order = 99

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
        """Extract S-parameter results from a driven simulation.

        Args:
            setup_name: Name of the setup.
            sweep_name: Name of the frequency sweep.

        Returns:
            DataFrame containing a 'frequency_ghz' column and a column
            for each S-parameter trace (e.g., "S(1,1)") containing complex values.
        """
        traces = self.hfss.get_traces_for_plot()
        data = {}

        for trace in traces:
            solution = self.hfss.post.get_solution_data(
                expressions=trace,
                setup_sweep_name=f"{setup_name} : {sweep_name}",
            )
            if solution:
                if "frequency_ghz" not in data:
                    data["frequency_ghz"] = np.array(solution.primary_sweep_values)

                # Use get_expression_data to get real and imaginary parts
                _, real_data = solution.get_expression_data(formula="real")
                _, imag_data = solution.get_expression_data(formula="imag")
                data[trace] = real_data + 1j * imag_data

        return pl.DataFrame(data)
