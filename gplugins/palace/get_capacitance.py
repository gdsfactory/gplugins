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

from pydantic.utils import deep_update
from gdsfactory.typings import Ports
from kfactory import kdb
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
from gplugins.common.utils.get_component_with_net_layers import (
    compare_layerlevel_and_port_layers,
    get_component_with_net_layers,
)
from gdsfactory.config import home
from gplugins.meshwell.get_meshwell_3D import get_meshwell_prisms
from meshwell.cad import cad
from meshwell.mesh import mesh
from gdsfactory import logger

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
    physical_name_to_dimtag_map: dict[str, tuple[int, int]],
    background_tag: str | None = None,
    solver_config: Mapping[str, Any] | None = None,
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
        physical_name_to_dimtag_map: Dictionary mapping physical names to dimension tags.
        background_tag: Physical name of the background.
        solver_config: Dictionary of solver parameters given to https://awslabs.github.io/palace/stable/config/solver/.
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
        v["material"]: physical_name_to_dimtag_map[k][1]
        for k, v in bodies.items()
        if k in physical_name_to_dimtag_map
    }

    palace_json_data["Model"]["Mesh"] = f"{name}.msh"
    palace_json_data["Domains"]["Materials"] = [
        {
            "Attributes": [material_to_attributes_map[material]],
            "Permittivity": props["relative_permittivity"],
        }
        for material, props in used_materials.items()
        if material in material_to_attributes_map
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
        "Attributes": [
            physical_name_to_dimtag_map[layer][1]
            for layer in ground_layers
            if layer in physical_name_to_dimtag_map
        ]
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

    # palace_json_data["Boundaries"]["Postprocessing"]["SurfaceFlux"] = [
    #     d | {"Type": "Electric"} for d in palace_json_data["Boundaries"]["Terminal"]
    # ]

    if solver_config is not None:
        palace_json_data["Solver"] = deep_update(palace_json_data["Solver"], solver_config)
    palace_json_data["Solver"]["Electrostatic"]["Save"] = len(signals)

    with open(simulation_folder / f"{name}.json", "w", encoding="utf-8") as fp:
        json.dump(palace_json_data, fp, indent=4)


def _palace(simulation_folder: Path, name: str, n_processes: int = 1) -> None:
    """Run simulations with Palace."""
    # Try to find palace in PATH first
    palace = shutil.which("palace")

    if palace is None:
        raise RuntimeError("palace not found. Make sure it is available in your PATH.")
    else:
        # Palace found in PATH, use the original method
        json_file = simulation_folder / f"{Path(name).stem}.json"

        logger.info(f"   Running Palace simulation...")
        logger.info(f"   Palace executable: {palace}")
        logger.info(f"   JSON config file: {json_file}")
        logger.info(f"   Simulation folder: {simulation_folder}")
        logger.info(f"   Working directory contents before Palace:")
        for item in simulation_folder.iterdir():
            print(f"     - {item.name}")

        try:
            run_async_with_event_loop(
                execute_and_stream_output(
                    (
                        [palace, json_file]
                        if n_processes == 1
                        else [palace, "-np", str(n_processes), json_file]
                    ),
                    shell=False,
                    log_file_dir=simulation_folder,
                    log_file_str=json_file.stem + "_palace",
                    cwd=simulation_folder,
                )
            )
        except Exception as e:
            logger.info(f"   ❌ Palace execution failed: {e}")
            raise

    # Check results after Palace execution (regardless of method used)
    logger.info(f"   Palace execution completed!")
    logger.debug(f"   Working directory contents after Palace:")
    for item in simulation_folder.iterdir():
        logger.debug(f"     - {item.name}")


def _read_palace_results(
    simulation_folder: Path,
    mesh_filename: str,
    ports: Ports,
    is_temporary: bool,
) -> ElectrostaticResults:
    """Fetch results from successful Palace simulations."""
    csv_file = simulation_folder / "postpro" / "terminal-Cm.csv"
    raw_capacitance_matrix = read_csv(csv_file, dtype=float).values[
        :, 1:
    ]  # remove index

    return ElectrostaticResults(
        capacitance_matrix={
            (port_i.name, port_j.name): raw_capacitance_matrix[i][j]
            for (i, port_i), (j, port_j) in itertools.product(
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
    n_processes: int = 1,
    layer_stack: LayerStack | None = None,
    material_spec: RFMaterialSpec | None = None,
    simulation_folder: Path | str | None = None,
    solver_config: Mapping[str, Any] | None = None,
    mesh_parameters: dict[str, Any] | None = None,
    mesh_file: Path | str | None = None,
) -> ElectrostaticResults:
    """Run electrostatic finite element method simulations using
    `Palace`_.
    Returns the field solution and resulting capacitance matrix.

    .. note:: You should have `palace` in your PATH.

    Args:
        component: Simulation environment as a gdsfactory component.
        n_processes: Number of processes to use for parallelization
        layer_stack:
            :class:`~LayerStack` defining defining what layers to include in the simulation
            and the material properties and thicknesses.
        material_spec:
            :class:`~RFMaterialSpec` defining material parameters for the ones used in ``layer_stack``.
        simulation_folder:
            Directory for storing the simulation results.
            Default is a temporary directory.
        solver_config: Palace-specific parameters. This will be expanded to ``config["Solver"]`` in
            the Palace config, see `Palace documentation <https://awslabs.github.io/palace/stable/config/solver/#config[%22Solver%22]>`_
        mesh_parameters:
            Keyword arguments to provide to :func:`~meshwell.mesh.mesh`.
        mesh_file: Path to a ready mesh to use. Useful for reusing one mesh file.
            By default a mesh is generated according to ``mesh_parameters``.

    .. _Palace: https://github.com/awslabs/palace
    """
    if not isinstance(n_processes, int):
        raise TypeError(f"n_processes must be an integer, got {type(n_processes)}")
    if n_processes < 1:
        raise ValueError(f"n_processes must be >= 1, got {n_processes}")

    if solver_config:
        order = solver_config.get("Order")
        if order is not None:
            if not isinstance(order, int):
                raise TypeError(f"Solver Order must be an integer, got {type(order)}")
            if order < 1:
                raise ValueError(f"Solver Order must be >= 1, got {order}")

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

    port_delimiter = "@"  # won't cause trouble unlike #
    boundary_delimiter = "boundary"
    if mesh_file:
        shutil.copyfile(str(mesh_file), str(simulation_folder / filename))
        filename = component.name + ".msh"
    else:
        # Generate a version of the component where layers are split according to ports they touch
        if component.ports:
            mesh_component = component.dup()
            mesh_component.flatten()
            component = get_component_with_net_layers(
                component=mesh_component,
                layer_stack=layer_stack,
                port_names=[p.name for p in component.ports],
                delimiter="@",
            )
        filename = component.name + ".msh"

        prisms = get_meshwell_prisms(
            component=component,
            layer_stack=layer_stack,
        )
        cad(
            entities_list=prisms,
            output_file=(
                cad_output := (simulation_folder / filename).with_suffix(".xao")
            ),
            boundary_delimiter=boundary_delimiter,
            progress_bars=True,
        )
        mesh(
            input_file=cad_output,
            output_file=(simulation_folder / filename).with_suffix(".msh"),
            boundary_delimiter=boundary_delimiter,
            dim=3,
            **(mesh_parameters or {}),
        )

    # Re-read the mesh
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

    # Signals are converted to Boundaries
    ground_layers = {
        k
        for port in component.ports
        for k, v in layer_stack.layers.items()
        if compare_layerlevel_and_port_layers(v, port)
        # and v.derived_layer is not None
    }
    # ports allowed only on metal

    metal_surfaces = [
        e for e in mesh_surface_entities if any(ground in e for ground in ground_layers)
    ]
    # Group signal BCs by ports
    # TODO we need to remove the port-boundary surfaces for palace to work, why?
    # TODO might as well remove the vacuum boundary and have just 2D sheets
    metal_signal_surfaces_grouped = [
        [e for e in metal_surfaces if port.name in e and boundary_delimiter not in e]
        for port in component.ports
    ]
    metal_ground_surfaces = set(metal_surfaces) - set(
        itertools.chain.from_iterable(metal_signal_surfaces_grouped)
    )
    ground_layers |= metal_ground_surfaces

    # breakpoint()

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
    # Use msh version 2.2 for MFEM / Palace compatibility, see https://mfem.org/mesh-formats/#gmsh-mesh-formats
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(str(simulation_folder / filename))
    gmsh.finalize()

    _generate_json(
        simulation_folder,
        component.name,
        metal_signal_surfaces_grouped,
        bodies,
        ground_layers,
        layer_stack,
        material_spec,
        physical_name_to_dimtag_map,
        background_tag,
        solver_config,
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


if __name__ == "__main__":
    import json
    import os
    import tempfile
    from pathlib import Path

    c = gf.components.interdigital_capacitor()
    with TemporaryDirectory() as tmp_dir:
        r = run_capacitive_simulation_palace(c, simulation_folder=tmp_dir)
        # Print capacitance matrix
        print(f"\n📈 CAPACITANCE MATRIX:")
        for key, value in r.capacitance_matrix.items():
            print(f"   C[{key[0]},{key[1]}] = {value:.2e} F")
