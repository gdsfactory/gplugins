# # 3D meshing and net entities
#
# The same API can be used to mesh a component in 3D. Furthermore, there are simple ways to tag elements attached to ports to define simulation boundary conditions.
#
# This time, let's use the LayerStack's box and clad layerlevels (associated with layer.WAFER) to define the background:

# +

import gdsfactory as gf
import meshio
from gdsfactory.generic_tech import get_generic_pdk
from gdsfactory.pdk import get_layer_stack
from gdsfactory.technology import LayerStack
from skfem.io import from_meshio

from gplugins.gmsh.get_mesh import get_mesh
from gplugins.gmsh.mesh import create_physical_mesh

PDK = get_generic_pdk()
PDK.activate()
gf.config.rich_output()

waveguide = gf.components.straight_pin(length=5, taper=None)
waveguide.plot()

# +
filtered_layer_stack = LayerStack(
    layers={
        k: get_layer_stack().layers[k]
        for k in (
            "slab90",
            "core",
            "via_contact",
            "metal1",
            "via1",
            "metal2",
            "via2",
            "metal3",
        )
    }
)

filename = "mesh"


def mesh_with_physicals(mesh, filename):
    mesh_from_file = meshio.read(f"{filename}.msh")
    return create_physical_mesh(mesh_from_file, "tetra")


# -

mesh = get_mesh(
    component=waveguide,
    type="3D",
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    default_characteristic_length=1,
    verbosity=5,
)

mesh = mesh_with_physicals(mesh, filename)
mesh = from_meshio(mesh)
mesh.draw().plot(xs=[], ys=[])

# ## Net entities
#
# The default behaviour of the plugin is to create Gmsh physical entities according to layernames. Oftentimes, however, different polygons on the same layer must be accessed separately, for instance to define boundary conditions. In gplugins, these are tagged with the ports of the Component.
#
# To use this feature, the `port_names` argument must be passed. For each portname in the list, GDS polygons touching the associated port will be put on a new layer called "{original_layername}{delimiter}{portname}". This new layer is otherwise physically identical to the original one (so same thickness, material, etc.).
#
# <div class="alert alert-success">
# Note: in the future, it would be interesting to broaden what is possible with port entities, for instance allowing 2D planes in a 3D simulation.
# </div>

# Print the port_names for reference:

waveguide.ports.keys()

# Choose two:

print(waveguide.ports["top_e1"])
print(waveguide.ports["bot_e1"])

mesh = get_mesh(
    component=waveguide,
    type="3D",
    layer_stack=filtered_layer_stack,
    filename=f"{filename}.msh",
    default_characteristic_length=1,
    port_names=["top_e1", "bot_e1"],
)

# Note the extra layers.
