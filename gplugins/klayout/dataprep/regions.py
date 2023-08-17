import kfactory as kf
from gdsfactory.typings import LayerSpecs, Tuple
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
    """RegionCollection of region per layer.

    Args:
        gdspath: to read GDS from.
        cell_name: optional top cell name to edit (defaults to the top cell of the layout if None).
    """

    def __init__(self, gdspath, cell_name: str | None = None) -> None:
        lib = kf.kcell.KCLayout()
        lib.read(filename=str(gdspath))
        self.layout = lib.cell_by_name(cell_name) if cell_name else lib.top_cell()
        self.lib = lib
        self.regions = {}

    def __getitem__(self, layer: tuple[int, int]) -> Region:
        if len(layer) != 2:
            raise ValueError(f"Layer {layer} must be a tuple of two integers")

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
            raise ValueError(f"Layer {layer} must be a tuple of two integers")
        self.regions[layer] = region

    def write(
        self, gdspath, keep_original: bool = True, cellname: str = "out"
    ) -> kf.KCell:
        """Write gds.

        Args:
            gdspath: gdspath.
            keep_original: keep original cell.
            cellname: for top cell.
        """
        c = kf.KCell(cellname, self.lib)
        if keep_original:
            c.copy_tree(self.layout)
            c.flatten()

        for layer, region in self.regions.items():
            c.shapes(self.lib.layer(layer[0], layer[1])).clear()
            c.shapes(self.lib.layer(layer[0], layer[1])).insert(region)

        c.write(gdspath)
        return c

    def __delattr__(self, element) -> None:
        setattr(self, element, Region())

    def get_fill(
        self,
        region,
        size: Tuple[float, float],
        spacing: Tuple[float, float],
        fill_layers: LayerSpecs | None,
        fill_name: str = "fill",
        fill_cell_name: str = "fill_cell",
    ) -> kf.KCell:
        """Generates rectangular fill on a set of layers in the region specified.

        Args:
            region: to fill, usually the result of prior boolean operations.
            size: (x,y) dimensions of the fill cell (um).
            spacing: (x,y) spacing of the fill cell (um).
            fill_layers: layers of the fill cell (can be multiple).
            fill_name: fill cell name.
            fill_cell_name: fill cell name.
        """
        fill_layers = fill_layers or ()

        fill_cell = kf.KCell(fill_cell_name)
        for layer in fill_layers:
            layer = kf.kcl.layer(*layer)
            fill_cell << kf.cells.waveguide.waveguide(
                width=size[0], length=size[1], layer=layer
            )

        fc_index = fill_cell.cell_index()  # fill cell index
        fc_box = fill_cell.bbox().enlarged(spacing[0] / 2 * 1e3, spacing[1] / 2 * 1e3)
        fill_margin = kf.kdb.Point(0, 0)

        fill = kf.KCell(fill_name)
        return fill.fill_region(
            region, fc_index, fc_box, None, region, fill_margin, None
        )


if __name__ == "__main__":
    import gdsfactory as gf
    import kfactory as kf
    from gdsfactory.generic_tech import LAYER

    c = gf.Component()
    ring = c << gf.components.coupler_ring(cross_section=gf.cross_section.rib_conformal)
    gdspath = c.write_gds()
    # c.show()

    # floorplan = c << gf.components.bbox(ring.bbox, layer=l.FLOORPLAN)
    # gdspath = c.write_gds()

    d = RegionCollection(gdspath)
    d[LAYER.SLAB90] += 2
    d[LAYER.SLAB90] -= 2
    d[LAYER.SLAB90].smooth(1000)

    d.write("out.gds", keep_original=True)
    gf.show("out.gds")

    # d["SLAB150"] = d.WG - d.FLOORPLAN
    # fill_cell = d.get_fill(
    #     d.FLOORPLAN - d.WG, size=(0.1, 0.1), spacing=(0.1, 0.1), fill_layers=(l.WG,)
    # )
    # fill_cell.write("fill.gds")
