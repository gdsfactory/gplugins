"""An MPh model with layout, study, and mesh methods.

:class:`COMSOL` keeps the extracted layout with the model while retaining MPh's
solve, save, and evaluation API. Import it from :mod:`gplugins.comsol`
after installing the optional ``comsol`` extra (``pip install gplugins[comsol]``).
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from types import SimpleNamespace
from typing import TYPE_CHECKING, Self

from gplugins.comsol import (
    capacitance,
    mesh,
    metal,
    rf,
    sheet,
)

if TYPE_CHECKING:
    import mph

    from gplugins.comsol.layout import ComsolBoundingBox, ComsolLayout, Point
else:
    try:
        mph = importlib.import_module("mph")
    except ModuleNotFoundError as error:
        if error.name != "mph":
            raise
        mph = SimpleNamespace(Model=object)


class COMSOL(mph.Model):
    """An MPh model holding the layout its geometry was built from.

    Use :meth:`create_sheet` or :meth:`create_metal` to build one. The study and
    mesh methods then use the stored layout. Study methods return the model for
    chaining; mesh methods return the resulting element count.
    """

    def __init__(self, model: mph.Model, layout: ComsolLayout) -> None:
        """Wrap an already created MPh model and the layout behind it.

        Args:
            model: The model a builder returned, e.g.
                :func:`~gplugins.comsol.sheet.build_comsol_sheet_model`.
                Its Java handle is reused as-is.
            layout: The layout that model was built from.

        Raises:
            ImportError: If the optional MPh dependency is not installed.
        """
        if mph.Model is object:
            raise ImportError("Install gplugins[comsol] to use the COMSOL model")
        super().__init__(model)
        self.layout = layout

    @classmethod
    def create_sheet(
        cls,
        client: mph.Client,
        layout: ComsolLayout,
        name: str,
        *,
        substrate_thickness_um: float = 200.0,
        air_height_um: float = 200.0,
        lateral_margin_um: float = 0.0,
        silicon_relative_permittivity: float = sheet.SILICON_RELATIVE_PERMITTIVITY,
        air_relative_permittivity: float = sheet.AIR_RELATIVE_PERMITTIVITY,
    ) -> Self:
        """Build a sheet model, with the metal as faces on the z = 0 interface.

        Args:
            client: A connected :class:`mph.Client`.
            layout: Extracted metal polygons and bounding box in µm.
            name: Name of the COMSOL model.
            substrate_thickness_um: Silicon thickness below the interface, in µm.
            air_height_um: Air height above the interface, in µm.
            lateral_margin_um: Margin around the layout bounding box for both
                blocks, in µm. Leave it at 0 for :meth:`add_cpw_rf_study`, whose
                ports have to sit on the outer faces where the feed metal ends.
            silicon_relative_permittivity: Relative permittivity of the silicon
                block, positive and finite.
            air_relative_permittivity: Relative permittivity of the air block,
                positive and finite.

        Returns:
            The built model, holding the layout it was built from. The builder
            validates the thicknesses, the margin, the permittivity, and the
            resulting geometry, and a layout with holes needs the Design Module
            licence.
        """
        return cls(
            sheet.build_comsol_sheet_model(
                client,
                layout,
                name,
                substrate_thickness_um=substrate_thickness_um,
                air_height_um=air_height_um,
                lateral_margin_um=lateral_margin_um,
                silicon_relative_permittivity=silicon_relative_permittivity,
                air_relative_permittivity=air_relative_permittivity,
            ),
            layout,
        )

    @classmethod
    def create_metal(
        cls,
        client: mph.Client,
        layout: ComsolLayout,
        *,
        metal_thickness_um: float = 0.2,
        name: str = "gdsfactory metal",
    ) -> Self:
        """Build a metal model, with the polygons extruded to a thickness.

        The layout-agnostic geometry milestone: no physics, materials, ports, or
        studies, and the feed ports are not used.

        Args:
            client: A connected :class:`mph.Client`.
            layout: Extracted metal polygons and feed ports in µm.
            metal_thickness_um: Extrusion height in µm, strictly positive.
            name: Name of the COMSOL model.

        Returns:
            The built model, holding the layout it was built from. The builder
            validates the thickness and refuses a layout with no polygons.
        """
        return cls(
            metal.build_comsol_metal_model(
                client,
                layout,
                metal_thickness_um=metal_thickness_um,
                name=name,
            ),
            layout,
        )

    def add_cpw_rf_study(
        self,
        *,
        cpw_gap_um: float,
        frequency_ghz: float = 7.5,
        mesh_size: int = 8,
        effective_index_shift: float = 2.5,
    ) -> Self:
        """Add an unsolved CPW full-wave study.

        Calls :func:`~gplugins.comsol.rf.add_cpw_rf_study` on this model
        and its layout. The model has to be a sheet model whose layout was
        extracted with ``crop_to_feed_ports=True``.

        Args:
            cpw_gap_um: Width of the etch gap between the centre conductor and
                the ground at the ports, in µm.
            frequency_ghz: Boundary mode analysis reference and initial
                frequency in GHz.
            mesh_size: COMSOL mesh size, an integer from 1 (finest) to 9
                (coarsest).
            effective_index_shift: Effective-index shift both boundary mode
                analyses search around, positive and finite.

        Returns:
            This model, so the call chains.
        """
        rf.add_cpw_rf_study(
            self,
            self.layout,
            cpw_gap_um=cpw_gap_um,
            frequency_ghz=frequency_ghz,
            mesh_size=mesh_size,
            effective_index_shift=effective_index_shift,
        )
        return self

    def add_capacitance_study(
        self,
        *,
        conductors: tuple[tuple[str, Point], ...],
        terminal: str,
        grounds: tuple[str, ...],
        voltage_v: float = 1.0,
        mesh_size: int = 7,
    ) -> Self:
        """Add an unsolved electrostatic capacitance study.

        Calls
        :func:`~gplugins.comsol.capacitance.add_capacitance_study` on
        this model and its layout.

        Args:
            conductors: One ``(tag, point)`` pair per metal face. The tag names
                the face selection created on ``comp1``, and the point in µm on
                the sheet plane sits well inside that face.
            terminal: Tag of the conductor to drive with the voltage terminal.
            grounds: Tags of the conductors to ground. Together with ``terminal``
                they name every conductor exactly once.
            voltage_v: Terminal voltage in V, positive.
            mesh_size: COMSOL mesh size, an integer from 1 (finest) to 9
                (coarsest).

        Returns:
            This model, so the call chains.
        """
        capacitance.add_capacitance_study(
            self,
            self.layout,
            conductors=conductors,
            terminal=terminal,
            grounds=grounds,
            voltage_v=voltage_v,
            mesh_size=mesh_size,
        )
        return self

    def refine_metal_plane_mesh(
        self,
        passes: int,
        *,
        z_half_um: float = 20.0,
        refine_box: ComsolBoundingBox | None = None,
    ) -> int:
        """Mesh and refine around the metal plane.

        Calls :func:`~gplugins.comsol.mesh.refine_metal_plane_mesh` on
        this model and its layout.

        Args:
            passes: Number of refinement passes, a non-negative integer.
            z_half_um: Half-height in µm of the refine box above and below the
                metal plane.
            refine_box: x/y bounds in µm to refine instead of the layout bounding
                box.

        Returns:
            The number of mesh elements after meshing.
        """
        return mesh.refine_metal_plane_mesh(
            self, self.layout, passes, z_half_um=z_half_um, refine_box=refine_box
        )

    def pin_absolute_mesh_sizes(
        self,
        *,
        global_hmax_um: float,
        global_hmin_um: float,
        face_sizes: Mapping[str, tuple[float, float]],
        hgrad: float | None = None,
        hcurve: float | None = None,
        hnarrow: float | None = None,
    ) -> int:
        """Mesh at absolute element sizes.

        Calls :func:`~gplugins.comsol.mesh.pin_absolute_mesh_sizes` on
        this model and its layout.

        Args:
            global_hmax_um: Largest element size in µm away from the metal.
            global_hmin_um: Smallest element size in µm away from the metal.
            face_sizes: ``(hmax, hmin)`` element sizes in µm keyed by the name of
                a face selection on ``comp1``.
            hgrad: Maximum element growth rate for the global sizes.
            hcurve: Curvature resolution for the global sizes, in elements per
                radian.
            hnarrow: Narrow region resolution for the global sizes.

        Returns:
            The number of mesh elements the pinned sequence built.
        """
        return mesh.pin_absolute_mesh_sizes(
            self,
            global_hmax_um=global_hmax_um,
            global_hmin_um=global_hmin_um,
            face_sizes=face_sizes,
            hgrad=hgrad,
            hcurve=hcurve,
            hnarrow=hnarrow,
        )

    def pin_absolute_edge_mesh_sizes(
        self,
        *,
        edge_selection: str,
        global_hmax_um: float,
        global_hmin_um: float,
        edge_hmax_um: float,
        edge_hmin_um: float,
    ) -> int:
        """Mesh at absolute element sizes on a named edge selection.

        Calls
        :func:`~gplugins.comsol.mesh.pin_absolute_edge_mesh_sizes` on
        this model and its layout.

        Args:
            edge_selection: Name of the edge selection to pin the local sizes on.
            global_hmax_um: Largest element size in µm away from the edges.
            global_hmin_um: Smallest element size in µm away from the edges.
            edge_hmax_um: Largest element size in µm on the selected edges.
            edge_hmin_um: Smallest element size in µm on the selected edges.

        Returns:
            The number of mesh elements the pinned sequence built.
        """
        return mesh.pin_absolute_edge_mesh_sizes(
            self,
            edge_selection=edge_selection,
            global_hmax_um=global_hmax_um,
            global_hmin_um=global_hmin_um,
            edge_hmax_um=edge_hmax_um,
            edge_hmin_um=edge_hmin_um,
        )
