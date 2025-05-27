
import gplugins.emode as emc

## Set simulation parameters
wavelength = 1550 # [nm] wavelength
dx, dy = 10, 10 # [nm] resolution
w_core = 600 # [nm] waveguide core width
w_trench = 800 # [nm] waveguide side trench width
h_core = 500 # [nm] waveguide core height
h_clad = 800 # [nm] waveguide top and bottom clad
num_modes = 2 # [-] number of modes

## Connect and initialize EMode
em = emc.EMode()

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