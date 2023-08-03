import sys
import warnings

from gplugins import tidy3d

message = (
    "gplugins.gtidy3d has been renamed to gplugins.tidy3d. Please update your code."
)
warnings.warn(message)
sys.modules["gplugins.gtidy3d"] = tidy3d
