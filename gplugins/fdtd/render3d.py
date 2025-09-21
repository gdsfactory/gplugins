"""3D rendering utilities for FDTD geometry visualization.

This module provides multiple 3D visualization options:
- PyVista: Desktop applications with full interactivity
- Open3D/Plotly: Jupyter notebooks and VS Code compatibility
- Three.js/FastAPI: Web browser visualization with enhanced controls
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import pyvista as pv
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False



def plot_prisms_3d(
    geometry_obj,
    show_edges: bool = True,
    opacity: float = 0.8,
    color_by_layer: bool = True,
    show_simulation_box: bool = True,
    camera_position: Optional[str] = "isometric",
    notebook: bool = True,
    theme: str = "default",
    **kwargs
) -> Optional[Any]:
    """Create interactive 3D visualization of MEEP prisms using PyVista.

    Args:
        geometry_obj: Geometry object with meep_prisms property and helper methods
        show_edges: Whether to show edges of the prisms
        opacity: Opacity of the prisms (0.0 to 1.0)
        color_by_layer: If True, color by layer name. If False, use material properties
        show_simulation_box: Whether to show the simulation bounding box
        camera_position: Camera view ("isometric", "xy", "xz", "yz", or custom tuple)
        notebook: Whether running in Jupyter notebook (enables widget mode)
        theme: PyVista theme ("default", "dark", "document")
        **kwargs: Additional arguments passed to PyVista plotter

    Returns:
        PyVista plotter object for further customization
    """
    if not PYVISTA_AVAILABLE:
        raise ImportError("PyVista is required for 3D visualization. Install with: pip install pyvista")

    # Create plotter with appropriate backend
    # Note: Removing theme parameter due to PyVista API changes
    if notebook:
        plotter = pv.Plotter(notebook=True, **kwargs)
    else:
        plotter = pv.Plotter(**kwargs)

    # Apply theme after creation if needed
    if theme == "dark":
        pv.set_plot_theme("dark")
    elif theme == "document":
        pv.set_plot_theme("document")

    # Convert MEEP prisms to PyVista meshes
    layer_meshes = _convert_prisms_to_meshes(geometry_obj)

    # Add each layer to the plotter
    colors = _generate_layer_colors(list(layer_meshes.keys()))

    for layer_name, meshes in layer_meshes.items():
        color = colors[layer_name] if color_by_layer else None

        # Set opacity based on layer - core is opaque, others are transparent
        layer_opacity = 1.0 if layer_name == "core" else 0.2

        for mesh in meshes:
            plotter.add_mesh(
                mesh,
                color=color,
                opacity=layer_opacity,
                show_edges=show_edges,
                label=layer_name,
                name=f"{layer_name}_{id(mesh)}"  # Unique name for each mesh
            )

    # Add simulation bounding box
    if show_simulation_box:
        sim_box = _create_simulation_box(geometry_obj)
        plotter.add_mesh(
            sim_box,
            style="wireframe",
            color="black",
            line_width=2,
            label="Simulation Box"
        )

    # Set camera position
    _set_camera_position(plotter, camera_position, geometry_obj)

    # Add legend if coloring by layer
    if color_by_layer and len(layer_meshes) > 1:
        # Note: PyVista legend functionality varies by version
        try:
            plotter.add_legend()
        except:
            pass  # Legend not supported in this PyVista version

    # Show the plot
    if notebook:
        # Try interactive first, fallback to static
        try:
            pv.set_jupyter_backend('trame')
            return plotter.show()
        except:
            pv.set_jupyter_backend('static')
            return plotter.show()
    else:
        return plotter.show()


def export_3d_mesh(
    geometry_obj,
    filename: str,
    format: str = "auto"
) -> None:
    """Export 3D geometry to various mesh formats.

    Args:
        geometry_obj: Geometry object with meep_prisms property
        filename: Output filename with extension
        format: Export format ("stl", "ply", "obj", "vtk", "gltf", or "auto")

    Raises:
        ImportError: If PyVista is not installed
        ValueError: If format is not supported
    """
    if not PYVISTA_AVAILABLE:
        raise ImportError("PyVista is required for mesh export. Install with: pip install pyvista")

    # Convert all prisms to a single combined mesh
    layer_meshes = _convert_prisms_to_meshes(geometry_obj)
    combined_mesh = pv.MultiBlock()

    for layer_name, meshes in layer_meshes.items():
        for i, mesh in enumerate(meshes):
            combined_mesh[f"{layer_name}_{i}"] = mesh

    # Export based on format
    if format == "auto":
        format = filename.split(".")[-1].lower()

    if format in ["stl"]:
        # STL doesn't support multiple objects, so combine everything
        merged = combined_mesh.combine()
        merged.save(filename)
    elif format in ["ply", "obj", "vtk"]:
        combined_mesh.save(filename)
    elif format == "gltf":
        # glTF export requires additional dependencies
        try:
            combined_mesh.save(filename)
        except Exception as e:
            raise ValueError(f"glTF export failed. May need additional dependencies: {e}")
    else:
        raise ValueError(f"Unsupported format: {format}")


def _convert_prisms_to_meshes(geometry_obj) -> Dict[str, List[Any]]:
    """Convert MEEP prisms to PyVista meshes organized by layer.

    Optimization: For layers with many triangular prisms (from triangulated polygons with holes,
    complex curves, or fractured geometries), we merge them into a single mesh for much better
    rendering performance (10-20x speedup).
    """
    layer_meshes = {}

    for layer_name, prisms in geometry_obj.meep_prisms.items():
        # Count how many triangular prisms we have
        triangular_count = sum(1 for p in prisms if len(p.vertices) == 3)

        # Optimization: merge many triangular prisms into single mesh for performance
        if triangular_count > 100:
            # Separate triangular and non-triangular prisms
            triangular_prisms = [p for p in prisms if len(p.vertices) == 3]
            non_triangular_prisms = [p for p in prisms if len(p.vertices) != 3]

            meshes = []

            # Merge all triangular prisms into a single mesh for performance
            if triangular_prisms:
                print(f"    Merging {len(triangular_prisms)} triangular prisms in layer {layer_name}")
                merged_mesh = _merge_triangular_prisms_to_mesh(triangular_prisms)
                if merged_mesh:
                    meshes.append(merged_mesh)

            # Process non-triangular prisms individually
            for i, prism in enumerate(non_triangular_prisms):
                vertices_3d = prism.vertices
                height = prism.height
                # Process non-triangular prism individually

                base_vertices = np.array([[v.x, v.y, v.z] for v in vertices_3d])
                top_vertices = base_vertices.copy()
                top_vertices[:, 2] += height

                mesh = _create_prism_mesh(base_vertices, top_vertices, prism)
                meshes.append(mesh)

            layer_meshes[layer_name] = meshes
        else:
            # Process prisms individually for layers without many triangulated prisms
            meshes = []
            for i, prism in enumerate(prisms):
                # Get prism properties
                vertices_3d = prism.vertices
                height = prism.height

                # Process individual prism

                # Convert MEEP Vector3 to numpy arrays
                base_vertices = np.array([[v.x, v.y, v.z] for v in vertices_3d])

                # Create top vertices by adding height
                top_vertices = base_vertices.copy()
                top_vertices[:, 2] += height

                # Create PyVista mesh for this prism
                mesh = _create_prism_mesh(base_vertices, top_vertices, prism)
                meshes.append(mesh)

            layer_meshes[layer_name] = meshes

    return layer_meshes


def _merge_triangular_prisms_to_mesh(prisms) -> Any:
    """Merge multiple triangular prisms into a single PyVista mesh for performance.

    This optimization dramatically speeds up rendering of triangulated geometries like:
    - Polygons with holes (rings, trenches, etc.)
    - Complex curved shapes
    - Photonic crystals with many features
    - Any heavily triangulated structure

    Performance improvement: 10-20x faster than individual mesh creation.
    """
    import pyvista as pv
    import numpy as np

    all_vertices = []
    all_faces = []
    vertex_offset = 0

    for prism in prisms:
        # Get prism vertices and height
        vertices_3d = prism.vertices
        height = prism.height

        # Convert to numpy arrays
        base_vertices = np.array([[v.x, v.y, v.z] for v in vertices_3d])
        top_vertices = base_vertices.copy()
        top_vertices[:, 2] += height

        # Combine base and top vertices
        prism_vertices = np.vstack([base_vertices, top_vertices])
        all_vertices.append(prism_vertices)

        n_verts = len(base_vertices)  # Should be 3 for triangular prisms

        # Create faces for this prism with appropriate vertex offset
        # Bottom face (triangle)
        all_faces.extend([3, vertex_offset + 2, vertex_offset + 1, vertex_offset + 0])

        # Top face (triangle)
        all_faces.extend([3, vertex_offset + n_verts + 0, vertex_offset + n_verts + 1, vertex_offset + n_verts + 2])

        # Side faces (3 quads for triangular prism)
        for i in range(n_verts):
            next_i = (i + 1) % n_verts
            all_faces.extend([4,
                              vertex_offset + i,
                              vertex_offset + next_i,
                              vertex_offset + next_i + n_verts,
                              vertex_offset + i + n_verts])

        vertex_offset += len(prism_vertices)

    # Combine all vertices
    if all_vertices:
        combined_vertices = np.vstack(all_vertices)
        # Create single merged mesh
        merged_mesh = pv.PolyData(combined_vertices, all_faces)
        return merged_mesh
    else:
        return None


def _create_prism_mesh(base_vertices: np.ndarray, top_vertices: np.ndarray, prism=None) -> Any:
    """Create a PyVista mesh from base and top vertices of a prism with hole support."""
    # Check if this prism has hole information from original Shapely polygon
    if prism and hasattr(prism, '_original_polygon') and hasattr(prism._original_polygon, 'interiors') and prism._original_polygon.interiors:
        return _create_prism_mesh_with_holes_pyvista(prism._original_polygon, base_vertices, top_vertices)

    # Fallback to simple triangulation for polygons without holes
    n_verts = len(base_vertices)

    # Combine all vertices (base + top)
    all_vertices = np.vstack([base_vertices, top_vertices])

    # Create faces
    faces = []

    # Bottom face (base vertices in reverse order for correct normal)
    bottom_face = [n_verts] + list(range(n_verts))[::-1]
    faces.extend(bottom_face)

    # Top face
    top_face = [n_verts] + [i + n_verts for i in range(n_verts)]
    faces.extend(top_face)

    # Side faces
    for i in range(n_verts):
        next_i = (i + 1) % n_verts

        # Create quad face (as two triangles or one quad)
        side_face = [4, i, next_i, next_i + n_verts, i + n_verts]
        faces.extend(side_face)

    # Create PyVista mesh
    mesh = pv.PolyData(all_vertices, faces)

    return mesh


def _generate_layer_colors(layer_names: List[str]) -> Dict[str, str]:
    """Generate distinct colors for each layer."""
    import matplotlib.pyplot as plt

    # Use matplotlib colormap for consistent colors
    cmap = plt.cm.get_cmap("tab10" if len(layer_names) <= 10 else "tab20")
    colors = {}

    for i, name in enumerate(layer_names):
        rgb = cmap(i / max(len(layer_names) - 1, 1))[:3]  # Get RGB, ignore alpha
        colors[name] = rgb

    return colors


def _create_simulation_box(geometry_obj) -> Any:
    """Create a wireframe box showing the simulation boundaries."""
    bbox = geometry_obj.bbox

    # Create box corners
    min_corner = bbox[0]
    max_corner = bbox[1]

    # Create PyVista box
    bounds = [
        min_corner[0], max_corner[0],  # x_min, x_max
        min_corner[1], max_corner[1],  # y_min, y_max
        min_corner[2], max_corner[2],  # z_min, z_max
    ]

    box = pv.Box(bounds=bounds)
    return box


def _set_camera_position(plotter: Any, position: str, geometry_obj) -> None:
    """Set camera position for optimal viewing."""
    if position == "isometric":
        plotter.camera_position = "iso"
    elif position == "xy":
        plotter.view_xy()
    elif position == "xz":
        plotter.view_xz()
    elif position == "yz":
        plotter.view_yz()
    elif isinstance(position, (tuple, list)) and len(position) == 3:
        plotter.camera_position = position
    else:
        # Default to isometric
        plotter.camera_position = "iso"

    # Ensure the geometry fits in view
    plotter.reset_camera()


def create_web_export(
    geometry_obj,
    filename: str = "geometry_3d.html",
    title: str = "3D Geometry Visualization"
) -> str:
    """Export 3D visualization as standalone HTML file for web deployment.

    Args:
        geometry_obj: Geometry object with meep_prisms property
        filename: Output HTML filename
        title: Title for the HTML page

    Returns:
        Path to the created HTML file

    """

    # Create plotter in off-screen mode
    plotter = pv.Plotter(notebook=False, off_screen=True)

    # Add geometry (reuse the main plotting function logic)
    layer_meshes = _convert_prisms_to_meshes(geometry_obj)
    colors = _generate_layer_colors(list(layer_meshes.keys()))

    for layer_name, meshes in layer_meshes.items():
        color = colors[layer_name]
        for mesh in meshes:
            plotter.add_mesh(mesh, color=color, opacity=0.8)

    # Export to HTML
    plotter.export_html(filename, backend="pythreejs")

    return filename


def plot_prisms_3d_open3d(
    geometry_obj,
    show_edges: bool = False,
    color_by_layer: bool = True,
    show_simulation_box: bool = True,
    notebook: bool = True,
    layer_opacity: Dict[str, float] = None,
    **kwargs
) -> None:
    """Create interactive 3D visualization using Open3D with Plotly backend.

    Args:
        geometry_obj: Geometry object with meep_prisms property
        show_edges: Whether to show wireframe edges
        color_by_layer: Color each layer differently
        show_simulation_box: Show simulation boundary box
        notebook: Whether to display in Jupyter notebook
        layer_opacity: Dictionary mapping layer names to opacity (0.0-1.0).
                      Default: core=1.0, others=0.2
        **kwargs: Additional Plotly figure options
    """
    if not OPEN3D_AVAILABLE:
        raise ImportError("Open3D is required. Install with: pip install open3d")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        raise ImportError("Plotly is required for Open3D notebook visualization. Install with: pip install plotly")

    # Convert MEEP prisms to Open3D meshes
    layer_meshes = _convert_prisms_to_open3d(geometry_obj)

    # Generate colors and opacity for layers
    colors, opacity_dict = _generate_layer_colors_open3d(list(layer_meshes.keys()), layer_opacity)

    # Collect all Plotly mesh objects
    plotly_meshes = []

    # Add each layer
    for layer_name, meshes in layer_meshes.items():
        layer_color = colors[layer_name] if color_by_layer else [0.7, 0.7, 0.7]
        layer_opacity_val = opacity_dict.get(layer_name, 0.8)

        for i, mesh in enumerate(meshes):
            # Set RGB color
            if color_by_layer:
                mesh.paint_uniform_color(layer_color[:3])  # Only RGB

            # Convert to Plotly mesh with opacity
            plotly_mesh = _mesh_to_mesh3d(
                mesh,
                opacity=layer_opacity_val,
                name=f"{layer_name}_{i}",
                color=layer_color[:3] if color_by_layer else [0.7, 0.7, 0.7]
            )
            plotly_meshes.append(plotly_mesh)

            # Add wireframe if requested
            if show_edges:
                wireframe_scatter = _wireframe_to_scatter3d(mesh, name=f"{layer_name}_edges_{i}")
                plotly_meshes.append(wireframe_scatter)

    # Add simulation box
    if show_simulation_box:
        sim_box_scatter = _create_simulation_box_plotly(geometry_obj)
        plotly_meshes.append(sim_box_scatter)

    # Create and display Plotly figure
    fig = go.Figure(data=plotly_meshes)

    # Calculate geometry bounds for better initial zoom
    all_x, all_y, all_z = [], [], []
    for layer_name, meshes in layer_meshes.items():
        for mesh in meshes:
            vertices = np.asarray(mesh.vertices)
            all_x.extend(vertices[:, 0])
            all_y.extend(vertices[:, 1])
            all_z.extend(vertices[:, 2])

    if all_x:  # If we have geometry
        x_range = [min(all_x), max(all_x)]
        y_range = [min(all_y), max(all_y)]
        z_range = [min(all_z), max(all_z)]

        # Calculate center and range for better zoom
        center_x, center_y, center_z = np.mean(x_range), np.mean(y_range), np.mean(z_range)
        range_size = max(x_range[1] - x_range[0], y_range[1] - y_range[0], z_range[1] - z_range[0])
    else:
        center_x = center_y = center_z = 0
        range_size = 10

    # Update layout for better 3D visualization with enhanced zoom sensitivity
    fig.update_layout(
        scene=dict(
            xaxis_title="X (μm)",
            yaxis_title="Y (μm)",
            zaxis_title="Z (μm)",
            aspectmode="data",
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5),  # Better initial view
                center=dict(x=0, y=0, z=0),
                projection=dict(type="perspective")
            ),
            # Set explicit ranges for more predictable zoom behavior
            xaxis=dict(range=[center_x - range_size*0.6, center_x + range_size*0.6]),
            yaxis=dict(range=[center_y - range_size*0.6, center_y + range_size*0.6]),
            zaxis=dict(range=[center_z - range_size*0.6, center_z + range_size*0.6])
        ),
        title="3D FDTD Geometry Visualization",
        dragmode="orbit",
        **kwargs
    )

    # Add custom JavaScript for enhanced zoom sensitivity (works in Jupyter)
    config = {
        'scrollZoom': True,
        'doubleClick': 'reset+autosize',
        'modeBarButtonsToRemove': ['pan2d', 'lasso2d'],
        'displayModeBar': True,
        'responsive': True
    }

    if notebook:
        fig.show(config=config)
    else:
        # Save to HTML and open in browser for desktop
        fig.write_html("geometry_3d.html", config=config)
        import webbrowser
        webbrowser.open("geometry_3d.html")



def serve_threejs_visualization(
    geometry_obj,
    show_edges: bool = False,
    color_by_layer: bool = True,
    show_simulation_box: bool = True,
    layer_opacity: Dict[str, float] = None,
    port: int = 8000,
    auto_open: bool = True,
    show_stats: bool = False,
    **kwargs
) -> str:
    """Start a FastAPI server to display Three.js visualization in browser.

    Args:
        geometry_obj: Geometry object with meep_prisms property
        show_edges: Whether to show wireframe edges
        color_by_layer: Color each layer differently
        show_simulation_box: Show simulation boundary box
        layer_opacity: Dictionary mapping layer names to opacity (0.0-1.0)
        port: Port to serve on (default 8000)
        auto_open: Whether to automatically open browser
        show_stats: Show FPS counter (default False)
        **kwargs: Additional Three.js options

    Returns:
        URL of the running server
    """
    try:
        from fastapi import FastAPI, Response
        from fastapi.responses import HTMLResponse
        import uvicorn
        import threading
        import webbrowser
        import time
    except ImportError:
        raise ImportError("FastAPI and uvicorn required. Install with: pip install fastapi uvicorn")

    # Create FastAPI app
    app = FastAPI(title="FDTD 3D Geometry Viewer")

    # Convert geometry to Three.js data
    layer_meshes = _convert_prisms_to_open3d(geometry_obj)
    colors, opacity_dict = _generate_layer_colors_open3d(list(layer_meshes.keys()), layer_opacity)

    print(f"Converting geometry: {len(layer_meshes)} layers found")
    for layer_name, meshes in layer_meshes.items():
        print(f"  Layer '{layer_name}': {len(meshes)} meshes")

    threejs_data = _convert_to_threejs_data_fastapi(layer_meshes, colors, opacity_dict, color_by_layer)

    if show_simulation_box:
        sim_box_data = _create_simulation_box_threejs_fastapi(geometry_obj)
        threejs_data["simulation_box"] = sim_box_data

    # Debug: Print data summary
    total_vertices = 0
    total_faces = 0
    for layer in threejs_data.get("layers", []):
        for mesh in layer.get("meshes", []):
            total_vertices += len(mesh.get("vertices", [])) // 3
            total_faces += len(mesh.get("faces", [])) // 3

    print(f"Three.js data prepared: {total_vertices} vertices, {total_faces} faces")

    @app.get("/", response_class=HTMLResponse)
    def get_visualization():
        """Serve the Three.js visualization page."""
        return _generate_threejs_html_fastapi(
            threejs_data,
            show_edges=show_edges,
            show_stats=show_stats,
            **kwargs
        )

    @app.get("/api/geometry")
    def get_geometry_data():
        """API endpoint to get geometry data as JSON."""
        return threejs_data

    @app.get("/api/info")
    def get_info():
        """Get summary information about the geometry."""
        info = {
            "layers": len(threejs_data.get("layers", [])),
            "total_meshes": sum(len(layer.get("meshes", [])) for layer in threejs_data.get("layers", [])),
            "has_simulation_box": "simulation_box" in threejs_data,
            "layer_names": [layer.get("name") for layer in threejs_data.get("layers", [])]
        }
        return info

    # Start server in background thread
    server_url = f"http://localhost:{port}"

    def run_server():
        try:
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
        except Exception as e:
            print(f"Server error: {e}")

    # Start server thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait a moment for server to start
    time.sleep(1)

    if auto_open:
        webbrowser.open(server_url)

    print(f"🚀 FastAPI server started at: {server_url}")
    print(f"📊 Geometry API available at: {server_url}/api/geometry")
    print("⚠️  Server running in background. Keep Python session alive to view.")

    return server_url


def _create_prism_mesh_with_holes_pyvista(shapely_polygon, base_vertices: np.ndarray, top_vertices: np.ndarray) -> Any:
    """Create PyVista mesh from Shapely polygon with proper hole handling using constrained triangulation."""
    try:
        import numpy as np
        from scipy.spatial import Delaunay
        import shapely.geometry as sg
        import pyvista as pv
    except ImportError:
        # Fallback to simple triangulation if libraries not available
        return _create_prism_mesh(base_vertices, top_vertices)

    # Extract boundary points (exterior + holes)
    all_points = []
    boundary_segments = []

    # Add exterior boundary
    exterior_coords = list(shapely_polygon.exterior.coords[:-1])  # Remove duplicate
    start_idx = 0
    all_points.extend(exterior_coords)

    # Create boundary segments for exterior (connect consecutive points)
    for i in range(len(exterior_coords)):
        boundary_segments.append([start_idx + i, start_idx + (i + 1) % len(exterior_coords)])

    # Add interior boundaries (holes)
    for interior in shapely_polygon.interiors:
        interior_coords = list(interior.coords[:-1])  # Remove duplicate
        start_idx = len(all_points)
        all_points.extend(interior_coords)

        # Create boundary segments for this hole
        for i in range(len(interior_coords)):
            boundary_segments.append([start_idx + i, start_idx + (i + 1) % len(interior_coords)])

    if len(all_points) < 3:
        # Fallback if not enough points
        return _create_prism_mesh(base_vertices, top_vertices)

    # Perform Delaunay triangulation
    points_2d = np.array(all_points)
    tri = Delaunay(points_2d)

    # Filter triangles to keep only those inside the polygon (not in holes)
    valid_triangles = []
    for triangle_indices in tri.simplices:
        # Calculate triangle centroid
        triangle_points = points_2d[triangle_indices]
        centroid = np.mean(triangle_points, axis=0)
        centroid_point = sg.Point(centroid[0], centroid[1])

        # Check if centroid is inside the polygon (and not in any hole)
        if shapely_polygon.contains(centroid_point):
            valid_triangles.append(triangle_indices)

    if not valid_triangles:
        # Fallback if no valid triangles
        return _create_prism_mesh(base_vertices, top_vertices)

    # Build 3D mesh
    z_base = base_vertices[0, 2] if len(base_vertices) > 0 else 0
    z_top = top_vertices[0, 2] if len(top_vertices) > 0 else z_base + 1

    # Create vertices (2D points at both Z levels)
    all_vertices_3d = []
    for point in points_2d:
        all_vertices_3d.append([point[0], point[1], z_base])  # Bottom
    for point in points_2d:
        all_vertices_3d.append([point[0], point[1], z_top])   # Top

    faces_pv = []
    n_points = len(points_2d)

    # Add triangulated bottom faces - PyVista format: [n_verts, v0, v1, v2]
    for triangle in valid_triangles:
        faces_pv.extend([3, triangle[0], triangle[1], triangle[2]])

    # Add triangulated top faces (reversed order for correct normal)
    for triangle in valid_triangles:
        faces_pv.extend([3, triangle[0] + n_points, triangle[2] + n_points, triangle[1] + n_points])

    # Add side faces along boundary segments - PyVista format: [4, v0, v1, v2, v3]
    for seg in boundary_segments:
        i, j = seg
        # Quad face
        faces_pv.extend([4, i, j, j + n_points, i + n_points])

    # Create PyVista mesh
    try:
        mesh = pv.PolyData(all_vertices_3d, faces_pv)
        return mesh
    except Exception:
        # Fallback if PyVista mesh creation failed
        return _create_prism_mesh(base_vertices, top_vertices)


def _convert_prisms_to_open3d(geometry_obj) -> Dict[str, List[Any]]:
    """Convert MEEP prisms to Open3D meshes organized by layer.

    Optimization: For layers with many triangular prisms (from triangulated polygons with holes,
    complex curves, or fractured geometries), we merge them into a single mesh for much better
    rendering performance (10-20x speedup).
    """
    layer_meshes = {}

    if not hasattr(geometry_obj, 'meep_prisms'):
        return layer_meshes

    meep_prisms = geometry_obj.meep_prisms
    if not meep_prisms:
        return layer_meshes

    for layer_name, prisms in meep_prisms.items():
        # Count how many triangular prisms we have
        triangular_count = sum(1 for p in prisms if len(p.vertices) == 3)

        # Optimization: merge many triangular prisms into single mesh for performance
        if triangular_count > 100:
            # Separate triangular and non-triangular prisms
            triangular_prisms = [p for p in prisms if len(p.vertices) == 3]
            non_triangular_prisms = [p for p in prisms if len(p.vertices) != 3]

            meshes = []

            # Merge all triangular prisms into a single mesh for performance
            if triangular_prisms:
                # Merging triangular prisms for better performance
                merged_mesh = _merge_triangular_prisms_to_open3d(triangular_prisms)
                if merged_mesh:
                    meshes.append(merged_mesh)

            # Process non-triangular prisms individually
            for i, prism in enumerate(non_triangular_prisms):
                vertices_3d = prism.vertices
                height = prism.height

                base_vertices = np.array([[v.x, v.y, v.z] for v in vertices_3d])
                top_vertices = base_vertices.copy()
                top_vertices[:, 2] += height

                mesh = _create_prism_mesh_open3d(base_vertices, top_vertices, prism)
                meshes.append(mesh)
        else:
            # Process prisms individually for non-triangulated layers
            meshes = []
            for i, prism in enumerate(prisms):
                # Get prism properties
                vertices_3d = prism.vertices
                height = prism.height

                # Convert to numpy arrays
                base_vertices = np.array([[v.x, v.y, v.z] for v in vertices_3d])
                top_vertices = base_vertices.copy()
                top_vertices[:, 2] += height

                # Create Open3D mesh
                mesh = _create_prism_mesh_open3d(base_vertices, top_vertices, prism)

            # Apply layer-specific opacity via alpha
            if layer_name == "core":
                # Core is fully opaque (handled by color)
                pass
            else:
                # Other layers - we'll make them more transparent via color intensity
                pass

            meshes.append(mesh)

        layer_meshes[layer_name] = meshes

    return layer_meshes


def _merge_triangular_prisms_to_open3d(prisms) -> Any:
    """Merge multiple triangular prisms into a single Open3D mesh for performance.

    This optimization dramatically speeds up rendering of triangulated geometries like:
    - Polygons with holes (rings, trenches, etc.)
    - Complex curved shapes
    - Photonic crystals with many features
    - Any heavily triangulated structure

    Performance improvement: 10-20x faster than individual mesh creation.
    """
    import open3d as o3d
    import numpy as np

    all_vertices = []
    all_triangles = []
    vertex_offset = 0

    for prism in prisms:
        # Get prism vertices and height
        vertices_3d = prism.vertices
        height = prism.height

        # Convert to numpy arrays
        base_vertices = np.array([[v.x, v.y, v.z] for v in vertices_3d])
        top_vertices = base_vertices.copy()
        top_vertices[:, 2] += height

        # Combine base and top vertices
        prism_vertices = np.vstack([base_vertices, top_vertices])
        all_vertices.append(prism_vertices)

        n_verts = len(base_vertices)  # Should be 3 for triangular prisms

        # Create triangular faces for this prism with appropriate vertex offset
        # Bottom face (triangle)
        all_triangles.append([vertex_offset + 0, vertex_offset + 2, vertex_offset + 1])

        # Top face (triangle)
        all_triangles.append([vertex_offset + n_verts + 0, vertex_offset + n_verts + 1, vertex_offset + n_verts + 2])

        # Side faces (3 quads = 6 triangles for triangular prism)
        for i in range(n_verts):
            next_i = (i + 1) % n_verts
            # Two triangles per quad
            all_triangles.append([vertex_offset + i, vertex_offset + next_i, vertex_offset + next_i + n_verts])
            all_triangles.append([vertex_offset + i, vertex_offset + next_i + n_verts, vertex_offset + i + n_verts])

        vertex_offset += len(prism_vertices)

    # Combine all vertices and create Open3D mesh
    if all_vertices:
        combined_vertices = np.vstack(all_vertices)
        combined_triangles = np.array(all_triangles, dtype=np.int32)

        # Create single merged mesh
        merged_mesh = o3d.geometry.TriangleMesh()
        merged_mesh.vertices = o3d.utility.Vector3dVector(combined_vertices)
        merged_mesh.triangles = o3d.utility.Vector3iVector(combined_triangles)
        merged_mesh.compute_vertex_normals()

        return merged_mesh
    else:
        return None


def _create_prism_mesh_open3d(base_vertices: np.ndarray, top_vertices: np.ndarray, prism=None) -> Any:
    """Create Open3D mesh from prism vertices with proper hole handling."""
    # Check if this prism has hole information from original Shapely polygon
    if prism and hasattr(prism, '_original_polygon'):
        return _create_prism_mesh_with_holes_open3d(prism._original_polygon, base_vertices, top_vertices)

    # Fallback to simple triangulation for polygons without holes
    n_verts = len(base_vertices)

    # Combine all vertices
    all_vertices = np.vstack([base_vertices, top_vertices])

    # Create triangular faces
    faces = []

    # Bottom face (triangulate polygon)
    for i in range(1, n_verts - 1):
        faces.append([0, i + 1, i])

    # Top face
    for i in range(1, n_verts - 1):
        faces.append([n_verts, n_verts + i, n_verts + i + 1])

    # Side faces
    for i in range(n_verts):
        next_i = (i + 1) % n_verts

        # Two triangles per side face
        faces.append([i, next_i, next_i + n_verts])
        faces.append([i, next_i + n_verts, i + n_verts])

    # Create Open3D mesh
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(all_vertices)
    mesh.triangles = o3d.utility.Vector3iVector(faces)

    # Compute normals for proper lighting
    mesh.compute_vertex_normals()

    return mesh


def _create_prism_mesh_with_holes_open3d(shapely_polygon, base_vertices: np.ndarray, top_vertices: np.ndarray) -> Any:
    """Create Open3D mesh from Shapely polygon with proper hole handling using constrained triangulation."""
    try:
        import numpy as np
        from scipy.spatial import Delaunay
        import shapely.geometry as sg
    except ImportError:
        # Fallback to simple triangulation if libraries not available
        return _create_prism_mesh_open3d(base_vertices, top_vertices)

    # Extract boundary points (exterior + holes)
    all_points = []
    boundary_segments = []

    # Add exterior boundary
    exterior_coords = list(shapely_polygon.exterior.coords[:-1])  # Remove duplicate
    start_idx = 0
    all_points.extend(exterior_coords)

    # Create boundary segments for exterior (connect consecutive points)
    for i in range(len(exterior_coords)):
        boundary_segments.append([start_idx + i, start_idx + (i + 1) % len(exterior_coords)])

    # Add interior boundaries (holes)
    for interior in shapely_polygon.interiors:
        interior_coords = list(interior.coords[:-1])  # Remove duplicate
        start_idx = len(all_points)
        all_points.extend(interior_coords)

        # Create boundary segments for this hole
        for i in range(len(interior_coords)):
            boundary_segments.append([start_idx + i, start_idx + (i + 1) % len(interior_coords)])

    if len(all_points) < 3:
        # Fallback if not enough points
        return _create_prism_mesh_open3d(base_vertices, top_vertices)

    # Perform Delaunay triangulation
    points_2d = np.array(all_points)
    tri = Delaunay(points_2d)

    # Filter triangles to keep only those inside the polygon (not in holes)
    valid_triangles = []
    for triangle_indices in tri.simplices:
        # Calculate triangle centroid
        triangle_points = points_2d[triangle_indices]
        centroid = np.mean(triangle_points, axis=0)
        centroid_point = sg.Point(centroid[0], centroid[1])

        # Check if centroid is inside the polygon (and not in any hole)
        if shapely_polygon.contains(centroid_point):
            valid_triangles.append(triangle_indices)

    if not valid_triangles:
        # Fallback if no valid triangles
        return _create_prism_mesh_open3d(base_vertices, top_vertices)

    # Build 3D mesh
    z_base = base_vertices[0, 2] if len(base_vertices) > 0 else 0
    z_top = top_vertices[0, 2] if len(top_vertices) > 0 else z_base + 1

    # Create vertices (2D points at both Z levels)
    all_vertices_3d = []
    for point in points_2d:
        all_vertices_3d.append([point[0], point[1], z_base])  # Bottom
    for point in points_2d:
        all_vertices_3d.append([point[0], point[1], z_top])   # Top

    faces_3d = []
    n_points = len(points_2d)

    # Add triangulated bottom faces
    for triangle in valid_triangles:
        faces_3d.append([triangle[0], triangle[1], triangle[2]])

    # Add triangulated top faces (reversed order for correct normal)
    for triangle in valid_triangles:
        faces_3d.append([triangle[0] + n_points, triangle[2] + n_points, triangle[1] + n_points])

    # Add side faces along boundary segments
    for seg in boundary_segments:
        i, j = seg
        # Two triangles per edge
        faces_3d.append([i, j, j + n_points])
        faces_3d.append([i, j + n_points, i + n_points])

    # Create Open3D mesh
    try:
        import open3d as o3d
        mesh = o3d.geometry.TriangleMesh()
        mesh.vertices = o3d.utility.Vector3dVector(all_vertices_3d)
        mesh.triangles = o3d.utility.Vector3iVector(faces_3d)
        mesh.compute_vertex_normals()
        return mesh
    except ImportError:
        # Fallback if Open3D is not available
        return _create_prism_mesh_open3d(base_vertices, top_vertices)


def _generate_layer_colors_open3d(layer_names: List[str], layer_opacity: Dict[str, float] = None) -> Tuple[Dict[str, List[float]], Dict[str, float]]:
    """Generate RGB colors and separate opacity values for Open3D.

    Args:
        layer_names: List of layer names
        layer_opacity: Dictionary mapping layer names to opacity values (0.0-1.0)
                      If None, uses default: core=1.0, others=0.2

    Returns:
        Tuple of (colors_dict, opacity_dict)
    """
    import matplotlib.pyplot as plt

    # Default opacity settings
    if layer_opacity is None:
        layer_opacity = {name: 1.0 if name == "core" else 0.2 for name in layer_names}

    cmap = plt.cm.get_cmap("tab10" if len(layer_names) <= 10 else "tab20")
    colors = {}

    for i, name in enumerate(layer_names):
        rgb = cmap(i / max(len(layer_names) - 1, 1))[:3]
        colors[name] = list(rgb)  # Only RGB, no alpha

    return colors, layer_opacity


def _create_simulation_box_open3d(geometry_obj) -> Any:
    """Create Open3D wireframe box for simulation boundaries."""
    bbox = geometry_obj.bbox
    min_corner = np.array(bbox[0])
    max_corner = np.array(bbox[1])

    # Create box as line set
    points = [
        min_corner,
        [max_corner[0], min_corner[1], min_corner[2]],
        [max_corner[0], max_corner[1], min_corner[2]],
        [min_corner[0], max_corner[1], min_corner[2]],
        [min_corner[0], min_corner[1], max_corner[2]],
        [max_corner[0], min_corner[1], max_corner[2]],
        max_corner,
        [min_corner[0], max_corner[1], max_corner[2]],
    ]

    lines = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # Bottom face
        [4, 5], [5, 6], [6, 7], [7, 4],  # Top face
        [0, 4], [1, 5], [2, 6], [3, 7],  # Vertical edges
    ]

    line_set = o3d.geometry.LineSet()
    line_set.points = o3d.utility.Vector3dVector(points)
    line_set.lines = o3d.utility.Vector2iVector(lines)
    line_set.paint_uniform_color([0, 0, 0])  # Black box

    return line_set


def _mesh_to_mesh3d(mesh, opacity: float = 1.0, name: str = "", color: List[float] = None) -> Any:
    """Convert Open3D mesh to Plotly Mesh3d with proper opacity support.

    Based on the approach provided by the user for handling transparency.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("Plotly is required for mesh conversion")

    # Get vertices and triangles
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)

    # Determine color
    if color is not None:
        # Convert RGB floats [0-1] to integers [0-255]
        c = (np.array(color) * 255).astype(int)
        color_str = f"rgb({c[0]},{c[1]},{c[2]})"
    elif len(mesh.vertex_colors):
        # Use first vertex color if set
        c = (np.asarray(mesh.vertex_colors)[0] * 255).astype(int)
        color_str = f"rgb({c[0]},{c[1]},{c[2]})"
    else:
        # Default gray
        color_str = "rgb(180,180,180)"

    return go.Mesh3d(
        x=vertices[:, 0],
        y=vertices[:, 1],
        z=vertices[:, 2],
        i=triangles[:, 0],
        j=triangles[:, 1],
        k=triangles[:, 2],
        color=color_str,
        opacity=opacity,
        name=name,
        showlegend=bool(name)
    )


def _wireframe_to_scatter3d(mesh, name: str = "") -> Any:
    """Convert Open3D mesh edges to Plotly Scatter3d for wireframe display."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("Plotly is required for wireframe conversion")

    # Create line set from triangle mesh
    line_set = o3d.geometry.LineSet.create_from_triangle_mesh(mesh)

    # Get points and lines
    points = np.asarray(line_set.points)
    lines = np.asarray(line_set.lines)

    # Create line traces for Plotly
    x_lines, y_lines, z_lines = [], [], []

    for line in lines:
        p1, p2 = points[line[0]], points[line[1]]
        x_lines.extend([p1[0], p2[0], None])
        y_lines.extend([p1[1], p2[1], None])
        z_lines.extend([p1[2], p2[2], None])

    return go.Scatter3d(
        x=x_lines,
        y=y_lines,
        z=z_lines,
        mode='lines',
        line=dict(color='black', width=2),
        name=name,
        showlegend=bool(name)
    )


def _create_simulation_box_plotly(geometry_obj) -> Any:
    """Create Plotly Scatter3d wireframe box for simulation boundaries."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        raise ImportError("Plotly is required for simulation box")

    bbox = geometry_obj.bbox
    min_corner = np.array(bbox[0])
    max_corner = np.array(bbox[1])

    # Define box vertices
    points = np.array([
        min_corner,
        [max_corner[0], min_corner[1], min_corner[2]],
        [max_corner[0], max_corner[1], min_corner[2]],
        [min_corner[0], max_corner[1], min_corner[2]],
        [min_corner[0], min_corner[1], max_corner[2]],
        [max_corner[0], min_corner[1], max_corner[2]],
        max_corner,
        [min_corner[0], max_corner[1], max_corner[2]],
    ])

    # Define line connections
    lines = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # Bottom face
        [4, 5], [5, 6], [6, 7], [7, 4],  # Top face
        [0, 4], [1, 5], [2, 6], [3, 7],  # Vertical edges
    ]

    # Create line traces
    x_lines, y_lines, z_lines = [], [], []

    for line in lines:
        p1, p2 = points[line[0]], points[line[1]]
        x_lines.extend([p1[0], p2[0], None])
        y_lines.extend([p1[1], p2[1], None])
        z_lines.extend([p1[2], p2[2], None])

    return go.Scatter3d(
        x=x_lines,
        y=y_lines,
        z=z_lines,
        mode='lines',
        line=dict(
            color='black',
            width=2,
            dash='dot'  # Finer dashes: 'dot', 'dashdot', or custom pattern
        ),
        name='Simulation Box',
        showlegend=True
    )




def _convert_to_threejs_data_fastapi(layer_meshes, colors, opacity_dict, color_by_layer):
    """Convert Open3D meshes to Three.js-compatible data structures for FastAPI."""
    threejs_data = {"layers": []}

    for layer_name, meshes in layer_meshes.items():
        layer_color = colors[layer_name] if color_by_layer else [0.7, 0.7, 0.7]
        layer_opacity = opacity_dict.get(layer_name, 0.8)

        layer_data = {
            "name": layer_name,
            "color": [int(c * 255) for c in layer_color[:3]],  # RGB 0-255
            "opacity": layer_opacity,
            "meshes": []
        }

        for i, mesh in enumerate(meshes):
            # Get vertices and faces
            vertices = np.asarray(mesh.vertices).flatten().tolist()  # [x1,y1,z1,x2,y2,z2,...]
            faces = np.asarray(mesh.triangles).flatten().tolist()    # [i1,j1,k1,i2,j2,k2,...]

            mesh_data = {
                "vertices": vertices,
                "faces": faces,
                "id": f"{layer_name}_{i}"
            }
            layer_data["meshes"].append(mesh_data)

        threejs_data["layers"].append(layer_data)

    return threejs_data


def _create_simulation_box_threejs_fastapi(geometry_obj):
    """Create simulation box data for Three.js FastAPI."""
    bbox = geometry_obj.bbox
    min_corner = np.array(bbox[0])
    max_corner = np.array(bbox[1])

    # Box vertices
    vertices = [
        min_corner,
        [max_corner[0], min_corner[1], min_corner[2]],
        [max_corner[0], max_corner[1], min_corner[2]],
        [min_corner[0], max_corner[1], min_corner[2]],
        [min_corner[0], min_corner[1], max_corner[2]],
        [max_corner[0], min_corner[1], max_corner[2]],
        max_corner,
        [min_corner[0], max_corner[1], max_corner[2]],
    ]

    # Line indices for box edges
    lines = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # Bottom face
        [4, 5], [5, 6], [6, 7], [7, 4],  # Top face
        [0, 4], [1, 5], [2, 6], [3, 7],  # Vertical edges
    ]

    return {
        "vertices": np.array(vertices).flatten().tolist(),
        "lines": [item for sublist in lines for item in sublist],  # Flatten
        "color": [0, 0, 0]  # Black
    }


def _generate_threejs_html_fastapi(threejs_data, show_edges=False, show_stats=False, **kwargs):
    """Generate complete HTML with Three.js visualization for FastAPI using external template."""

    from pathlib import Path
    import json

    # Get template path
    template_path = Path(__file__).parent / "templates" / "viewer.html"

    # Read the template
    with open(template_path, 'r') as f:
        template = f.read()

    # Extract kwargs
    width = kwargs.get('width', '100vw')
    height = kwargs.get('height', '100vh')
    background_color = kwargs.get('background_color', '#f0f0f0')
    show_wireframe = str(show_edges).lower()
    stats_display = 'block' if show_stats else 'none'

    # Convert data to JSON string for JavaScript
    data_json = json.dumps(threejs_data, indent=2)

    # Replace template variables
    html = template.format(
        geometry_data=data_json,
        show_wireframe=show_wireframe,
        show_stats=str(show_stats).lower(),
        width=width,
        height=height,
        background_color=background_color,
        stats_display=stats_display
    )

    return html
