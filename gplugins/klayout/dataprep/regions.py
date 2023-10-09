import uuid

import gdsfactory as gf
import kfactory as kf
from gdsfactory.component import GDSDIR_TEMP
from gdsfactory.typings import LayerSpecs, PathType, Tuple
from kfactory import kdb


def size(region: kdb.Region, offset: float, dbu=1e3) -> kdb.Region:
    return region.dup().size(int(offset * dbu))


def boolean_or(region1: kdb.Region, region2: kdb.Region) -> kdb.Region:
    return region1.__or__(region2)


def boolean_not(region1: kdb.Region, region2: kdb.Region) -> kdb.Region:
    return kdb.Region.__sub__(region1, region2)


def copy(region: kdb.Region) -> kdb.Region:
    return region.dup()


class Region(kdb.Region):
    def __iadd__(self, offset) -> kdb.Region:
        """Adds an offset to the layer."""
        return size(self, offset)

    def __isub__(self, offset) -> kdb.Region:
        """Adds an offset to the layer."""
        return size(self, -offset)

    def __add__(self, element) -> kdb.Region:
        if isinstance(element, float | int):
            return size(self, element)

        elif isinstance(element, kdb.Region):
            return boolean_or(self, element)
        else:
            raise ValueError(f"Cannot add type {type(element)} to region")

    def __sub__(self, element) -> kdb.Region | None:
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

    def __init__(self, gdspath, cell_name: str | None = None) -> None:
        lib = kf.kcell.KCLayout(str(gdspath))
        lib.read(filename=str(gdspath))
        self.layout = lib.cell_by_name(cell_name) if cell_name else lib.top_cell()
        self.lib = lib
        self.regions = {}

    def __getitem__(self, layer: tuple[int, int]) -> Region:
        if len(layer) != 2:
            raise ValueError(f"Layer must be a tuple of two integers. Got {layer!r}")

        if layer in self.regions:
            return self.regions[layer]
        region = Region()
        layer_index = self.lib.layer(layer[0], layer[1])
        region.insert(self.layout.begin_shapes_rec(layer_index))
        region.merge()
        self.regions[layer] = region
        return region

    def __setitem__(self, layer: tuple[int, int], region: Region) -> None:
        if len(layer) != 2:
            raise ValueError(f"Layer must be a tuple of two integers. Got {layer!r}")
        self.regions[layer] = region

    def write_gds(self, gdspath: PathType = GDSDIR_TEMP / "out.gds", **kwargs) -> None:
        """Write gds.

        Args:
            gdspath: gdspath.

        Keyword Args:
            keep_original: keep original cell.
            cellname: for top cell.
        """
        c = self.get_kcell(**kwargs)
        c.write(gdspath)

    def plot(self, **kwargs):
        """Plot regions."""
        gdspath = GDSDIR_TEMP / "out.gds"
        self.write_gds(gdspath=gdspath, **kwargs)
        gf.clear_cache()
        c = gf.import_gds(gdspath)
        return c.plot()

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
        c = kf.KCell(cellname, self.lib)
        if keep_original:
            c.copy_tree(self.layout)
            c.flatten()

        for layer, region in self.regions.items():
            c.shapes(self.lib.layer(layer[0], layer[1])).clear()
            c.shapes(self.lib.layer(layer[0], layer[1])).insert(region)
        return c

    def show(self, gdspath: PathType = GDSDIR_TEMP / "out.gds", **kwargs) -> None:
        """Show gds in klayout.

        Args:
            gdspath: gdspath.

        Keyword Args:
            keep_original: keep original cell.
            cellname: for top cell.
        """
        self.write_gds(**kwargs)
        gf.show(gdspath)

    def __delattr__(self, element) -> None:
        setattr(self, element, Region())

    def get_fill(
        self,
        region,
        size: Tuple[float, float],
        spacing: Tuple[float, float],
        fill_layers: LayerSpecs | None,
        cellname: str = "Unamed",
        fill_cellname: str = "Unnamed_fill",
    ) -> kf.KCell:
        """Generates rectangular fill on a set of layers in the region specified.

        Args:
            region: to fill, usually the result of prior boolean operations.
            size: (x,y) dimensions of the fill cell (um).
            spacing: (x,y) spacing of the fill cell (um).
            fill_layers: layers of the fill cell (can be multiple).
            fill_name: fill cell name.
            fill_cellname: fill cell name.
        """
        if fill_cellname == "Unnamed_fill":
            uid = str(uuid.uuid4())[:8]
            fill_cellname += f"_{uid}"

        if cellname == "Unnamed":
            uid = str(uuid.uuid4())[:8]
            cellname += f"_{uid}"

        fill_layers = fill_layers or ()

        fill_cell = kf.KCell(fill_cellname)
        for layer in fill_layers:
            layer = kf.kcl.layer(*layer)
            _ = fill_cell << kf.cells.straight.straight(
                width=size[0], length=size[1], layer=layer
            )

        fc_index = fill_cell.cell_index()  # fill cell index
        fc_box = fill_cell.bbox().enlarged(spacing[0] / 2 * 1e3, spacing[1] / 2 * 1e3)
        fill_margin = kf.kdb.Point(0, 0)

        fill = kf.KCell(cellname)
        return fill.fill_region(
            region, fc_index, fc_box, None, region, fill_margin, None
        )


if __name__ == "__main__":
    import kfactory as kf
    from gdsfactory.generic_tech import LAYER

    c = gf.Component()
    ring = c << gf.components.coupler_ring(
        # cross_section=gf.cross_section.rib_conformal, radius=20
    )
    # ring = c << gf.components.coupler_ring()
    gdspath = c.write_gds()
    c.show()

    # floorplan = c << gf.components.bbox(ring.bbox, layer=l.FLOORPLAN)
    # gdspath = c.write_gds()

    d = RegionCollection(gdspath)
    d[LAYER.N] = d[LAYER.WG].copy()
    # d[LAYER.WG].clear()

    # d[LAYER.SLAB90] += 2  # grow slab by 2um
    # d[LAYER.SLAB90] -= 2  # shrink slab by 2um
    # d[LAYER.SLAB90].smooth(1000)  # smooth slab by 1um points
    # d[LAYER.DEEP_ETCH] = d[LAYER.SLAB90]  # copy layer
    # d[LAYER.SLAB90].clear()  # clear slab150

    # d.write_gds("out.gds", keep_original=True)
    # gf.show("out.gds")
    d.show()

    # d["SLAB150"] = d.WG - d.FLOORPLAN
    fill_cell = d.get_fill(
        d[LAYER.FLOORPLAN] - d[LAYER.WG],
        size=(0.1, 0.1),
        spacing=(0.1, 0.1),
        fill_layers=(LAYER.WG,),
    )
    c = d.get_kcell()
    _ = c << fill_cell
    c.write("fill.gds")
