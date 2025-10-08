
import gplugins.emode as emc
from gdsfactory.cross_section import rib
from gdsfactory.generic_tech import LAYER_STACK
from gdsfactory.technology import LayerStack


## Set up GDSFactory LayerStack and CrossSection in units of microns
layer_stack = LayerStack(
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

layer_stack.layers["core"].thickness = 0.22
layer_stack.layers["core"].zmin = 0

layer_stack.layers["slab90"].thickness = 0.09
layer_stack.layers["slab90"].zmin = 0

layer_stack.layers["box"].thickness = 1.5
layer_stack.layers["box"].zmin = -1.5

layer_stack.layers["clad"].thickness = 1.5
layer_stack.layers["clad"].zmin = 0

## Connect and initialize EMode
em = emc.EMode()

## build_waveguide converts units to nanometers, which EMode's default
modes = em.build_waveguide(
    cross_section=rib(width=0.6),
    layer_stack=layer_stack,
    wavelength=1.55,
    num_modes=1,
    x_resolution=0.010,
    y_resolution=0.010,
    window_width = 3.0,
    window_height = 3.0,
    background_refractive_index='Air',
    max_effective_index=2.631,
)

## Launch FDM solver
em.FDM()

## Display the effective indices, TE fractions, and core confinement
em.report()

## Plot the field and refractive index profiles
em.plot()

## Close EMode
em.close()
