import math
import pathlib

import gdsfactory as gf
from gdsfactory.technology.processes import (
    Anneal,
    Etch,
    Grow,
    ImplantPhysical,
    Lithography,
)
from gdsfactory.typings import Dict, Tuple
from parse_gds import cleanup_component_layermap

from gplugins.sentaurus.mask import get_sentaurus_mask_2D, get_sentaurus_mask_3D

# DEFAULT_INIT_LINES = """AdvancedCalibration
# mgoals min.normal.size=0.01 normal.growth.ratio=1.618 accuracy=2e-5 minedge=5e-5
# """

DEFAULT_INIT_LINES = "AdvancedCalibration\n"

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
    filepath: str = "./sprocess.tcl",
    structroot: str = "struct",
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
    """

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
    out_file = pathlib.Path(filepath)
    if out_file.exists():
        out_file.unlink()

    with open(filepath, "a") as f:
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
            f.write(f"struct tdr={structroot}_0_wafer.tdr")

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

            if split_steps:
                f.write(f"struct tdr={structroot}_{i+1}_{step.name}.tdr")

            f.write("\n")

        # Remeshing options
        f.write("\n")
        if split_steps:
            f.write("#remeshing\n")
        f.write(remeshing_strategy)

        for _layername, layer in waferstack.layers.items():
            if layer.info and layer.info["active"] is True:
                f.write(
                    f"""refinebox name= Global refine.min.edge= {{ {layer.zmin - layer.thickness:1.3f} {xmin} {ymin} }} refine.max.edge= {{ {layer.zmin:1.3f} {xmax} {ymax} }} refine.fields= {{ NetActive }} def.max.asinhdiff= 0.5 adaptive {layer.material}
"""
                )
        f.write("grid remesh\n")

        # Tag contacts
        if contact_portnames:
            for contact_name in contact_portnames:
                port = component.ports[contact_name]
                if xsection_bounds:
                    for polygon in component.extract(
                        f"{port.layer}#{contact_name}"
                    ).get_polygons:
                        print(polygon)

            # f.write(f"contact name= {portname} box Silicon xlo=0 xhi=0.01 ylo=-1*$Ymax+0.2 yhi=$Ymax-0.2 zlo=$Zmax-0.01 zhi=$Zmax")

        # Create structure
        f.write("\n")
        f.write(f"struct tdr={structout}.tdr")


if __name__ == "__main__":
    from gdsfactory.components import straight_pn
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.generic_tech.layer_stack import WAFER_STACK, get_process

    # Create a component with the right contacts
    c = gf.Component()
    test_component = c << straight_pn(length=30, taper=None).extract(
        [
            LAYER.WG,
            LAYER.SLAB90,
            LAYER.N,
            LAYER.P,
            LAYER.VIAC,
        ]
    )
    yp = (test_component.ymax + test_component.ymin) / 2 + test_component.ysize / 2
    ym = (test_component.ymax + test_component.ymin) / 2 - test_component.ysize / 2
    c.add_port(
        name="e_p",
        center=(15, yp),
        width=test_component.ysize / 2,
        orientation=0,
        layer=LAYER.VIAC,
    )
    c.add_port(
        name="e_n",
        center=(15, ym),
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
        filepath="./sprocess_3D_fps.cmd",
    )

    write_sprocess(
        component=c,
        waferstack=WAFER_STACK,
        layermap=LAYER,
        process=get_process(),
        xsection_bounds=(
            ((test_component.xmin + test_component.xmax) / 2, test_component.ymin),
            ((test_component.xmin + test_component.xmax) / 2, test_component.ymax),
        ),
        filepath="./sprocess_2D_fps.cmd",
        initial_z_resolutions={"core": 0.02, "box": 0.5, "substrate": 0.5},
        initial_xy_resolution=0.2,
        split_steps=True,
        contact_portnames=("e_p", "e_n"),
    )
