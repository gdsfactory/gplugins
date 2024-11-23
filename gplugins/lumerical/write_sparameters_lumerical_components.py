"""Write Sparameters with for different components."""

from __future__ import annotations

import gdsfactory as gf
from gdsfactory.typings import ComponentSpec
from tqdm.auto import tqdm

from gplugins.lumerical.write_sparameters_lumerical import (
    write_sparameters_lumerical,
)


def write_sparameters_lumerical_components(
    components: list[ComponentSpec],
    run: bool = True,
    session: object | None = None,
    **kwargs,
) -> None:
    """Writes Sparameters for a list of components using Lumerical FDTD.

    Args:
        factory: list of component or component functions to simulate.
        run: if False, prompts you to review each simulation.
        session: Optional Lumerical FDTD session. Creates lumapi.FDTD() if None.

    Keyword Args:
        simulation settings

    """
    import lumapi

    session = session or lumapi.FDTD()
    need_review = []

    for component in tqdm(components):
        component = gf.get_component(component)
        write_sparameters_lumerical(component, run=run, session=session, **kwargs)
        if not run:
            response = input(
                f"does the simulation for {component.name} look good? (y/n)"
            )
            if response.upper()[0] == "N":
                need_review.append(component.name)


if __name__ == "__main__":
    from gdsfactory.components import (
        bend_euler,
        bend_s,
        coupler,
        coupler_adiabatic,
        coupler_asymmetric,
        coupler_full,
        coupler_ring,
        coupler_symmetric,
        crossing,
        crossing45,
        mmi1x2,
        mmi2x2,
        taper,
        taper_cross_section_linear,
        taper_cross_section_parabolic,
        taper_cross_section_sine,
    )

    factory_passives = dict(
        bend_euler=bend_euler,
        bend_s=bend_s,
        coupler=coupler,
        coupler_adiabatic=coupler_adiabatic,
        coupler_asymmetric=coupler_asymmetric,
        coupler_full=coupler_full,
        coupler_ring=coupler_ring,
        coupler_symmetric=coupler_symmetric,
        crossing=crossing,
        crossing45=crossing45,
        taper_cross_section_linear=taper_cross_section_linear,
        taper_cross_section_sine=taper_cross_section_sine,
        taper_cross_section_parabolic=taper_cross_section_parabolic,
        taper=taper,
        mmi1x2=mmi1x2,
        mmi2x2=mmi2x2,
    )

    write_sparameters_lumerical_components(components=factory_passives.values())
