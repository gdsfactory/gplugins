"""Useful optical constant manipulations."""

import numpy as np


def permittivity_real_from_index(n, k):
    """Real part of permittivity, complex constant index.

    Arguments:
        n: (unitless) real part of the refractive index
        k: (unitless) imaginary part of the refractive index

    Return:
        real part of the permittivity
    """
    return n**2 - k**2


def permittivity_imag_from_index(n, k):
    """Imaginary part of permittivity, complex constant index.

    Arguments:
        n: (unitless) real part of the refractive index
        k: (unitless) imaginary part of the refractive index

    Return:
        imaginary part of the permittivity
    """
    return 2 * n * k


def D_conductivity_um(n, k, wavelength):
    """Conductivity as defined by Meep https://meep.readthedocs.io/en/latest/Materials/#conductivity-and-complex.

    Assumes natural units, with lengthscale in microns (see https://meep.readthedocs.io/en/latest/Introduction/#units-in-meep)

    Arguments:
        n: (unitless) real part of the refractive index
        k: (unitless) imaginary part of the refractive index
        wavelength (um): of the light

    Returns:
        conductivity sigma_D D (see https://meep.readthedocs.io/en/latest/Materials/#conductivity-and-complex)
    """
    frequency = 1 / wavelength
    return (
        2
        * np.pi
        * frequency
        * permittivity_imag_from_index(n=n, k=k)
        / permittivity_real_from_index(n=n, k=k)
    )
