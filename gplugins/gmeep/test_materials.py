import gdsfactory as gf

from gplugins.common.utils import optical_constants
from gplugins.gmeep.write_sparameters_meep import write_sparameters_meep


def test_materials_override() -> None:
    """Checks that materials are properly overridden if index is provided."""

    c = gf.components.straight(length=2)

    # Default (materials strings)
    sp1 = write_sparameters_meep(
        c,
        run=False,
        animate=False,
        is_3d=False,
        overwrite=True,
    )

    # Override
    sp2 = write_sparameters_meep(
        c,
        run=False,
        animate=False,
        material_name_to_meep=dict(si=2.0),
        is_3d=False,
        overwrite=True,
    )

    assert sp1.geometry[0].material.epsilon(freq=1)[0][0] != 4.0
    assert sp2.geometry[0].material.epsilon(freq=1)[0][0] == 4.0


def test_materials_override_complex() -> None:
    """Checks that materials are properly overridden if complex index is provided."""

    c = gf.components.straight(length=2)

    # Default (materials strings)
    sp1 = write_sparameters_meep(
        c,
        run=False,
        animate=False,
        is_3d=False,
        overwrite=True,
    )

    # Override
    sp2 = write_sparameters_meep(
        c,
        run=False,
        animate=False,
        material_name_to_meep=dict(si=2.0 + 0.1j),
        is_3d=False,
        overwrite=True,
        wavelength_start=1.5,
        wavelength_stop=1.6,
    )

    assert sp1.geometry[0].material.epsilon(freq=1)[0][
        0
    ] != optical_constants.permittivity_real_from_index(n=2.0, k=0.1)
    assert sp1.geometry[0].material.D_conductivity_diag[0] == 0
    assert sp2.geometry[0].material.epsilon_diag[
        0
    ] == optical_constants.permittivity_real_from_index(n=2.0, k=0.1)
    assert sp2.geometry[0].material.D_conductivity_diag[
        0
    ] == optical_constants.D_conductivity_um(n=2.0, k=0.1, wavelength=1.55)


if __name__ == "__main__":
    # test_materials_override()
    test_materials_override_complex()
