from pathlib import Path

import gdsfactory as gf
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from gdsfactory.config import get_number_of_cores
from gdsfactory.typings import Layer
from klayout.db import Box, Layout, Polygon, TileOutputReceiver, TilingProcessor

from gplugins.typings import NDArrayF


class DensityOutputReceiver(TileOutputReceiver):
    def __init__(self) -> None:
        """Output receiver for density data."""
        super().__init__()
        self.data: list[tuple[float, float, float]] = []

    def put(
        self, ix: int, iy: int, tile: Box, obj: float, dbu: float, clip: bool
    ) -> None:
        """Put density data into the receiver.

        Arguments:
            ix: index position of the tile along the x-axis in a grid of tiles.
            iy: index position of the tile along the y-axis in a grid of tiles.
            tile: x-y boundaries of the tile (Klayout Box object)
            obj: density value (for this task)
            dbu: database units per user unit.
            clip: flag indicating if the tile has been clipped.

        Add data as:
            (tile_center_x, tile_center_y, density)
        """
        self.data.append(
            (
                (tile.left * dbu + tile.right * dbu) / 2,
                (tile.bottom * dbu + tile.top * dbu) / 2,
                obj,
            )
        )


def calculate_density(
    gdspath: Path,
    layer: tuple[int, int],
    cellname: str | None = None,
    tile_size: tuple[float, float] = (200, 200),
    threads: int = get_number_of_cores(),
) -> list[tuple[float, float, float]]:
    """Calculates the density of a given layer in a GDS file and returns the density data.

    Process a GDS file to calculate the density of a specified layer. It divides the layout into tiles of a specified size, computes the density of the layer within each tile, and returns a (x,y,density) list of density data. The density is calculated as the area of the layer within a tile divided by the total area of the tile.

    Args:
        gdspath (Path): The path to the GDS file.
        layer (Layer): The layer for which to calculate density (layer number, datatype).
        cellname (str | None, optional): The name of the cell to consider for the density heatmap. Defaults to all top cells.
        tile_size (Tuple, optional): The size of the tiles (width, height) in database units. Defaults to (200, 200).
        threads (int, optional): The number of threads to use for processing. Defaults to total number of threads.

    Returns:
        list: A list of tuples, each containing the center x-coordinate, center y-coordinate, and density of each tile.
    """
    # Validate input
    (xmin, ymin), (xmax, ymax) = get_gds_bbox(
        gdspath=gdspath, layer=layer, cellname=cellname
    )
    if tile_size[0] > xmax - xmin and tile_size[1] > ymax - ymin:
        raise ValueError(
            f"Too large tile size {tile_size} for bbox {(xmin, ymin), (xmax, ymax)}: reduce tile size (and merge later if needed)."
        )

    # Get GDS
    ly = Layout()
    ly.read(str(gdspath))
    li = ly.layer(layer[0], layer[1])
    si = ly.top_cell().begin_shapes_rec(li)

    # Setup and execute task
    tp = TilingProcessor()
    out_receiver = DensityOutputReceiver()
    tp.output("res", out_receiver)
    tp.input("input", si)
    tp.dbu = ly.dbu
    tp.tile_size(tile_size[0], tile_size[1])
    tp.threads = threads
    tp.queue(
        "_tile && (var d = to_f(input.area(_tile.bbox)) / to_f(_tile.bbox.area); _output(res, d))"
    )
    tp.execute("Density map")

    return out_receiver.data


def get_layer_polygons(
    gdspath: Path, layer: Layer, cellname: str | None = None
) -> dict[tuple[int, int] | str | int, list[Polygon]]:
    """Extracts polygons from a specified layer in a GDS file using gdsfactory.

    Args:
        gdspath (Path): The path to the GDS file.
        layer (Layer): The layer from which to extract polygons (layer number, datatype).
        cellname (str | None, optional): The name of the cell to consider for the density heatmap. Defaults to all top cells.

    Returns:
        list: A list of polygons from the specified layer.
    """
    # Load the layout and initialize an empty list to hold polygon coordinates
    component = gf.import_gds(gdspath=gdspath, cellname=cellname)
    component_layer = component.extract(layers=[layer])
    return component_layer.get_polygons()


def get_gds_bbox(
    gdspath: Path,
    layer: Layer | None = None,
    cellname: str | None = None,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Calculates the bounding box of the entire GDS file using gdsfactory.

    Args:
        gdspath (Path): The path to the GDS file.
        layer (Layer): if not None, only consider the bbox of that specific layer
        cellname (str | None, optional): The name of the cell to consider for the bounding box. Defaults to all top cells.

    Returns:
        tuple: ((xmin,ymin),(xmax,ymax))
    """
    component = gf.import_gds(gdspath, cellname=cellname)
    if layer is not None:
        component = component.extract(layers=[layer])
    return (component.xmin, component.ymin), (component.xmax, component.ymax)


def extend_grid_and_density_to_bbox(
    x: NDArrayF,
    y: NDArrayF,
    density: NDArrayF,
    bbox: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[NDArrayF, NDArrayF, NDArrayF]:
    """Extends the grid and pads the density arrays with zeros to cover the entire bounding box.

    Args:
        x (NDArrayF): Current x coordinates.
        y (NDArrayF): Current y coordinates.
        density (NDArrayF): Density values corresponding to the x and y coordinates.
        bbox (tuple): Bounding box specified as ((xmin, ymin), (xmax, ymax)).

    Returns:
        tuple: Updated unique_x, unique_y, x, y, and density arrays.
    """
    (xmin, ymin), (xmax, ymax) = bbox

    unique_x = np.unique(x)
    unique_y = np.unique(y)

    x_spacing = unique_x[1] - unique_x[0]
    y_spacing = unique_y[1] - unique_y[0]

    # Extend unique_x and unique_y to cover the full bbox range
    while unique_x[0] > xmin + x_spacing / 2:
        unique_x = np.insert(unique_x, 0, unique_x[0] - x_spacing)
    while unique_x[-1] < xmax - x_spacing / 2:
        unique_x = np.append(unique_x, unique_x[-1] + x_spacing)
    while unique_y[0] > ymin + y_spacing / 2:
        unique_y = np.insert(unique_y, 0, unique_y[0] - y_spacing)
    while unique_y[-1] < ymax - y_spacing / 2:
        unique_y = np.append(unique_y, unique_y[-1] + y_spacing)

    # Generate all combinations of new x and y coordinates
    new_x, new_y = np.meshgrid(unique_x, unique_y)
    new_x = new_x.flatten()
    new_y = new_y.flatten()

    # Filter out the original x, y pairs
    original_xy = set(zip(x, y))
    new_xy = set(zip(new_x, new_y)) - original_xy

    # Extend x, y, and density arrays with new combinations
    x_extension, y_extension = zip(*new_xy) if new_xy else ([], [])
    density_extension = [0] * len(x_extension)

    # Update x, y, and density arrays with extensions
    x = np.concatenate((x, np.array(x_extension)))
    y = np.concatenate((y, np.array(y_extension)))
    density = np.concatenate((density, np.array(density_extension)))

    return x, y, density


def density_data_to_meshgrid(
    density_data: list[tuple[float, float, float]],
    bbox: tuple[tuple[float, float], tuple[float, float]] | None = None,
) -> tuple[NDArrayF, NDArrayF, NDArrayF]:
    """Converts density data into a meshgrid for plotting.

    Args:
        density_data (List[Tuple[float, float, float]]): A list of tuples, each containing the x-coordinate, y-coordinate, and density value. Output of "calculate_density"
        bbox: ((xmin, ymin), (xmax, ymax)). If None, the processed layer is not padded to the full gds size.

    Returns:
        Tuple[NDArrayF, NDArrayF, NDArrayF]: Three 2D numpy arrays representing the X coordinates, Y coordinates, and density values on a meshgrid.
    """
    # Extract x, y, and density values
    x, y, density = zip(*density_data)

    # Convert to numpy arrays for plotting
    x_array = np.array(x)
    y_array = np.array(y)
    density_array = np.array(density)

    if bbox is not None:
        x_array, y_array, density_array = extend_grid_and_density_to_bbox(
            x_array, y_array, density_array, bbox
        )

    # Determine unique x and y coordinates for grid
    unique_x = np.unique(x_array)
    unique_y = np.unique(y_array)

    # Create a grid for plotting
    Xi, Yi = np.meshgrid(unique_x, unique_y)

    # Map density values to the grid
    Zi = np.zeros_like(Xi)
    for i, (x_val, y_val) in enumerate(zip(x_array, y_array)):
        xi_index = np.where(unique_x == x_val)[0][0]
        yi_index = np.where(unique_y == y_val)[0][0]
        Zi[yi_index, xi_index] = density_array[i]

    return Xi, Yi, Zi


def estimate_weighted_global_density(
    Xi: NDArrayF,
    Yi: NDArrayF,
    Zi: NDArrayF,
    bbox: tuple[tuple[float, float], tuple[float, float]] | None = None,
) -> float:
    """Calculates the mean density within a specified bounding box or overall if bbox is None.

    Args:
        Xi (NDArrayF): 2D array of X coordinates.
        Yi (NDArrayF): 2D array of Y coordinates.
        Zi (NDArrayF): 2D array of density values.
        bbox (tuple[tuple[float, float], tuple[float, float]], optional): Bounding box specified as ((xmin, ymin), (xmax, ymax)). Defaults to None.

    Returns:
        float: Mean density value.
    """
    (xmin, ymin), (xmax, ymax) = bbox

    total_weighted_density = 0
    total_weight = 0

    # Calculate the spacing between grid points
    xi_spacing = np.unique(np.diff(Xi[0, :]))[0]
    yi_spacing = np.unique(np.diff(Yi[:, 0]))[0]

    # Calculate half spacing for overlap calculation
    half_xi_spacing = xi_spacing / 2
    half_yi_spacing = yi_spacing / 2

    # Iterate over each grid point to calculate weighted density
    for i in range(Xi.shape[0]):
        for j in range(Xi.shape[1]):
            # Calculate the center of each tile
            x_center = Xi[i, j]
            y_center = Yi[i, j]

            # Calculate the overlap between the bbox and the tile
            x_overlap = max(
                0,
                min(x_center + half_xi_spacing, xmax)
                - max(x_center - half_xi_spacing, xmin),
            )
            y_overlap = max(
                0,
                min(y_center + half_yi_spacing, ymax)
                - max(y_center - half_yi_spacing, ymin),
            )
            overlap_area = x_overlap * y_overlap

            # Calculate the weighted density
            if overlap_area > 0:
                total_weighted_density += Zi[i, j] * overlap_area
                total_weight += overlap_area

    # Calculate the weighted average density
    if total_weight > 0:
        weighted_average_density = total_weighted_density / total_weight
    else:
        weighted_average_density = 0

    return weighted_average_density


def plot_density_heatmap(
    gdspath: Path,
    layer: Layer,
    cellname: str | None = None,
    tile_size: tuple = (200, 200),
    threads: int = get_number_of_cores(),
    cmap=cm.Reds,
    title: str | None = None,
    visualize_with_full_gds: bool = True,
    visualize_polygons: bool = False,
) -> None:
    """Generates and displays a heatmap visualization representing the density distribution across a specified layer of a GDS file. The heatmap is constructed using the density data calculated for each tile within the layer.

    Args:
        gdspath (Path): The path to the GDS file for which the density heatmap is to be plotted.
        layer (Layer): The specific layer within the GDS file for which the density heatmap is to be generated.
        cellname (str | None, optional): The name of the cell to consider for the density heatmap. Defaults to all top cells.
        tile_size (Tuple, optional): The dimensions (width, height) of each tile, in database units, used for density calculation. Defaults to (200, 200).
        threads (int, optional): The number of threads to utilize for processing the density calculations. Defaults to the total number of threads.
        cmap (Colormap, optional): The matplotlib colormap to use for the heatmap. Defaults to cm.Reds.
        title (str | None, optional): The title for the heatmap plot. If None, a default title is generated based on layer and tile size. Defaults to None.
        visualize_with_full_gds (bool, optional): Flag indicating whether to consider the full extent of the GDS file for plotting. Defaults to True.
        visualize_polygons (bool, optional): Flag indicating whether to overlay the actual layer polygons on top of the heatmap for reference. Defaults to False.
    """
    density_data = calculate_density(
        gdspath=gdspath,
        cellname=cellname,
        layer=layer,
        tile_size=tile_size,
        threads=threads,
    )

    Xi, Yi, Zi = density_data_to_meshgrid(
        density_data=density_data,
        bbox=get_gds_bbox(gdspath, cellname=cellname)
        if visualize_with_full_gds
        else None,
    )

    # Plot the heatmap
    plt.figure(figsize=(10, 8))
    plt.pcolormesh(Xi, Yi, Zi, shading="auto", cmap=cmap, alpha=0.5, edgecolor="k")
    for i, val in enumerate(Zi.flatten()):
        plt.text(
            Xi.flatten()[i],
            Yi.flatten()[i],
            f"{val * 100:2.0f}%",
            ha="center",
            va="center",
            fontsize=12,
            fontweight="bold",
        )
    if visualize_polygons:
        polygons = get_layer_polygons(gdspath=gdspath, layer=layer)
        for polygon in polygons:
            x, y = polygon[:, 0], polygon[:, 1]
            plt.fill(x, y, fill=False, edgecolor="r", hatch="/", linewidth=2)
    if visualize_with_full_gds:
        (xmin, ymin), (xmax, ymax) = get_gds_bbox(gdspath, cellname=cellname)
        plt.plot(
            [xmin, xmax, xmax, xmin, xmin],
            [ymin, ymin, ymax, ymax, ymin],
            "r--",
            linewidth=2,
            label="Full GDS Extent",
        )
    plt.colorbar(label="Density")
    plt.xlabel("X (um)")
    plt.ylabel("Y (um)")
    if visualize_with_full_gds:
        estimate = estimate_weighted_global_density(
            Xi, Yi, Zi, bbox=get_gds_bbox(gdspath, cellname=cellname)
        )
        plt.title(
            title
            or f"Layer: {layer}, tile size: {tile_size}, total density ~{estimate * 100:1.2f}%"
        )
    else:
        plt.title(title or f"Layer: {layer}, tile size: {tile_size}, layer bbox only")
    plt.show()


if __name__ == "__main__":

    @gf.cell
    def component_test_density1():
        c = gf.Component("density_test1")
        large_rect = c << gf.components.rectangle(size=(100, 150), layer=(1, 0))
        small_rect = c << gf.components.rectangle(size=(50, 50), layer=(2, 0))
        small_rect.x += 10
        small_rect.y += 10
        small_rect2 = c << gf.components.rectangle(size=(25, 25), layer=(2, 0))
        small_rect2.ymax = 100 - small_rect2.ysize
        small_rect2.xmax = large_rect.xmax - small_rect2.xsize
        # c.write_gds(PATH.test_data / "test_gds_density1.gds")
        return c

    test_component = component_test_density1()
    test_component.write_gds("./test_gds_density1.gds")

    test_component.show()

    plot_density_heatmap(
        gdspath="./test_gds_density1.gds",
        layer=(2, 0),
        tile_size=(20, 20),
        visualize_with_full_gds=True,
        visualize_polygons=True,
    )
