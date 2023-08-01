"""Sweep neff over wavelength and returns group index."""


from functools import partial

from gplugins.gmeep.get_material import get_index
from gplugins.modes.find_modes import find_modes_waveguide
from gplugins.modes.types import Mode


def find_mode_dispersion(
    wavelength: float = 1.55,
    wavelength_step: float = 0.01,
    core: str = "Si",
    clad: str = "SiO2",
    mode_number: int = 1,
    **kwargs,
) -> Mode:
    """Returns Mode with correct dispersion (ng).

    group index comes from a finite difference approximation at 3 wavelengths

    Args:
        wavelength: center wavelength (um).
        wavelength_step: in um.
        core: core material name.
        clad: clad material name.
        mode_number: mode index to compute (1: fundamental mode).

    Keyword Args:
        core_thickness: wg height (um).
        sx: supercell width (um).
        sy: supercell height (um).
        resolution: (pixels/um).
        wavelength: wavelength.
        num_bands: mode order.
        plot: if True plots mode.
        logscale: plots in logscale.
        plotH: plot magnetic field.
        cache: path to save the modes.
        polarization: prefix when saving the modes.
        parity: symmetries mp.ODD_Y mp.EVEN_X for TE, mp.EVEN_Y for TM.

    """
    w0 = wavelength - wavelength_step
    wc = wavelength
    w1 = wavelength + wavelength_step

    core_material = partial(get_index, name=core)
    clad_material = partial(get_index, name=clad)

    m0 = find_modes_waveguide(
        wavelength=w0,
        core_material=core_material(w0),
        clad_material=clad_material(w0),
        **kwargs,
    )
    mc = find_modes_waveguide(
        wavelength=wc,
        core_material=core_material(wc),
        clad_material=clad_material(wc),
        **kwargs,
    )
    m1 = find_modes_waveguide(
        wavelength=w1,
        core_material=core_material(w1),
        clad_material=clad_material(w1),
        **kwargs,
    )

    n0 = m0[mode_number].neff
    nc = mc[mode_number].neff
    n1 = m1[mode_number].neff

    # ng = ncenter - wavelength *dn/ step
    ng = nc - wavelength * (n1 - n0) / (2 * wavelength_step)
    neff = (n0 + nc + n1) / 3
    return Mode(mode_number=mode_number, ng=ng, neff=neff, wavelength=wavelength)


if __name__ == "__main__":
    m = find_mode_dispersion(core_width=0.45, core_thickness=0.22)
    print(m.ng)
    # test_ng()
    # print(get_index(name="Si"))
    # ngs = []
    # for wavelength_step in [0.001, 0.01]:
    #     neff, ng = find_modes_waveguide_dispersion(
    #         core_width=0.45, core_thickness=0.22, wavelength_step=wavelength_step
    #     )
    #     ngs.append(ng)
    #     print(wavelength_step, ng)
