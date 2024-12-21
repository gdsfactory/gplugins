from __future__ import annotations

import pytest
import tidy3d as td
from pydantic.v1 import ValidationError

import gplugins.tidy3d as gt

settings = dict(
    wavelength=1.55,
    core_width=1.0,
    slab_thickness=0,
    core_thickness=0.2,
    num_modes=4,
    side_margin=3.0,
    grid_resolution=20,
)


def test_material_medium() -> None:
    strip = gt.modes.Waveguide(
        core_material=td.Medium(permittivity=(2.1) ** 2),
        clad_material=td.Medium(permittivity=(1.448) ** 2),
        **settings,
    )
    assert strip._data


def test_material_float() -> None:
    strip = gt.modes.Waveguide(
        core_material=3.4,
        clad_material=1.4,
        **settings,
    )
    assert strip._data


def test_material_string() -> None:
    strip = gt.modes.Waveguide(
        core_material="si",
        clad_material="sio2",
        **settings,
    )
    assert strip._data


def test_material_validation_error() -> None:
    with pytest.raises(ValidationError):
        strip = gt.modes.Waveguide(
            core_material=td.material_library["cSi"],
            clad_material="sio2",
            **settings,
        )
        assert strip._data


def test_material_library_many_variants() -> None:
    with pytest.raises(ValueError):
        strip = gt.modes.Waveguide(
            core_material="cSi",
            clad_material="sio2",
            **settings,
        )
        assert strip._data


def test_material_library_single_variant() -> None:
    strip = gt.modes.Waveguide(
        core_material="AlxOy",
        clad_material="AlxOy",
        **settings,
    )
    assert strip._data


def test_material_library() -> None:
    strip = gt.modes.Waveguide(
        core_material=td.material_library["cSi"]["Li1993_293K"],
        clad_material="sio2",
        **settings,
    )
    assert strip._data


if __name__ == "__main__":
    pytest.main([__file__])
    # test_material_validation_error()
    # test_material_medium()
    # test_material_float()
    # test_material_library()
