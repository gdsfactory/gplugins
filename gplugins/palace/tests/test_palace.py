from math import inf

import gdsfactory as gf
import pytest
from gdsfactory.component import Component
from gdsfactory.components.interdigital_capacitor_enclosed import (
    interdigital_capacitor_enclosed,
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
            layer=LAYER.WAFER,
            thickness=500,
            zmin=0,
            material="Si",
            mesh_order=99,
        ),
        bw=LayerLevel(
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
def geometry(lumped_ports=False) -> Component:
    simulation_box = [[-200, -200], [200, 200]]
    c = gf.Component()
    cap = c << interdigital_capacitor_enclosed(
        metal_layer=LAYER.WG, gap_layer=LAYER.DEEPTRENCH, enclosure_box=simulation_box
    )
    if lumped_ports:
        lumped_port_1_1 = gf.components.bbox(((-40, 11), (-46, 5)), layer=LAYER.PORT)
        lumped_port_1_2 = gf.components.bbox(((-40, -11), (-46, -5)), layer=LAYER.PORT)
        c << lumped_port_1_1
        c << lumped_port_1_2
        c.add_port("o1_1", lumped_port_1_1.center, layer=LAYER.PORT, width=1)
        c.add_port("o1_2", lumped_port_1_2.center, layer=LAYER.PORT, width=1)

        lumped_port_2_1 = gf.components.bbox(((40, 11), (46, 5)), layer=LAYER.PORT)
        lumped_port_2_2 = gf.components.bbox(((40, -11), (46, -5)), layer=LAYER.PORT)
        c << lumped_port_2_1
        c << lumped_port_2_2
        c.add_port("o2_1", lumped_port_2_1.center, layer=LAYER.PORT, width=1)
        c.add_port("o2_2", lumped_port_2_2.center, layer=LAYER.PORT, width=1)
    else:
        c.add_ports(cap.ports)
    substrate = gf.components.bbox(bbox=simulation_box, layer=LAYER.WAFER)
    c << substrate
    c.flatten()
    return c


def get_reasonable_mesh_parameters_capacitance(c: Component):
    return dict(
        background_tag="vacuum",
        background_padding=(0,) * 5 + (700,),
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
def test_palace_capacitance_simulation_runs(geometry) -> None:
    c = geometry
    run_capacitive_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        mesh_parameters=get_reasonable_mesh_parameters_capacitance(c),
    )


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize("n_processes", [(1), (2), (4)])
def test_palace_capacitance_simulation_n_processes(geometry, n_processes) -> None:
    c = geometry
    run_capacitive_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        n_processes=n_processes,
        mesh_parameters=get_reasonable_mesh_parameters_capacitance(c),
    )


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize("element_order", [(1), (2), (3)])
def test_palace_capacitance_simulation_element_order(geometry, element_order) -> None:
    c = geometry
    run_capacitive_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        element_order=element_order,
        mesh_parameters=get_reasonable_mesh_parameters_capacitance(c),
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
        background_tag="vacuum",
        background_padding=(0,) * 5 + (700,),
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
        element_order=element_order,
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
