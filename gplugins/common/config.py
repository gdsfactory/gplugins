"""Store configuration."""

__all__ = ["PATH"]

import pathlib

home = pathlib.Path.home()
cwd = pathlib.Path.cwd()
cwd_config = cwd / "config.yml"

home_config = home / ".config" / "gplugins.yml"
config_dir = home / ".config"
config_dir.mkdir(exist_ok=True)
module_path = pathlib.Path(__file__).parents[1].absolute()
repo_path = module_path.parent


class Path:
    module = module_path
    repo = repo_path
    web = module / "web"
    results_tidy3d = home / ".tidy3d"
    test_data = repo / "test-data"
    sparameters_repo = test_data / "sp"
    extra = repo / "extra"
    cwd = pathlib.Path.cwd()


PATH = Path()

if __name__ == "__main__":
    print(PATH)
