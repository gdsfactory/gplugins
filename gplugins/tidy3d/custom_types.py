from typing import Annotated, Any

import tidy3d as td
from gdsfactory import Component
from pydantic.functional_serializers import PlainSerializer
from pydantic.functional_validators import AfterValidator
from shapely import GeometryCollection, MultiPolygon, Polygon


def validate_medium(v):
    assert isinstance(
        v, td.Medium
    ), f"Input should be an instance of {td.Medium}, but got {type(v)} instead"
    return v


Tidy3DMedium = Annotated[
    Any,
    AfterValidator(validate_medium),
    PlainSerializer(lambda x: dict(x), when_used="json"),
]

AnyShapelyPolygon = Annotated[
    GeometryCollection | MultiPolygon | Polygon,
    PlainSerializer(lambda x: x.wkb_hex, when_used="json"),
]

GFComponent = Annotated[
    Component, PlainSerializer(lambda x: x.to_dict(), when_used="json")
]
