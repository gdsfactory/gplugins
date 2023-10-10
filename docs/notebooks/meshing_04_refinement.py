# # Controlling mesh resolution
#
# ## Coarse global resolution
#
# The keyword arguments `default_resolution_min` and `default_resolution_max` set the minimum and maximum characteristic lengths used by `gmsh` when computing the mesh.
#
# They are used when other resolutions are not provided, and `default_resolution_max` effectively sets the minimum length possible, since when conflicting resolution at a point are given, the smallest one is taken.

# +
# # %matplotlib widget

# +

import gdsfactory as gf
import meshio
from gdsfactory.generic_tech import get_generic_pdk
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from skfem.io import from_meshio

from gplugins.gmsh.get_mesh import create_physical_mesh, get_mesh

PDK = get_generic_pdk()
PDK.activate()
gf.config.rich_output()

waveguide = gf.components.straight_pin(length=10, taper=None)
waveguide_trimmed = gf.Component()
waveguide_trimmed.add_ref(
    gf.geometry.trim(
        component=waveguide,
        domain=[[3, -4], [3, 4], [5, 4], [5, -4]],
    )
)


filtered_layer_stack = LayerStack(
    layers={
        k: get_layer_stack().layers[k]
        for k in (
            "slab90",
            "core",
            "via_contact",
        )
    }
)

filename = "mesh"


def mesh_with_physicals(mesh, filename):
    mesh_from_file = meshio.read(f"{filename}.msh")
    return create_physical_mesh(mesh_from_file, "triangle")


# -

# With `default_resolution_max` set to 1 um and `default_resolution_min` set to 100 nm:

# +
mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    background_tag="oxide",
    background_padding=(2.0, 2.0, 2.0, 2.0),
    default_resolution_min=0.1,
    default_resolution_max=1,
)

mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()
# -

# With `default_resolution_max` set to 300 nm and `default_resolution_max` set to 50 nm:

mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    background_tag="oxide",
    background_padding=(2.0, 2.0, 2.0, 2.0),
    default_resolution_min=0.05,
    default_resolution_max=0.3,
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().show()

# ## Label-wise coarse resolution control
#
# An advantage of finite-volume and finite-element schemes is the ability for different nodes to have different characteristics lengths.
#
# This simply achieved to first order here by supplying a `resolutions` dict with keys referencing the `LayerStack` names, and for value a second dict with keys `resolution` and `DistMax / SizeMax` (see gmsh documentation) which control, respectively, the characteristic length within a region and the dropoff away from interfaces with this region.
#
# For example, to refine within the core only, one could use:

resolutions = {"core": {"resolution": 0.05, "distance": 0}}
mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    background_tag="oxide",
    background_padding=(2.0, 2.0, 2.0, 2.0),
    resolutions=resolutions,
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().show()

# Adding a dropoff at the interface:

resolutions = {"core": {"resolution": 0.05, "DistMax": 1, "SizeMax": 0.2}}
mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    background_tag="oxide",
    background_padding=(2.0, 2.0, 2.0, 2.0),
    resolutions=resolutions,
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().show()

# Refining multiple elements simultaneously:

resolutions = {
    "core": {"resolution": 0.05, "DistMax": 1, "SizeMax": 0.2},
    "slab90": {"resolution": 0.02, "DistMax": 1, "SizeMax": 0.2},
    "via_contact": {"resolution": 0.2},
    "oxide": {"resolution": 1},
}
mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    background_tag="oxide",
    background_padding=(2.0, 2.0, 2.0, 2.0),
    resolutions=resolutions,
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().show()
