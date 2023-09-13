from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

CDict = dict[tuple[str, str], float]
RFMaterialSpec = dict[str, dict[str, float | int]]


class ElectrostaticResults(BaseModel):
    """Results class for electrostatic simulations."""

    capacitance_matrix: CDict
    mesh_location: Path | None = None
    field_file_location: Path | None = None

    # TODO uncomment after move to pydantic v2
    # @computed_field
    # @cached_property
    # def raw_capacitance_matrix(self) -> ndarray:
    #     n = int(sqrt(len(self.capacitance_matrix)))
    #     matrix = zeros((n, n))

    #     port_to_index_map = {}
    #     for iname, jname in self.capacitance_matrix.keys():
    #         if iname not in port_to_index_map:
    #             port_to_index_map[iname] = len(port_to_index_map) + 1
    #         if jname not in port_to_index_map:
    #             port_to_index_map[jname] = len(port_to_index_map) + 1

    #     for (iname, jname), c in self.capacitance_matrix.items():
    #         matrix[port_to_index_map[iname], port_to_index_map[jname]] = c

    #     return matrix


class DrivenFullWaveResults(BaseModel):
    """Results class for driven full-wave simulations."""

    scattering_matrix: Any  # TODO convert to SDict or similar
    mesh_location: Path | None = None
    field_file_locations: Sequence[Path] | None = None


__all__ = (
    "CDict",
    "DrivenFullWaveResults",
    "ElectrostaticResults",
    "RFMaterialSpec",
)
