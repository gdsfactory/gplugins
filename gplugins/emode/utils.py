import emodeconnection as emc
from gdsfactory import CrossSection
from gdsfactory.technology import LayerStack

class EMode(emc.EMode):
    def build_waveguide(
        self,
        cross_section: CrossSection,
        layer_stack: LayerStack,
        **kwargs,
    ) -> None:
        """Builds a waveguide structure in EMode based on GDSFactory CrossSection and LayerStack.

        Args:
            cross_section: A GDSFactory CrossSection object defining the waveguide's geometry.
            layer_stack: A GDSFactory LayerStack object defining the material layers.
            **kwargs: Additional keyword arguments to be passed directly to EMode's settings() function.
        """
        nm = 1e3 # convert microns to nanometers
        dim_keys = [
            'wavelength',
            'x_resolution',
            'y_resolution',
            'window_width',
            'window_height',
            'bend_radius',
            'expansion_resolution',
            'expansion_size',
            'propagation_resolution',
        ]

        # Pass all kwargs directly to EMode's settings function
        kwargs = {key: (value * nm if key in dim_keys else value) for key, value in kwargs.items()}
        self.settings(**kwargs)

        # Get a list of EMode materials for cleaning GDSFactory material names
        emode_materials = self.get('materials')

        # Process layer_stack to create EMode shapes
        max_order = max([info.mesh_order for name, info in layer_stack.layers.items()])
        min_zmin = min([info.zmin for name, info in layer_stack.layers.items()])

        for layer_name, layer_info in layer_stack.layers.items():

            material = next(
                (mat for mat in emode_materials if mat.lower() == layer_info.material.lower()),
                layer_info.material
            )

            shape_info = {
                'name': layer_name,
                'refractive_index': material,
                'height': layer_info.thickness * nm,
                'mask': layer_info.width_to_z * nm,
                'sidewall_angle': layer_info.sidewall_angle,
                'etch_depth': layer_info.thickness * nm if layer_info.width_to_z > 0 else 0,
                'position': [0.0, (layer_info.zmin - min_zmin + layer_info.thickness/2) * nm],
                'priority': max_order - layer_info.mesh_order + 1,
            }

            # Find a matching CrossSection for this layer
            xsection_ind = [k for k, s in enumerate(cross_section.sections) if str(layer_info.layer) == str(s.layer) or str(layer_info.derived_layer) == str(s.layer)]

            # Apply settings from the matching CrossSection
            if len(xsection_ind) > 0:
                xsection = cross_section.sections[xsection_ind[0]]
                shape_info['mask'] = xsection.width * nm
                shape_info['mask_offset'] = xsection.offset * nm

            self.shape(**shape_info)

        return
