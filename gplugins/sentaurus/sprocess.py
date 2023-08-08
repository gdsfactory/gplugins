import math
import pathlib
from pathlib import Path

import gdsfactory as gf
from gdsfactory.technology.processes import (
    Anneal,
    Etch,
    Grow,
    ImplantPhysical,
    Lithography,
    Planarize,
)
from gdsfactory.typings import Dict, Tuple
from parse_gds import cleanup_component_layermap

from gplugins.sentaurus.mask import get_sentaurus_mask_2D, get_sentaurus_mask_3D

DEFAULT_INIT_LINES = """AdvancedCalibration
mgoals min.normal.size=0.005 normal.growth.ratio=1.618 accuracy=2e-5 minedge=5e-5
"""

DEFAULT_REMESHING_STRATEGY = """refinebox clear
line clear
pdbSet Grid Adaptive 1
pdbSet Grid AdaptiveField Refine.Abs.Error 1e37
pdbSet Grid AdaptiveField Refine.Rel.Error 1e10
pdbSet Grid AdaptiveField Refine.Target.Length 100.0
pdbSet Grid SnMesh DelaunayType boxmethod
"""


def write_sprocess(
    component,
    waferstack,
    layermap,
    process,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]] = None,
    directory: Path = None,
    filename: str = "sprocess_fps.cmd",
    struct_prefix: str = "struct_",
    structout: str = "struct_out.tdr",
    contact_portnames: Tuple[str] = None,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    split_steps: bool = True,
    init_lines: str = DEFAULT_INIT_LINES,
    initial_z_resolutions: Dict = None,
    initial_xy_resolution: float = None,
    remeshing_strategy: str = DEFAULT_REMESHING_STRATEGY,
):
    """Writes a Sentaurus Process TLC file for the component + layermap + initial waferstack + process.

    Uses polygons of the electrical ports for contact definition (using port layer).

    The meshing strategy is to use a coarse-ish grid for the implants and diffusion, and perform a final adaptive remeshing on the net dopant concentration in LayerLevels tagged as "active". As it is difficult to make an automated decision on the meshing strategy, the user is encouraged to manually edit this function as needed.

    Note that Sentaurus uses the X-direction vertically, with more positive X values going "deeper" in the substrate. YZ-coordinates are in the plane. GDSFactory uses XY in the plane and Z vertically, with more positive Z going "up" away from the substrate.

    Since Sentaurus only supports box-type contacts, the bounding box of port polygons (from component_with_net_layers) are used to define contacts.

    Arguments:
        component: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object contaning all layers
        filepath: Path to the TLC file to be written.
        round_tol: for gds cleanup (grid snapping by rounding coordinates)
        simplify_tol: for gds cleanup (shape simplification)
        split_steps: if True, creates a new workbench node for each step. Useful for visualization and sweeps.
        init_lines (str): initial string to write to the TCL file. Useful for settings.

        component,: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object contaning all layers
        process:
        xsection_bounds: two in-plane coordinates ((x1,y1), (x2,y2)) defining a line cut for a 2D process cross-section
        directory: directory to save all output in
        filename: name of the final sprocess command file
        struct_prefix: prefixes of the final sprocess command file
        structout: tdr file containing the final structure, ready for sdevice simulation
        contact_portnames Tuple(str): list of portnames to convert into device contacts
        round_tol (int): for gds cleanup (grid snapping by rounding coordinates)
        simplify_tol (float): for gds cleanup (shape simplification)
        split_steps (bool): if True, creates a new workbench node for each step, and saves a TDR file at each step. Useful for fabrication splits, visualization, and debugging.
        init_lines (str): initial string to write to the TCL file. Useful for settings
        initial_z_resolutions {key: float}: initial layername: spacing mapping for mesh resolution in the wafer normal direction
        initial_xy_resolution (float): initial resolution in the wafer plane
        remeshing_strategy (str): commands to apply before remeshing
    """

    directory = Path(directory) or Path("./sprocess/")

    if contact_portnames:
        component = waferstack.get_component_with_net_layers(
            component,
            portnames=contact_portnames,
            add_to_layerstack=False,
            delimiter="#",
        )

    # Defaults
    initial_z_resolutions = initial_z_resolutions or {
        layername: 1e-2 for layername in waferstack.layers.keys()
    }
    initial_xy_resolution = initial_xy_resolution or 1

    # Parse 2D or 3D
    if xsection_bounds:
        get_mask = gf.partial(get_sentaurus_mask_2D, xsection_bounds=xsection_bounds)
    else:
        get_mask = gf.partial(get_sentaurus_mask_3D)

    # Cleanup gds polygons
    layer_polygons_dict = cleanup_component_layermap(
        component, layermap, round_tol, simplify_tol
    )

    # Get simulation bounds
    if xsection_bounds:
        xmin = 0
        xmax = math.dist(xsection_bounds[0], xsection_bounds[1])
        ymin = 0
        ymax = 0
    else:
        xmin = component.xmin
        xmax = component.xmax
        ymin = component.ymin
        ymax = component.ymax

    # Setup TCL file
    out_file = pathlib.Path(directory / filename)
    directory.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    with open(out_file, "a") as f:
        # Header
        f.write(f"{init_lines}\n")

        # Initial z-mesh from waferstack and resolutions
        z_map = {}
        for _i, (layername, layer) in enumerate(waferstack.layers.items()):
            resolution = initial_z_resolutions[layername]
            if f"{layer.zmin - layer.thickness:1.3f}" not in z_map:
                f.write(
                    f"line x loc={layer.zmin - layer.thickness:1.3f}<um>   tag={layername}_top     spacing={resolution}<um>\n"
                )
                z_map[f"{layer.zmin - layer.thickness:1.3f}"] = f"{layername}_top"
            if f"{layer.zmin:1.3f}" not in z_map:
                f.write(
                    f"line x loc={layer.zmin:1.3f}<um>   tag={layername}_bot     spacing={resolution}<um>\n"
                )
                z_map[f"{layer.zmin:1.3f}"] = f"{layername}_bot"

        # Initial xy-mesh from component bbox
        f.write(
            f"""line y location={xmin:1.3f}   spacing={initial_xy_resolution} tag=left
line y location={xmax:1.3f}   spacing={initial_xy_resolution} tag=right
"""
        )
        xdims = "ylo=left yhi=right"
        if xsection_bounds:
            ydims = ""
        else:
            ydims = "zlo=front zhi=back"
            f.write(
                f"""
line z location={ymin:1.3f}   spacing={initial_xy_resolution} tag=front
line z location={ymax:1.3f}   spacing={initial_xy_resolution} tag=back
"""
            )

        # Initialize with wafermap
        for _layername, layer in waferstack.layers.items():
            xlo = z_map[f"{layer.zmin - layer.thickness:1.3f}"]
            xhi = z_map[f"{layer.zmin:1.3f}"]
            f.write(f"region {layer.material} xlo={xlo} xhi={xhi} {xdims} {ydims}\n")
            if layer.background_doping_concentration:
                f.write(
                    f"init {layer.material} concentration={layer.background_doping_concentration:1.2e}<cm-3> field={layer.background_doping_ion} wafer.orient={layer.orientation}\n"
                )

        if split_steps:
            f.write(f"struct tdr={struct_prefix}0_wafer.tdr")

        for i, step in enumerate(process):
            f.write("\n")

            if split_steps:
                f.write(f"#split {step.name}\n")

            if isinstance(step, Lithography):
                if step.layer:
                    mask_lines = get_mask(
                        layer_polygons_dict=layer_polygons_dict,
                        name=step.name,
                        layer=step.layer,
                        layers_or=step.layers_or,
                        layers_diff=step.layers_diff,
                        layers_and=step.layers_and,
                        layers_xor=step.layers_xor,
                        positive_tone=step.positive_tone,
                    )
                    f.writelines(mask_lines)
                    f.write(
                        f"photo mask={step.name} thickness={step.resist_thickness}<um>\n"
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
                f.write(
                    f"implant {step.ion} dose={step.dose:1.3e}<cm-2> energy={step.energy}<keV> tilt={step.tilt}\n"
                )

            if isinstance(step, Lithography):
                if step.layer:
                    f.write("strip Resist\n")

            if isinstance(step, Anneal):
                f.write(f"diffuse temp={step.temperature}<C> time={step.time}<s>\n")

            if isinstance(step, Planarize):
                f.write(f"transform cut up location=-{step.height}<um>\n")

            if split_steps:
                f.write(f"struct tdr={struct_prefix}{i+1}_{step.name}.tdr")

            f.write("\n")

        # Remeshing options
        f.write("\n")
        if split_steps:
            f.write("#split remeshing\n")
        f.write(remeshing_strategy)

        for _layername, layer in waferstack.layers.items():
            if layer.info and layer.info["active"] is True:
                f.write(
                    f"""refinebox name= Global min= {{ {layer.zmin - layer.thickness:1.3f} {xmin} {ymin} }} max= {{ {layer.zmin:1.3f} {xmax} {ymax} }} refine.min.edge= {{ 0.001 0.001 0.001 }} refine.max.edge= {{ 0.1 0.1 0.1 }} refine.fields= {{ NetActive }} def.max.asinhdiff= 0.5 adaptive {layer.material}
"""
                )
        f.write("grid remesh\n")

        # Tag contacts
        # if contact_portnames:
        #     for contact_name in contact_portnames:
        #         port = component.ports[contact_name]
        #         if xsection_bounds:
        #             for polygon in component.extract(
        #                 f"{port.layer}#{contact_name}"
        #             ).get_polygons:
        #                 print(polygon)

        # Manual for now
        f.write("\n")
        f.write("#split Contacts\n")
        f.write(
            f"contact name=e1 box silicon adjacent.material=Aluminum xlo=0.12 xhi=0.14 ylo={xmin} yhi={(xmin + xmax)/2} zlo={ymin} zhi={ymax}\n"
        )
        f.write(
            f"contact name=e2 box silicon adjacent.material=Aluminum xlo=0.12 xhi=0.14 ylo={(xmin + xmax)/2} yhi={xmax} zlo={ymin} zhi={ymax}\n"
        )

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={structout}")


if __name__ == "__main__":
    from gdsfactory.components import straight_pn
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.generic_tech.layer_stack import WAFER_STACK, get_process

    # Create a component with the right contacts
    c = gf.Component()

    length = 3

    test_straight = straight_pn(length=length, taper=None).extract(
        [
            LAYER.WG,
            LAYER.SLAB90,
            LAYER.N,
            LAYER.P,
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
    WAFER_STACK = WAFER_STACK.z_offset(-1 * 0.22).invert_zaxis()

    # write_sprocess(
    #     component=c,
    #     waferstack=WAFER_STACK,
    #     layermap=LAYER,
    #     process=get_process(),
    #     filepath="./sprocess_3D_fps.cmd",
    # )

    write_sprocess(
        component=c,
        waferstack=WAFER_STACK,
        layermap=LAYER,
        process=get_process(),
        xsection_bounds=(
            ((test_component.xmin + test_component.xmax) / 2, test_component.ymin),
            ((test_component.xmin + test_component.xmax) / 2, test_component.ymax),
        ),
        directory="./sprocess/",
        filename="sprocess_2D_fps.cmd",
        initial_z_resolutions={"core": 0.005, "box": 0.05, "substrate": 0.5},
        initial_xy_resolution=0.05,
        split_steps=True,
        contact_portnames=("e1", "e2"),
    )
