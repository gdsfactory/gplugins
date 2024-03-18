"""Compute modes of a rectangular Si strip waveguide on top of oxide. Note that \
you should only pay attention, here, to the guided modes, which are the modes \
whose frequency falls under the light line -- that is, frequency < beta / 1.45, \
where 1.45 is the SiO2 index.

Since there's no special lengthscale here, you can just
use microns. In general, if you use units of x, the frequencies
output are equivalent to x/lambda# so here, the frequencies will be
output as um/lambda, e.g. 1.5um would correspond to the frequency
1/1.5 = 0.6667.

"""

import json
import pathlib
import pickle
from functools import partial

import meep as mp
import numpy as np
from gdsfactory.config import PATH
from gdsfactory.typings import PathType
from meep import mpb

from gplugins.common.utils.disable_print import DisablePrint
from gplugins.common.utils.get_sparameters_path import get_kwargs_hash
from gplugins.modes.get_mode_solver_coupler import get_mode_solver_coupler
from gplugins.modes.get_mode_solver_rib import get_mode_solver_rib
from gplugins.modes.types import Mode, ModeData

mpb.Verbosity(0)


def find_modes_waveguide(
    tol: float = 1e-6,
    wavelength: float = 1.55,
    mode_number: int = 1,
    parity=mp.NO_PARITY,
    cache_path: PathType | None = PATH.modes,
    overwrite: bool = False,
    single_waveguide: bool = True,
    **kwargs,
) -> dict[int, Mode]:
    """Computes mode effective and group index for a rectangular waveguide.

    Args:
        tol: tolerance when finding modes.
        wavelength: wavelength in um.
        mode_number: mode order of the first mode.
        parity: mp.ODD_Y mp.EVEN_X for TE, mp.EVEN_Y for TM.
        cache_path: path to cache folder. None to disable caching.
        overwrite: forces simulating again.
        single_waveguide: if True, compute a single waveguide. False computes a coupler.

    Keyword Args:
        core_width: core_width (um) for the symmetric case.
        gap: for the case of only two waveguides.
        core_widths: list or tuple of waveguide widths.
        gaps: list or tuple of waveguide gaps.
        core_thickness: wg height (um).
        slab_thickness: thickness for the waveguide slab.
        core_material: core material refractive index.
        clad_material: clad material refractive index.
        nslab: Optional slab material refractive index. Defaults to core_material.
        ymargin: margin in y.
        sz: simulation region thickness (um).
        resolution: resolution (pixels/um).
        nmodes: number of modes.
        sidewall_angles: waveguide sidewall angle (radians),
            tapers from core_width at top of slab, upwards, to top of waveguide.

    Returns: Dict[mode_number, Mode]

    compute mode_number lowest frequencies as a function of k. Also display
    "parities", i.e. whether the mode is symmetric or anti_symmetric
    through the y=0 and z=0 planes.
    mode_solver.run(mpb.display_yparities, mpb.display_zparities)

    Above, we outputted the dispersion relation: frequency (omega) as a
    function of wavevector kx (beta). Alternatively, you can compute
    beta for a given omega -- for example, you might want to find the
    modes and wavevectors at a fixed wavelength of 1.55 microns. You
    can do that using the find_k function:

    single_waveguide=True

    ::

          __________________________
          |
          |
          |         width
          |     <---------->
          |      ___________   _ _ _
          |     |           |       |
        sz|_____|           |_______|
          |     core_material       | core_thickness
          |slab_thickness    nslab  |
          |_________________________|
          |
          |        clad_material
          |__________________________
          <------------------------>
                        sy

    single_waveguide=False

    ::

          _____________________________________________________
          |
          |
          |         widths[0]                 widths[1]
          |     <---------->     gaps[0]    <---------->
          |      ___________ <-------------> ___________      _
          |     |           |               |           |     |
        sz|_____|           |_______________|           |_____|
          |    core_material                                  | core_thickness
          |slab_thickness        nslab                        |
          |___________________________________________________|
          |
          |<--->                                         <--->
          |ymargin               clad_material                   ymargin
          |____________________________________________________
          <--------------------------------------------------->
                                   sy



    """
    modes = {}
    mode_solver = (
        get_mode_solver_rib(**kwargs)
        if single_waveguide
        else get_mode_solver_coupler(**kwargs)
    )
    nmodes = mode_solver.nmodes
    omega = 1 / wavelength

    h = get_kwargs_hash(
        wavelength=wavelength,
        parity=parity,
        single_waveguide=single_waveguide,
        **kwargs,
    )

    if cache_path:
        cache_path = pathlib.Path(cache_path)
        cache_path.mkdir(exist_ok=True, parents=True)
        filepath = cache_path / f"{h}_{mode_number}.json"

        if filepath.exists() and not overwrite:
            for index, i in enumerate(range(mode_number, mode_number + nmodes)):
                filepath_json = cache_path / f"{h}_{index}.json"
                filepath_pickle = cache_path / f"{h}_{index}.pkl"
                mode_data = pickle.loads(filepath_pickle.read_bytes())
                d = json.loads(filepath_json.read_text())
                mode = Mode(
                    E=mode_data.E,
                    H=mode_data.H,
                    eps=mode_data.eps,
                    y=mode_data.y,
                    z=mode_data.z,
                    **d,
                )
                modes[i] = mode
            return modes

    # Output the x component of the Poynting vector for mode_number bands at omega
    with DisablePrint():
        k = mode_solver.find_k(
            parity,
            omega,
            mode_number,
            mode_number + nmodes,
            mp.Vector3(1),
            tol,
            omega * 2.02,
            omega * 0.01,
            omega * 10,
            # mpb.output_poynting_x,
            mpb.display_yparities,
            mpb.display_group_velocities,
        )
    neff = np.array(k) * wavelength

    # vg = mode_solver.compute_group_velocities()
    # vg = vg[0]
    # ng = 1 / np.array(vg)

    for index, i in enumerate(range(mode_number, mode_number + nmodes)):
        Ei = mode_solver.get_efield(i)
        Hi = mode_solver.get_hfield(i)
        Ei = np.array(Ei)
        Hi = np.array(Hi)
        y_num = np.shape(Ei[:, :, 0, 0])[0]
        z_num = np.shape(Ei[:, :, 0, 0])[1]
        y = np.linspace(
            -1 * mode_solver.info["sy"] / 2.0,
            mode_solver.info["sy"] / 2.0,
            y_num,
        )
        z = np.linspace(
            -1 * mode_solver.info["sz"] / 2.0,
            mode_solver.info["sz"] / 2.0,
            z_num,
        )

        modes[i] = Mode(
            mode_number=i,
            neff=neff[index],
            wavelength=wavelength,
            E=Ei,
            H=Hi,
            eps=np.array(mode_solver.get_epsilon().T),
            y=y,
            z=z,
        )
        mode_data = ModeData(
            E=Ei,
            H=Hi,
            eps=np.array(mode_solver.get_epsilon().T),
            y=y,
            z=z,
        )
        if cache_path:
            filepath_json = cache_path / f"{h}_{index}.json"
            filepath_pickle = cache_path / f"{h}_{index}.pkl"
            filepath_json.write_text(
                modes[i].model_dump_json(exclude={"E", "H", "eps", "y", "z"})
            )
            filepath_pickle.write_bytes(pickle.dumps(modes[i]))

    return modes


find_modes_coupler = partial(find_modes_waveguide, single_waveguide=False)


if __name__ == "__main__":
    m = find_modes_waveguide(core_width=0.612)
    print(m)

    m1 = m[1]

    # print(np.shape(m1.y))
    # print(np.shape(m1.z))
    # print(np.shape(m1.E[:, :, 0, 1]))

    # tol: float = 1e-6
    # wavelength: float = 1.55
    # mode_number: int = 1
    # parity = mp.NO_PARITY
    # mode_solver = get_mode_solver_rib()
    # nmodes = mode_solver.nmodes
    # omega = 1 / wavelength

    # # Output the x component of the Poynting vector for mode_number bands at omega
    # k = mode_solver.find_k(
    #     parity,
    #     omega,
    #     mode_number,
    #     mode_number + nmodes,
    #     mp.Vector3(1),
    #     tol,
    #     omega * 2.02,
    #     omega * 0.01,
    #     omega * 10,
    #     mpb.output_poynting_x,
    #     mpb.display_yparities,
    #     mpb.display_group_velocities,
    # )
    # enable_print()
    # vg = mode_solver.compute_group_velocities()
    # vg0 = vg[0]
    # neff = np.array(k) * wavelength
    # ng = 1 / np.array(vg0)

    # modes = {
    #     i: Mode(
    #         mode_number=i,
    #         neff=neff[index],
    #         solver=mode_solver,
    #         wavelength=wavelength,
    #     )
    #     for index, i in enumerate(range(mode_number, mode_number + nmodes))
    # }
