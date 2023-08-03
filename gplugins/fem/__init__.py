import sys
import warnings

from gplugins import femwell

message = "gplugins.fem has been renamed to gplugins.femwell. Please update your code."
warnings.warn(message)
sys.modules["gplugins.fem"] = femwell
