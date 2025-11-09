import numpy as np
import pytest
from gdsfactory.generic_tech import LAYER_STACK
from gdsfactory.technology import LayerStack
from meshwell.resolution import ConstantInField

from gplugins.femwell.mode_solver import Modes, compute_cross_section_modes

NUM_MODES = 1


def compute_modes(num_modes: int = NUM_MODES) -> Modes:
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

    resolution_specs = {
        "core": [ConstantInField(resolution=0.4, apply_to="surfaces")],
        "clad": [ConstantInField(resolution=0.4, apply_to="surfaces")],
        "box": [ConstantInField(resolution=0.4, apply_to="surfaces")],
        "slab90": [ConstantInField(resolution=1, apply_to="surfaces")],
    }
    return compute_cross_section_modes(
        cross_section="rib",
        layer_stack=filtered_layer_stack,
        wavelength=1.55,
        num_modes=num_modes,
        order=1,
        radius=np.inf,
        resolution_specs=resolution_specs,
    )


@pytest.mark.skip(reason="2D cross-section meshing not implemented")
def test_compute_cross_section_mode() -> None:
    modes = compute_modes()
    assert len(modes) == NUM_MODES, len(modes)


if __name__ == "__main__":
    test_compute_cross_section_mode()
