from typing import Annotated

from gdsfactory import Component
from pydantic.functional_serializers import PlainSerializer
from shapely import GeometryCollection, MultiPolygon, Polygon

RFMaterialSpec = dict[str, dict[str, float | int]]
CapacitanceDict = dict[tuple[str, str], float]
ScatteringDict = dict[tuple[str, str], float]
AnyShapelyPolygon = Annotated[
    GeometryCollection | MultiPolygon | Polygon,
    PlainSerializer(lambda x: x.wkb_hex, when_used="json"),
]
GFComponent = Annotated[
    Component, PlainSerializer(lambda x: x.to_dict(), when_used="json")
]
