from typing import Annotated, Any

import tidy3d as td
from pydantic.functional_serializers import PlainSerializer
from pydantic.functional_validators import AfterValidator


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
