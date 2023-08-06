from __future__ import annotations
import tidy3d as td
import gplugins.tidy3d as gt


def test_medium() -> None:
    gt.modes.Waveguide(
        wavelength=1.55,
        core_width=1.0,
        slab_thickness=0,
        core_material=td.Medium(permittivity=(2.1) ** 2),
        clad_material=td.Medium(permittivity=(1.448) ** 2),
        core_thickness=0.2,
        num_modes=4,
        side_margin=3.0,
        grid_resolution=20,
    )


def test_index() -> None:
    strip = gt.modes.Waveguide(
        wavelength=1.55,
        core_width=1.0,
        slab_thickness=0,
        core_material=3.4,
        clad_material=1.4,
        core_thickness=0.2,
        num_modes=4,
        side_margin=3.0,
        grid_resolution=20,
    )
    strip.plot_index()


if __name__ == "__main__":
    test_index()
    # test_medium()
