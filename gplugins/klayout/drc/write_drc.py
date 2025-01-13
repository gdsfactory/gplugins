"""Write DRC rule decks in KLayout.

More DRC examples:
- https://www.klayout.de/doc-qt5/about/drc_ref.html
- http://klayout.de/doc/manual/drc_basic.html
- https://github.com/usnistgov/SOEN-PDK/tree/master/tech/OLMAC
- https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr/tree/main/rules/klayout
"""

from __future__ import annotations

import pathlib
from dataclasses import asdict, is_dataclass

import gdsfactory as gf
from gdsfactory.install import get_klayout_path
from gdsfactory.typings import CrossSectionSpec, Layer, PathType

layer_name_to_min_width: dict[str, float]

valid_operations = {
    "|": "|",
    "&": "&",
    "-": "-",
    "^": "^",
    "or": "|",
    "and": "&",
    "not": "-",
    "xor": "^",
}


def get_drc_script_start(name, shortcut) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<klayout-macro>
 <description>{name} DRC</description>
 <version/>
 <category>drc</category>
 <prolog/>
 <epilog/>
 <doc/>
 <autorun>false</autorun>
 <autorun-early>false</autorun-early>
 <shortcut>{shortcut}</shortcut>
 <show-in-menu>true</show-in-menu>
 <group-name>drc_scripts</group-name>
 <menu-path>tools_menu.drc.end</menu-path>
 <interpreter>dsl</interpreter>
 <dsl-interpreter-name>drc-dsl-xml</dsl-interpreter-name>
 <text># {name} DRC

# Read about Klayout DRC scripts in the User Manual under "Design Rule Check (DRC)"
# Based on https://gdsfactory.github.io/gdsfactory/notebooks/_2_klayout.html#Klayout-DRC
# and https://gdsfactory.github.io/gdsfactory/api.html#klayout-drc

report("{name} DRC")
time_start = Time.now
"""


drc_script_end = r"""
time_end = Time.now
print "run time #{(time_end-time_start).round(3)} seconds \n"
</text>
</klayout-macro>
"""


def new_layers(**kwargs) -> str:
    """Returns a string with the new layers."""
    return "\n".join([f"{name} = input{layer}" for name, layer in kwargs.items()])


def derived_layer_sized(layer_new: str, layer_old: str, size: int | float) -> str:
    """Returns a derived layer operation of a layer by value."""
    return f"{layer_new} = {layer_old}.size({size})"


def derived_layer_boolean(
    layer_new: str, layer1: str, operation: str, layer2: str
) -> str:
    """Returns a derived layer operation of a layer by value."""
    if operation not in valid_operations:
        raise ValueError(
            f"operation {operation} not in {list(valid_operations.keys())}"
        )
    operation = valid_operations[operation]
    return f"{layer_new} = {layer1} {operation} {layer2}"


def size(layer: str, value: int | float, layer_out: str | None = None) -> str:
    """Returns a string with the sizing operation of a layer by value."""
    layer_out = layer_out or layer
    return f"{layer_out} = {layer}.size({value})"


def layer_or(layer_out: str, layer1: str, layer2: str) -> str:
    """Returns a string with the OR operation."""
    return f"{layer_out} = {layer1} | {layer2}"


def layer_not(layer_out: str, layer1: str, layer2: str) -> str:
    """Returns a string with the NOT operation."""
    return f"{layer_out} = {layer1} - {layer2}"


def layer_and(layer_out: str, layer1: str, layer2: str) -> str:
    """Returns a string with the AND operation."""
    return f"{layer_out} = {layer1} & {layer2}"


def check_not_inside(
    layer: str, not_inside: str, size: int | float | None = None
) -> str:
    """Checks for that a layer is not inside another layer.

    Args:
        layer: layer name.
        not_inside: layer name.
        size: optional layer size in um if float, dbu if int (nm).
    """
    if size is None:
        error = f"{layer} not inside {not_inside}"
        return f"{layer}.not_inside({not_inside}).output({error!r}, {error!r})"
    else:
        error = f"{layer} sized by {size} not inside {not_inside}"
        script = f"{layer}_sized = {layer}.size({size})\n "
        script += f"{layer}.not_inside({not_inside}).output({error!r}, {error!r})"
        return script


def output_layer(layer: str, output: tuple[int, int]) -> str:
    return f"{layer}.output({output[0]},{output[1]})"


def check_width(value: float | int, layer: str, angle_limit: float = 90.0) -> str:
    """Min feature size.

    Args:
        value: width in um if float, dbu if int (nm).
        layer: layer name.
        angle_limit: angle limit in degrees.
    """
    category = "width"
    error = f"{layer} {category} {value}um"
    return (
        f"{layer}.{category}({value}, angle_limit({angle_limit}))"
        f".output({error!r}, {error!r})"
    )


def check_space(value: float | int, layer: str, angle_limit: float = 90.0) -> str:
    """Min Space between shapes of layer.

    Args:
        value: width in um if float, dbu if int (nm).
        layer: layer name.
        angle_limit: angle limit in degrees.
    """
    category = "space"
    error = f"{layer} {category} {value}um"
    return (
        f"{layer}.{category}({value}, angle_limit({angle_limit}))"
        f".output({error!r}, {error!r})"
    )


def check_separation(value: float | int, layer1: str, layer2: str) -> str:
    """Min space between different layers.

    Args:
        value: width in um if float, dbu if int (nm).
        layer1: layer name.
        layer2: layer name.
    """
    error = f"min {layer1} {layer2} separation {value}um"
    return f"{layer1}.separation({layer2}, {value}).output({error!r}, {error!r})"


def check_enclosing(
    value: float | int, layer1: str, layer2: str, angle_limit: float = 90.0
) -> str:
    """Checks if layer1 encloses (is bigger than) layer2 by value.

    Args:
        value: width in um if float, dbu if int (nm).
        layer1: layer name.
        layer2: layer name.
        angle_limit: angle limit in degrees.

    """
    error = f"{layer1} enclosing {layer2} by {value}um"
    return (
        f"{layer1}.enclosing({layer2}, angle_limit({angle_limit}), {value})"
        f".output({error!r}, {error!r})"
    )


def check_area(layer: str, min_area_um2: float | int = 2.0) -> str:
    """Return script for min area checking.

    Args:
        layer: layer name.
        min_area_um2: min area in um2. int if dbu, float if um.

    """
    return f"""

min_{layer}_a = {min_area_um2}.um2
r_{layer}_a = {layer}.with_area(0, min_{layer}_a)
r_{layer}_a.output("{layer.upper()}_A: {layer} area &lt; min_{layer}_a um2")
"""


def check_density(
    layer: str = "metal1",
    layer_floorplan: str = "FLOORPLAN",
    min_density: float = 0.2,
    max_density: float = 0.8,
) -> str:
    """Return script to ensure density of layer is within min and max.

    based on https://github.com/klayoutmatthias/si4all

    """
    return f"""
min_density = {min_density}
max_density = {max_density}

area = {layer}.area
border_area = {layer_floorplan}.area
if border_area &gt;= 1.dbu * 1.dbu

  r_min_dens = polygon_layer
  r_max_dens = polygon_layer

  dens = area / border_area

  if dens &lt; min_density
    # copy border as min density marker
    r_min_dens = {layer_floorplan}
  end

  if dens &gt; max_density
    # copy border as max density marker
    r_max_dens = {layer_floorplan}
  end

  r_min_dens.output("{layer}_Xa: {layer} density below threshold of {min_density}")
  r_max_dens.output("{layer}: {layer} density above threshold of {max_density}")

end

"""


def connectivity_checks(
    WG_cross_sections: list[CrossSectionSpec], pin_widths: list[float] | float
) -> str:
    """Return script for photonic port connectivity check. Assumes the photonic port pins are inside the Component.

    Args:
        WG_cross_sections: list of waveguide layers to run check for.
        pin_widths: list of port pin widths or a single port pin width/
    """
    connectivity_check = ""
    for i, layer_name in enumerate(WG_cross_sections):
        layer = gf.pdk.get_cross_section(layer_name).width
        layer_name = gf.pdk.get_cross_section(layer_name).layer
        connectivity_check = connectivity_check.join(
            f"""{layer_name}_PIN2 = {layer_name}_PIN.sized(0.0).merged\n
{layer_name}_PIN2 = {layer_name}_PIN2.rectangles.without_area({layer} * {pin_widths if isinstance(pin_widths, float) else pin_widths[i]}) - {layer_name}_PIN2.rectangles.with_area({layer} * 2 * {pin_widths if isinstance(pin_widths, float) else pin_widths[i]})\n
{layer_name}_PIN2.output(\"port alignment error\")\n
{layer_name}_PIN2 = {layer_name}_PIN.sized(0.0).merged\n
{layer_name}_PIN2.non_rectangles.output(\"port width check\")\n\n"""
        )

    return connectivity_check


def write_layer_definition(layers: dict[str, Layer]) -> list[str]:
    """Returns layers definition script for KLayout.

    Args:
        layers: layer definitions can be dict, dataclass or pydantic BaseModel.
    """
    layers = asdict(layers) if is_dataclass(layers) else layers
    out = []
    for layer in layers:
        layer_name = str(layer)
        layer_tuple = tuple(layer)
        out += [f"{layer_name} = input({layer_tuple[0]}, {layer_tuple[1]})"]
    return out


def get_drc_script(
    rules: list[str],
    layers: dict[str, Layer] | None = None,
    mode: str = "tiled",
    threads: int = 4,
    tile_size: int = 500,
    tile_borders: int | None = None,
) -> str:
    """Returns drc_check_deck for KLayout.

    based on https://github.com/klayoutmatthias/si4all

    Args:
        rules: list of rules.
        layers: layer definitions can be dict, dataclass or pydantic BaseModel.
        mode: tiled, default or deep (hierarchical).
        threads: number of threads.
        tile_size: in um for tile mode.
        tile_borders: sides for each. Defaults None to automatic.

    modes:

    - default
        - flat polygon handling
        - single threaded
        - no overhead
        - use for small layouts
        - no side effects
    - tiled
        - need to optimize tile size (maybe 500x500um). Works of each tile individually.
        - finite lookup range
        - output is flat
        - multithreading enable
        - scales with number of CPUs
        - scales with layout area
        - predictable runtime and and memory footprint
    - deep
        - hierarchical mode
        - preserves hierarchy in many cases
        - does not predictably scale with number of CPUs
        - experimental (either very fast of very slow)
        - mainly used for LVS layer preparation

    Klayout supports to switch modes and tile parameters during execution.
    However this function does support switching modes yet.
    """
    script = ""
    if mode == "tiled":
        script += f"""
threads({threads})
tiles({tile_size})
"""
        if tile_borders:
            script += f"""
tile_borders({tile_borders})
"""
    elif mode == "deep":
        script += """
deep
"""
    script += "\n"
    if layers:
        script += "\n".join(write_layer_definition(layers=layers))
    script += "\n\n"
    script += "\n".join(rules)
    return script


modes = ["tiled", "default", "deep"]


def write_drc_deck_macro(
    rules: list[str],
    layers: dict[str, Layer] | None = None,
    name: str = "generic",
    filepath: PathType | None = None,
    shortcut: str = "Ctrl+Shift+D",
    mode: str = "tiled",
    threads: int = 4,
    tile_size: int = 500,
    tile_borders: int | None = None,
) -> str:
    """Write KLayout DRC macro.

    You can customize the shortcut to run the DRC macro from the Klayout GUI.

    Args:
        rules: list of rules.
        layers: layer definitions can be dict or dataclass.
        name: drc rule deck name.
        filepath: Optional macro path (defaults to .klayout/drc/name.lydrc).
        shortcut: to run macro from KLayout GUI.
        mode: tiled, default or deep (hierarchical).
        threads: number of threads.
        tile_size: in um for tile mode.
        tile_borders: sides for each. Defaults None to automatic.

    .. code::

        import gdsfactory as gf
        from gplugins.klayout.drc.write_drc import (
            write_drc_deck_macro,
            check_enclosing,
            check_width,
            check_space,
            check_separation,
            check_area,
            check_density,
        )
        from gdsfactory.generic_tech import LAYER
        rules = [
            check_width(layer="WG", value=0.2),
            check_space(layer="WG", value=0.2),
            check_separation(layer1="HEATER", layer2="M1", value=1.0),
            check_enclosing(layer1="VIAC", layer2="M1", value=0.2),
            check_area(layer="WG", min_area_um2=0.05),
            check_density(
                layer="WG", layer_floorplan="FLOORPLAN", min_density=0.5, max_density=0.6
            ),
            check_not_inside(layer="VIAC", not_inside="NPP"),
        ]

        drc_check_deck = write_drc_deck_macro(rules=rules, layers=LAYER, mode="tiled")
        print(drc_check_deck)

    """
    if mode not in modes:
        raise ValueError(f"{mode!r} not in {modes}")

    script = get_drc_script_start(name=name, shortcut=shortcut)

    script += get_drc_script(
        rules=rules,
        layers=layers,
        threads=threads,
        tile_size=tile_size,
        tile_borders=tile_borders,
        mode=mode,
    )

    script += drc_script_end
    filepath = filepath or get_klayout_path() / "drc" / f"{name}.lydrc"
    filepath = pathlib.Path(filepath)
    dirpath = filepath.parent
    dirpath.mkdir(parents=True, exist_ok=True)
    filepath = pathlib.Path(filepath)
    filepath.write_text(script, encoding="UTF-8")
    print(f"Wrote DRC deck to {str(filepath)!r} with shortcut {shortcut!r}")
    return script


if __name__ == "__main__":
    from gdsfactory.generic_tech import LAYER

    rules = [
        derived_layer_boolean("TRENCH", "SLAB90", "-", "WG"),
        check_width(layer="WG", value=0.2),
        check_space(layer="WG", value=0.2),
        check_width(layer="M1", value=0.2),
        check_space(layer="M1", value=0.2),
        check_width(layer="M2", value=1.0),
        check_space(layer="M2", value=1.0),
        check_width(layer="M3", value=1.0),
        check_space(layer="M3", value=1.0),
        check_separation(layer1="HEATER", layer2="M1", value=1.0),
        check_enclosing(layer1="VIAC", layer2="M1", value=0.2),
        check_area(layer="WG", min_area_um2=0.05),
        check_not_inside(layer="VIAC", not_inside="NPP"),
        new_layers(TRENCHES=(2, 33)),
        size(layer="WG", value=1000),
        output_layer("TRENCH", (2, 33)),
    ]

    layers = LAYER
    drc_check_deck = write_drc_deck_macro(rules=rules, layers=layers, mode="tiled")
    script = get_drc_script(rules=rules, layers=layers, mode="tiled")
    print(script)
