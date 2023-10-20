from __future__ import annotations

from collections.abc import Sequence
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, computed_field

from ..types import CapacitanceDict, ScatteringDict


def _raw_matrix_from_dict(dict_matrix: CapacitanceDict | ScatteringDict) -> NDArray:
    """Converts dictionary formatted matrix results to a NumPy array.

    Args:
        dict_matrix: Dictionary with matrix results in ``(port_i, port_j): result`` configuration.

    Returns:
        ndarray: A matrix representation of the connections.
    """
    n = int(np.sqrt(len(dict_matrix)))
    matrix = np.zeros((n, n))

    port_to_index_map = {}
    for iname, jname in dict_matrix.keys():
        if iname not in port_to_index_map:
            port_to_index_map[iname] = len(port_to_index_map)
        if jname not in port_to_index_map:
            port_to_index_map[jname] = len(port_to_index_map)

    for (iname, jname), c in dict_matrix.items():
        matrix[port_to_index_map[iname], port_to_index_map[jname]] = c

    return matrix


class ElectrostaticResults(BaseModel):
    """Results class for electrostatic simulations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    capacitance_matrix: CapacitanceDict
    mesh_location: Path | None = None
    field_file_location: Path | None = None

    @computed_field
    @cached_property
    def raw_capacitance_matrix(self) -> NDArray:
        """Capacitance matrix as a NumPy array."""
        return _raw_matrix_from_dict(self.capacitance_matrix)


class DrivenFullWaveResults(BaseModel):
    """Results class for driven full-wave simulations."""

    scattering_matrix: Any  # TODO convert dataframe to ScatteringDict
    mesh_location: Path | None = None
    field_file_locations: Sequence[Path] | None = None

    # @computed_field
    # @cached_property
    # def raw_scattering_matrix(self) -> NDArray:
    #     """Scattering matrix as a NumPy array."""
    #     return _raw_matrix_from_dict(self.scattering_matrix)
