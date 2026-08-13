import sys
from types import ModuleType

import gdsfactory as gf
from gdsfactory.technology import LayerLevel, LayerStack

from gplugins.lumerical.write_sparameters_lumerical import write_sparameters_lumerical


class _Session:
    def __init__(self) -> None:
        self.ports = 0

    def newproject(self) -> None:
        pass

    def selectall(self) -> None:
        pass

    def deleteall(self) -> None:
        pass

    def addrect(self, **kwargs: object) -> None:
        pass

    def setnamed(self, *args: object) -> None:
        pass

    def addfdtd(self, **kwargs: object) -> None:
        pass

    def gdsimport(self, *args: object) -> None:
        pass

    def addport(self) -> None:
        self.ports += 1

    def setglobalsource(self, *args: object) -> None:
        pass


def test_keeps_ports_on_layers_not_in_layer_stack(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(sys.modules, "lumapi", ModuleType("lumapi"))
    component = gf.Component()
    component.add_polygon([(0, 0), (10, 0), (10, 1), (0, 1)], layer=(1, 0))
    component.add_port(
        name="known",
        center=(0, 0.5),
        width=1,
        orientation=180,
        layer=(1, 0),
        port_type="optical",
    )
    component.add_port(
        name="unknown",
        center=(10, 0.5),
        width=1,
        orientation=0,
        layer=(2, 0),
        port_type="optical",
    )
    layer_stack = LayerStack(
        layers={
            "core": LayerLevel(layer=(1, 0), thickness=0.22, zmin=0, material="sio2")
        }
    )
    session = _Session()

    result = write_sparameters_lumerical(
        component,
        session=session,
        run=False,
        dirpath=tmp_path,
        layer_stack=layer_stack,
    )

    assert result is session
    assert session.ports == 2
