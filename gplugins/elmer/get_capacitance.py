from __future__ import annotations

import inspect
import itertools
import re
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import gdsfactory as gf
import gmsh
from gdsfactory.technology import LayerStack
from jinja2 import Environment, FileSystemLoader
from meshwell.cad import cad
from meshwell.mesh import mesh
from numpy import fill_diagonal, isfinite
from numpy.typing import NDArray
from pandas import read_csv

from gplugins.common.base_models.simulation import ElectrostaticResults
from gplugins.common.types import RFMaterialSpec
from gplugins.common.utils.async_helpers import (
    execute_and_stream_output,
    run_async_with_event_loop,
)
from gplugins.common.utils.get_component_with_net_layers import (
    get_component_with_net_layers,
)
from gplugins.meshwell.get_meshwell_3D import get_meshwell_prisms

ELECTROSTATIC_SIF = "electrostatic.sif"
ELECTROSTATIC_TEMPLATE = Path(__file__).parent / f"{ELECTROSTATIC_SIF}.j2"

# meshwell joins touching entity names with the interface delimiter and appends
# the boundary delimiter to the outer surface of each entity.
INTERFACE_DELIMITER = "___"
BOUNDARY_DELIMITER = "boundary"
# Layer-to-port delimiter used when splitting conductors per terminal.
PORT_DELIMITER = "@"

_INVALID_IDENTIFIER_CHARACTER = re.compile(r"[^0-9A-Za-z_]")


@dataclass(slots=True, frozen=True)
class _PhysicalGroup:
    """gmsh physical group together with its Elmer-safe name."""

    dim: int
    tag: int
    original_name: str
    name: str


@dataclass(slots=True)
class _MeshTerminals:
    """Terminal and body candidates read from the mesh physical groups."""

    signal_surfaces: dict[str, list[str]]
    ground_surfaces: list[str]
    bodies: list[tuple[_PhysicalGroup, str]]


def _sanitize_identifier(name: str) -> str:
    """Return a deterministic, MATC-safe alias for a physical group name."""
    sanitized = _INVALID_IDENTIFIER_CHARACTER.sub("_", name)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"g_{sanitized}"
    return sanitized


def _validate_solver_inputs(element_order: int, n_processes: int) -> None:
    for label, value in (
        ("element_order", element_order),
        ("n_processes", n_processes),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{label} must be an integer, got {type(value)}")
        if value < 1:
            raise ValueError(f"{label} must be >= 1, got {value}")


def _sanitize_mesh_physical_names(mesh_path: Path) -> list[_PhysicalGroup]:
    """Rename mesh physical groups to Elmer-safe identifiers, in place.

    meshwell names interfaces and boundaries with characters such as ``@`` that
    are not valid Elmer identifiers, and ElmerGrid copies physical names verbatim
    into ``mesh.names``. Sanitizing here keeps both ``mesh.names`` and the
    ``INCLUDE`` in the SIF parseable.
    """
    gmsh.initialize(
        **(
            {"interruptible": False}
            if "interruptible" in inspect.getfullargspec(gmsh.initialize).args
            else {}
        )
    )
    try:
        gmsh.merge(str(mesh_path))
        groups: list[_PhysicalGroup] = []
        used_names: set[str] = set()
        for dim, tag in sorted(gmsh.model.getPhysicalGroups()):
            original_name = gmsh.model.getPhysicalName(dim, tag)
            name = _sanitize_identifier(original_name)
            if name.lower() in used_names:
                raise ValueError(
                    f"Physical group {original_name!r} has a case-insensitive "
                    f"identifier collision after sanitization: {name!r}."
                )
            used_names.add(name.lower())
            groups.append(
                _PhysicalGroup(dim=dim, tag=tag, original_name=original_name, name=name)
            )
        for group in groups:
            gmsh.model.removePhysicalName(group.original_name)
        for group in groups:
            gmsh.model.setPhysicalName(group.dim, group.tag, group.name)
        # ElmerGrid keeps duplicate boundaries from gmsh 2.2 but drops them from 4.x
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.write(str(mesh_path))
        return groups
    finally:
        gmsh.finalize()


def _read_mesh_names(names_file: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Parse an ElmerGrid ``mesh.names`` file into body and boundary maps."""
    bodies: dict[str, int] = {}
    boundaries: dict[str, int] = {}
    target = bodies
    for line in names_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("!"):
            header = stripped.lower()
            if "names for boundaries" in header:
                target = boundaries
            elif "names for bodies" in header:
                target = bodies
            continue
        if not stripped.startswith("$"):
            continue
        name, separator, value = stripped[1:].partition("=")
        if not separator or not (indices := value.split()):
            continue
        target[name.strip().lower()] = int(indices[0])
    return bodies, boundaries


def _material_of_physical_name(
    physical_name: str,
    layer_stack: LayerStack,
    background_tag: str | None,
    split_name_to_layer: Mapping[str, str],
) -> str | None:
    """Map a physical name to a layer material, resolving per-port split names."""
    if physical_name in layer_stack.layers:
        return layer_stack.layers[physical_name].material
    for layer_name, layer_level in layer_stack.layers.items():
        if physical_name == _sanitize_identifier(layer_name):
            return layer_level.material
    if background_tag is not None and physical_name == background_tag:
        return background_tag
    if (layer_name := split_name_to_layer.get(physical_name)) is not None:
        return layer_stack.layers[layer_name].material
    return None


def _merge_port_layer_polygons(
    component: gf.Component, port_names: Sequence[str]
) -> gf.Component:
    for port_layer in {component.ports[name].layer for name in port_names}:
        polygons = component.get_polygons(merge=True, layers=[port_layer]).get(
            port_layer, []
        )
        component = component.remove_layers(layers=[port_layer], recursive=False)
        for polygon in polygons:
            component.add_polygon(polygon, layer=port_layer)
    return component


def _relative_permittivity(material_spec: RFMaterialSpec, material: str) -> float:
    if (
        material not in material_spec
        or "relative_permittivity" not in material_spec[material]
    ):
        raise ValueError(
            f"Material {material!r} needs relative_permittivity in material_spec."
        )
    permittivity = float(material_spec[material]["relative_permittivity"])
    if permittivity <= 0 or (not isfinite(permittivity) and permittivity != float("inf")):
        raise ValueError(
            f"Material {material!r} needs positive relative_permittivity or +inf for a conductor."
        )
    return permittivity


def _split_mesh_terminals(
    groups: Sequence[_PhysicalGroup],
    port_names: Sequence[str],
    layer_stack: LayerStack,
    material_spec: RFMaterialSpec,
    background_tag: str | None,
) -> _MeshTerminals:
    """Group physical surfaces by terminal and collect bodies and materials.

    Matching is done on the exact interface/boundary tokens of the physical
    names, so ``M1`` is never confused with ``M10`` nor ``o1`` with ``o10``.
    Either the meshwell name or the Elmer-safe alias of a split volume matches,
    so a mesh written by an earlier run can be reused through ``mesh_file``.
    """
    volume_groups = [group for group in groups if group.dim == 3]
    surface_groups = [group for group in groups if group.dim == 2]

    aliases: dict[str, str] = {}
    for layer_name in layer_stack.layers:
        for candidate in (
            layer_name,
            *(f"{layer_name}{PORT_DELIMITER}{port}" for port in port_names),
        ):
            alias = _sanitize_identifier(candidate).lower()
            if alias in aliases and aliases[alias] != candidate:
                raise ValueError(
                    f"Layer identifier collision between {aliases[alias]!r} "
                    f"and {candidate!r} after sanitization."
                )
            aliases[alias] = candidate

    # Per-terminal split volume names, in both meshwell and Elmer-safe spelling
    split_name_to_layer: dict[str, str] = {}
    port_volume_names: dict[str, set[str]] = {
        port_name: set() for port_name in port_names
    }
    for layer_name in layer_stack.layers:
        for port_name in port_names:
            split_name = f"{layer_name}{PORT_DELIMITER}{port_name}"
            split_name_to_layer[split_name] = layer_name
            split_name_to_layer[_sanitize_identifier(split_name)] = layer_name
            port_volume_names[port_name] |= {
                split_name,
                _sanitize_identifier(split_name),
            }

    volume_names = {group.original_name for group in volume_groups}
    if (
        background_tag is not None
        and not {
            background_tag,
            _sanitize_identifier(background_tag),
        }
        & volume_names
    ):
        raise ValueError(
            f"No background volume named {background_tag!r} in the mesh. "
            "Add an explicit background layer to the layer stack."
        )
    # Conductors are field-free because the terminal/ground BCs cover all their
    # surfaces, so their bodies get the surrounding material instead.
    free_space_material = (
        _material_of_physical_name(
            background_tag, layer_stack, background_tag, split_name_to_layer
        )
        if background_tag is not None
        else "vacuum"
    )
    if free_space_material is None or not isfinite(
        _relative_permittivity(material_spec, free_space_material)
    ):
        raise ValueError("The background material needs finite relative_permittivity.")
    conductor_volumes: set[str] = set()
    bodies: list[tuple[_PhysicalGroup, str]] = []
    for group in volume_groups:
        material = _material_of_physical_name(
            group.original_name, layer_stack, background_tag, split_name_to_layer
        )
        if material is None:
            raise ValueError(
                f"No layer or background material maps mesh body {group.original_name!r}."
            )
        if _relative_permittivity(material_spec, material) == float("inf"):
            conductor_volumes.add(group.original_name)
            material = free_space_material
        bodies.append((group, material))

    signal_volumes = {
        port_name: volume_names & port_volume_names[port_name]
        for port_name in port_names
    }
    for port_name, volumes in signal_volumes.items():
        if non_conductors := volumes - conductor_volumes:
            raise ValueError(
                f"Terminal {port_name!r} belongs to non-conductor volume(s) "
                f"{sorted(non_conductors)}."
            )

    signal_surfaces: dict[str, list[str]] = {port_name: [] for port_name in port_names}
    ground_surfaces: list[str] = []
    for group in surface_groups:
        tokens = {
            token
            for token in group.original_name.split(INTERFACE_DELIMITER)
            if token and token != BOUNDARY_DELIMITER
        }
        terminals = [
            port_name for port_name in port_names if signal_volumes[port_name] & tokens
        ]
        if len(terminals) > 1:
            raise ValueError(
                f"Surface {group.original_name!r} touches several terminals "
                f"{terminals}. Terminals have to be disjoint."
            )
        if terminals:
            signal_surfaces[terminals[0]].append(group.name)
        elif tokens & conductor_volumes:
            ground_surfaces.append(group.name)

    for port_name, surfaces in signal_surfaces.items():
        if not surfaces:
            available = sorted(group.original_name for group in surface_groups)
            raise ValueError(
                f"No conductor surfaces found for terminal {port_name!r}. "
                f"Physical surfaces in mesh: {available}"
            )

    return _MeshTerminals(
        signal_surfaces=signal_surfaces,
        ground_surfaces=ground_surfaces,
        bodies=bodies,
    )


def _resolve_group_indices(
    names: Iterable[str], name_to_index: Mapping[str, int], kind: str
) -> list[int]:
    indices = []
    for name in names:
        try:
            indices.append(name_to_index[name.lower()])
        except KeyError as error:
            raise ValueError(
                f"Physical group {name!r} missing from the Elmer {kind} in "
                f"mesh.names. Available: {sorted(name_to_index)}"
            ) from error
    return indices


def _generate_sif(
    simulation_folder: Path,
    name: str,
    *,
    materials: Sequence[Mapping[str, Any]],
    bodies: Sequence[Mapping[str, Any]],
    ground_boundaries: Sequence[int],
    signals: Sequence[Sequence[int]],
    element_order: int,
    simulator_params: Mapping[str, Any] | None = None,
) -> Path:
    """Render the Elmer SIF for an electrostatic capacitance simulation."""
    sif_template = Environment(
        loader=FileSystemLoader(ELECTROSTATIC_TEMPLATE.parent)
    ).get_template(ELECTROSTATIC_TEMPLATE.name)
    output = sif_template.render(
        name=name,
        element_order=element_order,
        simulator_params=simulator_params or {},
        materials=materials,
        bodies=bodies,
        ground_boundaries=ground_boundaries,
        signals=signals,
    )
    sif_path = simulation_folder / f"{name}.sif"
    sif_path.write_text(output, encoding="utf-8")
    return sif_path


def _run_checked(
    command: Sequence[str],
    simulation_folder: Path,
    log_file_str: str,
    *,
    append: bool = False,
) -> None:
    """Run a command, raising if it exits non-zero."""
    process = run_async_with_event_loop(
        execute_and_stream_output(
            list(command),
            shell=False,
            append=append,
            log_file_dir=simulation_folder,
            log_file_str=log_file_str,
            cwd=simulation_folder,
        )
    )
    if process.returncode:
        raise RuntimeError(
            f"`{command[0]}` failed with exit code {process.returncode}. "
            f"See the logs in {simulation_folder}."
        )


def _elmergrid(simulation_folder: Path, name: str, n_processes: int = 1) -> None:
    """Run ElmerGrid for converting gmsh mesh to Elmer format."""
    elmergrid = shutil.which("ElmerGrid")
    if elmergrid is None:
        raise RuntimeError(
            "`ElmerGrid` not found. Make sure it is available in your PATH."
        )
    stem = Path(name).stem
    _run_checked(
        [elmergrid, "14", "2", name, "-autoclean"],
        simulation_folder,
        f"{stem}_ElmerGrid",
    )
    if n_processes > 1:
        _run_checked(
            [
                elmergrid,
                "2",
                "2",
                f"{stem}/",
                "-metiskway",
                str(n_processes),
                "4",
                "-removeunused",
            ],
            simulation_folder,
            f"{stem}_ElmerGrid",
            append=True,
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
    _run_checked(
        [elmersolver, sif_file]
        if no_mpi
        else ["mpiexec", "-np", str(n_processes), elmersolver, sif_file],
        simulation_folder,
        f"{Path(name).stem}_ElmerSolver",
    )


def _pair_capacitance_matrix(
    raw_capacitance_matrix: NDArray, port_names: Sequence[str]
) -> dict[tuple[str, str], float]:
    """Map the raw Elmer capacitance matrix onto the component port names."""
    n_ports = len(port_names)
    if raw_capacitance_matrix.shape != (n_ports, n_ports):
        raise ValueError(
            f"Elmer returned a {raw_capacitance_matrix.shape} capacitance matrix "
            f"for {n_ports} terminal(s)."
        )
    return {
        (iname, jname): float(raw_capacitance_matrix[i][j])
        for (i, iname), (j, jname) in itertools.product(
            enumerate(port_names), enumerate(port_names)
        )
    }


def _lumped_to_maxwell(lumped_capacitance_matrix: NDArray) -> NDArray:
    """Convert Elmer's lumped matrix to charge-versus-voltage coefficients."""
    maxwell_matrix = -lumped_capacitance_matrix.copy()
    fill_diagonal(maxwell_matrix, lumped_capacitance_matrix.sum(axis=1))
    return maxwell_matrix


def _read_elmer_results(
    simulation_folder: Path,
    mesh_filename: str,
    n_processes: int,
    port_names: Sequence[str],
    is_temporary: bool,
) -> ElectrostaticResults:
    """Fetch results from successful Elmer simulations."""
    raw_name = Path(mesh_filename).stem
    lumped_capacitance_matrix = read_csv(
        simulation_folder / f"{raw_name.lower()}_capacitance.dat",
        sep=r"\s+",
        header=None,
        dtype=float,
    ).values
    return ElectrostaticResults(
        capacitance_matrix=_pair_capacitance_matrix(
            _lumped_to_maxwell(lumped_capacitance_matrix), port_names
        ),
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
    """Run electrostatic FEM simulations using `Elmer`_.

    Component ports define the capacitor terminals. Conductors touching a port
    are split onto their own layers before meshing so that terminals stay
    disjoint; remaining conductor surfaces are grounded. Returns the field
    solution and Maxwell capacitance matrix.

    .. note:: `ElmerGrid` and `ElmerSolver` must be on PATH. Parallel runs also
        require `ElmerSolver_mpi` and `mpiexec`.

    Args:
        component: Simulation environment as a gdsfactory component.
        element_order: Order of polynomial basis functions.
            Higher is more accurate but takes more memory and time to run.
        n_processes: Number of processes to use for parallelization
        layer_stack: :class:`~LayerStack` defining the simulation layers,
            materials, and thicknesses. A stack with conducting terminals and
            an explicit background volume named by ``background_tag`` is required.
        material_spec:
            :class:`~RFMaterialSpec` defining material parameters for the ones used in ``layer_stack``.
        simulation_folder: Directory for storing the simulation results.
            Default is a temporary directory.
        simulator_params: Elmer-specific parameters. See template file for more details.
        mesh_parameters: Keyword arguments to provide to :func:`meshwell.mesh.mesh`.
            ``background_tag`` names the explicit background volume;
            ``background_padding`` is unsupported by current meshwell.
        mesh_file: Path to a ready mesh to use. Useful for reusing one mesh file.
            By default a mesh is generated according to ``mesh_parameters``.
            The mesh has to contain the terminal surfaces for the component ports.

    .. _Elmer: https://github.com/ElmerCSC/elmerfem
    """
    _validate_solver_inputs(element_order, n_processes)

    if material_spec is None:
        material_spec: RFMaterialSpec = {
            "si": {"relative_permittivity": 11.45},
            "sio2": {"relative_permittivity": 1},
            "vacuum": {"relative_permittivity": 1},
        }

    port_names = [port.name for port in component.ports]
    if not port_names:
        raise ValueError("The component has no ports to use as capacitor terminals.")

    background_tag = (mesh_parameters or {}).get("background_tag", "vacuum")
    if mesh_parameters and "background_padding" in mesh_parameters:
        raise ValueError(
            "background_padding is unsupported by meshwell; add an explicit background layer."
        )
    if layer_stack is None:
        raise ValueError(
            "layer_stack is required with conducting terminal layers and an explicit background volume."
        )

    temp_dir = TemporaryDirectory()
    try:
        is_temporary = simulation_folder is None
        simulation_folder = Path(
            temp_dir.name if is_temporary else simulation_folder
        ).resolve()
        simulation_folder.mkdir(exist_ok=True, parents=True)

        filename = component.name + ".msh"
        mesh_path = simulation_folder / filename
        if mesh_file:
            source_mesh = Path(mesh_file).resolve()
            if source_mesh != mesh_path:
                shutil.copyfile(source_mesh, mesh_path)
        else:
            # Work on copies so that neither the component nor the layer stack
            # of the caller are modified by the per-terminal layer splitting.
            mesh_layer_stack = layer_stack.model_copy(deep=True)
            for layer_name, layer_level in mesh_layer_stack.layers.items():
                layer_level.name = layer_name
            mesh_component = component.dup()
            mesh_component.flatten()
            mesh_component = _merge_port_layer_polygons(mesh_component, port_names)
            mesh_component = get_component_with_net_layers(
                component=mesh_component,
                layer_stack=mesh_layer_stack,
                port_names=port_names,
                delimiter=PORT_DELIMITER,
            )
            # Implicit wafer padding can overlap a terminal in custom PDKs.
            prisms = get_meshwell_prisms(
                component=mesh_component,
                layer_stack=mesh_layer_stack,
                wafer_layer=None,
            )
            cad(
                entities_list=prisms,
                output_file=(
                    cad_output := (simulation_folder / filename).with_suffix(".xao")
                ),
                boundary_delimiter=BOUNDARY_DELIMITER,
                progress_bars=True,
            )
            # meshwell >= 2 dropped background volume options; `background_tag`
            # identifies the explicit background volume in the mesh.
            mesh_kwargs = {
                key: value
                for key, value in (mesh_parameters or {}).items()
                if key != "background_tag"
            }
            mesh(
                input_file=cad_output,
                output_file=mesh_path,
                boundary_delimiter=BOUNDARY_DELIMITER,
                dim=3,
                **mesh_kwargs,
            )

        groups = _sanitize_mesh_physical_names(mesh_path)
        terminals = _split_mesh_terminals(
            groups,
            port_names,
            layer_stack,
            material_spec,
            background_tag,
        )

        _elmergrid(simulation_folder, filename, n_processes)
        simulation_root = simulation_folder / Path(filename).stem
        (simulation_root / "results").mkdir(parents=True, exist_ok=True)
        names_file = simulation_root / "mesh.names"
        if not names_file.is_file():
            raise RuntimeError(
                f"ElmerGrid did not write {names_file}. Check the ElmerGrid logs."
            )
        body_indices, boundary_indices = _read_mesh_names(names_file)

        used_materials = sorted({material for _, material in terminals.bodies})
        material_to_index = {
            material: index for index, material in enumerate(used_materials, 1)
        }
        materials = []
        for material in used_materials:
            permittivity = _relative_permittivity(material_spec, material)
            materials.append(
                {
                    "index": material_to_index[material],
                    "relative_permittivity": float(permittivity),
                }
            )
        bodies = [
            {
                "index": index,
                "targets": _resolve_group_indices([group.name], body_indices, "bodies"),
                "material_index": material_to_index[material],
            }
            for index, (group, material) in enumerate(
                sorted(terminals.bodies, key=lambda item: item[0].original_name), 1
            )
        ]
        ground_boundaries = _resolve_group_indices(
            terminals.ground_surfaces, boundary_indices, "boundaries"
        )
        signals = [
            _resolve_group_indices(
                terminals.signal_surfaces[port_name], boundary_indices, "boundaries"
            )
            for port_name in port_names
        ]

        _generate_sif(
            simulation_folder,
            Path(filename).stem,
            materials=materials,
            bodies=bodies,
            ground_boundaries=ground_boundaries,
            signals=signals,
            element_order=element_order,
            simulator_params=simulator_params,
        )
        _elmersolver(simulation_folder, filename, n_processes)
        return _read_elmer_results(
            simulation_folder,
            filename,
            n_processes,
            port_names,
            is_temporary=is_temporary,
        )
    finally:
        temp_dir.cleanup()
