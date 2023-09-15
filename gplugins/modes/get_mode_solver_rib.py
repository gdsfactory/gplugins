from __future__ import annotations

import pathlib
import tempfile

import meep as mp
import numpy as np
import pydantic
from meep import mpb

mpb.Verbosity(0)

tmp = pathlib.Path(tempfile.TemporaryDirectory().name).parent / "meep"
tmp.mkdir(exist_ok=True)


@pydantic.validate_call
def get_mode_solver_rib(
    core_width: float = 0.45,
    core_thickness: float = 0.22,
    slab_thickness: float = 0.0,
    core_material: float = 3.47,
    clad_material: float = 1.44,
    nslab: float | None = None,
    sy: float = 2.0,
    sz: float = 2.0,
    resolution: int = 32,
    nmodes: int = 4,
    sidewall_angle: float | None = None,
) -> mpb.ModeSolver:
    """Returns a mode_solver simulation.

    Args:
        core_width: core_width (um).
        core_thickness: wg thickness (um).
        slab_thickness: thickness for the waveguide slab.
        core_material: core material refractive index.
        clad_material: clad material refractive index.
        nslab: Optional slab material refractive index. Defaults to core_material.
        sy: simulation region width (um).
        sz: simulation region height (um).
        resolution: resolution (pixels/um).
        nmodes: number of modes.
        sidewall_angle: waveguide sidewall angle (degrees),
            tapers from core_width at top of slab, upwards, to top of waveguide
            with respect to the normal.
            a sidewall_angle = 10, will have 80 degrees with respect to the substrate.

    ::

          __________________________
          |
          |
          |         width
          |     <---------->
          |      ___________   _ _ _
          |     |           |       |
        sz|_____|  core_material    |_______|
          |                         | core_thickness
          |slab_thickness    nslab  |
          |_________________________|
          |
          |        clad_material
          |__________________________
          <------------------------>
                        sy

    """
    material_core = mp.Medium(index=core_material)
    material_clad = mp.Medium(index=clad_material)
    material_slab = mp.Medium(index=nslab or core_material)

    # Define the computational cell.  We'll make x the propagation direction.
    # the other cell sizes should be big enough so that the boundaries are
    # far away from the mode field.
    geometry_lattice = mp.Lattice(size=mp.Vector3(0, sy, sz))

    geometry = []
    if sidewall_angle:
        geometry.append(
            mp.Prism(
                vertices=[
                    mp.Vector3(y=-core_width / 2, z=0),
                    mp.Vector3(y=core_width / 2, z=0),
                    mp.Vector3(x=1, y=core_width / 2, z=0),
                    mp.Vector3(x=1, y=-core_width / 2, z=0),
                ],
                height=core_thickness - slab_thickness,
                center=mp.Vector3(z=0),
                sidewall_angle=np.deg2rad(sidewall_angle),
                material=material_core,
            )
        )
    else:
        geometry.append(
            mp.Block(
                size=mp.Vector3(mp.inf, core_width, core_thickness),
                material=material_core,
                center=mp.Vector3(z=0),
            )
        )

    geometry += [
        mp.Block(
            size=mp.Vector3(mp.inf, mp.inf, slab_thickness),
            material=material_slab,
            center=mp.Vector3(z=-slab_thickness / 2),
        ),
    ]

    # The k (i.e. beta, i.e. propagation constant) points to look at, in
    # units of 2*pi/um.  We'll look at num_k points from k_min to k_max.
    num_k = 9
    k_min = 0.1
    k_max = 3.0
    k_points = mp.interpolate(num_k, [mp.Vector3(k_min), mp.Vector3(k_max)])

    # Increase this to see more modes.  (The guided ones are the ones below the
    # light line, i.e. those with frequencies < kmag / 1.45, where kmag
    # is the corresponding column in the output if you grep for "freqs:".)
    # use this prefix for output files

    filename_prefix = tmp / f"rib_{core_width}_{core_thickness}_{slab_thickness}"

    mode_solver = mpb.ModeSolver(
        geometry_lattice=geometry_lattice,
        geometry=geometry,
        k_points=k_points,
        resolution=resolution,
        num_bands=nmodes,
        default_material=material_clad,
        filename_prefix=str(filename_prefix),
    )
    mode_solver.nmodes = nmodes
    mode_solver.info = dict(
        core_width=core_width,
        core_thickness=core_thickness,
        slab_thickness=slab_thickness,
        core_material=core_material,
        clad_material=clad_material,
        sy=sy,
        sz=sz,
        resolution=resolution,
        nmodes=nmodes,
    )
    return mode_solver


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    m = get_mode_solver_rib(
        slab_thickness=0.25,
        # slab_thickness=0.,
        core_thickness=0.5,
        resolution=64,
        nslab=2,
    )
    m.init_params(p=mp.NO_PARITY, reset_fields=False)
    eps = m.get_epsilon()
    # cmap = 'viridis'
    # cmap = "RdBu"
    cmap = "binary"
    origin = "lower"
    plt.imshow(
        eps.T**0.5,
        cmap=cmap,
        origin=origin,
        aspect="auto",
        extent=[
            -m.info["sy"] / 2,
            m.info["sy"] / 2,
            -m.info["sz"] / 2,
            m.info["sz"] / 2,
        ],
    )
    plt.colorbar()
    plt.show()
