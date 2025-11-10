import tempfile
import time
from pathlib import Path
from typing import Any

import gdsfactory as gf
import numpy as np
from femwell.maxwell.waveguide import Modes, compute_modes
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from gdsfactory.typings import ComponentSpec, CrossSectionSpec, PathType
from meshwell.cad import cad
from meshwell.mesh import mesh as mesh_func
from shapely.geometry import LineString
from skfem import (
    Basis,
    ElementTriN2,
    ElementTriP0,
    ElementTriP2,
    Mesh,
)

from gplugins.meshwell import get_meshwell_cross_section

MESH_FILENAME = "mesh.msh"


def load_mesh_basis(mesh_filename: PathType):
    mesh = Mesh.load(mesh_filename)
    basis = Basis(mesh, ElementTriN2() * ElementTriP2())
    basis0 = basis.with_element(ElementTriP0())
    return mesh, basis0


def compute_cross_section_modes(
    cross_section: CrossSectionSpec,
    layer_stack: LayerStack,
    wavelength: float = 1.55,
    num_modes: int = 4,
    order: int = 1,
    radius: float = np.inf,
    wafer_padding: float = 2.0,
    **kwargs: Any,
) -> Modes:
    """Calculate effective index of a cross-section.

    Defines a "straight" component of the cross_section, and calls compute_component_slice_modes.

    Args:
        cross_section: gdsfactory cross_section.
        layer_stack: gdsfactory layer_stack.
        wavelength: in um.
        num_modes: to compute.
        order: order of the mesh elements. 1: linear, 2: quadratic.
        radius: defaults to inf.
        wafer_padding: in um.
        kwargs: kwargs for compute_component_slice_modes

    Keyword Args:
        solver: can be slepc or scipy.
        resolution_specs (Dict): meshwell resolution specifications.
            Format: {"layername": [ConstantInField(resolution=float, apply_to="surfaces")]}
        default_characteristic_length (float): default gmsh characteristic length.
        background_tag (str): name of the background layer to add (default: no background added).
        background_remeshing_file (Path): optional background mesh file for refinement.
        global_scaling (float): global scaling factor.
        verbosity (int): GMSH verbosity level.

    """
    # Get meshable component from cross-section
    c = gf.components.straight(length=10, cross_section=cross_section)
    dx = c.xsize
    dy = c.ysize

    xsection_bounds = [
        [dx / 2, dy - wafer_padding],
        [dx / 2, dy + wafer_padding],
    ]

    # Mesh as component
    return compute_component_slice_modes(
        component=c,
        xsection_bounds=xsection_bounds,
        layer_stack=layer_stack,
        wavelength=wavelength,
        num_modes=num_modes,
        order=order,
        radius=radius,
        wafer_padding=wafer_padding,
        **kwargs,
    )


_material_name_to_index = {
    "si": 3.48,
    "sio2": 1.44,
    "sin": 2.0,
}


def compute_component_slice_modes(
    component: ComponentSpec,
    xsection_bounds: tuple[tuple[float, float], tuple[float, float]],
    layer_stack: LayerStack,
    wavelength: float = 1.55,
    num_modes: int = 4,
    order: int = 1,
    wafer_padding: float = 2.0,
    radius: float = np.inf,
    metallic_boundaries: bool = False,
    n_guess: float | None = None,
    solver: str = "scipy",
    material_name_to_index: dict[str, float] | None = None,
    **kwargs: Any,
) -> Modes:
    """Calculate effective index of component slice.

    Args:
        component: gdsfactory component.
        xsection_bounds: xy line defining where to take component cross_section.
        layer_stack: gdsfactory layer_stack.
        wavelength: wavelength (um).
        num_modes: number of modes to return.
        order: order of the mesh elements. 1: linear, 2: quadratic.
        wafer_padding: padding beyond bbox to add to WAFER layers.
        radius: bend radius of the cross-section.
        metallic_boundaries: if True, will set the boundaries to be metallic.
        n_guess: initial guess for the effective index.
        solver: can be slepc or scipy.
        material_name_to_index: dictionary mapping material names to refractive indices.
        kwargs: kwargs for meshwell.mesh.mesh

    Keyword Args:
        resolution_specs (Dict): meshwell resolution specifications.
            Format: {"layername": [ConstantInField(resolution=float, apply_to="surfaces")]}
        default_characteristic_length (float): default gmsh characteristic length.
        background_tag (str): name of the background layer to add (default: no background added).
        background_remeshing_file (Path): optional background mesh file for refinement.
        global_scaling (float): global scaling factor.
        verbosity (int): GMSH verbosity level.
        wafer_layer: layer to use for WAFER padding.
    """
    material_name_to_index = material_name_to_index or _material_name_to_index

    # Mesh

    # Create cross-section line from xsection_bounds
    cross_section_line = LineString(xsection_bounds)

    # Generate 2D cross-section surfaces instead of 3D prisms
    surfaces = get_meshwell_cross_section(
        component=component,
        line=cross_section_line,
        layer_stack=layer_stack,
        wafer_padding=wafer_padding,
    )
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdirname = Path(tmpdirname)
        cad(entities_list=surfaces, output_file=tmpdirname / "temp.xao")
        mesh_func(
            input_file=tmpdirname / "temp.xao",
            output_file=MESH_FILENAME,
            default_characteristic_length=1000,
            dim=2,
            verbosity=10,
            **kwargs,
        )

    # Assign materials to mesh elements
    mesh, basis0 = load_mesh_basis(MESH_FILENAME)
    epsilon = basis0.zeros(dtype=complex)
    for layername, layer in layer_stack.layers.items():
        if layername in mesh.subdomains.keys():
            epsilon[basis0.get_dofs(elements=layername)] = (
                material_name_to_index[layer.material] ** 2
            )
        if "background_tag" in kwargs:
            epsilon[basis0.get_dofs(elements=kwargs["background_tag"])] = (
                material_name_to_index[kwargs["background_tag"]] ** 2
            )

    return compute_modes(
        basis0,
        epsilon,
        wavelength=wavelength,
        mu_r=1,
        num_modes=num_modes,
        order=order,
        radius=radius,
        solver=solver,
        n_guess=n_guess,
        metallic_boundaries=metallic_boundaries,
    )


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from meshwell.resolution import ConstantInField

    start = time.time()
    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "core",
                "clad",
                "slab90",
                "box",
            )
        }
    )

    filtered_layer_stack.layers["core"].thickness = 0.2

    # New meshwell resolution format
    resolution_specs = {
        "core": [ConstantInField(resolution=0.04, apply_to="surfaces")],
        "clad": [ConstantInField(resolution=0.4, apply_to="surfaces")],
        "box": [ConstantInField(resolution=0.4, apply_to="surfaces")],
        "slab90": [ConstantInField(resolution=0.1, apply_to="surfaces")],
    }

    cross_section = False
    cross_section = True

    if cross_section:
        modes = compute_cross_section_modes(
            cross_section="rib",
            layer_stack=filtered_layer_stack,
            wavelength=1.55,
            num_modes=4,
            order=1,
            radius=np.inf,
            resolution_specs=resolution_specs,
        )
        mode = modes[0]
        mode.show(mode.E.real, colorbar=True, direction="x")
    else:
        component = gf.components.coupler_full(dw=0)
        component.show()

        modes = compute_component_slice_modes(
            component,
            [[0, -3], [0, 3]],
            layer_stack=filtered_layer_stack,
            wavelength=1.55,
            num_modes=4,
            order=1,
            radius=np.inf,
            resolution_specs=resolution_specs,
        )

        print(modes)
        print(modes[0].te_fraction)

        modes[0].show(np.real(modes[0].E))
        modes[0].show(np.imag(modes[0].E))

        modes[0].show(np.real(modes[0].H))
        modes[0].show(np.imag(modes[0].H))

        integrals = np.zeros((len(modes),) * 2, dtype=complex)

        for i in range(len(modes)):
            for j in range(len(modes)):
                integrals[i, j] = modes[i].calculate_overlap(modes[j])

        plt.imshow(np.real(integrals))
        plt.colorbar()
        plt.show()

        # Create basis to select a certain simulation extent
        def sel_fun(x):
            return (x[0] < 0) * (x[0] > -1) * (x[1] > 0) * (x[1] < 0.5)

        print(modes.sorted(lambda mode: mode.calculate_power(elements=sel_fun)))
