import itertools
import pathlib
import pprint
import time
from typing import Literal

import gdsfactory as gf
import meow as mw
import numpy as np
import pandas as pd
import sax
import yaml
from gdsfactory import Component, logger
from gdsfactory.config import PATH
from gdsfactory.pdk import get_active_pdk, get_layer_stack
from gdsfactory.technology import DerivedLayer, LayerStack
from gdsfactory.typings import LayerSpec, PathType
from tqdm.auto import tqdm

from gplugins.common.utils.get_sparameters_path import (
    get_sparameters_path_meow as get_sparameters_path,
)


def list_unique_layer_stack_z(
    layer_stack: LayerStack,
) -> list[float]:
    """List all unique LayerStack z coordinates.

    Args:
        layer_stack: LayerStack
    Returns:
        Sorted set of z-coordinates for this layer_stack
    """
    thicknesses = [layer.thickness for layer in layer_stack.layers.values()]
    zmins = [layer.zmin for layer in layer_stack.layers.values()]
    zmaxs = [sum(value) for value in zip(zmins, thicknesses)]

    return sorted(set(zmins + zmaxs))


ColorRGB = tuple[float, float, float]

material_to_color_default = {
    "si": (0.9, 0, 0, 0.9),
    "sio2": (0.9, 0.9, 0.9, 0.9),
    "sin": (0.0, 0.9, 0.0, 0.9),
}


class MEOW:
    def __init__(
        self,
        component: gf.Component,
        layer_stack,
        wavelength: float = 1.55,
        temperature: float = 25.0,
        num_modes: int = 4,
        cell_length: float = 0.5,
        spacing_x: float = 2.0,
        center_x: float | None = None,
        resolution_x: int = 100,
        spacing_y: float = 2.0,
        center_y: float | None = None,
        resolution_y: int = 100,
        material_to_color: dict[str, ColorRGB] = material_to_color_default,
        dirpath: PathType | None = PATH.sparameters,
        filepath: PathType | None = None,
        overwrite: bool = False,
    ) -> None:
        """Computes multimode 2-port S-parameters for a gdsfactory component.

        assumes port 1 is at the left boundary and port 2 at the right boundary.

        Note coordinate systems:
            gdsfactory uses x,y in the plane to represent components, with the layer_stack existing in z
            meow uses x,y to represent a cross-section, with propagation in the z-direction
            hence we have [x,y,z] <--> [y,z,x] for gdsfactory <--> meow

        Arguments:
            component: gdsfactory component.
            layer_stack: gdsfactory layer_stack.
            wavelength: wavelength in microns (for FDE, and for material properties).
            temperature: temperature in C (for material properties). Unused now.
            num_modes: number of modes to compute for the eigenmode expansion.
            cell_length: in un.
            spacing_x: at beginning and end of the simulation region.
            center_x: in um.
            resolution_x: pixels in horizontal region.
            spacing_y: at the beginning and end of simulation region.
            center_y: in um.
            resolution_y: pixels in vertical direction.
            material_to_color: dict of materials colors for struct plot
            dirpath: directory to store Sparameters.
            filepath: to store pandas Dataframe with Sparameters in npz format.
                Defaults to dirpath/component_.npz.
            overwrite: overwrites stored Sparameter npz results.

        Returns:
            S-parameters in form o1@0,o2@0 at wavelength.

        ::

            cross_section view:
               ________________________________
              |                                |
              |                                |
              | spacing_x            spacing_x |  spacing_y
              |<--------->           <-------->|
              |          ___________   _ _ _   |
              |         |           |          |
              |         |           |_ _ _ _ _ |_ center_y
              |         |           |          |
              |         |___________|          |
              |               |                |
              |                                |
              |               |                |  spacing_y
              |                                |
              |_______________|________________|
                          center_x

            top side view:
               ________________________________
              |                                |
              |                                |
              |cell_length                     |
              |<-------->                      |
              |_____________________ __________|
              |         |           |          |
              |         |           |          |
              | cell0   |  cell1    |  cell2   |
              |_________|___________|__________|
              |                                |
              |                                |
              |                                |
              |                                |
              |________________________________|
        """
        # Validate component
        self.validate_component(component)

        # Save parameters
        self.wavelength = wavelength
        self.num_modes = num_modes
        self.temperature = temperature  # unused for now
        self.material_to_color = material_to_color

        # Process simulation bounds
        z_min, x_min, z_max, x_max = (
            component.xmin,
            component.ymin,
            component.xmax,
            component.ymax,
        )
        z_min, z_max = min(z_min, z_max) + 1e-10, max(z_min, z_max) - 1e-10
        x_min, x_max = min(x_min, x_max) + 1e-10, max(x_min, x_max) - 1e-10
        layer_stack = layer_stack.model_copy()
        ys = list_unique_layer_stack_z(layer_stack)
        y_min, y_max = np.min(ys) + 1e-10, np.max(ys) - 1e-10

        self.span_x = x_max - x_min + spacing_x
        self.center_x = center_x if center_x is not None else 0.5 * (x_max + x_min)
        self.resolution_x = resolution_x

        self.span_y = y_max - y_min + spacing_y
        self.center_y = center_y if center_y is not None else 0.5 * (y_max + y_min)
        self.resolution_y = resolution_y

        self.z_min = z_min
        self.z_max = z_max
        self.span_z = z_max - z_min

        self.cell_length = cell_length

        # you need two extra cells without length at beginning and end.
        self.num_cells = max(int(self.span_z / cell_length) + 2, 4)

        # Setup simulation
        self.component, self.layer_stack = self.add_global_layers(
            component, layer_stack
        )
        self.extrusion_rules = self.layer_stack_to_extrusion()
        self.structs = mw.extrude_gds(self.component, self.extrusion_rules)
        self.cells = self.create_cells()
        self.env = mw.Environment(wl=self.wavelength, T=self.temperature)
        self.css = [
            mw.CrossSection.from_cell(cell=cell, env=self.env) for cell in self.cells
        ]
        self.modes_per_cell = [None] * self.num_cells
        self.S = None
        self.port_map = None

        # Cache
        sim_settings = dict(
            wavelength=wavelength,
            temperature=temperature,
            num_modes=num_modes,
            cell_length=cell_length,
            spacing_x=spacing_x,
            center_x=center_x,
            resolution_x=resolution_x,
            spacing_y=spacing_y,
            center_y=center_y,
            resolution_y=resolution_y,
        )

        filepath = filepath or get_sparameters_path(
            component=component,
            dirpath=dirpath,
            layer_stack=layer_stack,
            **sim_settings,
        )

        sim_settings = sim_settings.copy()
        sim_settings["layer_stack"] = layer_stack.to_dict()
        sim_settings["component"] = component.to_dict()
        self.sim_settings = sim_settings
        self.filepath = pathlib.Path(filepath)
        self.filepath_sim_settings = filepath.with_suffix(".yml")
        self.overwrite = overwrite

    def gf_material_to_meow_material(
        self, material_name: str = "si", wavelengths=None, color=None
    ):
        """Converts a gdsfactory material into a MEOW material."""
        wavelengths = wavelengths or np.linspace(1.5, 1.6, 101)
        color = color or (0.9, 0.9, 0.9, 0.9)
        PDK = get_active_pdk()
        ns = PDK.materials_index[material_name](wavelengths)
        if ns.dtype in [np.float64, np.float32]:
            nr = ns
            ni = np.zeros_like(ns)
        else:
            nr = np.real(ns)
            ni = np.imag(ns)
        df = pd.DataFrame({"wl": wavelengths, "nr": nr, "ni": ni})
        return mw.SampledMaterial.from_df(
            material_name,
            df,
            meta={"color": color},
        )

    def add_global_layers(
        self,
        component,
        layer_stack,
        buffer_y: float = 1,
        global_layer_index: int = 10000,
        layer_wafer: LayerSpec = "WAFER",
    ) -> tuple[Component, LayerStack]:
        """Adds bbox polygons for global layers.

        LAYER.WAFER layers are represented as polygons of size [bbox.x, xspan (meow coords)]

        Arguments:
            component: gdsfactory component.
            layer_stack: gdsfactory LayerStack.
            buffer_y: float, y-buffer to add to box.
            xspan: from eme setup.
            global_layer_index: int, layer index at which to starting adding the global layers.
                    Default 10000 with +1 increments to avoid clashing with physical layers.
            layer_wafer: LayerSpec, layer to represent the wafer.

        """
        c = gf.Component()
        c.add_ref(component)
        layer_wafer = gf.get_layer(layer_wafer)

        for level in layer_stack.layers.values():
            if isinstance(level.layer, DerivedLayer):
                continue
            layer = gf.get_layer(level.layer.layer)
            if layer == layer_wafer:
                c.add_ref(
                    gf.components.bbox(
                        component,
                        layer=(global_layer_index, 0),
                    )
                )
                layer = (global_layer_index, 0)
                global_layer_index += 1

        return c, layer_stack

    def layer_stack_to_extrusion(self):
        """Convert LayerStack to meow extrusions."""
        extrusions = {}
        for layer in self.layer_stack.layers.values():
            if layer.layer not in extrusions.keys():
                extrusions[layer.layer] = []
            extrusions[layer.layer].append(
                mw.GdsExtrusionRule(
                    material=self.gf_material_to_meow_material(
                        layer.material,
                        np.array([self.wavelength]),
                        color=self.material_to_color.get(layer.material),
                    ),
                    h_min=layer.zmin,
                    h_max=layer.zmin + layer.thickness,
                    mesh_order=layer.mesh_order,
                )
            )
        return extrusions

    def create_cells(self) -> list[mw.Cell]:
        """Get meow cells from extruded component.

        Args:
            cell_length: in um.
        """
        zs = np.linspace(self.z_min, self.z_max, self.num_cells - 1)

        # add two cells without length:
        zs = np.concatenate([[self.z_min], zs, [self.z_max]])

        mesh = mw.Mesh2D(
            x=np.linspace(
                self.center_x - self.span_x / 2,
                self.center_x + self.span_x / 2,
                self.resolution_x,
            ),
            y=np.linspace(
                self.center_y - self.span_y / 2,
                self.center_y + self.span_y / 2,
                self.resolution_y,
            ),
            ez_interfaces=True,
        )
        cells = []
        for z_min, z_max in itertools.pairwise(zs):
            cell = mw.Cell(
                structures=self.structs,
                mesh=mesh,
                z_min=z_min,
                z_max=z_max,
            )
            cells.append(cell)

        return cells

    def plot_structure(self, scale=(1, 1, 0.2)):
        return mw.visualize(self.structs, scale=scale)

    def plot_cross_section(self, xs_num):
        env = mw.Environment(wl=self.wavelength, T=self.temperature)
        css = [mw.CrossSection.from_cell(cell=cell, env=env) for cell in self.cells]
        return mw.visualize(css[xs_num])

    def plot_mode(self, xs_num, mode_num):
        if self.modes_per_cell[xs_num] is None:
            self.modes_per_cell[xs_num] = self.compute_mode(xs_num)
        return mw.visualize(self.modes_per_cell[xs_num][mode_num])

    def get_port_map(self):
        if self.port_map is None:
            self.compute_sparameters()
        return self.port_map

    def plot_s_params(
        self, fmt: Literal["abs", "phase", "real-imag", "real", "imag"] = "abs"
    ):
        fmt_str = str(fmt).lower()
        supported_fmts = ["abs", "phase", "real-imag", "real", "imag"]
        if fmt_str not in supported_fmts:
            raise ValueError(
                f"EME Plot format '{fmt_str}' not in supported formats: {supported_fmts}."
            )

        if self.S is None:
            self.compute_sparameters()

        S = self.S
        kwargs = {}
        assert S is not None  # make type checker happy
        if fmt_str == "abs":
            S = abs(S)
        elif fmt_str == "real":
            S = np.real(S)
        elif fmt_str == "imag":
            S = np.imag(S)
        elif fmt_str == "phase":
            kwargs["phase"] = True

        return mw.visualize((S, self.port_map), **kwargs)

    def validate_component(self, component) -> None:
        optical_ports = [
            port for port in component.ports if port.port_type == "optical"
        ]
        if len(optical_ports) != 2:
            raise ValueError(
                "Component provided to MEOW does not have exactly 2 optical ports."
            )
        elif component.ports["o1"].orientation != 180:
            raise ValueError("Component port o1 does not face westward (180 deg).")
        elif component.ports["o2"].orientation != 0:
            raise ValueError("Component port o2 does not face eastward (0 deg).")

    def compute_mode(self, xs_num):
        return mw.compute_modes(self.css[xs_num], num_modes=self.num_modes)

    def compute_all_modes(self) -> None:
        self.modes_per_cell = []
        for cs in tqdm(self.css):
            modes_in_cs = mw.compute_modes(cs, num_modes=self.num_modes)
            self.modes_per_cell.append(modes_in_cs)

    def compute_sparameters(self) -> dict[str, np.ndarray]:
        """Returns Sparameters using EME."""
        if self.filepath.exists():
            if not self.overwrite:
                logger.info(f"Simulation loaded from {self.filepath!r}")
                sp = dict(np.load(self.filepath))

                def rename(p):
                    return p.replace("o1", "left").replace("o2", "right")

                sdict = {
                    tuple(rename(p) for p in k.split(",")): np.asarray(v)
                    for k, v in sp.items()
                }
                S, self.port_map = sax.sdense(sdict)
                self.S = np.asarray(S).view(np.ndarray)
                return sp
            else:
                self.filepath.unlink()

        start = time.time()

        self.compute_all_modes()

        self.S, self.port_map = mw.compute_s_matrix(self.modes_per_cell, self.cells)

        sdict = sax.sdict((self.S, self.port_map))

        def rename(p):
            return p.replace("left", "o1").replace("right", "o2")

        sp = {
            f"{rename(p1)},{rename(p2)}": np.asarray(v) for (p1, p2), v in sdict.items()
        }

        np.savez_compressed(self.filepath, **sp)

        end = time.time()

        self.sim_settings.update(compute_time_seconds=end - start)
        self.sim_settings.update(compute_time_minutes=(end - start) / 60)
        logger.info(f"Write simulation results to {self.filepath!r}")
        self.filepath_sim_settings.write_text(yaml.dump(self.sim_settings))
        logger.info(f"Write simulation settings to {self.filepath_sim_settings!r}")

        return sp


if __name__ == "__main__":
    c = gf.components.taper(length=10, width2=2)
    c.show()

    filtered_layer_stack = LayerStack(
        layers={
            k: get_layer_stack().layers[k]
            for k in (
                "slab90",
                "core",
                "box",
                "clad",
            )
        }
    )
    m = MEOW(
        component=c, layer_stack=filtered_layer_stack, wavelength=1.55, overwrite=False
    )
    m.plot_structure()
    print(len(m.cells))

    pprint.pprint(m.compute_sparameters())
