from __future__ import annotations

import pathlib

import matplotlib.pyplot as plt
import yaml
from klayout import rdb

PathType = pathlib.Path | str


def count_drc(rdb_path: PathType, threshold: int = 0) -> dict[str, int]:
    """Reads klayout Results database and returns a dict of error names to number of errors.

    Works for both single rdb files and directories of rdb files.

    Args:
        rdb_path: Path to rdb file or directory of rdb files.
        threshold: Minimum number of errors to be included in the output.
    """
    rdb_path = pathlib.Path(rdb_path)
    errors_dict = {}

    if not rdb_path.exists():
        raise FileNotFoundError(f"Cannot find {rdb_path}")

    if not rdb_path.is_dir():
        return _get_errors(rdb_path, threshold, errors_dict)
    for rdb_file in rdb_path.glob("*.rdb"):
        errors_dict[rdb_file.stem] = count_drc(rdb_file)

    return errors_dict


def _get_errors(rdb_path, threshold, errors_dict):
    r = rdb.ReportDatabase()
    r.load(rdb_path)

    categories = {cat.rdb_id(): cat for cat in r.each_category()}

    errors_total = 0

    for category_id, category in categories.items():
        errors_per_category = r.each_item_per_category(category_id)
        errors = len(list(errors_per_category))
        errors_total += errors

        if errors > threshold:
            errors_dict[category.name()] = errors

    errors_dict["total"] = errors_total
    return dict(sorted(errors_dict.items(), key=lambda item: item[1], reverse=True))


def write_yaml(rdb_path: PathType, filepath: PathType, threshold: int = 0) -> None:
    """Write DRC report to YAML.

    Args:
        rdb_path: Path to rdb file or directory of rdb files.
        filepath: Path to output YAML file.
        threshold: Minimum number of errors to be included in the output.

    """
    data = count_drc(rdb_path=rdb_path, threshold=threshold)
    with open(filepath, "w") as file:
        yaml.dump(data, file, default_flow_style=False)


def plot_drc(errors: dict[str, int]) -> None:
    """Plot DRC errors.

    Args:
        errors: Dict of error names to number of errors.
    """
    plt.bar(errors.keys(), errors.values())
    plt.title("DRC Errors")
    plt.xlabel("Categories")
    plt.ylabel("Error count")
    plt.show()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Count DRC errors.")
    parser.add_argument("rdb_path", help="Path to rdb file or directory of rdb files.")
    parser.add_argument("filepath", help="Path to output YAML file.")

    write_yaml(**vars(parser.parse_args()))

    # rdb_path = pathlib.Path("/home/jmatres/Downloads/demo")
    # errors = count_drc(rdb_path, threshold=100)
