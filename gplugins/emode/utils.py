import emodeconnection as emc
from gdsfactory import CrossSection
from gdsfactory.technology import LayerStack
import numbers


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
        nm = 1e-3 # convert microns to nanometers
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

        # Process layer_stack to create EMode shapes
        for layer_name, layer_info in layer_stack.layers.items():
            shape_info = {
                'name': layer_name,
                'refractive_index': layer_info.material,
                'height': layer_info.thickness * nm,
                'width': layer_info.width_to_z * nm,
                'sidewall_angle': layer_info.sidewall_angle,
            }
            # material = layer_info.material
            # thickness = layer_info.thickness
            # z_min = layer_info.zmin
            # layer=((WG - DEEP_ETCH) - SHALLOW_ETCH)
            # derived_layer=WG
            # thickness=0.22
            # thickness_tolerance=None
            # width_tolerance=None
            # zmin=0.0
            # zmin_tolerance=None
            # sidewall_angle=10.0
            # sidewall_angle_tolerance=None
            # width_to_z=0.5
            # z_to_bias=None
            # bias=None
            # mesh_order=2
            # material='si'
            # info={}

            # Find a matching CrossSection for this layer
            xsection_ind = [k for k, s in enumerate(cross_section.sections) if str(layer_info.layer) == str(s.layer) or str(layer_info.derived_layer) == str(s.layer)]

            # Apply settings from the matching CrossSection
            if len(xsection_ind) > 0:
                xsection = cross_section.sections[xsection_ind[0]]
                shape_info['width'] = xsection.width * nm
                shape_info['position'] = xsection.offset * nm

            # cross_section.sections[0]
            # Section(width=0.6, offset=0.0, insets=None, layer='WG', port_names=('o1', 'o2'), port_types=('optical', 'optical'), name='_default', hidden=False, simplify=None, width_function=None, offset_function=None)
            # cross_section.sections[1]
            # Section(width=6.6, offset=0.0, insets=None, layer='SLAB90', port_names=(None, None), port_types=('optical', 'optical'), name='cladding_0', hidden=False, simplify=0.05, width_function=None, offset_function=None)

            self.shape(**shape_info)

        return
