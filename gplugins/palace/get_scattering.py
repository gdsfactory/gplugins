from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import re
import shutil
from collections.abc import Collection, Mapping, Sequence
from math import atan2, degrees, inf
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import gdsfactory as gf
import gmsh
import pandas as pd
from gdsfactory.generic_tech import LAYER_STACK
from gdsfactory.technology import LayerStack
from numpy import isfinite

from gplugins.common.base_models.simulation import DrivenFullWaveResults
from gplugins.common.types import RFMaterialSpec
from gplugins.common.utils.async_helpers import (
    execute_and_stream_output,
    run_async_with_event_loop,
)
from gplugins.gmsh import get_mesh

DRIVE_JSON = "driven.json"
DRIVEN_TEMPLATE = Path(__file__).parent / DRIVE_JSON


def _generate_json(
    simulation_folder: Path,
    name: str,
    bodies: dict[str, dict[str, Any]],
    absorbing_surfaces: Collection[str],
    layer_stack: LayerStack,
    material_spec: RFMaterialSpec,
    element_order: int,
    physical_name_to_dimtag_map: dict[str, tuple[int, int]],
    metal_surfaces: Collection[str],
    background_tag: str | None = None,
    edge_signals: Sequence[Sequence[str]] | None = None,
    internal_signals: Sequence[tuple[Sequence[str], Sequence[str]]] | None = None,
    internal_signal_directions: Mapping[tuple[str, str], str] | None = None,
    simulator_params: Mapping[str, Any] | None = None,
    driven_settings: Mapping[str, float | int | bool] | None = None,
    mesh_refinement_levels: int | None = None,
    only_one_port: bool | None = True,
) -> list[Path]:
    """Generates a json file for full-wave Palace simulations.

    Args:
        simulation_folder: Path to the simulation folder.
        name: Name of the simulation.
        bodies: Dictionary of bodies to be simulated.
        absorbing_surfaces: Collection of surfaces to be treated as absorbing.
        layer_stack: Layer stack of the simulation.
        material_spec: Material specification of the simulation.
        element_order: Element order of the simulation.
        physical_name_to_dimtag_map: Mapping from physical names to dimension tags.
        metal_surfaces: Collection of surfaces to be treated as metal.
        background_tag: Tag of the background material.
        edge_signals: Collection of edge signals to be excited.
        internal_signals: Collection of internal signals to be excited.
        internal_signal_directions: Mapping from internal signals to directions.
        simulator_params: Parameters of the simulator.
        driven_settings: Settings of the driven solver.
        mesh_refinement_levels: Number of mesh refinement levels.
        only_one_port: Whether to only simulate one port at a time.
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

    with open(DRIVEN_TEMPLATE) as fp:
        palace_json_data = json.load(fp)

    material_to_attributes_map = dict()
    for k, v in bodies.items():
        material_to_attributes_map[v["material"]] = material_to_attributes_map.get(
            v["material"], []
        ) + [physical_name_to_dimtag_map[k][1]]

    palace_json_data["Model"]["Mesh"] = f"{name}.msh"
    if mesh_refinement_levels:
        palace_json_data["Model"]["Refinement"] = {
            "UniformLevels": mesh_refinement_levels
        }
    palace_json_data["Domains"]["Materials"] = [
        {
            "Attributes": material_to_attributes_map.get(material, None),
            "Permittivity": float(props["relative_permittivity"]),
            "Permeability": float(props["relative_permeability"]),
            "LossTan": float(props.get("loss_tangent", 0.0)),
            "Conductivity": float(props.get("conductivity", 0.0)),
        }
        for material, props in used_materials.items()
    ]
    # TODO list here attributes that contained LossTAN
    # palace_json_data["Domains"]["Postprocessing"]["Dielectric"] = [
    # ]

    palace_json_data["Boundaries"]["PEC"] = {
        "Attributes": [
            physical_name_to_dimtag_map[layer][1]
            for layer in set(metal_surfaces)
            - set(itertools.chain.from_iterable(edge_signals or []))
            - set(
                itertools.chain.from_iterable(
                    itertools.chain.from_iterable(internal_signals or [])
                )
            )
            - set(absorbing_surfaces or [])
        ]
    }

    # Farfield surface
    palace_json_data["Boundaries"]["Absorbing"] = {
        "Attributes": [
            physical_name_to_dimtag_map[e][1] for e in absorbing_surfaces
        ],  # TODO get farfield _None etc
        "Order": 1,
    }
    # TODO palace_json_data["Boundaries"]["Postprocessing"]["Dielectric"]

    palace_json_data["Solver"]["Order"] = element_order
    if driven_settings is not None:
        palace_json_data["Solver"]["Driven"] |= driven_settings
    if simulator_params is not None:
        palace_json_data["Solver"]["Linear"] |= simulator_params

    # need one simulation per port to excite, see https://github.com/awslabs/palace/issues/81
    jsons = []
    for port in itertools.chain(edge_signals or [], internal_signals or []):
        port_i = 0
        # TODO regex here is hardly robust
        port_name = re.search(
            r"__(.*?)___", port[0][0] if isinstance(port, tuple) else port[0]
        ).group(1)
        if edge_signals:
            palace_json_data["Boundaries"]["WavePort"] = [
                {
                    "Index": (port_i := port_i + 1),
                    "Attributes": [
                        physical_name_to_dimtag_map[signal][1]
                        for signal in signal_group
                    ],
                    "Excitation": port == signal_group,
                    "Mode": 1,
                    "Offset": 0.0,
                }
                for signal_group in edge_signals
            ]
        # TODO only two pair lumped ports supported for now
        if internal_signals:
            palace_json_data["Boundaries"]["LumpedPort"] = [
                {
                    "Index": (port_i := port_i + 1),
                    "Elements": [
                        {
                            "Attributes": [
                                physical_name_to_dimtag_map[signal][1]
                                for signal in signal_group_1
                            ],
                            "Direction": internal_signal_directions[
                                re.search(r"__(.*?)___", signal_group_1[0]).group(1)
                            ],
                        },
                        {
                            "Attributes": [
                                physical_name_to_dimtag_map[signal][1]
                                for signal in signal_group_2
                            ],
                            "Direction": internal_signal_directions[
                                re.search(r"__(.*?)___", signal_group_2[0]).group(1)
                            ],
                        },
                    ],
                    "Excitation": port == (signal_group_1, signal_group_2),
                    "R": 50,
                }
                for (signal_group_1, signal_group_2) in internal_signals
            ]
        palace_json_data["Problem"]["Output"] = f"postpro_{port_name}"

        with open(
            (json_name := simulation_folder / f"{name}_{port_name}.json"),
            "w",
            encoding="utf-8",
        ) as fp:
            json.dump(palace_json_data, fp, indent=4)
        jsons.append(json_name)

        # TODO if a user has both wave ports and lumped ports, this currently allows only computing from waveport elsewhere
        if only_one_port:
            break

    return jsons


async def _palace(
    simulation_folder: Path, json_files: Collection[Path], n_processes: int = 1
) -> None:
    """Run simulations with Palace."""
    # split processes as evenly as possible
    quotient, remainder = divmod(n_processes, len(json_files))
    n_processes_per_json = [quotient] * len(json_files)
    for i in range(remainder):
        n_processes_per_json[i] = max(
            n_processes_per_json[i] + 1, 1
        )  # need at least one

    palace = shutil.which("palace")
    if palace is None:
        raise RuntimeError(
            "`palace` not found. Make sure it is available in your PATH."
        )

    tasks = [
        execute_and_stream_output(
            (
                [palace, str(json_file)]
                if n_processes == 1
                else [palace, "-np", str(n_processes_json), str(json_file)]
            ),
            shell=False,
            log_file_dir=json_file.parent,
            log_file_str=json_file.stem + "_palace",
            cwd=simulation_folder,
        )
        for json_file, n_processes_json in zip(json_files, n_processes_per_json)
    ]
    await asyncio.gather(*tasks)


def _read_palace_results(
    simulation_folder: Path,
    mesh_filename: str,
    ports: Collection[str],
    is_temporary: bool,
) -> DrivenFullWaveResults:
    """Fetch results from successful Palace simulations."""
    scattering_matrix = pd.DataFrame()
    for port in ports:
        scattering_matrix = pd.concat(
            [
                scattering_matrix,
                pd.read_csv(
                    simulation_folder / f"postpro_{port}" / "port-S.csv", dtype=float
                ),
            ],
            axis="columns",
        )
    scattering_matrix = (
        scattering_matrix.T.drop_duplicates().T
    )  # Remove duplicate freqs.
    scattering_matrix.columns = scattering_matrix.columns.str.strip()
    DrivenFullWaveResults.update_forward_refs()
    return DrivenFullWaveResults(
        scattering_matrix=scattering_matrix,  # TODO maybe convert to SDict or similar from DataFrame
        **(
            {}
            if is_temporary
            else dict(
                mesh_location=simulation_folder / mesh_filename,
                field_file_locations=[
                    simulation_folder
                    / f"postpro_{port}"
                    / "paraview"
                    / "driven"
                    / "driven.pvd"
                    for port in ports
                ],
            )
        ),
    )


def run_scattering_simulation_palace(
    component: gf.Component,
    element_order: int = 1,
    n_processes: int = 1,
    layer_stack: LayerStack | None = None,
    material_spec: RFMaterialSpec | None = None,
    simulation_folder: Path | str | None = None,
    simulator_params: Mapping[str, Any] | None = None,
    driven_settings: Mapping[str, float | int | bool] | None = None,
    mesh_refinement_levels: int | None = None,
    only_one_port: bool | None = True,
    mesh_parameters: dict[str, Any] | None = None,
    mesh_file: Path | str | None = None,
) -> DrivenFullWaveResults:
    """Run full-wave finite element method simulations using Palace.
    Returns the field solution and resulting scattering matrix.

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
        driven_settings: Driven full-wave parameters in Palace. This will be expanded to ``solver["Driven"]`` in
            the Palace config, see `Palace documentation <https://awslabs.github.io/palace/stable/config/solver/#solver[%22Driven%22]>`_
        mesh_refinement_levels: Refine mesh this many times, see Palace for details.
        only_one_port: Whether to solve only scattering from the first port to other ports, e.g., `S11, S12, S13, ...`
        mesh_parameters:
            Keyword arguments to provide to :func:`get_mesh`.
        mesh_file: Path to a ready mesh to use. Useful for reusing one mesh file.
            By default a mesh is generated according to ``mesh_parameters``.

    .. _Palace https://github.com/awslabs/palace
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
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.merge(str(simulation_folder / filename))
    mesh_surface_entities = {
        gmsh.model.getPhysicalName(*dimtag)
        for dimtag in gmsh.model.getPhysicalGroups(dim=2)
    }
    background_tag = (mesh_parameters or {}).get("background_tag", "vacuum")

    # Signals are converted to Boundaries
    # TODO currently assumes signal layers have `bw`

    ground_layers = {
        next(k for k, v in layer_stack.layers.items() if v.layer == port.layer)
        for port in component.get_ports()
    } | {layer for layer in component.get_layer_names() if "_bw" in layer}
    # TODO infer port delimiter from somewhere
    port_delimiter = "__"
    metal_surfaces = [
        e for e in mesh_surface_entities if any(ground in e for ground in ground_layers)
    ]
    # Group signal BCs by ports and lumped port pairs
    # TODO tuple pairs by o1_1 o1_2

    lumped_two_ports = [
        e for e in [port.split("_") for port in component.ports] if len(e) > 1
    ]
    lumped_two_port_pairs = [
        ("_".join(p1), "_".join(p2))
        for p1, p2 in itertools.combinations(lumped_two_ports, 2)
        if p1[0] == p2[0]
    ]
    metal_signal_surfaces_grouped = [
        [e for e in metal_surfaces if port in e and background_tag in e]
        for port in component.ports
    ]
    metal_signal_surfaces_paired = [
        tuple(
            e
            for e in metal_signal_surfaces_grouped
            if all(p1 in s or p2 in s for s in e)
        )
        for p1, p2 in lumped_two_port_pairs
    ]

    metal_ground_surfaces = set(metal_surfaces) - set(
        itertools.chain.from_iterable(metal_signal_surfaces_grouped)
    )

    ground_layers |= metal_ground_surfaces

    def _xy_plusminus_direction(point_1, point_2):
        # TODO update after https://github.com/awslabs/palace/pull/75 is merged
        delta_x = point_2[0] - point_1[0]
        delta_y = point_2[1] - point_1[1]
        angle = atan2(delta_y, delta_x)
        angle_deg = degrees(angle) + 360

        directions = ["+X", "+Y", "-X", "-Y"]
        index = round(angle_deg / 90) % 4  # TODO check if shift is correct

        return directions[index]

    lumped_two_port_directions = {
        ports[0]: _xy_plusminus_direction(
            *[component.get_ports_dict()[port].center for port in ports]
        )
        for ports in itertools.chain(
            lumped_two_port_pairs, [tuple(reversed(e)) for e in lumped_two_port_pairs]
        )
    }

    # dielectrics
    bodies = {
        k: {
            "material": v.material,
        }
        for k, v in layer_stack.layers.items()
        if port_delimiter not in k and k not in ground_layers
    }
    if background_tag:
        bodies = {**bodies, background_tag: {"material": background_tag}}

    # TODO refactor to not require this map, the same information could be transferred with the variables above
    physical_name_to_dimtag_map = {
        gmsh.model.getPhysicalName(*dimtag): dimtag
        for dimtag in gmsh.model.getPhysicalGroups()
    }
    absorbing_surfaces = {
        k
        for k in physical_name_to_dimtag_map
        if "___None" in k
        and background_tag in k
        and all(p not in k for p in component.ports)
    } - set(ground_layers)

    gmsh.finalize()

    jsons = _generate_json(
        simulation_folder,
        component.name,
        bodies,
        absorbing_surfaces,
        layer_stack,
        material_spec,
        element_order,
        physical_name_to_dimtag_map,
        metal_surfaces,
        background_tag,
        None,  # TODO edge
        metal_signal_surfaces_paired,  # internal
        lumped_two_port_directions,
        simulator_params,
        driven_settings,
        mesh_refinement_levels,
        only_one_port,
    )
    run_async_with_event_loop(_palace(simulation_folder, jsons, n_processes))
    results = _read_palace_results(
        simulation_folder,
        filename,
        [e[0] for e in lumped_two_port_pairs][: 1 if only_one_port else -1],
        is_temporary=str(simulation_folder) == temp_dir.name,
    )
    temp_dir.cleanup()
    return results
