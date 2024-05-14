from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

import gdsfactory as gf
from gdsfactory.typings import ComponentSpec

from gplugins.common.base_models.simulation import DrivenFullWaveResults
from gplugins.palace.get_scattering import run_scattering_simulation_palace


def get_scattering(
    component: ComponentSpec,
    simulator: str = "palace",
    simulator_params: Mapping[str, Any] | None = None,
    simulation_folder: Path | str | None = None,
    **kwargs,
) -> DrivenFullWaveResults:
    """Simulate component with a full-wave simulation and return scattering matrix.

    Args:
        component: component or component factory.
        simulator: Simulator to use. The choices are 'elmer' or 'palace'. Both require manual install.
            This changes the format of ``simulator_params``.
        simulator_params: Simulator-specific params as a dictionary. See template files for more details.
            Has reasonable defaults.
        simulation_folder: Directory for storing the simulation results. Default is a temporary directory.
        **kwargs: Simulation settings propagated to inner :func:`~run_capacitive_simulation_elmer` or
            :func:`~run_capacitive_simulation_palace` implementation.
    """
    simulation_folder = Path(simulation_folder)
    component = gf.get_component(component)

    simulation_folder = (
        simulation_folder / component.function_name
        if hasattr(component, "function_name")
        else simulation_folder
    )
    simulation_folder.mkdir(exist_ok=True, parents=True)

    match simulator:
        case "elmer":
            raise NotImplementedError("TODO")
        #     return run_scattering_simulation_elmer(
        #         component,
        #         simulation_folder=simulation_folder,
        #         simulator_params=simulator_params,
        #         **kwargs,
        #     )
        case "palace":
            return run_scattering_simulation_palace(
                component,
                simulation_folder=simulation_folder,
                simulator_params=simulator_params,
                **kwargs,
            )
        case _:
            raise UserWarning(f"{simulator=!r} not implemented!")

    # TODO do we need to infer path or be explicit?
    # component_hash = get_component_hash(component)
    # kwargs_hash = get_kwargs_hash(**kwargs)
    # simulation_hash = hashlib.md5((component_hash + kwargs_hash).encode()).hexdigest()

    # return dirpath / f"{component.name}_{simulation_hash}.npz"


get_scattering_elmer = partial(get_scattering, tool="elmer")
get_scattering_palace = partial(get_scattering, tool="palace")

# if __name__ == "__main__":
# TODO example
