import uuid
from typing import Any

import gdsfactory as gf
import kfactory as kf
from gdsfactory.component import GDSDIR_TEMP
from gdsfactory.typings import PathType
from kfactory import kdb


def size(region: kdb.Region, offset: float, dbu=1e3) -> kdb.Region:
    return region.dup().size(int(offset * dbu))


def boolean_or(region1: kdb.Region, region2: kdb.Region) -> kdb.Region:
    return region1.__or__(region2)


def boolean_not(region1: kdb.Region, region2: kdb.Region) -> kdb.Region:
    return kdb.Region.__sub__(region1, region2)


def copy(region: kdb.Region) -> kdb.Region:
    return region.dup()


def _is_layer(value: any) -> bool:
    try:
        layer, datatype = value
    except Exception:
        return False
    return isinstance(layer, int) and isinstance(datatype, int)


def _assert_is_layer(value: any) -> None:
    if not _is_layer(value):
        raise ValueError(f"Layer must be a tuple of two integers. Got {value!r}")


class Region(kdb.Region):
    def __iadd__(self, offset) -> kdb.Region:
        """Adds an offset to the layer."""
        return size(self, offset)

    def __isub__(self, offset) -> kdb.Region:
        """Adds an offset to the layer."""
        return size(self, -offset)

    def __add__(self, element) -> kdb.Region:
        """Adds an element to the region."""
        if isinstance(element, float | int):
            return size(self, element)

        elif isinstance(element, kdb.Region):
            return boolean_or(self, element)
        else:
            raise ValueError(f"Cannot add type {type(element)} to region")

    def __sub__(self, element: float | int | kdb.Region) -> kdb.Region | None:
        """Subtracts an element from the region."""
        if isinstance(element, float | int):
            return size(self, -element)

        elif isinstance(element, kdb.Region):
            return boolean_not(self, element)

    def copy(self) -> kdb.Region:
        return self.dup()


class RegionCollection:
    """A RegionCollection can load a GDS file and make layer operations on it.

    It is a dictionary of layers with Region objects.

    Args:
        gdspath: to read GDS from.
        cell_name: optional top cell name to edit (defaults to the top cell of the layout if None).

    .. code::

        d = RegionCollection(gdspath)
        d[LAYER.SLAB90] += 2 # grow slab by 2um
        d[LAYER.SLAB90] -= 2 # shrink slab by 2um
        d[LAYER.SLAB90].smooth(1000) # smooth slab by 1um points
        d[LAYER.DEEP_ETCH] = d[LAYER.SLAB90] # copy layer
        d[LAYER.SLAB90].clear() # clear slab150
        d.write_gds("out.gds", keep_original=True)

    """

    def __init__(self, gdspath: PathType, cell_name: str | None = None) -> None:
        """Initializes the RegionCollection."""
        lib = kf.KCLayout(str(gdspath))
        lib.read(filename=str(gdspath))
        self.layout = lib.cell_by_name(cell_name) if cell_name else lib.top_cell()
        self.lib = lib
        self.regions: dict[tuple[int, int], Region] = {}
        self.cell = lib[lib.top_cell().cell_index()]

    def __getitem__(self, layer: tuple[int, int]) -> Region:
        """Gets a layer from the collection."""
        _assert_is_layer(layer)

        if layer in self.regions:
            return self.regions[layer]
        region = Region()
        layer_index = self.lib.layer(layer[0], layer[1])
        region.insert(self.layout.begin_shapes_rec(layer_index))
        region.merge()
        self.regions[layer] = region
        return region

    def __setitem__(self, layer: tuple[int, int], region: Region) -> None:
        """Sets a layer in the collection."""
        _assert_is_layer(layer)
        self.regions[layer] = region

    def __contains__(self, item: tuple[int, int]) -> bool:
        """Checks if the layout contains the given layer."""
        _assert_is_layer(item)
        layer, datatype = item
        return self.lib.find_layer(layer, datatype) is not None

    def write_gds(
        self,
        gdspath: PathType = GDSDIR_TEMP / "out.gds",
        top_cell_name: str | None = None,
        keep_original: bool = True,
        save_options: kdb.SaveLayoutOptions | None = None,
    ) -> None:
        """Write gds.

        Args:
            gdspath: output gds path.
            top_cell_name: name to use for the top cell of the output library.
            keep_original: if True, keeps all original cells (and hierarchy, to the extent possible) in the output. If false, only explicitly defined layers are output.
            save_options: if provided, specified KLayout SaveLayoutOptions are used when writing the GDS.
        """
        # use the working top cell name if not provided
        if top_cell_name is None:
            top_cell_name = self.layout.name
        c = self.get_kcell(cellname=top_cell_name, keep_original=keep_original)
        if save_options:
            c.write(gdspath, save_options=save_options)
        else:
            c.write(gdspath)

    def plot(self) -> kf.KCell:
        """Plot regions."""
        return self.cell

    def get_kcell(
        self, keep_original: bool = True, cellname: str = "Unnamed"
    ) -> kf.KCell:
        """Returns kfactory cell.

        Args:
            keep_original: keep original cell.
            cellname: for top cell.
        """
        if cellname == "Unnamed":
            uid = str(uuid.uuid4())[:8]
            cellname += f"_{uid}"

        output_lib = kf.KCLayout("output")
        c = kf.KCell(cellname, output_lib)
        if keep_original:
            c.copy_tree(self.layout)
            for layer in self.regions:
                layer_id = output_lib.layer(layer[0], layer[1])
                output_lib.layout.clear_layer(layer_id)

        for layer, region in self.regions.items():
            c.shapes(output_lib.layer(layer[0], layer[1])).insert(region)
        return c

    def show(self, gdspath: PathType = GDSDIR_TEMP / "out.gds", **kwargs: Any) -> None:
        """Show gds in klayout.

        Args:
            gdspath: gdspath.
            kwargs: keyword arguments.

        Keyword Args:
            keep_original: keep original cell.
            cellname: for top cell.
        """
        self.write_gds(**kwargs)
        gf.show(gdspath)

    def __delattr__(self, element) -> None:
        """Deletes a layer from the collection."""
        setattr(self, element, Region())


if __name__ == "__main__":
    import kfactory as kf
    from gdsfactory.generic_tech import LAYER

    c = gf.Component()
    ring = c << gf.components.coupler_ring()
    floorplan = c << gf.components.bbox(ring.bbox, layer=LAYER.FLOORPLAN)

    # ring = c << gf.components.coupler_ring()
    gdspath = c.write_gds()
    c.show()

    # gdspath = c.write_gds()

    d = RegionCollection(gdspath)
    d[LAYER.N] = d[LAYER.WG].copy()
    # d[LAYER.WG].clear()

    # d[LAYER.SLAB90] += 2  # grow slab by 2um
    # d[LAYER.SLAB90] -= 2  # shrink slab by 2um
    # d[LAYER.SLAB90].smooth(1000)  # smooth slab by 1um points
    # d[LAYER.DEEP_ETCH] = d[LAYER.SLAB90]  # copy layer
    # d[LAYER.SLAB90].clear()  # clear slab150

    d.write_gds("out.gds", keep_original=True)
    gf.show("out.gds")
    d.show()
