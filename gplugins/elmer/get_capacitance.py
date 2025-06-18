from __future__ import annotations

import inspect
import itertools
import shutil
from collections.abc import Iterable, Mapping, Sequence
from math import inf
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import gdsfactory as gf
import gmsh
from gdsfactory.generic_tech import LAYER_STACK
from gdsfactory.technology import LayerStack
from jinja2 import Environment, FileSystemLoader
from numpy import isfinite
from pandas import read_csv

from gplugins.common.base_models.simulation import ElectrostaticResults
from gplugins.common.types import RFMaterialSpec
from gplugins.common.utils.async_helpers import (
    execute_and_stream_output,
    run_async_with_event_loop,
)
from gplugins.gmsh import get_mesh

ELECTROSTATIC_SIF = "electrostatic.sif"
ELECTROSTATIC_TEMPLATE = Path(__file__).parent / f"{ELECTROSTATIC_SIF}.j2"


def _generate_sif(
    simulation_folder: Path,
    name: str,
    signals: Sequence[Sequence[str]],
    bodies: dict[str, dict[str, Any]],
    ground_layers: Iterable[str],
    layer_stack: LayerStack,
    material_spec: RFMaterialSpec,
    element_order: int,
    background_tag: str | None = None,
    simulator_params: Mapping[str, Any] | None = None,
) -> None:
    # pylint: disable=unused-argument
    """Generates a sif file for Elmer simulations using Jinja2."""
    # Have background_tag as first s.t. unaccounted elements use it by default
    used_materials = ({background_tag} if background_tag else {}) | {
        v.material for v in layer_stack.layers.values()
    }
    used_materials = {
        k: material_spec[k]
        for k in used_materials
        if isfinite(material_spec[k].get("relative_permittivity", inf))
    }

    sif_template = Environment(
        loader=FileSystemLoader(ELECTROSTATIC_TEMPLATE.parent)
    ).get_template(ELECTROSTATIC_TEMPLATE.name)
    output = sif_template.render(**locals())
    with open(simulation_folder / f"{name}.sif", "w", encoding="utf-8") as fp:
        fp.write(output)


def _elmergrid(simulation_folder: Path, name: str, n_processes: int = 1) -> None:
    """Run ElmerGrid for converting gmsh mesh to Elmer format."""
    elmergrid = shutil.which("ElmerGrid")
    if elmergrid is None:
        raise RuntimeError(
            "`ElmerGrid` not found. Make sure it is available in your PATH."
        )
    run_async_with_event_loop(
        execute_and_stream_output(
            [elmergrid, "14", "2", name, "-autoclean"],
            shell=False,
            log_file_dir=simulation_folder,
            log_file_str=Path(name).stem + "_ElmerGrid",
            cwd=simulation_folder,
        )
    )
    if n_processes > 1:
        run_async_with_event_loop(
            execute_and_stream_output(
                [
                    elmergrid,
                    "2",
                    "2",
                    f"{Path(name).stem}/",
                    "-metiskway",
                    str(n_processes),
                    "4",
                    "-removeunused",
                ],
                shell=False,
                append=True,
                log_file_dir=simulation_folder,
                log_file_str=Path(name).stem + "_ElmerGrid",
                cwd=simulation_folder,
            )
        )


def _elmersolver(simulation_folder: Path, name: str, n_processes: int = 1) -> None:
    """Run simulations with ElmerFEM."""
    elmersolver_name = (
        "ElmerSolver" if (no_mpi := n_processes == 1) else "ElmerSolver_mpi"
    )
    elmersolver = shutil.which(elmersolver_name)
    if elmersolver is None:
        raise RuntimeError(
            f"`{elmersolver_name}` not found. Make sure it is available in your PATH."
        )
    sif_file = str(simulation_folder / f"{Path(name).stem}.sif")
    run_async_with_event_loop(
        execute_and_stream_output(
            [elmersolver, sif_file]
            if no_mpi
            else ["mpiexec", "-np", str(n_processes), elmersolver, sif_file],
            shell=False,
            log_file_dir=simulation_folder,
            log_file_str=Path(name).stem + "_ElmerSolver",
            cwd=simulation_folder,
        )
    )


def _read_elmer_results(
    simulation_folder: Path,
    mesh_filename: str,
    n_processes: int,
    ports: Iterable[str],
    is_temporary: bool,
) -> ElectrostaticResults:
    """Fetch results from successful Elmer simulations."""
    raw_name = Path(mesh_filename).stem
    raw_capacitance_matrix = read_csv(
        simulation_folder / f"{raw_name}_capacitance.dat",
        sep=r"\s+",
        header=None,
        dtype=float,
    ).values
    return ElectrostaticResults(
        capacitance_matrix={
            (iname, jname): raw_capacitance_matrix[i][j]
            for (i, iname), (j, jname) in itertools.product(
                enumerate(ports), enumerate(ports)
            )
        },
        **(
            {}
            if is_temporary
            else dict(
                mesh_location=simulation_folder / mesh_filename,
                field_file_location=simulation_folder
                / raw_name
                / "results"
                / f"{raw_name}_t0001.{'pvtu' if n_processes > 1 else 'vtu'}",
            )
        ),
    )


def run_capacitive_simulation_elmer(
    component: gf.Component,
    element_order: int = 1,
    n_processes: int = 1,
    layer_stack: LayerStack | None = None,
    material_spec: RFMaterialSpec | None = None,
    simulation_folder: Path | str | None = None,
    simulator_params: Mapping[str, Any] | None = None,
    mesh_parameters: dict[str, Any] | None = None,
    mesh_file: Path | str | None = None,
) -> ElectrostaticResults:
    """Run electrostatic finite element method simulations using
    `Elmer`_.     Returns the field solution and resulting capacitance matrix.

    .. note:: You should have `ElmerGrid`, `ElmerSolver` and `ElmerSolver_mpi` and in your PATH.

    Args:
        component: Simulation environment as a gdsfactory component.
        element_order: Order of polynomial basis functions.
            Higher is more accurate but takes more memory and time to run.
        n_processes: Number of processes to use for parallelization
        layer_stack: :class:`~LayerStack` defining defining what layers to include \
                in the simulation and the material properties and thicknesses.
        material_spec:
            :class:`~RFMaterialSpec` defining material parameters for the ones used in ``layer_stack``.
        simulation_folder: Directory for storing the simulation results.
            Default is a temporary directory.
        simulator_params: Elmer-specific parameters. See template file for more details.
        mesh_parameters: Keyword arguments to provide to :func:`get_mesh`.
        mesh_file: Path to a ready mesh to use. Useful for reusing one mesh file.
            By default a mesh is generated according to ``mesh_parameters``.

    .. _Elmer: https://github.com/ElmerCSC/elmerfem
    """
    if layer_stack is None:
        layer_stack = LayerStack(
            layers={
                k: LAYER_STACK.layers[k]
                for k in (
                    "core",
                    "substrate",
                    "box",
                )
            }
        )
    if material_spec is None:
        material_spec: RFMaterialSpec = {
            "si": {"relative_permittivity": 11.45},
            "sio2": {"relative_permittivity": 1},
            "vacuum": {"relative_permittivity": 1},
        }

    temp_dir = TemporaryDirectory()
    simulation_folder = Path(simulation_folder or temp_dir.name)
    simulation_folder.mkdir(exist_ok=True, parents=True)

    port_delimiter = "__"  # won't cause trouble unlike #
    filename = component.name + ".msh"
    if mesh_file:
        shutil.copyfile(str(mesh_file), str(simulation_folder / filename))
    else:
        get_mesh(
            component=component,
            type="3D",
            filename=simulation_folder / filename,
            layer_stack=layer_stack,
            **((mesh_parameters or {}) | {"layer_port_delimiter": port_delimiter}),
        )

    # `interruptible` works on gmsh versions >= 4.11.2
    gmsh.initialize(
        **(
            {"interruptible": False}
            if "interruptible" in inspect.getfullargspec(gmsh.initialize).args
            else {}
        )
    )
    gmsh.merge(str(simulation_folder / filename))
    mesh_surface_entities = [
        gmsh.model.getPhysicalName(*dimtag)
        for dimtag in gmsh.model.getPhysicalGroups(dim=2)
    ]
    gmsh.finalize()

    # Signals are converted to Elmer Boundary Conditions
    ground_layers = {
        next(k for k, v in layer_stack.layers.items() if v.layer == port.layer)
        for port in component.get_ports()
    }  # ports allowed only on metal
    metal_surfaces = [
        e for e in mesh_surface_entities if any(ground in e for ground in ground_layers)
    ]
    # Group signal BCs by ports
    metal_signal_surfaces_grouped = [
        [e for e in metal_surfaces if port in e] for port in component.ports
    ]
    metal_ground_surfaces = set(metal_surfaces) - set(
        itertools.chain.from_iterable(metal_signal_surfaces_grouped)
    )

    ground_layers |= metal_ground_surfaces

    # dielectrics
    bodies = {
        k: {"material": v.material}
        for k, v in layer_stack.layers.items()
        if port_delimiter not in k and k not in ground_layers
    }
    if background_tag := (mesh_parameters or {}).get("background_tag", "vacuum"):
        bodies = {**bodies, background_tag: {"material": background_tag}}

    _generate_sif(
        simulation_folder,
        component.name,
        metal_signal_surfaces_grouped,
        bodies,
        ground_layers,
        layer_stack,
        material_spec,
        element_order,
        background_tag,
        simulator_params,
    )
    _elmergrid(simulation_folder, filename, n_processes)
    _elmersolver(simulation_folder, filename, n_processes)
    results = _read_elmer_results(
        simulation_folder,
        filename,
        n_processes,
        component.ports,
        is_temporary=str(simulation_folder) == temp_dir.name,
    )
    temp_dir.cleanup()
    return results
