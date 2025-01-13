from typing import Annotated, Any

import numpy as np
import tidy3d as td
from pydantic.functional_serializers import PlainSerializer
from pydantic.functional_validators import AfterValidator


# Function to validate the medium
def validate_medium(v):
    # Check if the input is an instance of td.Medium
    assert isinstance(v, td.AbstractMedium), (
        f"Input should be a tidy3d medium, but got {type(v)} instead"
    )
    return v


Sparameters = dict[str, np.ndarray]

# Annotated type for Tidy3D medium with validation and serialization
Tidy3DMedium = Annotated[
    Any,
    AfterValidator(validate_medium),
    PlainSerializer(lambda x: dict(x), when_used="json"),
]

# Type for Tidy3D element mapping
Tidy3DElementMapping = tuple[
    tuple[
        tuple[tuple[str, int], tuple[str, int]], tuple[tuple[str, int, tuple[str, int]]]
    ],
    ...,
]
