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

from gplugins.gmsh.parse_gds import cleanup_component_layermap
from gplugins.sentaurus.mask_sde import get_sentaurus_mask_3D

DEFAULT_HEADER = """(sde:clear)
(sde:set-process-up-direction "+z")
"""

REMESH_STR = """(sdedr:define-refinement-size \"RefDef.BG\" 0.5 0.5 0.5 0.01 0.01 0.01)
(sdedr:define-refinement-function \"RefDef.BG\" \"DopingConcentration\" \"MaxTransDiff\" 0.1)
"""

CONTACT_STR = ""


SLICE_STR = ""


def initialize_sde(
    component,
    waferstack,
    layermap,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None,
    u_offset: float = 0.0,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    header_str: str = DEFAULT_HEADER,
):
    """Returns a string defining the geometry definition for a Sentaurus sde file based on a component, initial wafer state, and settings.

    Arguments:
        component: gdsfactory component containing polygons defining the mask
        waferstack: gdsfactory layerstack representing the initial wafer
        layermap: gdsfactory LayerMap object containing all layers
        xsection_bounds: two in-plane coordinates ((x1,y1), (x2,y2)) defining a line cut for a 2D process cross-section. If None, simulate in 3D.
        u_offset: for the x-axis of the 2D coordinate system, useful to go back to component units if xsection_bounds parallel to x or y
        round_tol: for gds cleanup (grid snapping by rounding coordinates)
        simplify_tol: for gds cleanup (shape simplification)
        header_str: initial string to write to the TCL file. Useful for settings
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
    output_str += header_str

    # Initial z-mesh from waferstack and resolutions
    # output_str += f"(sdepe:define-pe-domain {xmin} {ymin} {xmax} {ymax})\n"

    # Regions
    regions = []
    for layername, layer in sorted(waferstack.layers.items()):
        region_name = f"{layername}_{layer.material}"
        regions.append(region_name)
        zlo = min(layer.zmin, layer.zmin + layer.thickness)
        zhi = max(layer.zmin, layer.zmin + layer.thickness)
        output_str += f'(sdegeo:create-cuboid (position {xmin} {ymin} {zlo}) (position {xmax} {ymax} {zhi}) "{layer.material}" "{region_name}")\n'

    return output_str, get_mask, layer_polygons_dict, xmin, xmax, ymin, ymax, regions


def write_sde(
    component,
    waferstack,
    layermap,
    process,
    contact_str: str | None = None,
    slice_str: str | None = None,
    init_tdr: str | None = None,
    save_directory: Path | None = None,
    execution_directory: Path | None = None,
    filename: str = "sprocess_fps.cmd",
    fileout: str | None = None,
    round_tol: int = 3,
    simplify_tol: float = 1e-3,
    device_remesh: bool = True,
    remesh_str: str = REMESH_STR,
    header_str: str = DEFAULT_HEADER,
    num_threads: int = 4,
) -> None:
    """Writes a Sentaurus Device Editor Scheme file for the component + layermap + initial waferstack + process.

    Arguments:
        component: gdsfactory component containing polygons defining the mask.
        waferstack: gdsfactory layerstack representing the initial wafer.
        layermap: gdsfactory LayerMap object containing all layers.
        process: list of gdsfactory.technology.processes process steps.
        contact_str: string defining the contacts to be added to the device.
        slice_str: string defining the slices to be added to the device.
        init_tdr: tdr file containing the initial structure, ready for sdevice simulation.
        save_directory: directory where to save output and script. Default ./sprocess.
        execution_directory: directory where sprocess will be run from. Default local ./
        filename: name of the final sprocess command file
        fileout: tdr file containing the final structure, ready for sdevice simulation. Defaults to component name.
        round_tol: for gds cleanup (grid snapping by rounding coordinates).
        simplify_tol (float): for gds cleanup (shape simplification)
        device_remesh (bool): whether to remesh the device after processing.
        remesh_str (str): string defining the remeshing options.
        header_str (str): initial string to write to the TCL file. Useful for settings.
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
            header_str=header_str,
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
                    f'(sdedr:define-gaussian-profile "{step.name}" "{species}" "PeakPos" {step.range} "PeakVal" {step.peak_conc} "ValueAtDepth" 1.0e16 "Depth" 0.5 "Erf" "Factor" 0.7)\n'
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
            f.write(f'(sdesnmesh:iocontrols "numThreads" {num_threads})\n')
            f.write(remesh_str)
            for region in regions:
                if "Silicon" in region:
                    f.write(
                        f'(sdedr:define-refinement-region "{region}" "RefDef.BG" "{region}")\n'
                    )

        # Add contacts
        if contact_str is not None:
            f.write(f"{contact_str}")

        # Slice before meshing
        if slice_str is not None:
            f.write(f"{slice_str}")

        # Save structure and build mesh
        f.write(f'(sde:save-model "{fileout}")\n')
        f.write(f'(sde:build-mesh "" "{fileout}")')
        f.write("\n")


if __name__ == "__main__":
    from gdsfactory.components import straight_pn
    from gdsfactory.generic_tech import LAYER
    from gdsfactory.generic_tech.layer_stack import WAFER_STACK

    # Create a component with the right contacts
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

    test_component = gf.functions.trim(
        component=test_straight, domain=[[0, -4], [0, 4], [length, 4], [length, -4]]
    )

    yp = (test_component.ymax + test_component.ymin) / 2 + test_component.ysize / 2
    ym = (test_component.ymax + test_component.ymin) / 2 - test_component.ysize / 2

    WAFER_STACK.layers["substrate"].material = "Silicon"
    WAFER_STACK.layers["substrate"].thickness = 1
    WAFER_STACK.layers["substrate"].zmin = WAFER_STACK.layers["box"].zmin - 1
    WAFER_STACK.layers["box"].material = "Oxide"
    WAFER_STACK.layers["core"].material = "Silicon"

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
                material="Silicon",
                resist_thickness=1.0,
                positive_tone=False,
            ),
            Etch(
                name="slab_etch",
                layer=LAYER.SLAB90,
                layers_diff=[LAYER.WG],
                depth=LayerStackParameters.thickness_wg
                - LayerStackParameters.thickness_slab_deep_etch,
                material="Silicon",
                resist_thickness=1.0,
            ),
            # See gplugins.process.implant tables for ballpark numbers
            # Adjust to your process
            ImplantGaussian(
                name="n_implant",
                layer=LAYER.N,
                ion="phosphorus",
                peak_conc=1e17,
                range=0.0,
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
                range=0.0,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="np_implant",
                layer=LAYER.NP,
                ion="phosphorus",
                peak_conc=1e18,
                range=0.0,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="ppp_implant",
                layer=LAYER.PPP,
                ion="boron",
                peak_conc=1e19,
                range=0.0,
                vertical_straggle=0.2,
                lateral_straggle=0.05,
                resist_thickness=1.0,
            ),
            ImplantGaussian(
                name="npp_implant",
                layer=LAYER.NPP,
                ion="phosphorus",
                peak_conc=1e19,
                range=0.0,
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
            # Grow(
            #     name="viac_metallization",
            #     layer=None,
            #     thickness=LayerStackParameters.zmin_metal1
            #     - LayerStackParameters.thickness_slab_deep_etch,
            #     material="Aluminum",
            #     type="anisotropic",
            # ),
            # Etch(
            #     name="viac_etch",
            #     layer=LAYER.VIAC,
            #     depth=LayerStackParameters.zmin_metal1
            #     - LayerStackParameters.thickness_slab_deep_etch
            #     + 0.1,
            #     material="Aluminum",
            #     type="anisotropic",
            #     resist_thickness=1.0,
            #     positive_tone=False,
            # ),
            # Grow(
            #     name="deposit_cladding",
            #     layer=None,
            #     thickness=LayerStackParameters.thickness_clad
            #     + LayerStackParameters.thickness_slab_deep_etch,
            #     material="Oxide",
            #     type="anisotropic",
            # ),
            # Planarize(
            #     name="planarization",
            #     height=LayerStackParameters.thickness_clad
            #     - LayerStackParameters.thickness_slab_deep_etch,
            # ),
        )

    import numpy as np

    via_positions = test_component.extract(layers=[LAYER.VIAC]).get_polygons()
    contact_str = ""
    labels = ["anode", "cathode"]
    for label, via_position in zip(labels, via_positions):
        xmin, ymin, xmax, ymax = (
            np.min(via_position[:, 0]),
            np.min(via_position[:, 1]),
            np.max(via_position[:, 0]),
            np.max(via_position[:, 1]),
        )
        contact_str += f'(define VIA (sdegeo:create-cuboid (position {xmin} {ymin} 0.09) (position {xmax} {ymax} 0.5) "Metal" "{label}"))\n'
        contact_str += f'(sdegeo:set-contact VIA "{label}" "remove")\n'

    slice_str = ""

    test_component.name = "pn_test"
    write_sde(
        component=test_component,
        waferstack=WAFER_STACK,
        layermap=LAYER,
        process=get_process(),
        save_directory="./sde/",
        filename="sde.scm",
        contact_str=contact_str,
        slice_str=slice_str,
    )
