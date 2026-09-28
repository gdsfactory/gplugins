from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gplugins.common.utils import get_capacitance as gc


class _RecordingDriver:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, component: object, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.calls[-1]


@pytest.fixture
def stub_component(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gc.gf, "get_component", lambda _: SimpleNamespace(function_name="stub")
    )


@pytest.fixture
def elmer_driver(monkeypatch: pytest.MonkeyPatch) -> _RecordingDriver:
    driver = _RecordingDriver()
    monkeypatch.setattr(gc, "run_capacitive_simulation_elmer", driver)
    return driver


@pytest.fixture
def palace_driver(monkeypatch: pytest.MonkeyPatch) -> _RecordingDriver:
    driver = _RecordingDriver()
    monkeypatch.setattr(gc, "run_capacitive_simulation_palace", driver)
    return driver


def test_elmer_rejects_missing_stack_before_creating_folder(
    tmp_path: Path, stub_component: None, elmer_driver: _RecordingDriver
) -> None:
    folder = tmp_path / "capacitance"
    with pytest.raises(ValueError, match="layer_stack"):
        gc.get_capacitance(
            "stub", simulator="elmer", simulation_folder=folder, mesh_parameters={}
        )
    assert not folder.exists()
    assert elmer_driver.calls == []


def test_elmer_forwards_explicit_stack(
    tmp_path: Path, stub_component: None, elmer_driver: _RecordingDriver
) -> None:
    stack = object()
    gc.get_capacitance(
        "stub",
        simulator="elmer",
        simulation_folder=tmp_path,
        layer_stack=stack,
    )
    assert elmer_driver.calls[0]["layer_stack"] is stack


def test_palace_forwards_explicit_stack(
    tmp_path: Path, stub_component: None, palace_driver: _RecordingDriver
) -> None:
    stack = object()
    gc.get_capacitance(
        "stub",
        simulator="palace",
        simulation_folder=tmp_path,
        layer_stack=stack,
    )
    assert palace_driver.calls[0]["layer_stack"] is stack


def test_palace_allows_default_stack(
    tmp_path: Path, stub_component: None, palace_driver: _RecordingDriver
) -> None:
    gc.get_capacitance("stub", simulator="palace", simulation_folder=tmp_path)
    assert palace_driver.calls[0]["layer_stack"] is None


def test_elmer_alias_selects_simulator(
    tmp_path: Path, stub_component: None, elmer_driver: _RecordingDriver
) -> None:
    gc.get_capacitance_elmer("stub", simulation_folder=tmp_path, layer_stack=object())
    assert len(elmer_driver.calls) == 1
    assert "tool" not in elmer_driver.calls[0]


def test_palace_alias_selects_simulator(
    tmp_path: Path, stub_component: None, palace_driver: _RecordingDriver
) -> None:
    gc.get_capacitance_palace("stub", simulation_folder=tmp_path)
    assert len(palace_driver.calls) == 1
    assert "tool" not in palace_driver.calls[0]
