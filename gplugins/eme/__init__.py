import sys
import warnings

from gplugins import meow

message = "gplugins.eme has been renamed to gplugins.meow. Please update your code."
warnings.warn(message)
sys.modules["gplugins.eme"] = meow
