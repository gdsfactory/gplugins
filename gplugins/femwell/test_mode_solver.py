import numpy as np
from gdsfactory.generic_tech import LAYER_STACK
from gdsfactory.technology import LayerStack

from gplugins.femwell.mode_solver import Modes, compute_cross_section_modes

NUM_MODES = 1


def compute_modes(
    overwrite: bool = True, with_cache: bool = False, num_modes: int = NUM_MODES
) -> Modes:
    filtered_layer_stack = LayerStack(
        layers={
            k: LAYER_STACK.layers[k]
            for k in (
                "core",
                "clad",
                "slab90",
                "box",
            )
        }
    )

    filtered_layer_stack.layers["core"].thickness = 0.2

    resolutions = {
        "core": {"resolution": 0.02, "distance": 2},
        "clad": {"resolution": 0.2, "distance": 1},
        "box": {"resolution": 0.2, "distance": 1},
        "slab90": {"resolution": 0.05, "distance": 1},
    }
    return compute_cross_section_modes(
        cross_section="rib",
        layer_stack=filtered_layer_stack,
        wavelength=1.55,
        num_modes=num_modes,
        order=1,
        radius=np.inf,
        resolutions=resolutions,
        overwrite=overwrite,
        with_cache=with_cache,
    )


def test_compute_cross_section_mode() -> None:
    modes = compute_modes()
    assert len(modes) == NUM_MODES, len(modes)


if __name__ == "__main__":
    test_compute_cross_section_mode()
