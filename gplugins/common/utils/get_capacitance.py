from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

import gdsfactory as gf
from gdsfactory.technology import LayerStack
from gdsfactory.typings import ComponentSpec

from gplugins.common.base_models.simulation import ElectrostaticResults
from gplugins.elmer.get_capacitance import run_capacitive_simulation_elmer
from gplugins.palace.get_capacitance import (
    run_capacitive_simulation_palace,
)


def get_capacitance_path() -> Path:
    return gf.config.PATH.capacitance


def get_capacitance(
    component: ComponentSpec,
    simulator: str = "elmer",
    simulator_params: Mapping[str, Any] | None = None,
    simulation_folder: Path | str | None = None,
    layer_stack: LayerStack | None = None,
    **kwargs,
) -> ElectrostaticResults:
    """Simulate component with an electrostatic simulation and return capacitance matrix.

    For more details, see Chapter 2.9 `Capacitance matrix` in `N. Savola, “Design and modelling of long-coherence
    qubits using energy participation ratios” <http://urn.fi/URN:NBN:fi:aalto-202305213270>`_.

    Args:
        component: component or component factory.
        simulator: Simulator to use. The choices are 'elmer' or 'palace'. Both require manual install.
            This changes the format of ``simulator_params``.
        simulator_params: Simulator-specific params as a dictionary. See template files for more details.
            Has reasonable defaults.
        simulation_folder: Directory for storing the simulation results. Default is a temporary directory.
        layer_stack: :class:`~LayerStack` defining the simulation layers, materials, and thicknesses.
            Required for ``simulator='elmer'``, which needs conducting terminal layers and an explicit
            background volume named by ``mesh_parameters['background_tag']``. Optional for
            ``simulator='palace'``, which falls back to its own default stack.
        **kwargs: Simulation settings propagated to inner :func:`~run_capacitive_simulation_elmer` or
            :func:`~run_capacitive_simulation_palace` implementation.
    """
    if simulator == "elmer" and layer_stack is None:
        raise ValueError(
            "simulator='elmer' requires an explicit layer_stack with conducting "
            "terminal layers and an explicit background volume."
        )

    simulation_folder = Path(simulation_folder or get_capacitance_path())
    component = gf.get_component(component)

    simulation_folder = (
        simulation_folder / component.function_name
        if hasattr(component, "function_name")
        else simulation_folder
    )
    simulation_folder.mkdir(exist_ok=True, parents=True)

    match simulator:
        case "elmer":
            return run_capacitive_simulation_elmer(
                component,
                simulation_folder=simulation_folder,
                simulator_params=simulator_params,
                layer_stack=layer_stack,
                **kwargs,
            )
        case "palace":
            return run_capacitive_simulation_palace(
                component,
                simulation_folder=simulation_folder,
                solver_config=simulator_params,
                layer_stack=layer_stack,
                **kwargs,
            )
        case _:
            raise UserWarning(f"{simulator=!r} not implemented!")


get_capacitance_elmer = partial(get_capacitance, simulator="elmer")
get_capacitance_palace = partial(get_capacitance, simulator="palace")


# if __name__ == "__main__":
#     c = gf.components.interdigital_capacitor()
#     print(get_capacitance(c))
