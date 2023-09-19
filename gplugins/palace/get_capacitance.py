from __future__ import annotations

import inspect
import itertools
import json
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
from numpy import isfinite
from pandas import read_csv

from gplugins.common.base_models.simulation import ElectrostaticResults
from gplugins.common.types import RFMaterialSpec
from gplugins.common.utils.async_helpers import (
    execute_and_stream_output,
    run_async_with_event_loop,
)
from gplugins.gmsh import get_mesh

ELECTROSTATIC_JSON = "electrostatic.json"
ELECTROSTATIC_TEMPLATE = Path(__file__).parent / ELECTROSTATIC_JSON


def _generate_json(
    simulation_folder: Path,
    name: str,
    signals: Sequence[Sequence[str]],
    bodies: dict[str, dict[str, Any]],
    ground_layers: Iterable[str],
    layer_stack: LayerStack,
    material_spec: RFMaterialSpec,
    element_order: int,
    physical_name_to_dimtag_map: dict[str, tuple[int, int]],
    background_tag: str | None = None,
    simulator_params: Mapping[str, Any] | None = None,
) -> None:
    """Generates a json file for capacitive Palace simulations.

    Args:
        simulation_folder: Folder where the json file will be saved.
        name: Name of the simulation.
        signals: List of lists of signal names.
        bodies: Dictionary of bodies with their physical names as keys.
        ground_layers: List of ground layer names.
        layer_stack: Layer stack of the circuit.
        material_spec: Dictionary of material specifications.
        element_order: Order of the elements.
        physical_name_to_dimtag_map: Dictionary mapping physical names to dimension tags.
        background_tag: Physical name of the background.
        simulator_params: Dictionary of simulator parameters.
    """
    # TODO: Generalise to merger with the Elmer implementations"""
    used_materials = {v.material for v in layer_stack.layers.values()} | (
        {background_tag} if background_tag else {}
    )
    used_materials = {
        k: material_spec[k]
        for k in used_materials
        if isfinite(material_spec[k].get("relative_permittivity", inf))
    }

    with open(ELECTROSTATIC_TEMPLATE) as fp:
        palace_json_data = json.load(fp)

    material_to_attributes_map = {
        v["material"]: physical_name_to_dimtag_map[k][1] for k, v in bodies.items()
    }

    palace_json_data["Model"]["Mesh"] = f"{name}.msh"
    palace_json_data["Domains"]["Materials"] = [
        {
            "Attributes": [material_to_attributes_map.get(material, None)],
            "Permittivity": props["relative_permittivity"],
        }
        for material, props in used_materials.items()
    ]
    # TODO 3d volumes as pec???, not needed for capacitance
    # palace_json_data['Boundaries']['PEC'] = {
    #     'Attributes': [
    #         physical_name_to_dimtag_map[pec][1] for pec in
    #         (set(k for k, v in physical_name_to_dimtag_map.items() if v[0] == 3) - set(bodies) -
    #          set(ground_layers))  # TODO same in Elmer??
    #     ]
    # }
    palace_json_data["Boundaries"]["Ground"] = {
        "Attributes": [physical_name_to_dimtag_map[layer][1] for layer in ground_layers]
    }
    palace_json_data["Boundaries"]["Terminal"] = [
        {
            "Index": i,
            "Attributes": [
                physical_name_to_dimtag_map[signal][1] for signal in signal_group
            ],
        }
        for i, signal_group in enumerate(signals, 1)
    ]
    # TODO try do we get energy method without this??
    palace_json_data["Boundaries"]["Postprocessing"]["Capacitance"] = palace_json_data[
        "Boundaries"
    ]["Terminal"]

    palace_json_data["Solver"]["Order"] = element_order
    palace_json_data["Solver"]["Electrostatic"]["Save"] = len(signals)
    if simulator_params is not None:
        palace_json_data["Solver"]["Linear"] |= simulator_params

    with open(simulation_folder / f"{name}.json", "w", encoding="utf-8") as fp:
        json.dump(palace_json_data, fp, indent=4)


def _palace(simulation_folder: Path, name: str, n_processes: int = 1):
    """Run simulations with Palace."""
    palace = shutil.which("palace")
    if palace is None:
        raise RuntimeError("palace not found. Make sure it is available in your PATH.")

    json_file = simulation_folder / f"{Path(name).stem}.json"
    run_async_with_event_loop(
        execute_and_stream_output(
            [palace, json_file]
            if n_processes == 1
            else [palace, "-np", str(n_processes), json_file],
            shell=False,
            log_file_dir=simulation_folder,
            log_file_str=json_file.stem + "_palace",
            cwd=simulation_folder,
        )
    )


def _read_palace_results(
    simulation_folder: Path,
    mesh_filename: str,
    ports: Iterable[str],
    is_temporary: bool,
) -> ElectrostaticResults:
    """Fetch results from successful Palace simulations."""
    raw_capacitance_matrix = read_csv(
        simulation_folder / "postpro" / "terminal-Cm.csv", dtype=float
    ).values[
        :, 1:
    ]  # remove index
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
                / "postpro"
                / "paraview"
                / "electrostatic"
                / "electrostatic.pvd",
            )
        ),
    )


def run_capacitive_simulation_palace(
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
    `Palace`_.
    Returns the field solution and resulting capacitance matrix.

    .. note:: You should have `palace` in your PATH.

    Args:
        component: Simulation environment as a gdsfactory component.
        element_order:
            Order of polynomial basis functions.
            Higher is more accurate but takes more memory and time to run.
        n_processes: Number of processes to use for parallelization
        layer_stack:
            :class:`~LayerStack` defining defining what layers to include in the simulation
            and the material properties and thicknesses.
        material_spec:
            :class:`~RFMaterialSpec` defining material parameters for the ones used in ``layer_stack``.
        simulation_folder:
            Directory for storing the simulation results.
            Default is a temporary directory.
        simulator_params: Palace-specific parameters. This will be expanded to ``solver["Linear"]`` in
            the Palace config, see `Palace documentation <https://awslabs.github.io/palace/stable/config/solver/#solver[%22Linear%22]>`_
        mesh_parameters:
            Keyword arguments to provide to :func:`get_mesh`.
        mesh_file: Path to a ready mesh to use. Useful for reusing one mesh file.
            By default a mesh is generated according to ``mesh_parameters``.

    .. _Palace: https://github.com/awslabs/palace
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

    filename = component.name + ".msh"
    if mesh_file:
        shutil.copyfile(str(mesh_file), str(simulation_folder / filename))
    else:
        get_mesh(
            component=component,
            type="3D",
            filename=simulation_folder / filename,
            layer_stack=layer_stack,
            n_threads=n_processes,
            gmsh_version=2.2,  # see https://mfem.org/mesh-formats/#gmsh-mesh-formats
            **(mesh_parameters or {}),
        )

    # re-read the mesh
    # `interruptible` works on gmsh versions >= 4.11.2
    gmsh.initialize(
        **(
            {"interruptible": False}
            if "interruptible" in inspect.getfullargspec(gmsh.initialize).args
            else {}
        )
    )
    gmsh.merge(str(simulation_folder / filename))
    mesh_surface_entities = {
        gmsh.model.getPhysicalName(*dimtag)
        for dimtag in gmsh.model.getPhysicalGroups(dim=2)
    }

    # Signals are converted to Boundaries
    ground_layers = {
        next(k for k, v in layer_stack.layers.items() if v.layer == port.layer)
        for port in component.get_ports()
    }  # ports allowed only on metal
    # TODO infer port delimiter from somewhere
    port_delimiter = "__"
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
        k: {
            "material": v.material,
        }
        for k, v in layer_stack.layers.items()
        if port_delimiter not in k and k not in ground_layers
    }
    if background_tag := (mesh_parameters or {}).get("background_tag", "vacuum"):
        bodies = {**bodies, background_tag: {"material": background_tag}}

    # TODO refactor to not require this map, the same information could be transferred with the variables above
    physical_name_to_dimtag_map = {
        gmsh.model.getPhysicalName(*dimtag): dimtag
        for dimtag in gmsh.model.getPhysicalGroups()
    }
    gmsh.finalize()

    _generate_json(
        simulation_folder,
        component.name,
        metal_signal_surfaces_grouped,
        bodies,
        ground_layers,
        layer_stack,
        material_spec,
        element_order,
        physical_name_to_dimtag_map,
        background_tag,
        simulator_params,
    )
    _palace(simulation_folder, filename, n_processes)
    results = _read_palace_results(
        simulation_folder,
        filename,
        component.ports,
        is_temporary=str(simulation_folder) == temp_dir.name,
    )
    temp_dir.cleanup()
    return results
