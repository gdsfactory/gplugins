import importlib
import math
import pathlib
from pathlib import Path

import gdsfactory as gf
from gdsfactory.technology.processes import (
    Anneal,
    ArbitraryStep,
    Etch,
    Grow,
    ImplantPhysical,
    Lithography,
    Planarize,
)
from gdsfactory.typings import Dict, Tuple

from gplugins.gmsh.parse_gds import cleanup_component_layermap
from gplugins.sentaurus.mask_sprocess import (
    get_sentaurus_mask_2D,
    get_sentaurus_mask_3D,
)

DEFAULT_INIT_LINES = """AdvancedCalibration
mgoals accuracy=2e-5
"""

DEFAULT_PROCESS_REMESHING = """
pdbSet Grid Adaptive 1
pdbSet Grid AdaptiveField Refine.Rel.Error 1.25
"""

DEFAULT_DEVICE_REMESHING = """refinebox clear
line clear
pdbSet Grid Adaptive 1
pdbSet Grid AdaptiveField Refine.Abs.Error 1e37
pdbSet Grid AdaptiveField Refine.Rel.Error 1e10
pdbSet Grid AdaptiveField Refine.Target.Length 100.0
pdbSet Grid SnMesh DelaunayType boxmethod
"""

DEFAULT_CONTACT_STR = ""


def initialize_sprocess(
    component,
    waferstack,
    layermap,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None,
    u_offset: float = 0.0,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    initial_z_resolutions: Dict = None,
    initial_xy_resolution: float | None = None,
    extra_resolution_str: str | None = None,
):
    """Returns a string defining the geometry definition for a Sentaurus sprocess file based on a component, initial wafer state, and settings.

    Arguments:
        component,: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object containing all layers
        process: list of gdsfactory.technology.processes process steps
        xsection_bounds: two in-plane coordinates ((x1,y1), (x2,y2)) defining a line cut for a 2D process cross-section
        u_offset: for the x-axis of the 2D coordinate system, useful to go back to component units if xsection_bounds parallel to x or y
        round_tol (int): for gds cleanup (grid snapping by rounding coordinates)
        simplify_tol (float): for gds cleanup (shape simplification)
        initial_z_resolutions {key: float}: initial layername: spacing mapping for mesh resolution in the wafer normal direction
        initial_xy_resolution (float): initial resolution in the wafer plane
        extra_resolution_str (str): extra initial meshing commands
    """
    output_str = ""

    # Defaults
    initial_z_resolutions = initial_z_resolutions or {
        layername: 1e-2 for layername in waferstack.layers.keys()
    }
    initial_xy_resolution = initial_xy_resolution or 1

    extra_resolution_str = extra_resolution_str or ""

    # Parse 2D or 3D
    if xsection_bounds:
        get_mask = gf.partial(
            get_sentaurus_mask_2D, xsection_bounds=xsection_bounds, u_offset=u_offset
        )
    else:
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

    # Initial z-mesh from waferstack and resolutions
    z_map = {}
    for _i, (layername, layer) in enumerate(waferstack.layers.items()):
        resolution = initial_z_resolutions[layername]
        if f"{layer.zmin - layer.thickness:1.3f}" not in z_map:
            output_str += f"line x loc={layer.zmin - layer.thickness:1.3f}<um>   tag={layername}_top     spacing={resolution}<um>\n"
            z_map[f"{layer.zmin - layer.thickness:1.3f}"] = f"{layername}_top"
        if f"{layer.zmin:1.3f}" not in z_map:
            output_str += f"line x loc={layer.zmin:1.3f}<um>   tag={layername}_bot     spacing={resolution}<um>\n"
            z_map[f"{layer.zmin:1.3f}"] = f"{layername}_bot"

    # Initial xy-mesh from component bbox
    output_str += f"line y location={xmin:1.3f}   spacing={initial_xy_resolution} tag=left\nline y location={xmax:1.3f}   spacing={initial_xy_resolution} tag=right\n"
    xdims = "ylo=left yhi=right"
    if xsection_bounds:
        ydims = ""
    else:
        ydims = "zlo=front zhi=back"
        output_str += f"line z location={ymin:1.3f}   spacing={initial_xy_resolution} tag=front\nline z location={ymax:1.3f}   spacing={initial_xy_resolution} tag=back\n"

    # Additional resolution settings
    output_str += extra_resolution_str

    # Initialize with wafermap
    initializations = []
    # Regions
    for layername, layer in waferstack.layers.items():
        if layername == "substrate":
            extra_tag = "substrate"
        else:
            extra_tag = ""
        xlo = z_map[f"{layer.zmin - layer.thickness:1.3f}"]
        xhi = z_map[f"{layer.zmin:1.3f}"]
        output_str += (
            f"region {layer.material} xlo={xlo} xhi={xhi} {xdims} {ydims} {extra_tag}\n"
        )

        if layer.background_doping_concentration:
            initializations.append(
                f"init {layer.material} concentration={layer.background_doping_concentration:1.2e}<cm-3> field={layer.background_doping_ion} wafer.orient={layer.orientation}\n"
            )

        # # Adaptive remeshing in active regions
        # if "active" in layer.info and layer.info["active"]:
        #     output_str += "refinebox adaptive\n"
        #     output_str += f"refinebox min= {{{layer.zmin - layer.thickness:1.3f} {xmin} {ymin}}} max= {{{layer.zmin:1.3f} {xmax} {ymax}}} adaptive def.rel.error=1\n"

    # Materials
    for line in set(initializations):
        output_str += line

    return output_str, get_mask, layer_polygons_dict, xmin, xmax, ymin, ymax


def write_sprocess(
    component,
    waferstack,
    layermap,
    process,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None,
    u_offset: float = 0.0,
    init_tdr: str | None = None,
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
    filename: str = "sprocess_fps.cmd",
    struct_prefix: str = "struct_",
    structout: str | None = None,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    split_steps: bool = True,
    init_lines: str = DEFAULT_INIT_LINES,
    initial_z_resolutions: Dict = None,
    initial_xy_resolution: float | None = None,
    extra_resolution_str: str | None = None,
    global_process_remeshing_str: str = DEFAULT_PROCESS_REMESHING,
    global_device_remeshing_str: str = DEFAULT_DEVICE_REMESHING,
    num_threads: int = 6,
    contact_str: str = DEFAULT_CONTACT_STR,
    device_remesh: bool = True,
) -> None:
    """Writes a Sentaurus Process TLC file for the component + layermap + initial waferstack + process.

    The meshing strategy is to initially use a fixed grid defined by initial_z_resolutions and initial_xy_resolution, and use default adaptive refinement on all fields in regions defined as "active", followed by adaptive refinement on net active dopants in "active" regions.

    Note that Sentaurus uses the X-direction vertically, with more positive X values going "deeper" in the substrate. YZ-coordinates are in the plane. GDSFactory uses XY in the plane and Z vertically, with more positive Z going "up" away from the substrate.

    If init_str is given, will initialize the simulation from that file. Otherwise, will setup the simulation according to initialize_sprocess.

    Arguments:
        component,: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object containing all layers
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
    gf_version = importlib.metadata.version("gdsfactory")
    if int(gf_version.split(".")[0]) >= 8:
        raise ImportError(
            "The Sentaurus Process plugin is not compatible with gdsfactory version 8 or above."
        )

    save_directory = (
        Path("./sprocess/") if save_directory is None else Path(save_directory)
    )
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )
    structout = structout or component.name + ".tdr"

    relative_save_directory = save_directory.relative_to(execution_directory)
    if init_tdr is not None:
        relative_tdr_file = init_tdr.relative_to(execution_directory)

    # Setup TCL file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    with open(out_file, "a") as f:
        # Header
        f.write(f"{init_lines}\n")

        # Parallelization
        f.write(f"math numThreads={num_threads}\n")

        # Initial simulation state
        (
            output_str,
            get_mask,
            layer_polygons_dict,
            xmin,
            xmax,
            ymin,
            ymax,
        ) = initialize_sprocess(
            component=component,
            waferstack=waferstack,
            layermap=layermap,
            xsection_bounds=xsection_bounds,
            round_tol=round_tol,
            simplify_tol=simplify_tol,
            initial_z_resolutions=initial_z_resolutions,
            initial_xy_resolution=initial_xy_resolution,
            extra_resolution_str=extra_resolution_str,
            u_offset=u_offset,
        )
        if init_tdr:
            f.write(f"init tdr= {relative_tdr_file!s}")
        else:
            f.write(str(output_str))
            if split_steps:
                f.write(
                    f"struct tdr={relative_save_directory!s}/{struct_prefix}0_wafer.tdr\n"
                )

        # Global remeshing strategy
        f.write(global_process_remeshing_str)

        # Process
        for i, step in enumerate(process):
            f.write("\n")

            if split_steps:
                f.write(f"#split {step.name}\n")

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
                        positive_tone=step.positive_tone,
                    )
                    if not exists:
                        continue
                    f.writelines(mask_lines)
                    f.write(
                        f"photo mask={step.name} thickness={step.resist_thickness}<um>\n"
                    )
                    if step.planarization_height:
                        f.write(
                            f"transform cut up location=-{step.planarization_height:1.3f}<um>\n"
                        )
                    if split_steps:
                        f.write(
                            f"struct tdr={relative_save_directory!s}/{struct_prefix}{i + 1}_{step.name}_litho.tdr\n"
                        )

            if isinstance(step, Etch):
                f.write(
                    f"etch {step.material} thickness={step.depth}<um> type={step.type}\n"
                )

            if isinstance(step, Grow):
                f.write(
                    f"deposit {step.material} thickness={step.thickness}<um> type={step.type}\n"
                )

            if isinstance(step, ImplantPhysical):
                extra_implant = ""
                if step.twist:
                    extra_implant += f"rotation={step.twist}<degree> "
                elif step.rotation:
                    extra_implant += "mult.rot=4 "
                if step.tilt:
                    extra_implant += f"tilt={step.tilt}<degree> "
                f.write(
                    f"implant {step.ion} dose={step.dose:1.3e}<cm-2> energy={step.energy}<keV> {extra_implant}\n"
                )

            if isinstance(step, Lithography):
                if step.layer:
                    f.write("strip Resist\n")

            if isinstance(step, Anneal):
                f.write(f"diffuse temp={step.temperature}<C> time={step.time}<s>\n")

            if isinstance(step, Planarize):
                f.write(f"transform cut up location=-{step.height:1.3f}<um>\n")

            if isinstance(step, ArbitraryStep):
                f.write(step.info)
                f.write("\n")

            if split_steps:
                f.write(
                    f"struct tdr={relative_save_directory!s}/{struct_prefix}{i + 1}_{step.name}.tdr"
                )

            f.write("\n")

        # Remeshing options
        if device_remesh:
            f.write("\n")
            if split_steps:
                f.write("#split remeshing\n")
            f.write(global_device_remeshing_str)

            for layer in waferstack.layers.values():
                if layer.info and layer.info["active"] is True:
                    f.write(
                        f"""refinebox name= Global min= {{ {layer.zmin - layer.thickness:1.3f} {xmin} {ymin} }} max= {{ {layer.zmin:1.3f} {xmax} {ymax} }} refine.min.edge= {{ 0.0005 0.0005 0.0005 }} refine.max.edge= {{ 0.01 0.01 0.01 }}  refine.fields= {{ NetActive }} def.max.asinhdiff= 0.5 adaptive {layer.material}
    """
                    )
            f.write("grid remesh\n")

        # Manual for now
        f.write(contact_str)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={relative_save_directory!s}/{structout}")


def write_add_contacts_to_tdr(
    struct_in: str = "/struct_out_fps.tdr",
    struct_out: str = "struct_out_contacts_fps.tdr",
    contact_str: str | None = None,
    filename: str = "sprocess_contacts.cmd",
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
) -> None:
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
        f.write(f"init tdr= {relative_input_tdr_file!s}")
        f.write("\n")

        # Manual for now
        f.write(contact_str)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={relative_output_tdr_file!s}")


def write_generic_sprocess_tdr(
    struct_in: str = "/struct_out_fps.tdr",
    struct_out: str = "struct_out_contacts_fps.tdr",
    lines: str | None = None,
    filename: str = "sprocess_contacts.cmd",
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
) -> None:
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
        f.write(f"init tdr= {relative_input_tdr_file!s}")
        f.write("\n")

        # Manual for now
        f.write(lines)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={relative_output_tdr_file!s}")


def write_extrude_combine_tdrs(
    structs_in: str = "/struct_out_fps.tdr",
    extrusions: Tuple[float] = (0,),
    struct_out: str = "struct_out_fps.tdr",
    contact_str: str | None = None,
    remesh_str: str | None = None,
    filename: str = "sprocess_contacts.cmd",
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
) -> None:
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

        # Manual for now
        f.write(contact_str)

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={relative_output_tdr_file!s}")


def cut_tdr(
    struct_in: str = "/struct_in_fps.tdr",
    struct_out: str = "struct_out_fps.tdr",
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    filename: str = "sprocess_cut.cmd",
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
    global_device_remeshing_str: str = DEFAULT_DEVICE_REMESHING,
) -> None:
    # Fix paths
    save_directory = Path("./") if save_directory is None else Path(save_directory)
    execution_directory = (
        Path("./") if execution_directory is None else Path(execution_directory)
    )

    save_directory.relative_to(execution_directory)

    struct_in.relative_to(execution_directory)
    relative_output_tdr_file = struct_out.relative_to(execution_directory)
    # Setup TCL file
    out_file = pathlib.Path(save_directory / filename)
    save_directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    with open(out_file, "a") as f:
        # Load and extrude first tdr file
        tdr_file = str(struct_in)
        f.write(f"init tdr= {tdr_file}\n")

        slice_str = f"struct tdr= {relative_output_tdr_file!s}"
        # Perform coordinate change too
        if x is not None:
            slice_str += " z= {x}"
        if y is not None:
            slice_str += " y= {y}"
        if z is not None:
            slice_str += " x= -{z}"
        f.write(slice_str)

        # Remeshing instructions
        f.write(f"init tdr= {relative_output_tdr_file!s}\n")

        f.write(global_device_remeshing_str)

        f.write(
            """refinebox name= Global refine.min.edge= {0.0005 0.0005 0.0005} refine.max.edge= {0.1 0.1 0.1}  refine.fields= {NetActive} def.max.asinhdiff= 0.5 adaptive Silicon
grid remesh
struct tdr= pn_test_msh_zcut_remeshed
"""
        )


if __name__ == "__main__":
    from gdsfactory.components import straight_pn
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.generic_tech.layer_stack import WAFER_STACK, get_process

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

    test_component = c << gf.functions.trim(
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
    WAFER_STACK = WAFER_STACK.z_offset(-1 * 0.22).invert_zaxis()

    write_sprocess(
        component=c,
        waferstack=WAFER_STACK,
        layermap=LAYER,
        process=get_process(),
        save_directory="./sprocess_3D/",
        filename="sprocess_3D_fps.cmd",
        initial_z_resolutions={"core": 0.005, "box": 0.05, "substrate": 0.5},
        initial_xy_resolution=0.05,
        split_steps=True,
    )

    contact_str = f"""contact name=cathode aluminum silicon xlo=0.0 xhi=0.2 ylo=0.0 yhi=1 zlo=0 zhi=0
contact name=anode aluminum silicon xlo=0.0 xhi=0.2 ylo={c.ysize - 1:1.3f} yhi={c.ysize:1.3f} zlo=0 zhi=0
contact name=substrate box silicon xlo=4.2 xhi=4.3 ylo=0.0 yhi={c.ysize:1.3f} zlo=0 zhi=0
    """

    write_sprocess(
        component=c,
        waferstack=WAFER_STACK,
        layermap=LAYER,
        process=get_process(),
        xsection_bounds=(
            ((test_component.xmin + test_component.xmax) / 2, test_component.ymin),
            ((test_component.xmin + test_component.xmax) / 2, test_component.ymax),
        ),
        save_directory="./sprocess/",
        filename="sprocess_2D_fps.cmd",
        initial_z_resolutions={"core": 0.005, "box": 0.05, "substrate": 0.5},
        initial_xy_resolution=0.05,
        split_steps=True,
        contact_str=contact_str,
    )
