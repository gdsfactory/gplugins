from __future__ import annotations

from functools import partial

import tidy3d as td
from tidy3d.components.medium import PoleResidue
from tidy3d.components.types import ComplexNumber

material_name_to_tidy3d = {
    "si": td.material_library["cSi"]["Li1993_293K"],
    "sio2": td.material_library["SiO2"]["Horiba"],
    "sin": td.material_library["Si3N4"]["Luke2015PMLStable"],
}

MaterialSpecTidy3d = (
    float
    | int
    | str
    | td.Medium
    | td.CustomMedium
    | td.PoleResidue
    | tuple[float, float]
    | tuple[str, str]
)


def get_epsilon(
    spec: MaterialSpecTidy3d,
    wavelength: float = 1.55,
) -> ComplexNumber:
    """Return permittivity from material database.

    Args:
        spec: material name or refractive index.
        wavelength: wavelength (um).
    """
    medium = get_medium(spec=spec)
    frequency = td.C_0 / wavelength
    return medium.eps_model(frequency)


def get_index(
    spec: MaterialSpecTidy3d,
    wavelength: float = 1.55,
) -> float:
    """Return refractive index from material database.

    Args:
        spec: material name or refractive index.
        wavelength: wavelength (um).
    """
    eps_complex = get_epsilon(
        wavelength=wavelength,
        spec=spec,
    )
    n, _ = td.Medium.eps_complex_to_nk(eps_complex)
    return n


def get_nk(
    spec: MaterialSpecTidy3d,
    wavelength: float = 1.55,
) -> float:
    """Return refractive index and optical extinction coefficient from material database.

    Args:
        spec: material name or refractive index.
        wavelength: wavelength (um).
    """
    eps_complex = get_epsilon(
        wavelength=wavelength,
        spec=spec,
    )
    n, k = td.Medium.eps_complex_to_nk(eps_complex)
    return n, k


def get_medium(spec: MaterialSpecTidy3d) -> td.Medium:
    """Return Medium from materials database.

    Args:
        spec: material name or refractive index.
    """
    if isinstance(spec, int | float):
        return td.Medium(permittivity=spec**2)
    elif isinstance(spec, td.Medium | td.Medium2D | td.CustomMedium):
        return spec
    elif spec in material_name_to_tidy3d:
        return material_name_to_tidy3d[spec]
    elif isinstance(spec, PoleResidue):
        return spec
    elif spec in td.material_library:
        variants = td.material_library[spec].variants
        if len(variants) == 1:
            return list(variants.values())[0].medium
        raise ValueError(
            f"You need to specify the variant of {td.material_library[spec].variants.keys()}"
        )
    elif isinstance(spec, tuple):
        if len(spec) == 2 and isinstance(spec[0], str) and isinstance(spec[1], str):
            return td.material_library[spec[0]][spec[1]]
        raise ValueError("Tuple must have length 2 and be make of strings")
    materials = set(td.material_library.keys())
    raise ValueError(f"Material {spec!r} not in {materials}")


si = partial(get_index, "si")
sio2 = partial(get_index, "sio2")
sin = partial(get_index, "sin")


if __name__ == "__main__":
    # print(si(1.55))
    # print(si(1.31))
    # print(get_index(spec="si"))
    # print(get_index(spec=3.4))
    # m = get_medium("SiO2")
    # m = get_medium(("cSi", "Li1993_293K"))
    # m = td.Medium(permittivity=1.45 ** 2)
    m = get_medium(td.material_library["cSi"]["Li1993_293K"])
