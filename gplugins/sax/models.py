from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from functools import cache, partial
from inspect import getmembers

import jax
import jax.numpy as jnp
import sax
from numpy.typing import NDArray
from sax import SDict
from sax.utils import reciprocal

nm = 1e-3

FloatArray = NDArray[jnp.floating]
Float = float | FloatArray

################
# PassThrus
################


@cache
def _2port(p1, p2):
    @jax.jit
    def _2port(wl=1.5):
        wl = jnp.asarray(wl)
        return sax.reciprocal({(p1, p2): jnp.ones_like(wl)})

    return _2port


@cache
def _3port(p1, p2, p3):
    @jax.jit
    def _3port(wl=1.5):
        wl = jnp.asarray(wl)
        thru = jnp.ones_like(wl) / jnp.sqrt(2)
        return sax.reciprocal(
            {
                (p1, p2): thru,
                (p1, p3): thru,
            }
        )

    return _3port


@cache
def _4port(p1, p2, p3, p4):
    @jax.jit
    def _4port(wl=1.5):
        wl = jnp.asarray(wl)
        thru = jnp.ones_like(wl) / jnp.sqrt(2)
        cross = 1j * thru
        return sax.reciprocal(
            {
                (p1, p4): thru,
                (p2, p3): thru,
                (p1, p3): cross,
                (p2, p4): cross,
            }
        )

    return _4port


def straight(
    *,
    wl: float = 1.55,
    wl0: float = 1.55,
    neff: float = 2.34,
    ng: float = 3.4,
    length: float = 10.0,
    loss: float = 0.0,
) -> SDict:
    """Dispersive straight waveguide model.

    based on sax.models

    Args:
        wl: wavelength.
        wl0: center wavelength.
        neff: effective index.
        ng: group index.
        length: um.
        loss: in dB/um.

    .. code::

        o1 -------------- o2
                length

    """
    dwl = wl - wl0
    dneff_dwl = (ng - neff) / wl0
    neff -= dwl * dneff_dwl
    phase = 2 * jnp.pi * neff * length / wl
    amplitude = jnp.asarray(10 ** (-loss * length / 20), dtype=complex)
    transmission = amplitude * jnp.exp(1j * phase)
    return reciprocal(
        {
            ("o1", "o2"): transmission,
        }
    )


def bend(wl: float = 1.5, length: float = 20.0, loss: float = 0.0) -> SDict:
    """Returns bend Sparameters."""
    amplitude = jnp.asarray(10 ** (-loss * length / 20), dtype=complex)
    return {k: amplitude * v for k, v in straight(wl=wl, length=length).items()}


def attenuator(*, loss: float = 0.0) -> SDict:
    """Attenuator model.

    based on sax.models

    Args:
        loss: in dB.

    .. code::

        o1 -------------- o2
                loss

    """
    transmission = jnp.asarray(10 ** (-loss / 20), dtype=complex)
    return reciprocal(
        {
            ("o1", "o2"): transmission,
        }
    )


def phase_shifter(
    wl: float = 1.55,
    neff: float = 2.34,
    voltage: float = 0,
    length: float = 10,
    loss: float = 0.0,
) -> SDict:
    """Returns simple phase shifter model.

    Args:
        wl: wavelength in um.
        neff: effective index.
        voltage: voltage per PI phase shift.
        length: in um.
        loss: in dB.
    """
    deltaphi = voltage * jnp.pi
    phase = 2 * jnp.pi * neff * length / wl + deltaphi
    amplitude = jnp.asarray(10 ** (-loss * length / 20), dtype=complex)
    transmission = amplitude * jnp.exp(1j * phase)
    return reciprocal(
        {
            ("o1", "o2"): transmission,
        }
    )


def grating_coupler(
    *,
    wl: float = 1.55,
    wl0: float = 1.55,
    loss: float = 0.0,
    reflection: float = 0.0,
    reflection_fiber: float = 0.0,
    bandwidth: float = 40 * nm,
) -> SDict:
    """Grating_coupler model.

    equation adapted from photontorch grating coupler
    https://github.com/flaport/photontorch/blob/master/photontorch/components/gratingcouplers.py

    Args:
        wl: wavelength.
        wl0: center wavelength.
        loss: in dB.
        reflection: from waveguide side.
        reflection_fiber: from fiber side.
        bandwidth: 3dB bandwidth (um).

    .. code::

                      fiber o2

                   /  /  /  /
                  /  /  /  /

                _|-|_|-|_|-|___
            o1  ______________|

    """
    amplitude = jnp.asarray(10 ** (-loss / 20), dtype=complex)
    sigma = bandwidth / (2 * jnp.sqrt(2 * jnp.log(2)))
    transmission = amplitude * jnp.exp(-((wl - wl0) ** 2) / (2 * sigma**2))
    return reciprocal(
        {
            ("o1", "o1"): reflection * jnp.ones_like(transmission),
            ("o1", "o2"): transmission,
            ("o2", "o1"): transmission,
            ("o2", "o2"): reflection_fiber * jnp.ones_like(transmission),
        }
    )


def coupler(
    *,
    wl: float = 1.55,
    wl0: float = 1.55,
    length: float = 0.0,
    coupling0: float = 0.2,
    dk1: float = 1.2435,
    dk2: float = 5.3022,
    dn: float = 0.02,
    dn1: float = 0.1169,
    dn2: float = 0.4821,
) -> SDict:
    r"""Dispersive coupler model.

    equations adapted from photontorch.
    https://github.com/flaport/photontorch/blob/master/photontorch/components/directionalcouplers.py

    kappa = coupling0 + coupling

    Args:
        wl: wavelength (um).
        wl0: center wavelength (um).
        length: coupling length (um).
        coupling0: bend region coupling coefficient from FDTD simulations.
        dk1: first derivative of coupling0 vs wavelength.
        dk2: second derivative of coupling vs wavelength.
        dn: effective index difference between even and odd modes.
        dn1: first derivative of effective index difference vs wavelength.
        dn2: second derivative of effective index difference vs wavelength.

    .. code::

          coupling0/2        coupling        coupling0/2
        <-------------><--------------------><---------->
         o2 ________                           _______o3
                    \                         /
                     \        length         /
                      =======================
                     /                       \
            ________/                         \________
         o1                                           o4

                      ------------------------> K (coupled power)
                     /
                    / K
           -----------------------------------> T = 1 - K (transmitted power)
    """
    dwl = wl - wl0
    dn = dn + dn1 * dwl + 0.5 * dn2 * dwl**2
    kappa0 = coupling0 + dk1 * dwl + 0.5 * dk2 * dwl**2
    kappa1 = jnp.pi * dn / wl

    tau = jnp.cos(kappa0 + kappa1 * length)
    kappa = -jnp.sin(kappa0 + kappa1 * length)
    return reciprocal(
        {
            ("o1", "o4"): tau,
            ("o1", "o3"): 1j * kappa,
            ("o2", "o4"): 1j * kappa,
            ("o2", "o3"): tau,
        }
    )


def coupler_single_wavelength(*, coupling: float = 0.5) -> SDict:
    r"""Coupler model for a single wavelength.

    Based on sax.models.

    Args:
        coupling: power coupling coefficient.

    .. code::

         o2 ________                           ______o3
                    \                         /
                     \        length         /
                      =======================
                     /                       \
            ________/                         \_______
         o1                                          o4

    """
    kappa = coupling**0.5
    tau = (1 - coupling) ** 0.5
    return reciprocal(
        {
            ("o1", "o4"): tau,
            ("o1", "o3"): 1j * kappa,
            ("o2", "o4"): 1j * kappa,
            ("o2", "o3"): tau,
        }
    )


################
# MMIs
################


def _mmi_amp(
    wl: Float = 1.55, wl0: Float = 1.55, fwhm: Float = 0.2, loss_dB: Float = 0.3
):
    """Amplitude of the MMI transfer function.

    Args:
        wl: wavelength.
        wl0: center wavelength.
        fwhm: full width at half maximum.
        loss_dB: loss in dB.
    """
    max_power = 10 ** (-abs(loss_dB) / 10)
    f = 1 / wl
    f0 = 1 / wl0
    f1 = 1 / (wl0 + fwhm / 2)
    f2 = 1 / (wl0 - fwhm / 2)
    _fwhm = f2 - f1

    sigma = _fwhm / (2 * jnp.sqrt(2 * jnp.log(2)))
    power = jnp.exp(-((f - f0) ** 2) / (2 * sigma**2))
    power = max_power * power / power.max()
    return jnp.sqrt(power)


def _mmi_nxn(
    n,
    wl=1.55,
    wl0=1.55,
    fwhm=0.2,
    loss_dB=None,
    shift=None,
    splitting_matrix=None,
) -> sax.SDict:
    """General n x n MMI model.

    Args:
        n (int): Number of input and output ports.
        wl (float): Operating wavelength.
        wl0 (float): Center wavelength of the MMI.
        fwhm (float): Full width at half maximum.
        loss_dB (np.array): Array of loss values in dB for each port.
        shift (np.array): Array of wavelength shifts for each port.
        splitting_matrix (np.array): nxn matrix defining the power splitting ratios between ports.
    """
    if loss_dB is None:
        loss_dB = jnp.zeros(n)
    if shift is None:
        shift = jnp.zeros(n)
    if splitting_matrix is None:
        splitting_matrix = jnp.full((n, n), 1 / n)  # Uniform splitting as default

    S = {}
    for i in range(n):
        for j in range(n):
            amplitude = _mmi_amp(wl, wl0 + shift[j], fwhm, loss_dB[j])
            amplitude *= jnp.sqrt(
                splitting_matrix[i][j]
            )  # Convert power ratio to amplitude
            loss_factor = 10 ** (-loss_dB[j] / 20)
            S[(f"o{i + 1}", f"o{j + 1}")] = amplitude * loss_factor

    return sax.reciprocal(S)


def mmi1x2(
    wl: Float = 1.55, wl0: Float = 1.55, fwhm: Float = 0.2, loss_dB: Float = 0.3
) -> sax.SDict:
    """1x2 MMI model.

    Args:
        wl: wavelength.
        wl0: center wavelength.
        fwhm: full width at half maximum 3dB.
        loss_dB: loss in dB.
    """
    thru = _mmi_amp(wl=wl, wl0=wl0, fwhm=fwhm, loss_dB=loss_dB) / 2**0.5

    return sax.reciprocal(
        {
            ("o1", "o2"): thru,
            ("o1", "o3"): thru,
        }
    )


def mmi2x2(
    wl: Float = 1.55,
    wl0: Float = 1.55,
    fwhm: Float = 0.2,
    loss_dB: Float = 0.3,
    shift: Float = 0.005,
    loss_dB_cross: Float | None = None,
    loss_dB_thru: Float | None = None,
    splitting_ratio_cross: Float = 0.5,
    splitting_ratio_thru: Float = 0.5,
) -> sax.SDict:
    """2x2 MMI model.

    Args:
        wl: wavelength.
        wl0: center wavelength.
        fwhm: full width at half maximum.
        loss_dB: loss in dB.
        shift: shift in wavelength for both cross and thru ports.
        loss_dB_cross: loss in dB for the cross port.
        loss_dB_thru: loss in dB for the bar port.
        splitting_ratio_cross: splitting ratio for the cross port.
        splitting_ratio_thru: splitting ratio for the bar port.
    """
    loss_dB_cross = loss_dB_cross or loss_dB
    loss_dB_thru = loss_dB_thru or loss_dB

    # Convert splitting ratios from power to amplitude by taking the square root
    amplitude_ratio_thru = splitting_ratio_thru**0.5
    amplitude_ratio_cross = splitting_ratio_cross**0.5

    loss_factor_thru = 10 ** (-loss_dB_thru / 20)
    loss_factor_cross = 10 ** (-loss_dB_cross / 20)

    thru = (
        _mmi_amp(wl=wl, wl0=wl0 + shift, fwhm=fwhm, loss_dB=loss_dB_thru)
        * amplitude_ratio_thru
        * loss_factor_thru
    )
    cross = (
        1j
        * _mmi_amp(wl=wl, wl0=wl0 + shift, fwhm=fwhm, loss_dB=loss_dB_cross)
        * amplitude_ratio_cross
        * loss_factor_cross
    )

    return sax.reciprocal(
        {
            ("o1", "o3"): thru,
            ("o1", "o4"): cross,
            ("o2", "o3"): cross,
            ("o2", "o4"): thru,
        }
    )


def mmi1x2_ideal() -> SDict:
    """Returns an ideal 1x2 splitter."""
    return reciprocal(
        {
            ("o1", "o2"): 0.5**0.5,
            ("o1", "o3"): 0.5**0.5,
        }
    )


def mmi2x2_ideal(*, coupling: float = 0.5) -> SDict:
    """Returns an ideal 2x2 splitter.

    Args:
        coupling: power coupling coefficient.
    """
    kappa = coupling**0.5
    tau = (1 - coupling) ** 0.5
    return reciprocal(
        {
            ("o1", "o4"): tau,
            ("o1", "o3"): 1j * kappa,
            ("o2", "o4"): 1j * kappa,
            ("o2", "o3"): tau,
        }
    )


################
# Crossings
################


@jax.jit
def crossing(wl: Float = 1.5) -> sax.SDict:
    one = jnp.ones_like(jnp.asarray(wl))
    return sax.reciprocal(
        {
            ("o1", "o3"): one,
            ("o2", "o4"): one,
        }
    )


################
# Models Dict
################
def get_models(modules) -> dict[str, Callable[..., sax.SDict]]:
    """Returns all models in a module or list of modules."""
    models = {}
    modules = modules if isinstance(modules, Iterable) else [modules]

    for module in modules:
        for t in getmembers(module):
            name = t[0]
            func = t[1]
            if not callable(func):
                continue
            _func = func
            while isinstance(_func, partial):
                _func = _func.func
            try:
                sig = inspect.signature(_func)
            except ValueError:
                continue
            if str(sig.return_annotation) in {
                "sax.SDict",
                "SDict",
            } and not name.startswith("_"):
                models[name] = func
    return models


if __name__ == "__main__":
    import sys

    import gplugins.sax as gs

    models = get_models(sys.modules[__name__])
    for i in models.keys():
        print(i)

    gs.plot_model(grating_coupler)
    # gs.plot_model(coupler)
