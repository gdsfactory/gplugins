"""gplugins - gdsfactory plugins."""

__version__ = "1.3.3"

import pathlib

from gplugins.common.utils import plot, port_symmetries
from gplugins.common.utils.get_effective_indices import get_effective_indices

home = pathlib.Path.home()
cwd = pathlib.Path.cwd()
module_path = pathlib.Path(__file__).parent.absolute()
repo_path = module_path.parent


class Paths:
    module = module_path
    repo = repo_path


PATH = Paths()

__all__ = ["get_effective_indices", "plot", "port_symmetries"]
