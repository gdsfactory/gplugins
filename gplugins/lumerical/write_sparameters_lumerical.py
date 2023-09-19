"""Write Sparameters with Lumerical FDTD."""
from __future__ import annotations

import shutil
import time
from typing import TYPE_CHECKING

import gdsfactory as gf
import numpy as np
import yaml
from gdsfactory.config import __version__, logger
from gdsfactory.generic_tech.simulation_settings import (
    SIMULATION_SETTINGS_LUMERICAL_FDTD,
    SimulationSettingsLumericalFdtd,
)
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack

from gplugins.common.utils.get_sparameters_path import (
    get_sparameters_path_lumerical as get_sparameters_path,
)

if TYPE_CHECKING:
    from gdsfactory.typings import ComponentSpec, MaterialSpec, PathType

run_false_warning = """
You have passed run=False to debug the simulation

run=False returns the simulation session for you to debug and make sure it is correct

To compute the Sparameters you need to pass run=True
"""


def set_material(session, structure: str, material: MaterialSpec) -> None:
    """Sets the material of a structure.

    Args:
        session: lumerical session.
        structure: name of the lumerical structure.
        material: material spec, can be
            a string from lumerical database materials.
            a float or int, representing refractive index.
            a complex for n, k materials.

    """
    if isinstance(material, str):
        session.setnamed(structure, "material", material)
    elif isinstance(material, int | float):
        session.setnamed(structure, "index", material)
    elif isinstance(material, complex):
        mat = session.addmaterial("(n,k) Material")
        session.setmaterial(mat, "Refractive Index", material.real)
        session.setmaterial(mat, "Imaginary Refractive Index", material.imag)
        session.setnamed(structure, "material", mat)
    elif isinstance(material, tuple | list):
        if len(material) != 2:
            raise ValueError(
                "Complex material requires a tuple or list of two numbers "
                f"(real, imag). Got {material} "
            )
        real, imag = material
        mat = session.addmaterial("(n,k) Material")
        session.setmaterial(mat, "Refractive Index", real)
        session.setmaterial(mat, "Imaginary Refractive Index", imag)
        session.setnamed(structure, "material", mat)
    else:
        raise ValueError(
            f"{material!r} needs to be a float refractive index, a complex number or tuple "
            "or a string from lumerical's material database"
        )


def write_sparameters_lumerical(
    component: ComponentSpec,
    session: object | None = None,
    run: bool = True,
    overwrite: bool = False,
    dirpath: PathType | None = None,
    layer_stack: LayerStack | None = None,
    simulation_settings: SimulationSettingsLumericalFdtd = SIMULATION_SETTINGS_LUMERICAL_FDTD,
    material_name_to_lumerical: dict[str, MaterialSpec] | None = None,
    delete_fsp_files: bool = True,
    xmargin: float = 0,
    ymargin: float = 0,
    xmargin_left: float = 0,
    xmargin_right: float = 0,
    ymargin_top: float = 0,
    ymargin_bot: float = 0,
    zmargin: float = 1.0,
    **settings,
) -> np.ndarray:
    r"""Returns and writes component Sparameters using Lumerical FDTD.

    If simulation exists it returns the Sparameters directly unless overwrite=True
    which forces a re-run of the simulation

    Writes Sparameters both in .npz and .DAT (interconnect format) as well as
    simulation settings in .YAML

    In the npz format you can see `S12m` where `m` stands for magnitude
    and `S12a` where `a` stands for angle in radians

    Your components need to have ports, that will extend over the PML.

    .. image:: https://i.imgur.com/dHAzZRw.png

    For your Fab technology you can overwrite

    - simulation_settings
    - dirpath
    - layerStack

    converts gdsfactory units (um) to Lumerical units (m)

    Disclaimer: This function tries to extract Sparameters automatically
    is hard to make a function that will fit all your possible simulation settings.
    You can use this function for inspiration to create your own.

    Args:
        component: Component to simulate.
        session: you can pass a session=lumapi.FDTD() or it will create one.
        run: True runs Lumerical, False only draws simulation.
        overwrite: run even if simulation results already exists.
        dirpath: directory to store sparameters in npz.
            Defaults to active Pdk.sparameters_path.
        layer_stack: contains layer to thickness, zmin and material.
            Defaults to active pdk.layer_stack.
        simulation_settings: dataclass with all simulation_settings.
        material_name_to_lumerical: alias to lumerical material's database name
            or refractive index.
            translate material name in LayerStack to lumerical's database name.
        delete_fsp_files: deletes lumerical fsp files after simulation.
        xmargin: left/right distance from component to PML.
        xmargin_left: left distance from component to PML.
        xmargin_right: right distance from component to PML.
        ymargin: left/right distance from component to PML.
        ymargin_top: top distance from component to PML.
        ymargin_bot: bottom distance from component to PML.
        zmargin: thickness for cladding above and below core.

    Keyword Args:
        background_material: for the background.
        port_margin: on both sides of the port width (um).
        port_height: port height (um).
        port_extension: port extension (um).
        mesh_accuracy: 2 (1: coarse, 2: fine, 3: superfine).
        wavelength_start: 1.2 (um).
        wavelength_stop: 1.6 (um).
        wavelength_points: 500.
        simulation_time: (s) related to max path length 3e8/2.4*10e-12*1e6 = 1.25mm.
        simulation_temperature: in kelvin (default = 300).
        frequency_dependent_profile: computes mode profiles for different wavelengths.
        field_profile_samples: number of wavelengths to compute field profile.


    .. code::

         top view
              ________________________________
             |                               |
             | xmargin                       | port_extension
             |<------>          port_margin ||<-->
          o2_|___________          _________||_o3
             |           \        /          |
             |            \      /           |
             |             ======            |
             |            /      \           |
          o1_|___________/        \__________|_o4
             |   |                           |
             |   |ymargin                    |
             |   |                           |
             |___|___________________________|

        side view
              ________________________________
             |                               |
             |                               |
             |                               |
             |ymargin                        |
             |<---> _____         _____      |
             |     |     |       |     |     |
             |     |     |       |     |     |
             |     |_____|       |_____|     |
             |       |                       |
             |       |                       |
             |       |zmargin                |
             |       |                       |
             |_______|_______________________|



    Return:
        Sparameters np.ndarray (wavelengths, o1@0,o1@0, o1@0,o2@0 ...)
            suffix `a` for angle in radians and `m` for module.

    """
    component = gf.get_component(component)
    sim_settings = dict(simulation_settings)

    layer_stack = layer_stack or get_layer_stack()

    layer_to_thickness = layer_stack.get_layer_to_thickness()
    layer_to_zmin = layer_stack.get_layer_to_zmin()
    layer_to_material = layer_stack.get_layer_to_material()

    if hasattr(component.info, "simulation_settings"):
        sim_settings |= component.info.simulation_settings
        logger.info(
            f"Updating {component.name!r} sim settings {component.simulation_settings}"
        )
    for setting in settings:
        if setting not in sim_settings:
            raise ValueError(
                f"Invalid setting {setting!r} not in ({list(sim_settings.keys())})"
            )

    sim_settings.update(**settings)
    ss = SimulationSettingsLumericalFdtd(**sim_settings)

    component_with_booleans = layer_stack.get_component_with_derived_layers(component)
    component_with_padding = gf.add_padding_container(
        component_with_booleans,
        default=0,
        top=ymargin or ymargin_top,
        bottom=ymargin or ymargin_bot,
        left=xmargin or xmargin_left,
        right=xmargin or xmargin_right,
    )

    component_extended = gf.components.extend_ports(
        component_with_padding, length=ss.distance_monitors_to_pml
    )

    ports = component.get_ports_list(port_type="optical")
    if not ports:
        raise ValueError(f"{component.name!r} does not have any optical ports")

    component_extended_beyond_pml = gf.components.extension.extend_ports(
        component=component_extended, length=ss.port_extension
    )
    component_extended_beyond_pml.name = "top"
    gdspath = component_extended_beyond_pml.write_gds()

    filepath_npz = get_sparameters_path(
        component=component,
        dirpath=dirpath,
        layer_stack=layer_stack,
        **settings,
    )
    filepath = filepath_npz.with_suffix(".dat")
    filepath_sim_settings = filepath.with_suffix(".yml")
    filepath_fsp = filepath.with_suffix(".fsp")
    fspdir = filepath.parent / f"{filepath.stem}_s-parametersweep"

    if run and filepath_npz.exists() and not overwrite:
        logger.info(f"Reading Sparameters from {filepath_npz.absolute()!r}")
        return np.load(filepath_npz)

    if not run and session is None:
        print(run_false_warning)

    logger.info(f"Writing Sparameters to {filepath_npz.absolute()!r}")
    x_min = (component_extended.xmin - xmargin) * 1e-6
    x_max = (component_extended.xmax + xmargin) * 1e-6
    y_min = (component_extended.ymin - ymargin) * 1e-6
    y_max = (component_extended.ymax + ymargin) * 1e-6

    layers_thickness = [
        layer_to_thickness[layer]
        for layer in component_with_booleans.get_layers()
        if layer in layer_to_thickness
    ]
    if not layers_thickness:
        raise ValueError(
            f"no layers for component {component.get_layers()}"
            f"in layer stack {layer_stack}"
        )
    layers_zmin = [
        layer_to_zmin[layer]
        for layer in component_with_booleans.get_layers()
        if layer in layer_to_zmin
    ]
    component_thickness = max(layers_thickness)
    component_zmin = min(layers_zmin)

    z = (component_zmin + component_thickness) / 2 * 1e-6
    z_span = (2 * zmargin + component_thickness) * 1e-6

    x_span = x_max - x_min
    y_span = y_max - y_min

    sim_settings.update(dict(layer_stack=layer_stack.to_dict()))

    sim_settings = dict(
        simulation_settings=sim_settings,
        component=component.to_dict(),
        version=__version__,
    )

    logger.info(
        f"Simulation size = {x_span*1e6:.3f}, {y_span*1e6:.3f}, {z_span*1e6:.3f} um"
    )

    # from pprint import pprint
    # filepath_sim_settings.write_text(yaml.dump(sim_settings))
    # print(filepath_sim_settings)
    # pprint(sim_settings)
    # return

    try:
        import lumapi
    except ModuleNotFoundError as e:
        print(
            "Cannot import lumapi (Python Lumerical API). "
            "You can add set the PYTHONPATH variable or add it with `sys.path.append()`"
        )
        raise e
    except OSError as e:
        raise e

    start = time.time()
    s = session or lumapi.FDTD(hide=False)
    s.newproject()
    s.selectall()
    s.deleteall()
    s.addrect(
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        z=z,
        z_span=z_span,
        index=1.5,
        name="clad",
    )

    material_name_to_lumerical_new = material_name_to_lumerical or {}
    material_name_to_lumerical = ss.material_name_to_lumerical.copy()
    material_name_to_lumerical.update(**material_name_to_lumerical_new)

    material = material_name_to_lumerical[ss.background_material]
    set_material(session=s, structure="clad", material=material)

    s.addfdtd(
        dimension="3D",
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        z=z,
        z_span=z_span,
        mesh_accuracy=ss.mesh_accuracy,
        use_early_shutoff=True,
        simulation_time=ss.simulation_time,
        simulation_temperature=ss.simulation_temperature,
    )
    component_layers = component_with_booleans.get_layers()

    for layer, thickness in layer_to_thickness.items():
        if layer not in component_layers:
            continue

        if layer not in layer_to_material:
            raise ValueError(f"{layer} not in {layer_to_material.keys()}")

        material_name = layer_to_material[layer]
        if material_name not in material_name_to_lumerical:
            raise ValueError(
                f"{material_name!r} not in {list(material_name_to_lumerical.keys())}"
            )
        material = material_name_to_lumerical[material_name]

        if layer not in layer_to_zmin:
            raise ValueError(f"{layer} not in {list(layer_to_zmin.keys())}")

        zmin = layer_to_zmin[layer]
        zmax = zmin + thickness
        z = (zmax + zmin) / 2

        s.gdsimport(str(gdspath), "top", f"{layer[0]}:{layer[1]}")
        layername = f"GDS_LAYER_{layer[0]}:{layer[1]}"
        s.setnamed(layername, "z", z * 1e-6)
        s.setnamed(layername, "z span", thickness * 1e-6)
        set_material(session=s, structure=layername, material=material)
        logger.info(f"adding {layer}, thickness = {thickness} um, zmin = {zmin} um ")

    for i, port in enumerate(ports):
        zmin = layer_to_zmin[port.layer]
        thickness = layer_to_thickness[port.layer]
        z = (zmin + thickness) / 2
        zspan = 2 * ss.port_margin + thickness

        s.addport()
        p = f"FDTD::ports::port {i+1}"
        s.setnamed(p, "x", port.x * 1e-6)
        s.setnamed(p, "y", port.y * 1e-6)
        s.setnamed(p, "z", z * 1e-6)
        s.setnamed(p, "z span", zspan * 1e-6)
        s.setnamed(p, "frequency dependent profile", ss.frequency_dependent_profile)
        s.setnamed(p, "number of field profile samples", ss.field_profile_samples)

        deg = int(port.orientation)
        # if port.orientation not in [0, 90, 180, 270]:
        #     raise ValueError(f"{port.orientation} needs to be [0, 90, 180, 270]")

        if -45 <= deg <= 45:
            direction = "Backward"
            injection_axis = "x-axis"
            dxp = 0
            dyp = 2 * ss.port_margin + port.width
        elif 45 < deg < 90 + 45:
            direction = "Backward"
            injection_axis = "y-axis"
            dxp = 2 * ss.port_margin + port.width
            dyp = 0
        elif 90 + 45 < deg < 180 + 45:
            direction = "Forward"
            injection_axis = "x-axis"
            dxp = 0
            dyp = 2 * ss.port_margin + port.width
        elif 180 + 45 < deg < 180 + 45 + 90:
            direction = "Forward"
            injection_axis = "y-axis"
            dxp = 2 * ss.port_margin + port.width
            dyp = 0

        else:
            raise ValueError(
                f"port {port.name!r} orientation {port.orientation} is not valid"
            )

        s.setnamed(p, "direction", direction)
        s.setnamed(p, "injection axis", injection_axis)
        s.setnamed(p, "y span", dyp * 1e-6)
        s.setnamed(p, "x span", dxp * 1e-6)
        # s.setnamed(p, "theta", deg)
        s.setnamed(p, "name", port.name)
        # s.setnamed(p, "name", f"o{i+1}")

        logger.info(
            f"port {p} {port.name!r}: at ({port.x}, {port.y}, 0)"
            f"size = ({dxp}, {dyp}, {zspan})"
        )

    s.setglobalsource("wavelength start", ss.wavelength_start * 1e-6)
    s.setglobalsource("wavelength stop", ss.wavelength_stop * 1e-6)
    s.setnamed("FDTD::ports", "monitor frequency points", ss.wavelength_points)

    if run:
        s.save(str(filepath_fsp))
        s.deletesweep("s-parameter sweep")

        s.addsweep(3)
        s.setsweep("s-parameter sweep", "Excite all ports", 0)
        s.setsweep("S sweep", "auto symmetry", True)
        s.runsweep("s-parameter sweep")
        sp = s.getsweepresult("s-parameter sweep", "S parameters")
        s.exportsweep("s-parameter sweep", str(filepath))
        logger.info(f"wrote sparameters to {str(filepath)!r}")

        sp["wavelengths"] = sp.pop("lambda").flatten() * 1e6
        np.savez_compressed(filepath, **sp)

        # keys = [key for key in sp.keys() if key.startswith("S")]
        # ra = {
        #     f"{key.lower()}a": list(np.unwrap(np.angle(sp[key].flatten())))
        #     for key in keys
        # }
        # rm = {f"{key.lower()}m": list(np.abs(sp[key].flatten())) for key in keys}
        # results = {"wavelengths": wavelengths}
        # results.update(ra)
        # results.update(rm)
        # df = pd.DataFrame(results, index=wavelengths)
        # df.to_csv(filepath_npz, index=False)

        end = time.time()
        sim_settings.update(compute_time_seconds=end - start)
        sim_settings.update(compute_time_minutes=(end - start) / 60)
        filepath_sim_settings.write_text(yaml.dump(sim_settings))
        if delete_fsp_files and fspdir.exists():
            shutil.rmtree(fspdir)
            logger.info(
                f"deleting simulation files in {str(fspdir)!r}. "
                "To keep them, use delete_fsp_files=False flag"
            )

        return sp

    filepath_sim_settings.write_text(yaml.dump(sim_settings))
    return s


def _sample_write_coupler_ring():
    """Write Sparameters when changing a component setting."""
    return [
        write_sparameters_lumerical(
            gf.components.coupler_ring(
                width=width, length_x=length_x, radius=radius, gap=gap
            )
        )
        for width in [0.5]
        for length_x in [0.1, 1, 2, 3, 4]
        for gap in [0.15, 0.2]
        for radius in [5, 10]
    ]


def _sample_bend_circular():
    """Write Sparameters for a circular bend with different radius."""
    return [
        write_sparameters_lumerical(gf.components.bend_circular(radius=radius))
        for radius in [2, 5, 10]
    ]


def _sample_bend_euler():
    """Write Sparameters for a euler bend with different radius."""
    return [
        write_sparameters_lumerical(gf.components.bend_euler(radius=radius))
        for radius in [2, 5, 10]
    ]


def _sample_convergence_mesh():
    return [
        write_sparameters_lumerical(
            component=gf.components.straight(length=2),
            mesh_accuracy=mesh_accuracy,
        )
        for mesh_accuracy in [1, 2, 3]
    ]


def _sample_convergence_wavelength():
    return [
        write_sparameters_lumerical(
            component=gf.components.straight(length=2),
            wavelength_start=wavelength_start,
        )
        for wavelength_start in [1.2, 1.4]
    ]


if __name__ == "__main__":
    import lumapi

    s = lumapi.FDTD()

    # component = gf.components.straight(length=2.5)
    component = gf.components.mmi1x2()

    material_name_to_lumerical = dict(si=(3.45, 2))  # or dict(si=3.45+2j)
    r = write_sparameters_lumerical(
        component=component,
        material_name_to_lumerical=material_name_to_lumerical,
        run=False,
        session=s,
    )
    # c = gf.components.coupler_ring(length_x=3)
    # c = gf.components.mmi1x2()
    # print(r)
    # print(r.keys())
    # print(component.ports.keys())
