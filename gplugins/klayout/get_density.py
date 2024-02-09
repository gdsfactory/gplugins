from pathlib import Path

import gdsfactory as gf
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from gdsfactory.config import get_number_of_cores
from gdsfactory.typings import Layer
from klayout.db import Layout, TileOutputReceiver, TilingProcessor


class DensityOutputReceiver(TileOutputReceiver):
    def __init__(self):
        super().__init__()
        self.data = []

    def put(self, ix, iy, tile, obj, dbu, clip):
        """
        Arguments:
            ix: index position of the tile along the x-axis in a grid of tiles.
            iy: index position of the tile along the y-axis in a grid of tiles.
            tile: x-y boundaries of the tile (Klayout Box object)
            obj: density value (for this task)
            dbu: database units per user unit.
            clip: flag indicating if the tile has been clipped
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
    layer: Layer,
    tile_size: tuple = (200, 200),
    threads: int = get_number_of_cores(),
):
    """
    Calculates the density of a given layer in a GDS file and returns the density data.

    Process a GDS file to calculate the density of a specified layer. It divides the layout into tiles of a specified size, computes the density of the layer within each tile, and returns a (x,y,density) list of density data. The density is calculated as the area of the layer within a tile divided by the total area of the tile.

    Args:
        gdspath (Path): The path to the GDS file.
        layer (Layer): The layer for which to calculate density (layer number, datatype).
        tile_size (Tuple, optional): The size of the tiles (width, height) in database units. Defaults to (200, 200).
        threads (int, optional): The number of threads to use for processing. Defaults to total number of threads.

    Returns:
        list: A list of tuples, each containing the bottom-left x-coordinate, bottom-left y-coordinate, and density of each tile.
    """
    # Validate input
    (xmin, ymin), (xmax, ymax) = get_gds_bbox(gdspath=gdspath, layer=layer)
    if tile_size[0] > xmax - xmin and tile_size[1] > ymax - ymin:
        raise ValueError(
            f"Too large tile size {tile_size} for bbox {(xmin, ymin), (xmax, ymax)}: reduce tile size (and merge later if needed)."
        )

    # Get GDS
    ly = Layout()
    ly.read(gdspath)
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


def get_layer_polygons(gdspath: Path, layer: Layer) -> list[np.array]:
    """
    Extracts polygons from a specified layer in a GDS file using gdsfactory.

    Args:
        gdspath (Path): The path to the GDS file.
        layer (Layer): The layer from which to extract polygons (layer number, datatype).

    Returns:
        list: A list of polygons from the specified layer.
    """
    # Load the layout and initialize an empty list to hold polygon coordinates
    component = gf.import_gds(gdspath)
    component_layer = component.extract(layers=[layer])
    return component_layer.get_polygons()


def get_gds_bbox(
    gdspath: Path, layer: Layer | None = None
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Calculates the bounding box of the entire GDS file using gdsfactory.

    Args:
        gdspath (Path): The path to the GDS file.
        layer (Layer): if not None, only consider the bbox of that specific layer

    Returns:
        tuple: ((xmin,ymin),(xmax,ymax))
    """
    component = gf.import_gds(gdspath)
    if layer is not None:
        component = component.extract(layers=[layer])
    return component.bbox


def density_data_to_meshgrid(
    density_data: list[tuple[float, float, float]],
    bbox: tuple[tuple[float, float], tuple[float, float]] | None = None,
):
    """
    Converts density data into a meshgrid for plotting.

    Args:
        density_data (List[Tuple[float, float, float]]): A list of tuples, each containing the x-coordinate, y-coordinate, and density value. Output of "calculate_density"
        bbox: ((xmin, ymin), (xmax, ymax)). If None, the processed layer is not padded to the full gds size.

    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]: Three 2D numpy arrays representing the X coordinates, Y coordinates, and density values on a meshgrid.
    """
    # Extract x, y, and density values
    x, y, density = zip(*density_data)

    # Convert to numpy arrays for plotting
    x = np.array(x)
    y = np.array(y)
    density = np.array(density)

    # Determine unique x and y coordinates for grid
    unique_x = np.unique(x)
    unique_y = np.unique(y)

    if bbox is not None:
        (xmin, ymin), (xmax, ymax) = bbox
        x_spacing = unique_x[1] - unique_x[0]
        y_spacing = unique_y[1] - unique_y[0]

        # Extend unique_x down to xmin and up to xmax and add x, y, density = 0 data
        x_extension = []
        y_extension = []
        density_extension = []
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

    # Create a grid for plotting
    Xi, Yi = np.meshgrid(unique_x, unique_y)

    # Map density values to the grid
    Zi = np.zeros_like(Xi)
    for i, (x_val, y_val) in enumerate(zip(x, y)):
        xi_index = np.where(unique_x == x_val)[0][0]
        yi_index = np.where(unique_y == y_val)[0][0]
        Zi[yi_index, xi_index] = density[i]

    return Xi, Yi, Zi


def plot_density_heatmap(
    gdspath: Path,
    layer: Layer,
    tile_size: tuple = (200, 200),
    threads: int = get_number_of_cores(),
    cmap=cm.Reds,
    title: str | None = None,
    visualize_with_full_gds: bool = True,
    visualize_polygons: bool = False,
) -> None:
    """
    Generates and displays a heatmap visualization representing the density distribution across a specified layer of a GDS file. The heatmap is constructed using the density data calculated for each tile within the layer.

    Args:
        gdspath (Path): The path to the GDS file for which the density heatmap is to be plotted.
        layer (Layer): The specific layer within the GDS file for which the density heatmap is to be generated.
        tile_size (Tuple, optional): The dimensions (width, height) of each tile, in database units, used for density calculation. Defaults to (200, 200).
        threads (int, optional): The number of threads to utilize for processing the density calculations. Defaults to the total number of threads.
        cmap (Colormap, optional): The matplotlib colormap to use for the heatmap. Defaults to cm.Reds.
        title (str | None, optional): The title for the heatmap plot. If None, a default title is generated based on layer and tile size. Defaults to None.
        visualize_with_full_gds (bool, optional): Flag indicating whether to consider the full extent of the GDS file for plotting. Defaults to True.
        visualize_polygons (bool, optional): Flag indicating whether to overlay the actual layer polygons on top of the heatmap for reference. Defaults to False.
    """
    density_data = calculate_density(
        gdspath=gdspath, layer=layer, tile_size=tile_size, threads=threads
    )

    Xi, Yi, Zi = density_data_to_meshgrid(
        density_data=density_data,
        bbox=get_gds_bbox(gdspath) if visualize_with_full_gds else None,
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
        (xmin, ymin), (xmax, ymax) = get_gds_bbox(gdspath)
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
        plt.title(
            title
            or f"Layer: {layer}, tile size: {tile_size}, total density ~{np.mean(Zi) * 100:1.2f}%"
        )
    else:
        plt.title(title or f"Layer: {layer}, tile size: {tile_size}, layer bbox only")
    plt.show()
