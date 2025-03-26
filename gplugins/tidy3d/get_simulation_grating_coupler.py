from __future__ import annotations

import warnings

import gdsfactory as gf
import gdstk
import matplotlib.pyplot as plt
import numpy as np
import tidy3d as td
from gdsfactory.component import Component
from gdsfactory.pdk import get_layer, get_layer_stack
from gdsfactory.technology import DerivedLayer, LayerStack, LogicalLayer
from gdsfactory.typings import CrossSectionSpec, LayerSpecs

from gplugins.common.base_models.component import move_polar_rad_copy
from gplugins.tidy3d.materials import get_medium


def get_simulation_grating_coupler(
    component: Component,
    port_extension: float = 10.0,
    layer_stack: LayerStack | None = None,
    exclude_layers: LayerSpecs | None = None,
    thickness_pml: float = 1.0,
    xmargin: float = 0,
    ymargin: float = 0,
    xmargin_left: float = 0,
    xmargin_right: float = 0,
    ymargin_top: float = 0,
    ymargin_bot: float = 0,
    zmargin: float = 1.0,
    clad_material: str = "sio2",
    box_material: str = "sio2",
    box_thickness: float = 3.0,
    substrate_material: str = "si",
    port_waveguide_name: str = "o1",
    port_margin: float = 0.5,
    port_waveguide_offset: float = 0.1,
    wavelength: float = 1.55,
    wavelength_start: float = 1.20,
    wavelength_stop: float = 1.80,
    wavelength_points: int = 256,
    plot_modes: bool = False,
    num_modes: int = 2,
    run_time_ps: float = 10.0,
    fiber_port_prefix: str = "o2",
    fiber_xoffset: float = 0,
    fiber_z: float = 2,
    fiber_mfd: float = 10.4,
    fiber_angle_deg: float = 20.0,
    material_name_to_tidy3d: dict[str, str] | None = None,
    is_3d: bool = True,
    with_all_monitors: bool = False,
    boundary_spec: td.BoundarySpec | None = None,
    grid_spec: td.GridSpec | None = None,
    sidewall_angle_deg: float = 0,
    dilation: float = 0.0,
    cross_section: CrossSectionSpec | None = None,
    **kwargs,
) -> td.Simulation:
    r"""Returns Simulation object from a gdsfactory grating coupler component.

    Injects a Gaussian beam from above and monitors the transmission into the waveguide.

    based on grating coupler example
    https://docs.simulation.cloud/projects/tidy3d/en/latest/notebooks/GratingCoupler.html

    .. code::

         top view
              ________________________________
             |                               |
             | xmargin_left                  |
             |<------>                       |
             |           ________________    |
             |          /   |  |  |  |  |    |
             |         /    |  |  |  |  |    |
             |=========     |  |  |  |  |    |
             |         \    |  |  |  |  |    |
             |   _ _ _ _\___|__|__|__|__|    |
             |   |                       <-->|
             |   |ymargin_bot   xmargin_right|
             |   |                           |
             |___|___________________________|


        side view

              fiber_xoffset
                 |<--->|
            fiber_port_name
                 |
                         fiber_angle_deg > 0
                        |  /
                        | /
                        |/
                 /              /       |
                /  fiber_mfd   /        |
               /<------------>/    _ _ _| _ _ _ _ _ _ _
                                        |
                   clad_material        | fiber_z
                    _   _   _      _ _ _|_ _ _ _ _ _ _
                   | | | | | |          ||core_thickness
                  _| |_| |_| |__________||___
                                        || |
        waveguide            |          || | slab_thickness
              ____________________ _ _ _||_|_
                             |          |
                   box_material         |box_thickness
              _______________|____ _ _ _|_ _ _ _ _ _ _
                             |          |
                 substrate_material     |substrate_thickness
             ________________|____ _ _ _|_ _ _ _ _ _ _
                             |
        |--------------------|<-------->
                                xmargin

    Args:
        component: gdsfactory Component.
        port_extension: extend ports beyond the PML.
        layer_stack: contains layer to thickness, zmin and material.
            Defaults to active pdk.layer_stack.
        exclude_layers: list of layers to exclude.
        thickness_pml: PML thickness (um).
        xmargin: left/right distance from component to PML.
        xmargin_left: left distance from component to PML.
        xmargin_right: right distance from component to PML.
        ymargin: left/right distance from component to PML.
        ymargin_top: top distance from component to PML.
        ymargin_bot: bottom distance from component to PML.
        zmargin: thickness for cladding above and below core.
        clad_material: material for cladding.
        box_material: material for box.
        substrate_material: material for substrate.
        box_thickness: (um).
        substrate_thickness: (um).
        port_waveguide_name: input port name.
        port_margin: margin on each side of the port.
        port_waveguide_offset: mode solver workaround.
            positive moves source forward, negative moves source backward.
        wavelength: source center wavelength (um).
            if None takes mean between wavelength_start, wavelength_stop
        wavelength_start: in (um).
        wavelength_stop: in (um).
        wavelength_points: number of wavelengths.
        plot_modes: plot source modes.
        num_modes: number of modes to plot.
        run_time_ps: make sure it's sufficient for the fields to decay.
            defaults to 10ps and automatic shutoff stops earlier if needed.
        fiber_port_prefix: port prefix to place fiber source.
        fiber_xoffset: fiber center xoffset to fiber_port_name.
        fiber_z: fiber zoffset from grating zmax.
        fiber_mfd: fiber mode field diameter (um). 10.4 for Cband and 9.2um for Oband.
        fiber_angle_deg: fiber_angle in degrees with respect to normal.
            Positive for west facing, Negative for east facing sources.
        material_name_to_tidy3d: dispersive materials have a wavelength
            dependent index. Maps layer_stack names with tidy3d material database names.
        is_3d: if False collapses the Y direction for a 2D simulation.
        with_all_monitors: True includes field monitors which increase results filesize.
        grid_spec: defaults to automatic td.GridSpec.auto(wavelength=wavelength)
            td.GridSpec.uniform(dl=20*nm)
            td.GridSpec(
                grid_x = td.UniformGrid(dl=0.04),
                grid_y = td.AutoGrid(min_steps_per_wvl=20),
                grid_z = td.AutoGrid(min_steps_per_wvl=20),
                wavelength=wavelength,
                override_structures=[refine_box]
            )
        boundary_spec: Specification of boundary conditions along each dimension.
            Defaults to td.BoundarySpec.all_sides(boundary=td.PML())
        sidewall_angle_deg : float = 0
            Angle of the sidewall.
            ``sidewall_angle=0`` (default) specifies vertical wall,
            while ``0<sidewall_angle_deg<90`` for the base to be larger than the top.
        dilation: float = 0.0
            Dilation of the polygon in the base by shifting each edge along its
            normal outwards direction by a distance;
            a negative value corresponds to erosion.
        cross_section: optional cross_section to extend ports beyond PML.
        kwargs: Additional keyword arguments to pass to the Simulation constructor.

    Keyword Args:
        symmetry: Define Symmetries.
            Tuple of integers defining reflection symmetry across a plane
            bisecting the simulation domain normal to the x-, y-, and z-axis
            at the simulation center of each axis, respectively.
            Each element can be ``0`` (no symmetry), ``1`` (even, i.e. 'PMC' symmetry) or
            ``-1`` (odd, i.e. 'PEC' symmetry).
            Note that the vectorial nature of the fields must be taken into account to correctly
            determine the symmetry value.
        medium: Background medium of simulation, defaults to vacuum if not specified.
        shutoff: shutoff condition
            Ratio of the instantaneous integrated E-field intensity to the maximum value
            at which the simulation will automatically terminate time stepping.
            Used to prevent extraneous run time of simulations with fully decayed fields.
            Set to ``0`` to disable this feature.
        subpixel: subpixel averaging.If ``True``, uses subpixel averaging of the permittivity
        based on structure definition, resulting in much higher accuracy for a given grid size.
        courant: courant factor.
            Courant stability factor, controls time step to spatial step ratio.
            Lower values lead to more stable simulations for dispersive materials,
            but result in longer simulation times.
        version: String specifying the front end version number.

    .. code::

        import matplotlib.pyplot as plt
        import gdsfactory as gf
        import gplugins.tidy3d as gt

        c = gf.components.grating_coupler_elliptical_arbitrary(
            widths=[0.343] * 25, gaps=[0.345] * 25
        )
        sim = gt.get_simulation(c)
        gt.plot_simulation(sim)

    """
    # Handle layer stack and layer views
    layer_stack = layer_stack or get_layer_stack()

    # Exclude specified layers
    exclude_layers = exclude_layers or ()
    exclude_layers = [get_layer(layer) for layer in exclude_layers]

    # Get component with derived layers applied
    component_with_booleans = layer_stack.get_component_with_derived_layers(component)

    # Extract polygons per layer
    polygons_per_layer = component_with_booleans.get_polygons_points(merge=True)
    if not polygons_per_layer:
        raise ValueError(
            f"{component.name!r} does not have polygons defined in the "
            f"layer_stack or layer_views for the active Pdk {gf.get_active_pdk().name!r}"
        )

    # Initialize simulation structures
    structures = []
    has_polygons = False
    xmargin_left = xmargin_left or xmargin
    xmargin_right = xmargin_right or xmargin
    ymargin_top = ymargin_top or ymargin
    ymargin_bot = ymargin_bot or ymargin

    component_extended = (
        gf.components.extend_ports(
            component=component_with_booleans,
            length=port_extension,
            centered=True,
            cross_section=cross_section,
        )
        if port_extension
        else component
    )
    gdspath = component_extended.write_gds()
    component_exteded_name = component_extended.name

    lib_loaded = gdstk.read_gds(gdspath)
    # Create a cell dictionary with all the cells in the file
    all_cells = {c.name: c for c in lib_loaded.cells}
    component_extended_cell = all_cells[component_exteded_name]

    # Iterate through each layer in the layer stack
    for level in layer_stack.layers.values():
        layer = level.layer

        # Determine layer index and tuple
        if isinstance(layer, LogicalLayer):
            layer_index = layer.layer
            layer_tuple: tuple[int, int] = tuple(layer_index)  # type: ignore
        elif isinstance(layer, DerivedLayer):
            assert level.derived_layer is not None
            layer_index = level.derived_layer.layer
            layer_tuple = tuple(layer_index)  # type: ignore
        else:
            warnings.warn(
                f"Layer {layer!r} is neither LogicalLayer nor DerivedLayer. Skipping."
            )
            continue

        # Normalize layer index
        normalized_layer = int(get_layer(layer_index))  # type: ignore

        # Skip excluded layers
        if normalized_layer in exclude_layers:
            continue

        # Skip layers without polygons
        if normalized_layer not in polygons_per_layer:
            continue

        # Get zmin and thickness
        zmin = level.zmin
        thickness = level.thickness
        zmax = zmin + thickness

        # Get material for the layer
        material_name_to_tidy3d = material_name_to_tidy3d or {}
        material_name = layer_stack.get_layer_to_material().get(layer, "vacuum")
        material_spec = material_name_to_tidy3d.get(material_name, material_name)
        medium = get_medium(spec=material_spec)

        # Get polygons for the current layer
        polygons = polygons_per_layer[normalized_layer]
        polygons = td.PolySlab.from_gds(
            gds_cell=component_extended_cell,
            gds_layer=layer_tuple[0],
            gds_dtype=layer_tuple[1],
            axis=2,
            slab_bounds=(zmin, zmax),
            sidewall_angle=np.deg2rad(sidewall_angle_deg),
            dilation=dilation,
        )

        print(f"Adding layer {layer_tuple}, {zmin=}, {zmax=}")

        for polygon in polygons:
            geometry = td.Structure(
                geometry=polygon,
                medium=medium,
            )
            structures.append(geometry)
            has_polygons = True

    if not has_polygons:
        raise ValueError(
            f"{component.name!r} does not have valid polygons for simulation."
        )

    # Define simulation boundaries
    boundary_spec = boundary_spec or (
        td.BoundarySpec.all_sides(boundary=td.PML())
        if is_3d
        else td.BoundarySpec(
            x=td.Boundary.pml(),
            y=td.Boundary.periodic(),
            z=td.Boundary.pml(),
        )
    )

    # Define grid specification
    grid_spec = grid_spec or td.GridSpec.auto(wavelength=wavelength)

    # Define simulation size based on component dimensions and margins
    sim_xsize = (
        component_with_booleans.size_info.width
        + 2 * thickness_pml
        + xmargin_left
        + xmargin_right
    )
    sim_ysize = (
        component_with_booleans.size_info.height
        + 2 * thickness_pml
        + ymargin_top
        + ymargin_bot
        if is_3d
        else 0
    )
    sim_zsize = (
        thickness_pml
        + box_thickness
        + max(layer_stack.get_layer_to_thickness().values(), default=0)
        + thickness_pml
        + 2 * zmargin
    )
    sim_size = [sim_xsize, sim_ysize, sim_zsize]

    # Handle material mapping
    material_name_to_tidy3d = material_name_to_tidy3d or {}
    clad_medium = get_medium(
        spec=material_name_to_tidy3d.get(clad_material, clad_material)
    )
    box_medium = get_medium(
        spec=material_name_to_tidy3d.get(box_material, box_material)
    )
    substrate_medium = get_medium(
        spec=material_name_to_tidy3d.get(substrate_material, substrate_material)
    )

    # Define cladding, box, and substrate structures
    clad = td.Structure(
        geometry=td.Box(
            size=(td.inf, td.inf, sim_zsize),
            center=(0, 0, sim_zsize / 2),
        ),
        medium=clad_medium,
    )
    box = td.Structure(
        geometry=td.Box(
            size=(td.inf, td.inf, box_thickness),
            center=(0, 0, -box_thickness / 2),
        ),
        medium=box_medium,
    )
    substrate_thickness = 10  # Define substrate thickness (um)
    substrate = td.Structure(
        geometry=td.Box(
            size=(td.inf, td.inf, substrate_thickness),
            center=(0, 0, -box_thickness - substrate_thickness / 2),
        ),
        medium=substrate_medium,
    )
    structures = [substrate, box, clad] + structures

    # Define wavelengths and frequencies
    wavelengths = np.linspace(wavelength_start, wavelength_stop, wavelength_points)
    freqs = td.constants.C_0 / wavelengths
    freq0 = td.constants.C_0 / np.mean(wavelengths)
    fwidth = freq0 / 10

    # Add input waveguide port
    if port_waveguide_name not in component_with_booleans.ports:
        available_ports = list(component_with_booleans.ports.keys())
        raise ValueError(
            f"port_waveguide_name='{port_waveguide_name}' not found in component ports {available_ports}."
        )
    port = component_with_booleans.ports[port_waveguide_name]
    angle = port.orientation
    width = port.width + 2 * port_margin
    size_x = width * abs(np.sin(np.deg2rad(angle)))
    size_y = width * abs(np.cos(np.deg2rad(angle)))
    size_x = size_x if size_x > 0.001 else 0
    size_y = size_y if size_y > 0.001 else 0
    size_y = size_y if is_3d else td.inf
    size_z = (
        max(layer_stack.get_layer_to_thickness().values(), default=0)
        + zmargin
        + box_thickness
    )
    waveguide_port_size = [size_x, size_y, size_z]

    xy_shifted = move_polar_rad_copy(
        np.array(port.dcenter), angle=np.deg2rad(angle), length=port_waveguide_offset
    )
    waveguide_port_center = [xy_shifted[0], xy_shifted[1], (size_z) / 2]

    waveguide_monitor = td.ModeMonitor(
        center=waveguide_port_center,
        size=waveguide_port_size,
        freqs=freqs,
        mode_spec=td.ModeSpec(num_modes=1, precision="double"),
        name="waveguide",
    )

    # Identify fiber port
    fiber_port_name = None
    for port in component_with_booleans.ports:
        port_name = port.name
        if port_name.startswith(fiber_port_prefix):
            fiber_port_name = port_name
            break

    if fiber_port_name is None:
        raise ValueError(
            f"No port starting with prefix '{fiber_port_prefix}' found in component ports {list(component_with_booleans.ports.keys())}."
        )

    fiber_port = component_with_booleans.ports[fiber_port_name]
    fiber_port_x = fiber_port.dcenter[0] + fiber_xoffset - component_with_booleans.x

    if not (-sim_size[0] / 2 <= fiber_port_x <= sim_size[0] / 2):
        xmin = float(np.round(-sim_size[0] / 2, 3))
        xmax = -xmin
        raise ValueError(
            f"Fiber port x-position {fiber_port_x} is outside the simulation domain {xmin=}, {xmax=}."
        )

    # Define Gaussian beam source
    gaussian_beam = td.GaussianBeam(
        size=(td.inf, td.inf, 0),
        center=[fiber_port_x, 0, fiber_z],
        source_time=td.GaussianPulse(freq0=freq0, fwidth=fwidth),
        angle_theta=np.deg2rad(-fiber_angle_deg),
        angle_phi=np.pi,
        direction="-",
        waist_radius=fiber_mfd / 2,
        pol_angle=np.pi / 2,
    )

    # Define additional monitors
    plane_monitor = td.FieldMonitor(
        center=[0, 0, sim_zsize / 2],
        size=[sim_size[0], sim_size[1], 0],
        freqs=[freq0],
        name="full_domain_fields",
    )

    rad_monitor = td.FieldMonitor(
        center=[0, 0, 0],
        size=[td.inf, 0, td.inf],
        freqs=[freq0],
        name="radiated_fields",
    )

    near_field_monitor = td.FieldMonitor(
        center=[0, 0, fiber_z],
        size=[td.inf, td.inf, 0],
        freqs=[freq0],
        name="radiated_near_fields",
    )

    # Compile list of monitors
    monitors = [waveguide_monitor]
    if with_all_monitors:
        monitors += [plane_monitor, rad_monitor, near_field_monitor]

    # Assemble simulation structures
    sim = td.Simulation(
        size=sim_size,
        structures=structures,
        sources=[gaussian_beam],
        monitors=monitors,
        run_time=run_time_ps * 1e-12,
        boundary_spec=boundary_spec,
        grid_spec=grid_spec,
        **kwargs,
    )

    # Optional: Plotting modes
    if plot_modes:
        src_plane = td.Box(center=waveguide_port_center, size=waveguide_port_size)
        mode_spec = td.ModeSpec(num_modes=num_modes)

        ms = td.ModeSolver(
            simulation=sim,
            plane=src_plane,
            freqs=[freq0],
            mode_spec=mode_spec,
        )
        modes = ms.solve()

        print(
            "Effective index of computed modes: ",
            ", ".join([f"{n_eff:.4f}" for n_eff in modes.n_eff.isel(f=0).values]),
        )

        if is_3d:
            fig, axs = plt.subplots(num_modes, 2, figsize=(12, 6 * num_modes))
        else:
            fig, axs = plt.subplots(num_modes, 3, figsize=(18, 6 * num_modes))

        for mode_ind in range(num_modes):
            if is_3d:
                modes.Ey.isel(mode_index=mode_ind).abs.plot(
                    x="y", y="z", cmap="magma", ax=axs[mode_ind, 0]
                )
                modes.Ez.isel(mode_index=mode_ind).abs.plot(
                    x="y", y="z", cmap="magma", ax=axs[mode_ind, 1]
                )
                axs[mode_ind, 0].set_title(f"|Ey|: mode_index={mode_ind}")
                axs[mode_ind, 1].set_title(f"|Ez|: mode_index={mode_ind}")
            else:
                modes.Ex.isel(mode_index=mode_ind).abs.plot(ax=axs[mode_ind, 0])
                modes.Ey.isel(mode_index=mode_ind).abs.plot(ax=axs[mode_ind, 1])
                modes.Ez.isel(mode_index=mode_ind).abs.plot(ax=axs[mode_ind, 2])

                axs[mode_ind, 0].set_title(f"|Ex|: mode_index={mode_ind}")
                axs[mode_ind, 1].set_title(f"|Ey|: mode_index={mode_ind}")
                axs[mode_ind, 2].set_title(f"|Ez|: mode_index={mode_ind}")

        if is_3d:
            for ax in axs.flat:
                ax.set_aspect("equal")
        plt.tight_layout()
        plt.show()

    return sim


if __name__ == "__main__":
    import gplugins.tidy3d as gt

    c = gf.components.grating_coupler_elliptical_trenches()
    # c = gf.components.grating_coupler_elliptical_lumerical()

    # Example of using an arbitrary grating coupler
    # c = gf.components.grating_coupler_elliptical_arbitrary(
    #     widths=[0.343] * 25, gaps=[0.345] * 25
    # )

    sim = get_simulation_grating_coupler(
        c,
        plot_modes=False,
        is_3d=False,
        fiber_angle_deg=20,
    )
    gt.plot_simulation(sim)  # Ensure simulation looks good
    c.show()
