from __future__ import annotations

import pathlib

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
            errors_dict.update(count_drc(rdb_file))

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


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    rdb_path = pathlib.Path("/home/jmatres/Downloads/demo.rdb")
    errors = count_drc(rdb_path, threshold=100)

    plt.bar(errors.keys(), errors.values())

    # Adding titles and labels
    plt.title("Histogram of Data")
    plt.xlabel("Categories")
    plt.ylabel("Errors")
    plt.show()

    # error_count = count_drc(rdb_path)
