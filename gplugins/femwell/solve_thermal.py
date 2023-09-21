from __future__ import annotations

import matplotlib.pyplot as plt

thermal_conductivities = {
    "*Al": 28.0,
    "*Ni": 90.9,  # unchecked
    "*Cu": 398,  # unchecked
    "*Sn": 90.9,  # unchecked
    "*Si": 90.0,
    "*SiN": 2.1,
    "*TiN": 28,
    "*GENERIC_OXIDE": 1.4,
    "*Air": 0.024,
}
materials_dict = {
    "*Al": [
        "M1",
        "VIA1",
        "M2",
        "VIA1",
        "M3",
        "VIAC",
    ],
    "*Ni": ["BUMP_NI"],
    "*Cu": ["BUMP_CU"],
    "*Sn": ["BUMP_SN"],
    "*Si": ["WG", "SLAB90", "SLAB150"],
    "*SiN": ["WGN", "NITRIDE_PASSIVATION"],
    "*TiN": ["HEATER"],
    "*GENERIC_OXIDE": [
        "BOX",
        "CLAD",
    ],
    "*Air": ["UNDERCUT", "UNDERCUT_BACKGROUND"],
}


def get_thermal_conductivities(basis):
    thermal_conductivity = basis.zeros()

    for domain in basis.mesh.subdomains:
        # Find which material this domain is
        # We can override the material properties by
        # adding the layer to the thermal_conductivities dict. Check for that
        # case
        if domain in thermal_conductivities:
            thermal_conductivity[
                basis.get_dofs(elements=domain)
            ] = thermal_conductivities[domain]
        else:
            for material, labels in materials_dict.items():
                if domain in labels:
                    # Assign the right values
                    thermal_conductivity[
                        basis.get_dofs(elements=domain)
                    ] = thermal_conductivities[material]
                    break

    thermal_conductivity *= 1e-12  # 1e-12 -> conversion from 1/m^2 -> 1/um^2

    return thermal_conductivity


if __name__ == "__main__":
    import gdsfactory as gf
    from femwell.visualization import plot_domains
    from gdsfactory.generic_tech import LAYER_STACK
    from skfem import Mesh

    from gplugins.gmsh.get_mesh import get_mesh

    LAYER_STACK.layers["heater"].thickness = 0.13
    LAYER_STACK.layers["heater"].zmin = 2.2
    heater_len = 1  # 1 um, so normalized

    sheet_resistance_TiN = 10
    heater_width = 2
    heater_res = heater_len * sheet_resistance_TiN / heater_width

    c = heater = gf.components.straight_heater_metal(
        length=50, heater_width=heater_width
    )
    heater.show()

    # ====== MESH =====
    filtered_layer_stack = LAYER_STACK
    heater_derived = filtered_layer_stack.get_component_with_derived_layers(heater)
    get_mesh(
        component=heater_derived,
        type="uz",
        xsection_bounds=[(3, c.bbox[0, 1]), (3, c.bbox[1, 1])],
        # xsection_bounds=[(3, -4), (3, 4)],
        layer_stack=filtered_layer_stack,
        filename="mesh.msh",
        resolutions={
            "WG": {"resolution": 0.02, "distance": 1.0},
            "SLAB150": {"resolution": 0.02, "distance": 1.0},
            "SLAB90": {"resolution": 0.02, "distance": 1.0},
            "WGN": {"resolution": 0.04, "distance": 1.0},
            "HEATER": {"resolution": 0.1, "distance": 1.0},
        },
        default_resolution_max=0.3,
        z_bounds=(1.0, 8.0),
    )
    mesh = Mesh.load("mesh.msh")

    plot_domains(mesh)
    plt.show()
    mesh.draw().show()
