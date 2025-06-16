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
from gdsfactory.config import home

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
        v["material"]: physical_name_to_dimtag_map[k][1]
        for k, v in bodies.items()
        if k in physical_name_to_dimtag_map
    }

    # Debug: Show the physical name to dimtag mapping
    print(f"🔍 DEBUG: Physical surface mapping...")
    print(f"   Available physical surfaces and their IDs:")
    for name, (dim, tag) in physical_name_to_dimtag_map.items():
        if dim == 2:  # Surface entities
            print(f"     {name}: ID = {tag}")

    # Show what we're assigning to boundaries
    print(f"   Ground layers: {ground_layers}")
    print(
        f"   Ground surface IDs: {[physical_name_to_dimtag_map.get(layer, 'NOT_FOUND') for layer in ground_layers]}"
    )
    print(f"   Terminal surface assignments:")
    for i, signal_group in enumerate(signals):
        print(
            f"     Terminal {i + 1}: {signal_group} -> IDs: {[physical_name_to_dimtag_map.get(signal, 'NOT_FOUND') for signal in signal_group]}"
        )

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
    # Debug ground layer assignment
    ground_attributes = []
    print(f"   Processing ground layers for JSON:")
    for layer in ground_layers:
        if layer in physical_name_to_dimtag_map:
            attr_id = physical_name_to_dimtag_map[layer][1]
            ground_attributes.append(attr_id)
            print(f"     {layer} -> ID {attr_id}")
        else:
            print(f"     ❌ {layer} not found in physical_name_to_dimtag_map")

    print(f"   Final ground attributes: {ground_attributes}")

    palace_json_data["Boundaries"]["Ground"] = {"Attributes": ground_attributes}
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


def _palace(simulation_folder: Path, name: str, n_processes: int = 1) -> None:
    """Run simulations with Palace."""
    # Try to find palace in PATH first
    palace = shutil.which("palace")

    # If not found, try to load it via Spack
    if palace is None:
        print("   Palace not found in PATH, attempting to load via Spack...")
        # Create a command that sources Spack and then runs palace
        json_file = simulation_folder / f"{Path(name).stem}.json"
        spack_cmd = f"source {home}/install_new_computer/bash/spack/share/spack/setup-env.fish && spack load palace && palace {json_file.absolute()}"

        print(f"🔍 DEBUG: Running Palace simulation via Spack...")
        print(f"   Command: {spack_cmd}")
        print(f"   JSON config file: {json_file}")
        print(f"   Simulation folder: {simulation_folder}")
        print(f"   Working directory contents before Palace:")
        for item in simulation_folder.iterdir():
            print(f"     - {item.name}")

        try:
            import subprocess

            result = subprocess.run(
                spack_cmd,
                shell=True,
                cwd=simulation_folder,
                capture_output=True,
                text=True,
                executable="/opt/homebrew/bin/fish",  # Use fish shell explicitly
            )

            if result.returncode != 0:
                print(f"   ❌ Palace execution failed!")
                print(f"   STDOUT: {result.stdout}")
                print(f"   STDERR: {result.stderr}")
                raise RuntimeError(
                    f"Palace execution failed with return code {result.returncode}"
                )
            else:
                print(f"   ✅ Palace executed successfully!")
                print(f"   STDOUT: {result.stdout}")

        except Exception as e:
            print(f"   ❌ Failed to run Palace via Spack: {e}")
            raise RuntimeError(
                "palace not found. Make sure it is available in your PATH or via Spack."
            )
    else:
        # Palace found in PATH, use the original method
        json_file = simulation_folder / f"{Path(name).stem}.json"

        print(f"🔍 DEBUG: Running Palace simulation...")
        print(f"   Palace executable: {palace}")
        print(f"   JSON config file: {json_file}")
        print(f"   Simulation folder: {simulation_folder}")
        print(f"   Working directory contents before Palace:")
        for item in simulation_folder.iterdir():
            print(f"     - {item.name}")

        try:
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
        except Exception as e:
            print(f"   ❌ Palace execution failed: {e}")
            raise

    # Check results after Palace execution (regardless of method used)
    print(f"   Palace execution completed!")
    print(f"   Working directory contents after Palace:")
    for item in simulation_folder.iterdir():
        print(f"     - {item.name}")

    # Check if postpro directory exists
    postpro_dir = simulation_folder / "postpro"
    if postpro_dir.exists():
        print(f"   Postpro directory contents:")
        for item in postpro_dir.iterdir():
            print(f"     - {item.name}")
    else:
        print(f"   ⚠️  Postpro directory not found!")


def _read_palace_results(
    simulation_folder: Path,
    mesh_filename: str,
    ports: Iterable[str],
    is_temporary: bool,
) -> ElectrostaticResults:
    """Fetch results from successful Palace simulations."""

    print(f"🔍 DEBUG: Reading Palace results...")
    print(f"   Simulation folder: {simulation_folder}")
    print(f"   Looking for: {simulation_folder / 'postpro' / 'terminal-Cm.csv'}")

    # Check what files actually exist
    postpro_dir = simulation_folder / "postpro"
    if postpro_dir.exists():
        print(f"   Postpro directory contents:")
        for item in postpro_dir.iterdir():
            print(f"     - {item.name}")
    else:
        print(f"   ❌ Postpro directory does not exist!")
        print(f"   Available directories in {simulation_folder}:")
        for item in simulation_folder.iterdir():
            if item.is_dir():
                print(f"     - {item.name}/")
        raise FileNotFoundError(f"Postpro directory not found in {simulation_folder}")

    csv_file = simulation_folder / "postpro" / "terminal-Cm.csv"
    if not csv_file.exists():
        print(f"   ❌ Expected CSV file not found: {csv_file}")
        print(f"   Available files in postpro:")
        for item in postpro_dir.iterdir():
            print(f"     - {item.name}")
        raise FileNotFoundError(f"Palace output file not found: {csv_file}")

    print(f"   ✅ Found CSV file: {csv_file}")
    raw_capacitance_matrix = read_csv(csv_file, dtype=float).values[
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
            n_threads=n_processes,
            gmsh_version=2.2,  # see https://mfem.org/mesh-formats/#gmsh-mesh-formats
            **((mesh_parameters or {}) | {"layer_port_delimiter": port_delimiter}),
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
    ground_layers = set()
    for port in component.ports:
        # Find layer stack layer that corresponds to this port layer
        for layer_name, layer_info in layer_stack.layers.items():
            # Check if the layer definition contains or matches the port layer
            if (
                hasattr(layer_info.layer, "value")
                and layer_info.layer.value == port.layer
            ):
                ground_layers.add(layer_name)
                break
            elif str(layer_info.layer) == str(port.layer):
                ground_layers.add(layer_name)
                break
            elif (
                "WG" in str(layer_info.layer) and port.layer == 1
            ):  # WG layer typically has value 1
                ground_layers.add(layer_name)
                break
    metal_surfaces = [
        e for e in mesh_surface_entities if any(ground in e for ground in ground_layers)
    ]
    print(f"🔍 DEBUG: Surface processing...")
    print(f"   Metal surfaces: {metal_surfaces}")
    print(f"   Component ports: {[port.name for port in component.ports]}")
    print(f"   All mesh surface entities: {mesh_surface_entities}")

    # Look for port-specific surfaces using the port delimiter
    port_surfaces = [
        [e for e in mesh_surface_entities if port_delimiter in e and port.name in e]
        for port in component.ports
    ]

    print(f"   Port surfaces found: {port_surfaces}")

    # If no port-specific surfaces found, assign metal surfaces to ports
    # This is a fallback for simple geometries like interdigital capacitors
    if not any(port_surfaces):
        print(f"   ⚠️  No port-specific surfaces found, using fallback assignment")
        # For interdigital capacitor, both ports use the same metal layer
        # but we need to create distinct boundaries for Palace
        metal_signal_surfaces_grouped = [
            [metal_surfaces[0]]
            if i == 0 and len(metal_surfaces) > 0
            else [metal_surfaces[1]]
            if i == 1 and len(metal_surfaces) > 1
            else []
            for i, port in enumerate(component.ports)
        ]
        # If we only have one type of metal surface, assign it to the first port
        if len(metal_surfaces) == 1:
            metal_signal_surfaces_grouped = [[metal_surfaces[0]], []]
        elif len(metal_surfaces) >= 2:
            metal_signal_surfaces_grouped = [[metal_surfaces[0]], [metal_surfaces[1]]]
    else:
        # Use the port-specific surfaces
        metal_signal_surfaces_grouped = [
            [s for s in surfaces if s in metal_surfaces] for surfaces in port_surfaces
        ]

    print(f"   Final grouped surfaces: {metal_signal_surfaces_grouped}")

    # Check if we have valid surface assignments
    for i, group in enumerate(metal_signal_surfaces_grouped):
        port_name = list(component.ports)[i].name
        print(f"   Port {port_name}: surfaces = {group}")
        if not group:
            print(f"   ⚠️  WARNING: No surfaces assigned to port {port_name}")

    metal_ground_surfaces = set(metal_surfaces) - set(
        itertools.chain.from_iterable(metal_signal_surfaces_grouped)
    )

    # For electrostatic simulations, we need a proper ground reference
    # Use substrate surfaces as ground instead of metal surfaces
    substrate_surfaces = [
        e
        for e in mesh_surface_entities
        if any(substrate in e for substrate in ["substrate", "box"])
    ]

    print(f"   Available substrate surfaces for ground: {substrate_surfaces}")

    # Use substrate surfaces as ground, but exclude surfaces used by terminals
    terminal_surfaces = set(
        itertools.chain.from_iterable(metal_signal_surfaces_grouped)
    )

    if substrate_surfaces:
        # Remove any substrate surfaces that are being used as terminals
        actual_ground_surfaces = [
            s for s in substrate_surfaces if s not in terminal_surfaces
        ]
    else:
        actual_ground_surfaces = list(metal_ground_surfaces)

    print(f"   Terminal surfaces: {terminal_surfaces}")
    print(f"   Using as ground: {actual_ground_surfaces}")

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
        actual_ground_surfaces,
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


def test_components():
    """Test individual components of the capacitance simulation."""
    import tempfile

    print("🧪 TESTING INDIVIDUAL COMPONENTS")
    print("=" * 40)

    # Test component creation
    print("1. Creating component...")
    c = gf.components.interdigital_capacitor()
    print(f"   ✅ Component: {c.name}")
    print(f"   ✅ Ports: {[p.name for p in c.ports]}")

    # Test layer stack processing
    print("\n2. Testing layer stack...")
    from gdsfactory.generic_tech import LAYER_STACK

    ground_layers = set()
    for port in c.ports:
        for layer_name, layer_info in LAYER_STACK.layers.items():
            if (
                hasattr(layer_info.layer, "value")
                and layer_info.layer.value == port.layer
            ):
                ground_layers.add(layer_name)
                break
            elif "WG" in str(layer_info.layer) and port.layer == 1:
                ground_layers.add(layer_name)
                break
    print(f"   ✅ Ground layers found: {ground_layers}")

    # Test mesh creation (without Palace)
    print("\n3. Testing mesh creation...")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # This will test everything up to Palace execution
            from gplugins.gmsh.get_mesh import get_mesh

            mesh_info = get_mesh(
                component=c,
                type="3D",
                layer_stack=LAYER_STACK,
                resolutions={},
                filename=f"{temp_dir}/test_mesh.msh",
            )
            print(f"   ✅ Mesh created successfully")

    except Exception as e:
        print(f"   ❌ Mesh creation failed: {e}")

    return c


if __name__ == "__main__":
    import json
    import os
    import tempfile
    from pathlib import Path

    print("🧪 TESTING GET_CAPACITANCE.PY WITH PALACE")
    print("=" * 50)

    c = gf.components.interdigital_capacitor()
    print(f"✅ Component created: {c.name}")
    print(f"✅ Component ports: {[p.name for p in c.ports]}")
    print(f"✅ Component layers: {set(port.layer for port in c.ports)}")

    # Use a persistent directory for debugging
    debug_dir = Path("./palace_debug_output")
    debug_dir.mkdir(exist_ok=True)

    print(f"\n📊 RUNNING PALACE SIMULATION:")
    print(f"   Debug output folder: {debug_dir.absolute()}")

    try:
        # Load Spack environment in the subprocess by modifying PATH
        print("   Loading Palace via Spack...")

        # Run the simulation with persistent folder for debugging
        r = run_capacitive_simulation_palace(c, simulation_folder=debug_dir)
        print(f"✅ Simulation completed successfully!")
        print(f"✅ Results: {r}")

        # Print capacitance matrix
        print(f"\n📈 CAPACITANCE MATRIX:")
        for key, value in r.capacitance_matrix.items():
            print(f"   C[{key[0]},{key[1]}] = {value:.2e} F")

    except Exception as e:
        print(f"❌ Error during simulation: {e}")
        print(f"\n🔍 DEBUG INFORMATION:")
        print(f"   Check debug folder: {debug_dir.absolute()}")
        if debug_dir.exists():
            print(f"   Contents of debug folder:")
            for item in debug_dir.iterdir():
                print(f"     - {item.name}")
        import traceback

        traceback.print_exc()
