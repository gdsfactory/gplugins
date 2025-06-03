
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

layer_stack.layers[
    "core"
].thickness = 0.22

layer_stack.layers[
    "slab90"
].thickness = 0.09

## Connect and initialize EMode
em = emc.EMode()

modes = em.build_waveguide(
    cross_section=rib(width=0.6),
    layer_stack=layer_stack,
    wavelength=1.55,
    num_modes=1,
    x_resolution=0.010,
    y_resolution=0.010,
    window_width = w_core + w_trench*2,
    window_height = h_core + h_clad*2,
    background_refractive_index='Air',
    max_effective_index=2.631,
)

em.plot()

em.close()

quit()

## Settings
em.settings(
    wavelength = wavelength, x_resolution = dx, y_resolution = dy,
    window_width = w_core + w_trench*2, window_height = h_core + h_clad*2,
    num_modes = num_modes, background_refractive_index = 'Air')

## Draw shapes
em.shape(name = 'BOX', refractive_index = 'SiO2', height = h_clad)
em.shape(name = 'core', refractive_index = 'Si', width = w_core, height = h_core)

## Launch FDM solver
em.FDM()

## Display the effective indices, TE fractions, and core confinement
em.report()

## Plot the field and refractive index profiles
em.plot()

## Close EMode
em.close()
