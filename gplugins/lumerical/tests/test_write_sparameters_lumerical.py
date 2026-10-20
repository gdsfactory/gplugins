import sys
from types import ModuleType

import gdsfactory as gf
from gdsfactory.technology import LayerLevel, LayerStack

from gplugins.lumerical.write_sparameters_lumerical import write_sparameters_lumerical


class _Session:
    def __init__(self) -> None:
        self.ports = 0
        self.fdtd_settings: dict[str, object] = {}
        self.gdspath: str | None = None

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
        self.fdtd_settings = kwargs

    def gdsimport(self, *args: object) -> None:
        self.gdspath = str(args[0])

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


def test_port_extension_reaches_beyond_pml(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(sys.modules, "lumapi", ModuleType("lumapi"))
    component = gf.components.straight(length=10, cross_section="strip")
    layer_stack = LayerStack(
        layers={
            "core": LayerLevel(layer=(1, 0), thickness=0.22, zmin=0, material="sio2")
        }
    )
    session = _Session()

    write_sparameters_lumerical(
        component,
        session=session,
        run=False,
        dirpath=tmp_path,
        layer_stack=layer_stack,
        xmargin=2,
        ymargin=0,
        port_extension=1,
    )

    assert session.gdspath is not None
    exported_component = gf.import_gds(session.gdspath)
    assert exported_component.xmin < session.fdtd_settings["x_min"] * 1e6
    assert exported_component.xmax > session.fdtd_settings["x_max"] * 1e6
