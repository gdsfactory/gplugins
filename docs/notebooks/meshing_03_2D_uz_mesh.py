# # 2D meshing: uz cross-section
#
# You can mesh an out of plane `Component` cross-section by supplying the argument `type="uz"` and a `xsection_bounds` under the form `[[x1,y1], [x2,y2]]`, which parametrizes a line in `u`-coordinates

# +
import gdsfactory as gf
import meshio
from gdsfactory.generic_tech import get_generic_pdk
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from skfem.io import from_meshio

from gplugins.gmsh.get_mesh import get_mesh
from gplugins.gmsh.mesh import create_physical_mesh

gf.config.rich_output()
PDK = get_generic_pdk()
PDK.activate()

waveguide = gf.components.straight_pin(length=10, taper=None)
waveguide_trimmed = gf.Component()
waveguide_trimmed.add_ref(
    gf.geometry.trim(
        component=waveguide,
        domain=[[3, -4], [3, 4], [5, 4], [5, -4]],
    )
)

waveguide_trimmed
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

# Choosing the line going from `y=-4` to `y=4` at `x=4`, which crosses slab, via, and core:

mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()

# We can plot as usual (note that the `u-z` coordinates we are working in still map to `xy` for the plotter):

# ## Mesh background
#
# You can add a convenience argument to add a background mesh around the geometry (instead of defining a dummy polygon and layer in the layer_stack with low mesh_order):

mesh = get_mesh(
    component=waveguide_trimmed,
    type="uz",
    xsection_bounds=[(4, -4), (4, 4)],
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    background_tag="oxide",
    background_padding=(2.0, 2.0, 2.0, 2.0),
)
mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot()
