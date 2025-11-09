from __future__ import annotations

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
            thermal_conductivity[basis.get_dofs(elements=domain)] = (
                thermal_conductivities[domain]
            )
        else:
            for material, labels in materials_dict.items():
                if domain in labels:
                    # Assign the right values
                    thermal_conductivity[basis.get_dofs(elements=domain)] = (
                        thermal_conductivities[material]
                    )
                    break

    thermal_conductivity *= 1e-12  # 1e-12 -> conversion from 1/m^2 -> 1/um^2

    return thermal_conductivity


if __name__ == "__main__":
    # TODO: Update this example to use the new meshwell API
    # The old gplugins.gmsh.get_mesh has been replaced with:
    # 1. get_meshwell_cross_section() to generate cross-section surfaces
    # 2. meshwell.cad.cad() to create CAD file
    # 3. meshwell.mesh.mesh() to create mesh file
    # See gplugins/femwell/mode_solver.py for an example of the new API
    pass
