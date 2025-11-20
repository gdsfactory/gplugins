from math import inf

import gdsfactory as gf
from meshwell.resolution import ConstantInField, ThresholdField
import pytest
from gdsfactory.component import Component
from gdsfactory.components.analog.interdigital_capacitor import (
    interdigital_capacitor,
)
from gdsfactory.generic_tech import LAYER
from gdsfactory.technology import LayerStack
from gdsfactory.technology.layer_stack import LayerLevel

from gplugins.palace import (
    run_capacitive_simulation_palace,
    run_scattering_simulation_palace,
)

layer_stack = LayerStack(
    layers=dict(
        substrate=LayerLevel(
            name="substrate",
            layer=LAYER.WAFER,
            thickness=500,
            zmin=0,
            material="Si",
            mesh_order=99,
        ),
        bw=LayerLevel(
            name="bw",
            layer=LAYER.WG,
            thickness=200e-3,
            zmin=500,
            material="Nb",
            mesh_order=2,
        ),
    )
)
material_spec = {
    "Si": {"relative_permittivity": 11.45, "relative_permeability": 1},
    "Nb": {"relative_permittivity": inf, "relative_permeability": 1},
    "vacuum": {"relative_permittivity": 1, "relative_permeability": 1},
}


@pytest.fixture
@gf.cell
def geometry() -> Component:
    c = gf.Component()
    cap = c << interdigital_capacitor()
    # Add ports for marking capacitor terminals
    for port in cap.ports:
        c.add_port(name=f"bw_{port.name}", port=port)
    # Add simulation area layer around the layout
    c.kdb_cell.shapes(LAYER.WAFER).insert(c.bbox().enlarged(50, 50))
    return c


def get_reasonable_mesh_parameters_capacitance(c: Component):
    return dict(
        # background_tag="vacuum",
        # background_padding=(0,) * 5 + (700,),
        # port_names=[port.name for port in c.ports],
        default_characteristic_length=50,
        resolution_specs={
            "bw": [ConstantInField(resolution=100, apply_to="surfaces")],
            "substrate": [
                ConstantInField(resolution=200, apply_to="curves"),
                ConstantInField(resolution=150, apply_to="surfaces"),
                ConstantInField(resolution=300, apply_to="volumes"),
            ],
            "vacuum": [ConstantInField(resolution=200, apply_to="surfaces")],
            **{
                f"bw@{port.name}___substrate": [
                    ThresholdField(
                        sizemin=20, distmin=4, distmax=30, sizemax=100, apply_to="curves"
                    )
                ]
                # Older style:
                # {  # `__` is used as the layer to port delimiter for Palace
                #     "resolution": 10,
                #     "DistMax": 30,
                #     "DistMin": 10,
                #     "SizeMax": 10,
                #     "SizeMin": 1,
                # }
                for port in c.ports
            },
        },
    )


def test_palace_capacitance_simulation_runs(geometry, tmp_path) -> None:
    results = run_capacitive_simulation_palace(
        geometry,
        layer_stack=layer_stack,
        material_spec=material_spec,
        mesh_parameters=get_reasonable_mesh_parameters_capacitance(geometry),
        simulation_folder=tmp_path,
    )
    assert results.capacitance_matrix
    assert results.mesh_location
    assert results.field_file_location


@pytest.mark.parametrize("n_processes", [(1), (2), (4)])
def test_palace_capacitance_simulation_n_processes(geometry, n_processes) -> None:
    run_capacitive_simulation_palace(
        geometry,
        layer_stack=layer_stack,
        material_spec=material_spec,
        n_processes=n_processes,
        mesh_parameters=get_reasonable_mesh_parameters_capacitance(geometry),
    )


@pytest.mark.parametrize("invalid_n_processes", [0, -1, -5, 1.5, "two", None])
def test_palace_capacitance_simulation_invalid_n_processes(
    geometry, invalid_n_processes
) -> None:
    with pytest.raises((ValueError, TypeError)):
        run_capacitive_simulation_palace(
            geometry,
            layer_stack=layer_stack,
            material_spec=material_spec,
            mesh_parameters=get_reasonable_mesh_parameters_capacitance(geometry),
            n_processes=invalid_n_processes,
        )


@pytest.mark.parametrize("element_order", [(1), (2), (3)])
def test_palace_capacitance_simulation_element_order(geometry, element_order) -> None:
    run_capacitive_simulation_palace(
        geometry,
        layer_stack=layer_stack,
        material_spec=material_spec,
        solver_config={"Order": element_order},
        mesh_parameters=get_reasonable_mesh_parameters_capacitance(geometry),
    )


@pytest.mark.parametrize("invalid_element_order", [0, -1, 1.5, "two"])
def test_palace_capacitance_simulation_invalid_element_order(
    geometry, invalid_element_order
) -> None:
    with pytest.raises((ValueError, TypeError)):
        run_capacitive_simulation_palace(
            geometry,
            layer_stack=layer_stack,
            material_spec=material_spec,
            solver_config={"Order": invalid_element_order},
            mesh_parameters=get_reasonable_mesh_parameters_capacitance(geometry),
        )


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_mesh_size_field(geometry) -> None:
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_flip_chip(geometry) -> None:
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_pyvista_plot(geometry) -> None:
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_cdict_form(geometry) -> None:
    pass


def get_reasonable_mesh_parameters_scattering(c: Component):
    return dict(
        # background_tag="vacuum",
        # background_padding=(0,) * 5 + (700,),
        port_names=c.ports,
        default_characteristic_length=200,
        resolutions={
            "bw": {
                "resolution": 15,
            },
            "substrate": {
                "resolution": 40,
            },
            "vacuum": {
                "resolution": 40,
            },
            **{
                f"bw{port}": {
                    "resolution": 20,
                    "DistMax": 30,
                    "DistMin": 10,
                    "SizeMax": 14,
                    "SizeMin": 3,
                }
                for port in c.ports
            },
        },
    )


@pytest.mark.skip(reason="Palace not in CI")
@pytest.mark.parametrize("geometry", [True], indirect=True)
def test_palace_scattering_simulation_runs(geometry) -> None:
    c = geometry
    run_scattering_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        mesh_parameters=get_reasonable_mesh_parameters_scattering(c),
    )


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize(
    "geometry, n_processes", [(True, 1), (True, 2), (True, 4)], indirect=["geometry"]
)
def test_palace_scattering_simulation_n_processes(geometry, n_processes) -> None:
    c = geometry
    run_scattering_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        n_processes=n_processes,
        mesh_parameters=get_reasonable_mesh_parameters_scattering(c),
    )


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize(
    "geometry, element_order", [(True, 1), (True, 2), (True, 3)], indirect=["geometry"]
)
def test_palace_scattering_simulation_element_order(geometry, element_order) -> None:
    c = geometry()
    run_scattering_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        solver_config={"Order": element_order},
        mesh_parameters=get_reasonable_mesh_parameters_scattering(c),
    )


@pytest.mark.skip(reason="TODO")
def test_palace_scattering_simulation_mesh_size_field(geometry) -> None:
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_scattering_simulation_flip_chip(geometry) -> None:
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_scattering_simulation_pyvista_plot(geometry) -> None:
    pass
