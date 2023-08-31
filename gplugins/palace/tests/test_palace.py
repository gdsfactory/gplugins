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

from gplugins.palace import run_capacitive_simulation_palace

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
    "Si": {"relative_permittivity": 11.45},
    "Nb": {"relative_permittivity": inf},
    "vacuum": {"relative_permittivity": 1},
}


@pytest.fixture
@gf.cell
def geometry():
    simulation_box = [[-200, -200], [200, 200]]
    c = gf.Component()
    cap = c << interdigital_capacitor_enclosed(
        metal_layer=LAYER.WG, gap_layer=LAYER.DEEPTRENCH, enclosure_box=simulation_box
    )
    c.add_ports(cap.ports)
    substrate = gf.components.bbox(bbox=simulation_box, layer=LAYER.WAFER)
    c << substrate
    c.flatten()
    return c


def get_reasonable_mesh_parameters(c: Component):
    return dict(
        background_tag="vacuum",
        background_padding=(0,) * 5 + (700,),
        portnames=c.ports,
        default_characteristic_length=200,
        layer_portname_delimiter=(delimiter := "__"),
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
                f"bw{delimiter}{port}": {
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
def test_palace_capacitance_simulation_runs(geometry):
    c = geometry
    run_capacitive_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        mesh_parameters=get_reasonable_mesh_parameters(c),
    )


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize("n_processes", [(1), (2), (4)])
def test_palace_capacitance_simulation_n_processes(geometry, n_processes):
    c = geometry
    run_capacitive_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        n_processes=n_processes,
        mesh_parameters=get_reasonable_mesh_parameters(c),
    )


@pytest.mark.skip(reason="TODO")
@pytest.mark.parametrize("element_order", [(1), (2), (3)])
def test_palace_capacitance_simulation_element_order(geometry, element_order):
    c = geometry
    run_capacitive_simulation_palace(
        c,
        layer_stack=layer_stack,
        material_spec=material_spec,
        element_order=element_order,
        mesh_parameters=get_reasonable_mesh_parameters(c),
    )


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_mesh_size_field(geometry):
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_flip_chip(geometry):
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_pyvist_plot(geometry):
    pass


@pytest.mark.skip(reason="TODO")
def test_palace_capacitance_simulation_cdict_form(geometry):
    pass
