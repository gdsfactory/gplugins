# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.0
#   kernelspec:
#     display_name: ''
#     language: ''
#     name: ''
# ---

# # 2D meshing: xy cross-section
#
# You can supply the argument `type="xy"` and a `z`-value, to mesh arbitrary `Component` planar cross-sections.

# +
import gdsfactory as gf
import meshio
from gdsfactory.generic_tech import get_generic_pdk
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from skfem.io import from_meshio

from gplugins.gmsh.get_mesh import create_physical_mesh, get_mesh

gf.config.rich_output()
PDK = get_generic_pdk()
PDK.activate()

waveguide = gf.components.straight_pin(length=10, taper=None)
waveguide.plot()
# -

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

# +
filename = "mesh"


def mesh_with_physicals(mesh, filename):
    mesh_from_file = meshio.read(f"{filename}.msh")
    return create_physical_mesh(mesh_from_file, "triangle")


# -

# At `z=0.09` um, according to the layer stack above we should see polygons from all three layers:

filename = "mesh"
mesh = get_mesh(
    component=waveguide,
    type="xy",
    z=0.09,
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()

# At `z=0`, you can see only the core and slab:

mesh = get_mesh(
    component=waveguide,
    type="xy",
    z=0.0,
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()

# At `z=1.0`, you can only see the vias appear:

mesh = get_mesh(
    component=waveguide,
    type="xy",
    z=1.0,
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()

# ## Controlling meshing domain
#
# You can use functions that return other components to modify the simulation domain, for instance `gdsfactory.geometry.trim`:

# +
waveguide_trimmed = gf.Component()
waveguide_trimmed.add_ref(
    gf.geometry.trim(
        component=waveguide,
        domain=[[3, -4], [3, 4], [5, 4], [5, -4]],
    )
)

waveguide_trimmed.plot()
# -

mesh = get_mesh(
    component=waveguide_trimmed,
    type="xy",
    z=0.09,
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()
