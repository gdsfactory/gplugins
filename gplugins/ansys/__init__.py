"""Ansys AEDT (HFSS, Q3D Extractor, 2D Extractor) simulations through PyAEDT.

The wrappers take an existing PyAEDT application, so opening and closing the AEDT
session stays in your hands.

**HFSS workflow:**

1. Create an ``ansys.aedt.core.Hfss`` application and wrap it in :class:`HFSS`.
2. Import a component with :meth:`HFSS.import_component`, add lumped ports with
   :meth:`HFSS.add_lumped_ports` and a vacuum box with :meth:`HFSS.add_air_region`.
3. Configure an eigenmode or driven setup through PyAEDT and solve it.
4. Read results with :meth:`HFSS.get_eigenmode_results` or
   :meth:`HFSS.get_sparameter_results`.

**Q3D Extractor workflow:**

1. Import a component with :meth:`Q3D.import_component`.
2. Assign signal nets with :meth:`Q3D.assign_nets_from_ports`.
3. Configure a setup through PyAEDT and solve it.
4. Read the capacitance matrix with :meth:`Q3D.get_capacitance_matrix`.

**2D Extractor:** :meth:`Q2D.create_2d_cpw` draws a coplanar waveguide cross
section for impedance extraction.

Layers are mapped to 3D objects through a gdsfactory ``LayerStack`` (the active
PDK's by default), and materials through ``material_properties``
(:data:`DEFAULT_MATERIAL_PROPERTIES` by default).

Note:
    Requires ``pip install "gplugins[ansys]"`` and a local Ansys Electronics
    Desktop installation with a licence.

References:
    - PyAEDT documentation: https://aedt.docs.pyansys.com/
    - HFSS import_gds_3d: https://aedt.docs.pyansys.com/version/stable/API/_autosummary/ansys.aedt.core.hfss.Hfss.import_gds_3d.html
    - Q3D Extractor: https://aedt.docs.pyansys.com/version/stable/API/_autosummary/ansys.aedt.core.q3d.Q3d.html
"""

from gplugins.ansys.base import (
    DEFAULT_MATERIAL_PROPERTIES,
    AEDTBase,
    MaterialProperties,
    add_materials_to_aedt,
    detach_desktop_logging,
    export_component_to_gds_temp,
    fit_view,
    layer_stack_to_gds_mapping,
    object_names_to_materials,
    rename_imported_objects,
)
from gplugins.ansys.hfss import HFSS, LumpedPortConfig, lumped_port_rectangle_from_cpw
from gplugins.ansys.q3d import Q2D, Q3D

__all__ = [
    "DEFAULT_MATERIAL_PROPERTIES",
    "HFSS",
    "Q2D",
    "Q3D",
    "AEDTBase",
    "LumpedPortConfig",
    "MaterialProperties",
    "add_materials_to_aedt",
    "detach_desktop_logging",
    "export_component_to_gds_temp",
    "fit_view",
    "layer_stack_to_gds_mapping",
    "lumped_port_rectangle_from_cpw",
    "object_names_to_materials",
    "rename_imported_objects",
]
