import math
import pathlib
from pathlib import Path

import gdsfactory as gf
from gdsfactory.technology.processes import (
    Anneal,
    ArbitraryStep,
    Etch,
    Grow,
    ImplantGaussian,
    Lithography,
    Planarize,
)
from gdsfactory.typings import Tuple

from gplugins.gmsh.parse_gds import cleanup_component_layermap
from gplugins.sentaurus.mask_sde import get_sentaurus_mask_3D

DEFAULT_HEADER = """(sde:clear)
(sde:set-process-up-direction "+z")
"""

REMESH_STR = """(sdedr:define-refinement-size \"RefDef.BG\" 1.0 1.0 1.0 0.01 0.01 0.001)
(sdedr:define-refinement-function \"RefDef.BG\" \"DopingConcentration\" \"MaxTransDiff\" 1)\n"""


def initialize_sde(
    component,
    waferstack,
    layermap,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]] = None,
    u_offset: float = 0.0,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
):
    """Returns a string defining the geometry definition for a Sentaurus sde file based on a component, initial wafer state, and settings.

    Arguments:
        component,: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object contaning all layers
        process: list of gdsfactory.technology.processes process steps
        xsection_bounds: two in-plane coordinates ((x1,y1), (x2,y2)) defining a line cut for a 2D process cross-section
        u_offset: for the x-axis of the 2D coordinate system, useful to go back to component units if xsection_bounds parallel to x or y
        round_tol (int): for gds cleanup (grid snapping by rounding coordinates)
        simplify_tol (float): for gds cleanup (shape simplification)
    """

    output_str = ""

    get_mask = gf.partial(get_sentaurus_mask_3D)

    # Cleanup gds polygons
    layer_polygons_dict = cleanup_component_layermap(
        component, layermap, round_tol, simplify_tol
    )

    # Get simulation bounds
    if xsection_bounds:
        xmin = u_offset
        xmax = math.dist(xsection_bounds[0], xsection_bounds[1]) + u_offset
        ymin = 0
        ymax = 0
    else:
        xmin = component.xmin
        xmax = component.xmax
        ymin = component.ymin
        ymax = component.ymax

    # Initialize
    output_str += "(sde:clear)\n"

    # Initial z-mesh from waferstack and resolutions
    output_str += f"(sdepe:define-pe-domain {xmin} {ymin} {xmax} {ymax})\n"

    # Regions
    regions = []
    layer = waferstack.layers["substrate"]
    regions.append(f"substrate_{layer.material}")
    output_str += f'(sdepe:add-substrate "material" "{layer.material}" "thickness" {layer.thickness} "base" {layer.zmin:1.3f})\n'

    for layername, layer in sorted(waferstack.layers.items(), key=lambda x: x[1].zmin):
        if layername == "substrate":
            continue
        else:
            regions.append(f"{layername}_{layer.material}")
            output_str += f'(sdepe:depo "material" "{layer.material}" "thickness" {layer.thickness})\n'

    return output_str, get_mask, layer_polygons_dict, xmin, xmax, ymin, ymax, regions


def write_sde(
    component,
    waferstack,
    layermap,
    process,
    init_tdr: str = None,
    save_directory: Path = None,
    execution_directory: Path = None,
    filename: str = "sprocess_fps.cmd",
    fileout: str | None = None,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    device_remesh: bool = True,
    remesh_str: str = REMESH_STR,
):
    """Writes a Sentaurus Device Editor Scheme file for the component + layermap + initial waferstack + process.

    Arguments:
        component,: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object contaning all layers
        process: list of gdsfactory.technology.processes process steps
        xsection_bounds: two in-plane coordinates ((x1,y1), (x2,y2)) defining a line cut for a 2D process cross-section. If None, simulate in 3D.
        u_offset: offset for lateral dimension of xsection mesh
        save_directory: directory where to save output and script. Default ./sprocess
        execution_directory: directory where sprocess will be run from. Default local ./
        filename: name of the final sprocess command file
        struct_prefix: prefixes of the final sprocess command file
        structout: tdr file containing the final structure, ready for sdevice simulation. Defaults to component name.
        contact_portnames Tuple(str): list of portnames to convert into device contacts
        round_tol (int): for gds cleanup (grid snapping by rounding coordinates)
        simplify_tol (float): for gds cleanup (shape simplification)
        split_steps (bool): if True, creates a new workbench node for each step, and saves a TDR file at each step. Useful for fabrication splits, visualization, and debugging.
        init_lines (str): initial string to write to the TCL file. Useful for settings
        initial_z_resolutions {key: float}: initial layername: spacing mapping for mesh resolution in the wafer normal direction
        initial_xy_resolution (float): initial resolution in the wafer plane
        global_device_remeshing_str (str): commands to apply before remeshing
        num_threads (int): for parallelization
    """

    save_directory = Path("./sde/") if save_directory is None else Path(save_directory)
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )
    fileout = fileout or component.name

    save_directory.relative_to(execution_directory)
    if init_tdr is not None:
        init_tdr.relative_to(execution_directory)

    # Setup Scheme file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    with open(out_file, "a") as f:
        # Initial simulation state
        (
            output_str,
            get_mask,
            layer_polygons_dict,
            xmin,
            xmax,
            ymin,
            ymax,
            regions,
        ) = initialize_sde(
            component=component,
            waferstack=waferstack,
            layermap=layermap,
            round_tol=round_tol,
            simplify_tol=simplify_tol,
        )
        f.write(str(output_str))

        # Process
        for _i, step in enumerate(process):
            f.write("\n")

            # device editor syntax
            if hasattr(step, "type"):
                if step.type == "anisotropic":
                    type = "aniso"
                elif step.type == "isotropic":
                    type = "iso"

            if isinstance(step, Lithography):
                if step.layer:
                    mask_lines, exists = get_mask(
                        layer_polygons_dict=layer_polygons_dict,
                        name=step.name,
                        layer=step.layer,
                        layers_or=step.layers_or,
                        layers_diff=step.layers_diff,
                        layers_and=step.layers_and,
                        layers_xor=step.layers_xor,
                    )
                    if not exists:
                        continue
                    f.writelines(mask_lines)

                    polarity = "dark" if step.positive_tone else "light"
                    f.write(
                        f'(sdepe:pattern "mask" "{step.name}" "polarity" "{polarity}" "material"  "Resist" "thickness" {step.resist_thickness} "type" "iso")\n'
                    )

            if isinstance(step, Etch):
                f.write(
                    f'(sdepe:etch-material "material" "{step.material}" "depth" {step.depth} "type" "{type}")\n'
                )

            if isinstance(step, Grow):
                regions.append(f"{step.name}_{step.material}")
                f.write(
                    f'(sdepe:depo "material" "{step.material}" "thickness" {step.thickness} "type" "{type}" "region" "{step.material}")\n'
                )

            if isinstance(step, ImplantGaussian):
                if step.ion == "phosphorus":
                    species = "PhosphorusActiveConcentration"
                elif step.ion == "boron":
                    species = "BoronActiveConcentration"
                f.write(
                    f'(sdedr:define-gaussian-profile "{step.name}" "{species}" "PeakPos" {step.range} "PeakVal" {step.peak_conc} "Length" {step.vertical_straggle} "Gauss" "StdDev" {step.lateral_straggle})\n'
                )
                f.write(f'(sdepe:implant "{step.name}" "flat")\n')

            if isinstance(step, Lithography):
                if step.layer:
                    f.write('(sdepe:remove "material" "Resist")\n')

            if isinstance(step, Planarize):
                f.write(f'(sdepe:polish-device "thickness" {step.height:1.3f})\n')

            if isinstance(step, ArbitraryStep):
                f.write(step.info)
                f.write("\n")

        # Remeshing options
        if device_remesh:
            f.write(remesh_str)
            for region in regions:
                if "silicon" in region:
                    f.write(
                        f'(sdedr:define-refinement-region "{region}" "RefDef.BG" "{region}")\n'
                    )

        # Save structure and build mesh
        f.write(f'(sde:save-model "{fileout}")\n')
        f.write(f'(sde:build-mesh "" "{fileout}")')
        f.write("\n")


def write_add_contacts_to_tdr(
    struct_in: str = "/struct_out_fps.tdr",
    struct_out: str = "struct_out_contacts_fps.tdr",
    contact_str: str = None,
    filename: str = "sprocess_contacts.cmd",
    save_directory: Path = None,
    execution_directory: Path = None,
):
    """Add contacts to tdr file, and (optionally) remesh.

    Arguments:
    struct_in: filepath of the struct to modify
    struct_out: filepath of the output struct
    remesh_str: dict containing information of remeshing to add
    contacts_str: dict containing information of contact to add
    """
    # Fix paths
    save_directory = Path("./") if save_directory is None else Path(save_directory)
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )

    save_directory.relative_to(execution_directory)

    relative_input_tdr_file = struct_in.relative_to(execution_directory)
    relative_output_tdr_file = struct_out.relative_to(execution_directory)

    # Setup TCL file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    # Load TDR file
    with open(out_file, "a") as f:
        f.write(f"init tdr= {str(relative_input_tdr_file)}")
        f.write("\n")

        # Manual for now
        f.write(contact_str)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={str(relative_output_tdr_file)}")


def write_generic_sprocess_tdr(
    struct_in: str = "/struct_out_fps.tdr",
    struct_out: str = "struct_out_contacts_fps.tdr",
    lines: str = None,
    filename: str = "sprocess_contacts.cmd",
    save_directory: Path = None,
    execution_directory: Path = None,
):
    """Loads struct_in, add scripts lines, and outputs struct_out."""
    # Fix paths
    save_directory = Path("./") if save_directory is None else Path(save_directory)
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )

    save_directory.relative_to(execution_directory)

    relative_input_tdr_file = struct_in.relative_to(execution_directory)
    relative_output_tdr_file = struct_out.relative_to(execution_directory)

    # Setup TCL file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    # Load TDR file
    with open(out_file, "a") as f:
        f.write(f"init tdr= {str(relative_input_tdr_file)}")
        f.write("\n")

        # Manual for now
        f.write(lines)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={str(relative_output_tdr_file)}")


def write_extrude_combine_tdrs(
    structs_in: str = "/struct_out_fps.tdr",
    extrusions: Tuple[float] = (0,),
    struct_out: str = "struct_out_fps.tdr",
    contact_str: str = None,
    remesh_str: str = None,
    filename: str = "sprocess_contacts.cmd",
    save_directory: Path = None,
    execution_directory: Path = None,
):
    """Extrude the 2D structs_in according to extrusions, paste the structs sequentially into one tdr, add contacts, and remesh.

    Arguments:
    structs_in: list of filepath of the structs to combine (in order, left to right)
    struct_out: filepath of the output struct
    extrusions: list of extrusion lengths for structs_in that are 2D
    contact_str: str to add contacts
    remesh_str: str to remesh
    """
    # Fix paths
    save_directory = Path("./") if save_directory is None else Path(save_directory)
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )

    save_directory.relative_to(execution_directory)

    structs_in.relative_to(execution_directory)
    relative_output_tdr_file = struct_out.relative_to(execution_directory)

    # Setup TCL file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    with open(out_file, "a") as f:
        # Load and extrude first tdr file
        tdr_file = str(structs_in[0])
        f.write(f"init tdr= {tdr_file}\n")
        f.write(f"init tdr= {tdr_file}\n")

        # Manual for now
        f.write(contact_str)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={str(relative_output_tdr_file)}")


if __name__ == "__main__":
    from gdsfactory.components import straight_pn
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.generic_tech.layer_stack import WAFER_STACK

    # Create a component with the right contacts
    c = gf.Component(name="test_pn")

    length = 3

    test_straight = straight_pn(length=length, taper=None).extract(
        [
            LAYER.WG,
            LAYER.SLAB90,
            LAYER.N,
            LAYER.P,
            LAYER.NP,
            LAYER.PP,
            LAYER.NPP,
            LAYER.PPP,
            LAYER.VIAC,
        ]
    )

    test_component = c << gf.geometry.trim(
        component=test_straight, domain=[[0, -4], [0, 4], [length, 4], [length, -4]]
    )

    yp = (test_component.ymax + test_component.ymin) / 2 + test_component.ysize / 2
    ym = (test_component.ymax + test_component.ymin) / 2 - test_component.ysize / 2
    c.add_port(
        name="e1",
        center=(length / 2, yp),
        width=test_component.ysize / 2,
        orientation=0,
        layer=LAYER.VIAC,
    )
    c.add_port(
        name="e2",
        center=(length / 2, ym),
        width=test_component.ysize / 2,
        orientation=0,
        layer=LAYER.VIAC,
    )

    WAFER_STACK.layers["substrate"].material = "silicon"
    WAFER_STACK.layers["substrate"].thickness = 1
    WAFER_STACK.layers["substrate"].zmin = WAFER_STACK.layers["box"].zmin - 1
    WAFER_STACK.layers["box"].material = "Oxide"
    WAFER_STACK.layers["core"].material = "silicon"

    #  initialize_sde(component=c,
    #                 waferstack=WAFER_STACK,
    #                 layermap=LAYER,
    #                 xsection_bounds = None,
    #                )

    # Tweak process
    from gdsfactory.generic_tech.layer_stack import LayerStackParameters
    from gdsfactory.technology.processes import ProcessStep

    def get_process() -> tuple[ProcessStep]:
        """Returns generic process to generate LayerStack.

        Represents processing steps that will result in the GenericLayerStack, starting from the waferstack LayerStack.

        based on paper https://www.degruyter.com/document/doi/10.1515/nanoph-2013-0034/html
        """

        return (
            Etch(
                name="strip_etch",
                layer=LAYER.WG,
                layers_or=[LAYER.SLAB90],
                depth=LayerStackParameters.thickness_wg
                + 0.01,  # slight overetch for numerics
                material="silicon",
                resist_thickness=1.0,
                positive_tone=False,
            ),
            Etch(
                name="slab_etch",
                layer=LAYER.SLAB90,
                layers_diff=[LAYER.WG],
                depth=LayerStackParameters.thickness_wg
                - LayerStackParameters.thickness_slab_deep_etch,
                material="silicon",
                resist_thickness=1.0,
            ),
            # See gplugins.process.implant tables for ballpark numbers
            # Adjust to your process
            ImplantGaussian(
                name="n_implant",
                layer=LAYER.N,
                ion="phosphorus",
                peak_conc=1e17,
                range=0.1,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="p_implant",
                layer=LAYER.P,
                ion="boron",
                peak_conc=1e17,
                range=0.1,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="pp_implant",
                layer=LAYER.PP,
                ion="boron",
                peak_conc=1e18,
                range=0.1,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="np_implant",
                layer=LAYER.NP,
                ion="phosphorus",
                peak_conc=1e18,
                range=0.1,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="ppp_implant",
                layer=LAYER.PPP,
                ion="boron",
                peak_conc=1e19,
                range=0.1,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="npp_implant",
                layer=LAYER.NPP,
                ion="phosphorus",
                peak_conc=1e19,
                range=0.1,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            # "Temperatures of ~1000C for not more than a few seconds"
            # Adjust to your process
            # https://en.wikipedia.org/wiki/Rapid_thermal_processing
            Anneal(
                name="dopant_activation",
                time=5,
                temperature=1000,
            ),
            Grow(
                name="viac_metallization",
                layer=None,
                thickness=LayerStackParameters.zmin_metal1
                - LayerStackParameters.thickness_slab_deep_etch,
                material="Aluminum",
                type="anisotropic",
            ),
            Etch(
                name="viac_etch",
                layer=LAYER.VIAC,
                depth=LayerStackParameters.zmin_metal1
                - LayerStackParameters.thickness_slab_deep_etch
                + 0.1,
                material="Aluminum",
                type="anisotropic",
                resist_thickness=1.0,
                positive_tone=False,
            ),
            Grow(
                name="deposit_cladding",
                layer=None,
                thickness=LayerStackParameters.thickness_clad
                + LayerStackParameters.thickness_slab_deep_etch,
                material="Oxide",
                type="anisotropic",
            ),
            Planarize(
                name="planarization",
                height=LayerStackParameters.thickness_clad
                - LayerStackParameters.thickness_slab_deep_etch,
            ),
        )

    write_sde(
        component=c,
        waferstack=WAFER_STACK,
        layermap=LAYER,
        process=get_process(),
        save_directory="./sde/",
        filename="sde.scm",
    )
