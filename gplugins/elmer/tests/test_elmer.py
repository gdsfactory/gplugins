from __future__ import annotations

import shutil
from math import inf
from pathlib import Path
from types import SimpleNamespace

import gdsfactory as gf
import gmsh
import numpy as np
import pytest
from gdsfactory.component import Component
from gdsfactory.gpdk import LAYER
from gdsfactory.technology import LayerStack
from gdsfactory.technology.layer_stack import LayerLevel
from meshwell.resolution import ConstantInField

from gplugins.common.utils.get_component_with_net_layers import (
    get_component_with_net_layers,
)
from gplugins.elmer import run_capacitive_simulation_elmer
from gplugins.elmer.get_capacitance import (
    _elmergrid,
    _elmersolver,
    _generate_sif,
    _lumped_to_maxwell,
    _merge_port_layer_polygons,
    _MeshTerminals,
    _pair_capacitance_matrix,
    _PhysicalGroup,
    _read_mesh_names,
    _read_elmer_results,
    _sanitize_mesh_physical_names,
    _split_mesh_terminals,
)

layer_stack = LayerStack(
    layers=dict(
        substrate=LayerLevel(
            name="substrate",
            layer=LAYER.WAFER,
            thickness=5,
            zmin=0,
            material="Si",
            mesh_order=99,
        ),
        metal=LayerLevel(
            name="metal",
            layer=LAYER.M1,
            thickness=200e-3,
            zmin=5,
            material="Nb",
            mesh_order=2,
        ),
        vacuum=LayerLevel(
            name="vacuum",
            layer=LAYER.WAFER,
            thickness=5,
            zmin=5,
            material="vacuum",
            mesh_order=100,
        ),
    )
)
material_spec = {
    "Si": {"relative_permittivity": 11.45},
    "Nb": {"relative_permittivity": inf},
    "vacuum": {"relative_permittivity": 1},
}

elmer_installed = all(shutil.which(binary) for binary in ("ElmerGrid", "ElmerSolver"))


@pytest.fixture
@gf.cell
def geometry() -> Component:
    """Two metal plates on a substrate, each plate carrying one terminal port."""
    c = gf.Component()
    c.add_polygon([(-50, -50), (50, -50), (50, 50), (-50, 50)], layer=LAYER.WAFER)
    for name, x in (("o1", -15.0), ("o2", 15.0)):
        c.add_polygon(
            [(x - 10, -10), (x + 10, -10), (x + 10, 10), (x - 10, 10)], layer=LAYER.M1
        )
        c.add_port(name=name, center=(x, 0), width=1, orientation=0, layer=LAYER.M1)
    return c


def get_mesh_parameters() -> dict:
    return dict(
        default_characteristic_length=10,
        resolution_specs={
            "substrate": [ConstantInField(resolution=10, apply_to="volumes")],
            "metal@o1": [ConstantInField(resolution=2, apply_to="volumes")],
            "metal@o2": [ConstantInField(resolution=2, apply_to="volumes")],
        },
    )


def test_generate_sif_uses_resolved_indices(tmp_path: Path) -> None:
    sif_path = _generate_sif(
        tmp_path,
        "Study",
        materials=[{"index": 1, "relative_permittivity": 11.45}],
        bodies=[{"index": 1, "targets": [1], "material_index": 1}],
        ground_boundaries=[4],
        signals=[[2, 3], [5]],
        element_order=2,
    )
    text = sif_path.read_text()
    assert 'INCLUDE "Study/mesh.names"' in text
    assert "Element = p:2" in text
    assert "Target Bodies(1) = 1" in text
    assert "Material = 1" in text
    assert "Relative Permittivity = 11.45" in text
    assert "Target Boundaries(1) = 4" in text
    assert "Target Boundaries(2) = 2 3" in text
    assert "Potential = 0.0" in text
    assert "Capacitance Body = 1" in text
    assert "Capacitance Body = 2" in text
    assert "Boundary Condition 3" in text
    assert 'Capacitance Matrix Filename = "study_capacitance.dat"' in text
    assert "Linear System Max Iterations = 500" in text
    assert "Linear System Abort Not Converged = True" in text
    # no references to material variables that are never defined
    assert "_material =" not in text


def test_generate_sif_without_ground(tmp_path: Path) -> None:
    sif_path = _generate_sif(
        tmp_path,
        "study",
        materials=[{"index": 1, "relative_permittivity": 1}],
        bodies=[{"index": 1, "targets": [7], "material_index": 1}],
        ground_boundaries=[],
        signals=[[2], [3]],
        element_order=1,
        simulator_params=None,
    )
    text = sif_path.read_text()
    assert "Potential = 0.0" not in text
    assert "Boundary Condition 1" in text
    assert "Boundary Condition 2" in text
    assert "Capacitance Body = 1" in text
    assert "Capacitance Body = 2" in text


def test_pair_capacitance_matrix_maps_port_names() -> None:
    raw = np.array([[1.0, -0.25], [-0.25, 2.0]])
    matrix = _pair_capacitance_matrix(raw, ["o1", "o2"])
    assert matrix == {
        ("o1", "o1"): 1.0,
        ("o1", "o2"): -0.25,
        ("o2", "o1"): -0.25,
        ("o2", "o2"): 2.0,
    }


def test_pair_capacitance_matrix_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError, match="capacitance matrix"):
        _pair_capacitance_matrix(np.zeros((2, 2)), ["o1", "o2", "o3"])


def test_lumped_to_maxwell_capacitance_matrix() -> None:
    lumped = np.array([[0.5, 2.0], [3.0, 1.0]])
    np.testing.assert_allclose(_lumped_to_maxwell(lumped), [[2.5, -2.0], [-3.0, 4.0]])


def test_read_results_uses_lowercase_capacitance_name(tmp_path: Path) -> None:
    (tmp_path / "study_capacitance.dat").write_text(
        "   1.0E+00  2.0E+00\n   2.0E+00  3.0E+00\n", encoding="utf-8"
    )
    results = _read_elmer_results(tmp_path, "Study.msh", 1, ["o1", "o2"], True)
    assert results.capacitance_matrix["o1", "o2"] == -2.0


def test_read_mesh_names_accepts_title_case_headers(tmp_path: Path) -> None:
    names_file = tmp_path / "mesh.names"
    names_file.write_text(
        "! Names for Bodies\n$ vacuum = 4\n! Names for Boundaries\n$ metal_o1 = 7\n"
    )
    assert _read_mesh_names(names_file) == ({"vacuum": 4}, {"metal_o1": 7})


def test_split_mesh_terminals_maps_sanitized_base_layer() -> None:
    stack = layer_stack.model_copy(deep=True)
    stack.layers["substrate-Si"] = stack.layers.pop("substrate")
    groups = [
        _PhysicalGroup(3, 1, "substrate_Si", "substrate_Si"),
        _PhysicalGroup(3, 2, "metal_o1", "metal_o1"),
        _PhysicalGroup(3, 3, "metal_o2", "metal_o2"),
        _PhysicalGroup(3, 6, "vacuum", "vacuum"),
        _PhysicalGroup(2, 4, "metal_o1___boundary", "metal_o1___boundary"),
        _PhysicalGroup(2, 5, "metal_o2___boundary", "metal_o2___boundary"),
    ]
    terminals = _split_mesh_terminals(
        groups, ["o1", "o2"], stack, material_spec, "vacuum"
    )
    assert isinstance(terminals, _MeshTerminals)
    assert terminals.bodies[0][1] == "Si"
    assert terminals.signal_surfaces == {
        "o1": ["metal_o1___boundary"],
        "o2": ["metal_o2___boundary"],
    }


def test_missing_material_is_rejected() -> None:
    groups = [
        _PhysicalGroup(3, 1, "substrate", "substrate"),
        _PhysicalGroup(3, 2, "vacuum", "vacuum"),
    ]
    with pytest.raises(ValueError, match="Material 'Si' needs relative_permittivity"):
        _split_mesh_terminals(
            groups, [], layer_stack, {"vacuum": material_spec["vacuum"]}, "vacuum"
        )


@pytest.mark.parametrize("permittivity", [float("nan"), -float("inf"), 0.0, -1.0])
def test_invalid_permittivity_is_rejected(permittivity: float) -> None:
    groups = [_PhysicalGroup(3, 1, "vacuum", "vacuum")]
    spec = {**material_spec, "vacuum": {"relative_permittivity": permittivity}}
    with pytest.raises(ValueError, match="relative_permittivity"):
        _split_mesh_terminals(groups, [], layer_stack, spec, "vacuum")


def test_port_on_dielectric_is_rejected() -> None:
    groups = [
        _PhysicalGroup(3, 1, "vacuum", "vacuum"),
        _PhysicalGroup(3, 2, "metal_o1", "metal_o1"),
        _PhysicalGroup(2, 3, "metal_o1___vacuum", "metal_o1___vacuum"),
    ]
    spec = {**material_spec, "Nb": {"relative_permittivity": 4.0}}
    with pytest.raises(ValueError, match="non-conductor"):
        _split_mesh_terminals(groups, ["o1"], layer_stack, spec, "vacuum")


def test_missing_background_volume_is_rejected() -> None:
    groups = [_PhysicalGroup(3, 1, "substrate", "substrate")]
    with pytest.raises(ValueError, match="No background volume"):
        _split_mesh_terminals(groups, [], layer_stack, material_spec, "vacuum")


def test_background_volume_uses_its_layer_material() -> None:
    stack = layer_stack.model_copy(deep=True)
    stack.layers["enclosure"] = stack.layers.pop("vacuum")
    stack.layers["enclosure"].material = "air"
    spec = {**material_spec, "air": {"relative_permittivity": 1}}
    del spec["vacuum"]
    groups = [
        _PhysicalGroup(3, 1, "enclosure", "enclosure"),
        _PhysicalGroup(3, 2, "metal_o1", "metal_o1"),
        _PhysicalGroup(2, 3, "metal_o1___boundary", "metal_o1___boundary"),
    ]
    terminals = _split_mesh_terminals(groups, ["o1"], stack, spec, "enclosure")
    assert [material for _, material in terminals.bodies] == ["air", "air"]


def test_ambiguous_layer_aliases_are_rejected() -> None:
    stack = layer_stack.model_copy(deep=True)
    stack.layers["substrate-Si"] = stack.layers.pop("substrate")
    stack.layers["substrate_Si"] = stack.layers["substrate-Si"].model_copy(deep=True)
    stack.layers["substrate_Si"].material = "other"
    groups = [_PhysicalGroup(3, 1, "substrate_Si", "substrate_Si")]
    with pytest.raises(ValueError, match="Layer identifier collision"):
        _split_mesh_terminals(groups, [], stack, material_spec, None)


def test_unsupported_background_padding_is_rejected(geometry: Component) -> None:
    with pytest.raises(ValueError, match="background_padding is unsupported"):
        run_capacitive_simulation_elmer(
            geometry, mesh_parameters={"background_padding": 2.0}
        )


def test_layer_stack_is_required(geometry: Component) -> None:
    with pytest.raises(ValueError, match="layer_stack is required"):
        run_capacitive_simulation_elmer(geometry)


def test_connected_metal_polygons_form_one_terminal() -> None:
    component = gf.Component()
    component.add_polygon([(0, 0), (10, 0), (10, 10), (0, 10)], layer=LAYER.M1)
    component.add_polygon([(8, 0), (18, 0), (18, 10), (8, 10)], layer=LAYER.M1)
    component.add_port(
        name="o1", center=(0, 5), width=1, orientation=180, layer=LAYER.M1
    )
    merged = _merge_port_layer_polygons(component.dup(), ["o1"])
    split_stack = layer_stack.model_copy(deep=True)
    split = get_component_with_net_layers(merged, split_stack, ["o1"], delimiter="@")
    assert not split.get_polygons(layers=[LAYER.M1]).get(LAYER.M1)
    assert (
        len(split.get_polygons(layers=[(10010, 0)], by="tuple").get((10010, 0), []))
        == 1
    )


def test_case_only_physical_names_are_rejected(tmp_path: Path) -> None:
    mesh_file = tmp_path / "collision.msh"
    gmsh.initialize()
    try:
        gmsh.model.add("collision")
        first = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
        second = gmsh.model.occ.addBox(2, 0, 0, 1, 1, 1)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [first], name="Metal")
        gmsh.model.addPhysicalGroup(3, [second], name="metal")
        gmsh.model.mesh.generate(3)
        gmsh.write(str(mesh_file))
    finally:
        gmsh.finalize()

    with pytest.raises(ValueError, match="identifier collision"):
        _sanitize_mesh_physical_names(mesh_file)


def test_overlong_physical_name_is_rejected(tmp_path: Path) -> None:
    mesh_file = tmp_path / "overlong.msh"
    overlong_name = "m" * 51
    gmsh.initialize()
    try:
        gmsh.model.add("overlong")
        box = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [box], name=overlong_name)
        gmsh.model.mesh.generate(3)
        gmsh.write(str(mesh_file))
    finally:
        gmsh.finalize()

    with pytest.raises(ValueError, match="limit"):
        _sanitize_mesh_physical_names(mesh_file)

    # The name is rejected before the mesh is rewritten with the sanitized ones.
    gmsh.initialize()
    try:
        gmsh.merge(str(mesh_file))
        names = [
            gmsh.model.getPhysicalName(dim, tag)
            for dim, tag in gmsh.model.getPhysicalGroups()
        ]
    finally:
        gmsh.finalize()
    assert names == [overlong_name]


@pytest.mark.parametrize("n_processes", [0, -1, 1.5, "two", None, True])
def test_invalid_n_processes(geometry: Component, n_processes) -> None:
    with pytest.raises((TypeError, ValueError), match="n_processes"):
        run_capacitive_simulation_elmer(geometry, n_processes=n_processes)


@pytest.mark.parametrize("element_order", [0, -1, 1.5, "two", None, True])
def test_invalid_element_order(geometry: Component, element_order) -> None:
    with pytest.raises((TypeError, ValueError), match="element_order"):
        run_capacitive_simulation_elmer(geometry, element_order=element_order)


def test_missing_executable_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="ElmerGrid"):
        _elmergrid(tmp_path, "study.msh")
    with pytest.raises(RuntimeError, match="ElmerSolver"):
        _elmersolver(tmp_path, "study.msh")


def test_missing_mpi_launcher_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: None if name == "mpiexec" else f"/usr/bin/{name}",
    )
    with pytest.raises(RuntimeError, match="mpiexec"):
        _elmersolver(tmp_path, "study.msh", n_processes=2)


@pytest.mark.parametrize("binary", ["ElmerGrid", "ElmerSolver"])
def test_nonzero_exit_propagates(monkeypatch, tmp_path: Path, binary) -> None:
    class _ProcessStub:
        returncode = 1

    async def _execute(*args, **kwargs):
        return _ProcessStub()

    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "gplugins.elmer.get_capacitance.execute_and_stream_output", _execute
    )
    with pytest.raises(RuntimeError, match="exit code 1"):
        if binary == "ElmerGrid":
            _elmergrid(tmp_path, "study.msh")
        else:
            _elmersolver(tmp_path, "study.msh")


def test_mesh_file_without_terminal_surfaces_raises(
    geometry: Component, tmp_path: Path
) -> None:
    mesh_file = tmp_path / "no_terminals.msh"
    gmsh.initialize()
    gmsh.model.add("no_terminals")
    box = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
    gmsh.model.occ.synchronize()
    gmsh.model.addPhysicalGroup(3, [box], name="vacuum")
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(mesh_file))
    gmsh.finalize()

    with pytest.raises(ValueError, match="terminal 'o1'"):
        run_capacitive_simulation_elmer(
            geometry,
            layer_stack=layer_stack,
            material_spec=material_spec,
            mesh_file=mesh_file,
            simulation_folder=tmp_path,
        )


@pytest.mark.parametrize("background_tag", [None, "", "   ", 42])
def test_invalid_background_tag_raises(
    geometry: Component, tmp_path: Path, background_tag
) -> None:
    with pytest.raises(ValueError, match="background_tag"):
        run_capacitive_simulation_elmer(
            geometry,
            layer_stack=layer_stack,
            material_spec=material_spec,
            simulation_folder=tmp_path,
            mesh_parameters={"background_tag": background_tag},
        )


class _StubComponent:
    """Minimal stand-in so duplicate and non-string port names can be exercised."""

    def __init__(self, names: list[object]) -> None:
        self.ports = [SimpleNamespace(name=name) for name in names]


@pytest.mark.parametrize("bad_name", [None, 42, "", "   "])
def test_invalid_port_names_are_rejected(bad_name: object, tmp_path: Path) -> None:
    component = _StubComponent([bad_name])
    with pytest.raises(ValueError, match="Port names"):
        run_capacitive_simulation_elmer(
            component,
            simulation_folder=tmp_path,
            mesh_parameters={"background_tag": "vacuum"},
        )
    assert list(tmp_path.iterdir()) == []


def test_duplicate_port_names_are_rejected(tmp_path: Path) -> None:
    component = _StubComponent(["o1", "o1"])
    with pytest.raises(ValueError, match="unique"):
        run_capacitive_simulation_elmer(
            component,
            simulation_folder=tmp_path,
            mesh_parameters={"background_tag": "vacuum"},
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(elmer_installed, reason="Expects ElmerGrid to be missing")
def test_layer_stack_is_not_mutated(geometry: Component, tmp_path: Path) -> None:
    stack = layer_stack.model_copy(deep=True)
    layers_before = set(stack.layers)
    with pytest.raises(RuntimeError, match="ElmerGrid"):
        run_capacitive_simulation_elmer(
            geometry,
            layer_stack=stack,
            material_spec=material_spec,
            mesh_parameters=get_mesh_parameters(),
            simulation_folder=tmp_path,
        )
    assert set(stack.layers) == layers_before


@pytest.mark.skipif(not elmer_installed, reason="Elmer is not installed")
@pytest.mark.parametrize("relative_folder", [False, True])
def test_elmer_capacitance_simulation_smoke(
    geometry: Component, tmp_path: Path, monkeypatch, relative_folder: bool
) -> None:
    stack = layer_stack.model_copy(deep=True)
    stack.layers["metal"].name = "other_name"
    if relative_folder:
        monkeypatch.chdir(tmp_path)
    simulation_folder = Path("relative_elmer_results") if relative_folder else tmp_path
    results = run_capacitive_simulation_elmer(
        geometry,
        layer_stack=stack,
        material_spec=material_spec,
        mesh_parameters=get_mesh_parameters(),
        simulation_folder=simulation_folder,
    )
    assert stack.layers["metal"].name == "other_name"
    matrix = results.raw_capacitance_matrix
    assert matrix.shape == (2, 2)
    assert np.all(np.isfinite(matrix))
    assert set(results.capacitance_matrix) == {
        ("o1", "o1"),
        ("o1", "o2"),
        ("o2", "o1"),
        ("o2", "o2"),
    }
    assert results.mesh_location is not None
    assert results.field_file_location is not None


@pytest.mark.skipif(not elmer_installed, reason="Elmer is not installed")
def test_temporary_simulation_has_no_deleted_result_paths(geometry: Component) -> None:
    results = run_capacitive_simulation_elmer(
        geometry,
        layer_stack=layer_stack,
        material_spec=material_spec,
        mesh_parameters=get_mesh_parameters(),
    )
    assert results.mesh_location is None
    assert results.field_file_location is None
