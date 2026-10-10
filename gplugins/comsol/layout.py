"""Extract a gdsfactory component into COMSOL-ready metal polygons and ports.

This module is pure geometry: it converts the positive metal on one layer of a
component into polygons (in micrometres) plus optional feed-port metadata so a
separate COMSOL model builder can consume it. Layouts that are not fed (e.g. an
eigenmode qubit cell) are extracted with ``feed_ports=None`` and carry no feed
metadata. No COMSOL or MPh imports live here.

The component is expected to already hold the physical metal, ground plane
included, on ``layer``. PDKs that draw negative (etch) masks invert them first
and then call :func:`prepare_comsol_layout`; :func:`feed_port`,
:func:`crop_planes`, and :func:`validate_crop_containment` are public so such a
wrapper can validate its own input before the inversion.

Optionally the metal can be cropped at the two feed-port planes so a component
whose CPW conductors and gaps reach those planes ends in open CPW cross sections
instead of solid ground.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

import gdsfactory as gf
import klayout.db as kdb

if TYPE_CHECKING:
    from gdsfactory.component import Component
    from gdsfactory.typings import LayerSpec

Point: TypeAlias = tuple[float, float]

# Feed planes are currently defined only for axis-aligned ports.
_ANGLE_TOLERANCE = 1e-6

#: Coordinate tolerance in µm for feed-plane alignment and ordering.
_PLANE_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True, kw_only=True)
class ComsolPolygon:
    """One physical metal polygon in µm.

    ``outline`` is the outer boundary (vertices in order, first vertex not
    repeated). ``holes`` are inner boundaries, i.e. etched negative space
    enclosed by metal.

    A single simple COMSOL polygon point list cannot encode a hole, so a
    consumer that only accepts plain outlines must either subtract ``holes``
    itself or reject polygons where ``holes`` is non-empty. ``outline`` alone
    is the complete shape only when ``holes`` is empty.
    """

    outline: tuple[Point, ...]
    holes: tuple[tuple[Point, ...], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ComsolFeedPort:
    """A feed port selected for the COMSOL model, in µm and degrees."""

    name: str
    center: Point
    width: float
    orientation: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ComsolBoundingBox:
    """Axis-aligned bounding box of the prepared ground region, in µm."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def width(self) -> float:
        """Box width in µm."""
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        """Box height in µm."""
        return self.ymax - self.ymin


@dataclass(frozen=True, slots=True, kw_only=True)
class ComsolLayout:
    """Extracted COMSOL geometry and feed ports for one component.

    All coordinates are in micrometres in the component's own frame.
    ``feed_ports`` is empty for layouts extracted with ``feed_ports=None``.

    Note:
        The feed ports are reported as-is. Whether each one actually sits on
        the outer boundary of the prepared ground region is *not* asserted
        here: a ground plane usually surrounds the feeds,
        so a port center can legitimately lie inside the bounding box. A model
        builder that needs the port to coincide with a ground boundary must
        check that against ``polygons`` and ``bbox`` itself. The exception is
        an extraction made with ``crop_to_feed_ports=True``, where the two feed
        planes bound the metal and each feed center lies on a face of ``bbox``.
    """

    polygons: tuple[ComsolPolygon, ...]
    feed_ports: tuple[ComsolFeedPort, ...]
    bbox: ComsolBoundingBox


@dataclass(frozen=True, slots=True, kw_only=True)
class CropPlanes:
    """The two feed-port planes a cropped extraction is bounded by, in µm.

    ``axis`` is 0 to crop along x, 1 to crop along y. ``low``/``high`` are the
    port centers on that axis, ordered low to high.
    """

    axis: int
    low: float
    high: float

    def snap(self, dbu: float) -> tuple[int, int]:
        """Return the planes in database units, snapped outwards.

        Snapping outwards means a sub-grid port offset never clips metal that
        was validated to lie between the planes.

        Args:
            dbu: Database unit in µm, e.g. ``component.kcl.dbu``.

        Returns:
            The low and high plane in database units.
        """
        return math.floor(self.low / dbu), math.ceil(self.high / dbu)


def prepare_comsol_layout(
    component: Component,
    layer: LayerSpec,
    feed_ports: tuple[str, str] | None = None,
    *,
    crop_to_feed_ports: bool = False,
) -> ComsolLayout:
    """Extract metal polygons on one layer and optional feed ports from a component.

    Args:
        component: The gdsfactory component to extract. Its geometry on
            ``layer`` is taken as the physical metal, ground plane included.
        layer: The layer holding the positive metal.
        feed_ports: Names of exactly two distinct ports to expose as feeds, or
            ``None`` for an unfed layout, in which case the result carries no
            feed ports. ``None`` fits layouts with no CPW feedline, e.g. an
            eigenmode qubit cell.
        crop_to_feed_ports: When ``True``, cut the metal back to the two
            feed-port planes so each external face shows an open CPW cross
            section instead of extended ground. Requires two feed ports that
            are axis-aligned, opposite, outward-facing, and share their
            transverse coordinate (left/right along x, or bottom/top along y).
            The planes snap outwards to the database grid, so the returned
            ``bbox`` can exceed the port span by less than one database unit.
            This only clips; it does not check that the device itself lies
            between the planes. Call :func:`validate_crop_containment` on the
            drawn layers first if that matters. Defaults to ``False``.

    Returns:
        A :class:`ComsolLayout` with metal polygons (holes preserved), the
        selected feed ports (empty when ``feed_ports`` is ``None``), and the
        metal bounding box, all in µm.

    Raises:
        ValueError: If ``feed_ports`` is supplied but does not name two
            distinct available ports, if a feed port is not cardinal or has
            non-finite coordinates or width, if no metal is found on
            ``layer``, or if ``crop_to_feed_ports`` is set but the feeds are
            not a valid opposite pair.
    """
    ports: tuple[ComsolFeedPort, ...]
    if feed_ports is None:
        ports = ()
    else:
        if len(feed_ports) != 2:
            raise ValueError(
                "feed_ports must name exactly two ports or be None, "
                f"got {len(feed_ports)}"
            )
        if feed_ports[0] == feed_ports[1]:
            raise ValueError(
                f"feed_ports must be two distinct names, got {feed_ports!r}"
            )
        ports = tuple(feed_port(component, name) for name in feed_ports)

    planes: CropPlanes | None = None
    if crop_to_feed_ports:
        if not ports:
            raise ValueError(
                "crop_to_feed_ports=True needs two feed ports to define the "
                "crop planes, but feed_ports is None"
            )
        planes = crop_planes(ports)

    dbu = component.kcl.dbu
    region = _metal_region(component, layer)
    if planes is not None and not region.is_empty():
        low_dbu, high_dbu = planes.snap(dbu)
        outer = region.bbox()
        clip_box = (
            kdb.Box(low_dbu, outer.bottom, high_dbu, outer.top)
            if planes.axis == 0
            else kdb.Box(outer.left, low_dbu, outer.right, high_dbu)
        )
        region = region & kdb.Region(clip_box)
        region.merge()

    if region.is_empty():
        where = " between the feed planes" if planes is not None else ""
        raise ValueError(
            f"Component {component.name!r} has no metal on layer "
            f"{gf.get_layer_tuple(layer)}{where} to extract"
        )

    box = region.bbox()
    return ComsolLayout(
        polygons=_polygons_from_shapes(region.each(), dbu),
        feed_ports=ports,
        bbox=ComsolBoundingBox(
            xmin=box.left * dbu,
            ymin=box.bottom * dbu,
            xmax=box.right * dbu,
            ymax=box.top * dbu,
        ),
    )


def _metal_region(component: Component, layer: LayerSpec) -> kdb.Region:
    """Return the merged geometry of ``layer``, hierarchy flattened.

    Returns:
        The merged region, in database units.
    """
    spec = gf.get_layer_tuple(layer)
    region = kdb.Region(component.begin_shapes_rec(component.kcl.layer(*spec)))
    region.merge()
    return region


def _polygons_from_shapes(
    shapes: Iterable[kdb.Polygon], dbu: float
) -> tuple[ComsolPolygon, ...]:
    """Convert KLayout polygons to µm :class:`ComsolPolygon` values.

    Returns:
        One :class:`ComsolPolygon` per shape, holes preserved.
    """
    return tuple(
        ComsolPolygon(
            outline=tuple(
                (point.x * dbu, point.y * dbu) for point in shape.each_point_hull()
            ),
            holes=tuple(
                tuple(
                    (point.x * dbu, point.y * dbu)
                    for point in shape.each_point_hole(hole)
                )
                for hole in range(shape.holes())
            ),
        )
        for shape in shapes
    )


def _axial_bounds(box: kdb.Box, axis: int) -> tuple[int, int]:
    """Return the low and high extent of a box along the crop axis.

    Returns:
        The box extents in database units along ``axis``.
    """
    return (box.left, box.right) if axis == 0 else (box.bottom, box.top)


def _axis_of_orientation(orientation: float) -> int:
    """Return the crop axis a cardinal port faces along, 0 for x and 1 for y.

    Returns:
        ``0`` when the port faces along ±x, ``1`` along ±y.
    """
    remainder = orientation % 180.0
    return 0 if min(remainder, 180.0 - remainder) <= _ANGLE_TOLERANCE else 1


def _same_angle(first: float, second: float) -> bool:
    """Return whether two orientations point the same way modulo 360°.

    Returns:
        ``True`` when the orientations differ by less than
        :data:`_ANGLE_TOLERANCE`.
    """
    return abs((first - second + 180.0) % 360.0 - 180.0) <= _ANGLE_TOLERANCE


def crop_planes(ports: Sequence[ComsolFeedPort]) -> CropPlanes:
    """Validate a feed pair and derive the two crop planes.

    Args:
        ports: The two feed ports, e.g. from :func:`feed_port`.

    Returns:
        The axis and ordered planes of the valid feed pair.

    Raises:
        ValueError: If the feeds are not two axis-aligned, opposite,
            outward-facing ports sharing a transverse coordinate.
    """
    axes = {_axis_of_orientation(port.orientation) for port in ports}
    if len(axes) != 1:
        raise ValueError(
            "crop_to_feed_ports requires both feed ports to face along the same "
            f"axis, got orientations {[port.orientation for port in ports]}"
        )
    axis = axes.pop()
    low_port, high_port = sorted(ports, key=lambda port: port.center[axis])
    expected = (180.0, 0.0) if axis == 0 else (270.0, 90.0)
    if not (
        _same_angle(low_port.orientation, expected[0])
        and _same_angle(high_port.orientation, expected[1])
    ):
        raise ValueError(
            "crop_to_feed_ports requires the feeds to face outwards, "
            f"{expected[0]} on the low side and {expected[1]} on the high side, "
            f"got {low_port.orientation} and {high_port.orientation}"
        )
    transverse = 1 - axis
    if (
        abs(low_port.center[transverse] - high_port.center[transverse])
        > _PLANE_TOLERANCE
    ):
        raise ValueError(
            "crop_to_feed_ports requires both feed centers to share their "
            f"transverse coordinate, got {low_port.center} and {high_port.center}"
        )
    if high_port.center[axis] - low_port.center[axis] <= _PLANE_TOLERANCE:
        raise ValueError(
            "crop_to_feed_ports requires two distinct ordered feed planes, got "
            f"{low_port.center[axis]} and {high_port.center[axis]}"
        )
    return CropPlanes(axis=axis, low=low_port.center[axis], high=high_port.center[axis])


def validate_crop_containment(
    component: Component,
    planes: CropPlanes,
    *,
    layers: Sequence[LayerSpec],
    gap_layer: LayerSpec | None = None,
) -> None:
    """Refuse a crop that would cut device geometry or leave a closed face.

    Every polygon on ``layers`` must lie between the planes, otherwise cropping
    would slice device metal. When ``gap_layer`` is given, its geometry must
    also reach both planes, otherwise the cropped faces would be solid metal
    rather than open CPW cross sections. Run this on the drawn component,
    before any mask inversion or ground-plane margin is added.

    Args:
        component: The drawn component.
        planes: The crop planes from :func:`crop_planes`.
        layers: Layers whose geometry must fit between the planes.
        gap_layer: Layer drawing the CPW gaps (e.g. an etch layer), or
            ``None`` to skip the open-face check.

    Raises:
        ValueError: If geometry extends beyond a plane or the gaps do not span
            both planes.
    """
    low_dbu, high_dbu = planes.snap(component.kcl.dbu)
    for layer in layers:
        spec = gf.get_layer_tuple(layer)
        for shape in component.get_polygons(by="tuple", layers=[spec]).get(spec, []):
            low, high = _axial_bounds(shape.bbox(), planes.axis)
            if low < low_dbu or high > high_dbu:
                raise ValueError(
                    "crop_to_feed_ports would cut component geometry: "
                    f"{spec} extends beyond the feed planes at "
                    f"[{planes.low}, {planes.high}] µm. Move the feeds to the "
                    "component ends or drop cropping."
                )

    if gap_layer is None:
        return
    spec = gf.get_layer_tuple(gap_layer)
    gap_shapes = component.get_polygons(by="tuple", layers=[spec]).get(spec, [])
    if not gap_shapes:
        raise ValueError("crop_to_feed_ports requires gaps at both feed planes")
    gaps = kdb.Region()
    gaps.insert(gap_shapes)
    low, high = _axial_bounds(gaps.bbox(), planes.axis)
    if low > low_dbu or high < high_dbu:
        raise ValueError(
            "crop_to_feed_ports requires the gaps to reach both feed "
            f"planes at [{planes.low}, {planes.high}] µm, otherwise the cropped "
            "faces are not open CPW cross sections"
        )


def feed_port(component: Component, name: str) -> ComsolFeedPort:
    """Validate one feed port and return its metadata, in µm and degrees.

    Args:
        component: The component holding the port.
        name: The port name.

    Returns:
        The validated feed port.

    Raises:
        ValueError: If the port is unavailable, non-cardinal, or has
            non-finite or non-positive values.
    """
    try:
        port = component.ports[name]
    except KeyError as exc:
        available = sorted(port_.name for port_ in component.ports)
        raise ValueError(
            f"Feed port {name!r} is not available; component has {available}"
        ) from exc

    center: Point = (float(port.center[0]), float(port.center[1]))
    width = float(port.width)
    orientation = float(port.orientation)

    for label, value in (
        ("x coordinate", center[0]),
        ("y coordinate", center[1]),
        ("width", width),
        ("orientation", orientation),
    ):
        if not math.isfinite(value):
            raise ValueError(f"Feed port {name!r} has non-finite {label}")
    if width <= 0.0:
        raise ValueError(f"Feed port {name!r} has non-positive width {width}")
    remainder = orientation % 90.0
    if min(remainder, 90.0 - remainder) > _ANGLE_TOLERANCE:
        raise ValueError(
            f"Feed port {name!r} orientation {orientation} is not cardinal; "
            "COMSOL feeds must face along ±x or ±y"
        )

    return ComsolFeedPort(
        name=name, center=center, width=width, orientation=orientation
    )
