from __future__ import annotations

import pathlib

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

    if rdb_path.is_dir():
        for rdb_file in rdb_path.glob("*.rdb"):
            errors_dict[rdb_file.stem] = count_drc(rdb_file)

    else:
        r = rdb.ReportDatabase()
        r.load(rdb_path)

        categories = {cat.rdb_id(): cat for cat in r.each_category()}

        for category_id, category in categories.items():
            errors_per_category = r.each_item_per_category(category_id)
            errors = len(list(errors_per_category))

            if errors > threshold:
                errors_dict[category.name()] = errors

        return dict(sorted(errors_dict.items(), key=lambda item: item[1], reverse=True))
    return errors_dict


def write_count_drc(rdb_path: PathType, filepath: PathType, theshold: int = 0) -> None:
    """Write DRC report to YAML.

    Args:
        rdb_path: Path to rdb file or directory of rdb files.
        filepath: Path to output YAML file.
        threshold: Minimum number of errors to be included in the output.

    """
    data = count_drc(rdb_path=rdb_path, threshold=theshold)
    with open(filepath, "w") as file:
        yaml.dump(data, file, default_flow_style=False)


if __name__ == "__main__":
    # import matplotlib.pyplot as plt

    rdb_path = pathlib.Path("/home/jmatres/Downloads/demo")
    errors = count_drc(rdb_path, threshold=100)

    # plt.bar(errors.keys(), errors.values())
    # plt.title("Histogram of Data")
    # plt.xlabel("Categories")
    # plt.ylabel("Errors")
    # plt.show()
