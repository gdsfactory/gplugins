"""Returns simulation from component."""

from __future__ import annotations

import inspect
import warnings
from typing import Any, Literal

import gdsfactory as gf
import meep as mp
import numpy as np
from gdsfactory.component import Component
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from gdsfactory.typings import LayerSpecs, Float3

from gplugins.common.base_models.component import move_polar_rad_copy
from gplugins.gmeep.get_material import get_material
from gplugins.gmeep.get_meep_geometry import (
    get_meep_geometry_from_component,
)

mp.verbosity(0)

sig = inspect.signature(mp.Simulation)
settings_meep = set(sig.parameters.keys())


def is_point_in_plane(
        test_point: Float3,
        plane_support: Float3,
        plane_normal: Float3,
        tolerance: float = 1e-6,        # 1 pm for coordinates in µm
):
    a, b, c = plane_normal
    xt, yt, zt = test_point
    x0, y0, z0 = plane_support
    distance = (a*(xt-x0) + b*(yt-y0) + c*(zt-z0)) / np.linalg.norm(plane_normal)
    return bool(abs(distance) <= tolerance)


def get_simulation(
    component: Component,
    resolution: int = 30,
    extend_ports_length: float | None = 10.0,
    layer_stack: LayerStack | None = None,
    zmargin_top: float = 3.0,
    zmargin_bot: float = 3.0,
    tpml: float = 1.5,
    clad_material: str = "SiO2",
    is_3d: bool = False,
    normal_2d: Literal['X', 'Y', 'Z'] = 'Z',
    point_2d: tuple[float, float, float] = (0, 0, 0),
    wavelength_start: float = 1.5,
    wavelength_stop: float = 1.6,
    wavelength_points: int = 50,
    dfcen: float = 0.2,
    port_source_name: str = "o1",
    port_source_mode: int = 0,
    port_margin: float = 3,
    distance_source_to_monitors: float = 0.2,
    port_source_offset: float = 0,
    port_monitor_offset: float = 0,
    dispersive: bool = False,
    material_name_to_meep: dict[str, str | float] | None = None,
    continuous_source: bool = False,
    exclude_layers: LayerSpecs | None = None,
    **settings,
) -> dict[str, Any]:
    r"""Returns Simulation dict from gdsfactory Component.

    based on meep directional coupler example
    https://meep.readthedocs.io/en/latest/Python_Tutorials/GDSII_Import/

    https://support.lumerical.com/hc/en-us/articles/360042095873-Metamaterial-S-parameter-extraction

    .. code::

         top view
              ________________________________
             |                               |
             | xmargin_left                  | port_extension
             |<------>          port_margin ||<-->
          ___|___________          _________||___
             |           \        /          |
             |            \      /           |
             |             ======            |
             |            /      \           |
          ___|___________/        \__________|___
             |   |                 <-------->|
             |   |ymargin_bot   xmargin_right|
             |   |                           |
             |___|___________________________|

        side view
              ________________________________
             |                     |         |
             |                     |         |
             |                   zmargin_top |
             |ymargin              |         |
             |<---> _____         _|___      |
             |     |     |       |     |     |
             |     |     |       |     |     |
             |     |_____|       |_____|     |
             |       |                       |
             |       |                       |
             |       |zmargin_bot            |
             |       |                       |
             |_______|_______________________|


    Args:
        component: gdsfactory Component.
        resolution: in pixels/um (20: for coarse, 120: for fine).
        extend_ports_length: to extend ports beyond the PML.
        layer_stack: contains layer to thickness, zmin and material.
            Defaults to active pdk.layer_stack.
        zmargin_top: thickness for cladding above core.
        zmargin_bot: thickness for cladding below core.
        tpml: PML thickness (um).
        clad_material: material for cladding.
        is_3d: if True runs in 3D.
        normal_2d: specified normal of 2D simulation plane
        point_2d: specifies support point for 2D simulation plane
        wavelength_start: wavelength min (um).
        wavelength_stop: wavelength max (um).
        wavelength_points: wavelength steps.
        dfcen: delta frequency.
        port_source_name: input port name.
        port_source_mode: mode number for source.
        port_margin: margin on each side of the port.
        distance_source_to_monitors: in (um) source goes before.
        port_source_offset: offset between source GDS port and source MEEP port.
        port_monitor_offset: offset between monitor GDS port and monitor MEEP port.
        dispersive: use dispersive material models (requires higher resolution).
        material_name_to_meep: map layer_stack names with meep material database name
            or refractive index. dispersive materials have a wavelength dependent index.
        continuous_source: if True, defines a continuous source at (wavelength_start + wavelength_stop)/2 instead of the ramped source
        exclude_layers: these layers will be ignored in geometry generation.

    Keyword Args:
        settings: extra simulation settings (resolution, symmetries, etc.)

    Returns:
        simulation dict: sim, monitors, sources.

    Make sure you review the simulation before you simulate a component

    .. code::

        import gdsfactory as gf
        import gplugins.meep as gm

        c = gf.components.bend_circular()
        gm.write_sparameters_meep(c, run=False)

    """
    for setting in settings:
        if setting not in settings_meep:
            raise ValueError(f"{setting!r} not in {sorted(settings_meep)}")
    normal_2d = normal_2d.upper()
    normal_vec = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}[normal_2d]

    layer_stack = layer_stack or get_layer_stack()
    layer_to_thickness = layer_stack.get_layer_to_thickness()

    wavelength = (wavelength_start + wavelength_stop) / 2
    wavelengths = np.linspace(wavelength_start, wavelength_stop, wavelength_points)

    port_names = [port.name for port in component.ports]
    if port_source_name not in port_names:
        warnings.warn(f"port_source_name={port_source_name!r} not in {port_names}")
        port_source = component.ports[0]
        port_source_name = port_source.name
        warnings.warn(f"Selecting port_source_name={port_source_name!r} instead.")

    assert isinstance(component, Component), (
        f"component needs to be a gf.Component, got Type {type(component)}"
    )

    component_extended = gf.c.extend_ports(component=component, length=extend_ports_length)
    component_extended = component_extended.copy()
    component_extended.flatten()

    layers_thickness = [
        layer_to_thickness[layer]
        for layer in component.layers
        if layer in layer_to_thickness
    ]

    if layers_thickness is None:
        raise ValueError(
            f"Component layers {component.layers} not in {layer_to_thickness.keys()}. "
            "Did you passed the correct layer_stack?"
        )

    t_core = sum(
        layers_thickness
    )  # This isn't exactly what we want but I think it's better than max
    cell_thickness = tpml + zmargin_bot + t_core + zmargin_top + tpml

    cell_size = mp.Vector3(
        0 if normal_2d == 'X' and not is_3d else component.xsize + 2 * tpml,
        0 if normal_2d == 'Y' and not is_3d else component.ysize + 2 * tpml,
        0 if normal_2d == 'Z' and not is_3d else cell_thickness,
    )

    geometry = get_meep_geometry_from_component(
        component=component_extended,
        layer_stack=layer_stack,
        material_name_to_meep=material_name_to_meep,
        wavelength=wavelength,
        dispersive=dispersive,
        exclude_layers=exclude_layers,
    )

    freqs = 1 / wavelengths
    fcen = np.mean(freqs)
    frequency_width = dfcen * fcen

    # Add source
    port = component.ports[port_source_name]
    angle_rad = np.radians(port.orientation)
    width = port.width + 2 * port_margin
    size_x = width * abs(np.sin(angle_rad))
    size_y = width * abs(np.cos(angle_rad))
    size_x = 0 if size_x < 0.001 else size_x
    size_y = 0 if size_y < 0.001 else size_y
    size_z = cell_thickness - 2 * tpml
    size = [
        0 if normal_2d == 'X' and not is_3d else size_x,
        0 if normal_2d == 'Y' and not is_3d else size_y,
        0 if normal_2d == 'Z' and not is_3d else size_z,
    ]
    xy_shifted = move_polar_rad_copy(
        np.array(port.center), angle=angle_rad, length=port_source_offset
    )
    center = xy_shifted.round(6).tolist() + [0]  # (x, y, z=0)

    if np.isclose(port.orientation, 0):
        direction = mp.X
    elif np.isclose(port.orientation, 90):
        direction = mp.Y
    elif np.isclose(port.orientation, 180):
        direction = mp.X
    elif np.isclose(port.orientation, 270):
        direction = mp.Y
    else:
        raise ValueError(
            f"Port source {port_source_name!r} orientation {port.orientation} "
            "not 0, 90, 180, 270 degrees"
        )

    if not (is_3d or is_point_in_plane(center, point_2d, normal_vec)):
        raise ValueError(
            f"Source '{port_source_name}' (center={center}) is not in {normal_2d}-normal 2D simulation domain around {point_2d}."
        )

    sources = [
        mp.EigenModeSource(
            src=mp.ContinuousSource(fcen)
            if continuous_source
            else mp.GaussianSource(fcen, fwidth=frequency_width),
            size=size,
            center=center,
            eig_band=port_source_mode + 1,
            eig_parity=mp.NO_PARITY,
            eig_match_freq=True,
            eig_kpoint=-1 * mp.Vector3(x=1).rotate(mp.Vector3(z=1), angle_rad),
            direction=direction,
        )
    ]

    sim_center = mp.Vector3(
        point_2d[0] if normal_2d == 'X' and not is_3d else component.x,
        point_2d[1] if normal_2d == 'Y' and not is_3d else component.y,
        point_2d[2] if normal_2d == 'Z' and not is_3d else 0,
    )
    sim = mp.Simulation(
        cell_size=cell_size,
        geometry_center=sim_center,
        boundary_layers=[mp.PML(tpml)],
        sources=sources,
        geometry=geometry,
        default_material=get_material(
            name=clad_material,
            material_name_to_meep=material_name_to_meep,
            wavelength=wavelength,
        ),
        resolution=resolution,
        **settings,
    )

    # Add port monitors dict
    monitors = {}
    for port in component.ports:
        port_name = port.name
        angle_rad = np.radians(port.orientation)
        width = port.width + 2 * port_margin
        size_x = width * abs(np.sin(angle_rad))
        size_y = width * abs(np.cos(angle_rad))
        size_x = 0 if size_x < 0.001 else size_x
        size_y = 0 if size_y < 0.001 else size_y
        size = mp.Vector3(
            0 if normal_2d == 'X' and not is_3d else size_x,
            0 if normal_2d == 'Y' and not is_3d else size_y,
            0 if normal_2d == 'Z' and not is_3d else size_z,
        )

        # if monitor has a source move monitor inwards
        length = (
            -distance_source_to_monitors + port_source_offset
            if port_name == port_source_name
            else port_monitor_offset
        )
        xy_shifted = move_polar_rad_copy(
            np.array(port.center), angle=angle_rad, length=length
        )
        center = xy_shifted.round(6).tolist() + [0]  # (x, y, z=0)
        if is_3d or is_point_in_plane(center, point_2d, normal_vec):
            m = sim.add_mode_monitor(freqs, mp.ModeRegion(center=center, size=size))
            m.z = 0
            monitors[port_name] = m
        else:
            warnings.warn(f"Monitor at port '{port_name}' ignored, "
                          f"because it is not in the {normal_2d}-normal 2D simulation domain around {point_2d}.")
    return dict(
        sim=sim,
        cell_size=cell_size,
        freqs=freqs,
        monitors=monitors,
        sources=sources,
        port_source_name=port_source_name,
        port_source_mode=port_source_mode,
        initialized=False,
    )


sig = inspect.signature(get_simulation)
settings_get_simulation = set(sig.parameters.keys()).union(settings_meep)


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    c = gf.components.bend_circular()

    sim_dict = get_simulation(
        c,
        is_3d=False,
        # resolution=50,
        # port_source_offset=-0.1,
        # port_field_monitor_offset=-0.1,
        # port_margin=2.5,
        continuous_source=True,
    )
    sim = sim_dict["sim"]
    sim.plot2D()
    plt.show()

    # Plot monitor cross-section (is_3D needs to be True)
    # sim.init_sim()
    # eps_data = sim.get_epsilon()

    # from mayavi import mlab
    # s = mlab.contour3d(eps_data, colormap="YlGnBu")
    # mlab.show()

    print(settings_get_simulation)
