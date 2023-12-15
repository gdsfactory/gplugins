from __future__ import annotations

import pathlib

from klayout import rdb

PathType = pathlib.Path | str


def count_drc(rdb_path: PathType) -> dict[str, int]:
    """Reads klayout Results database and returns a dict of error names to number of errors.

    Works for both single rdb files and directories of rdb files.
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

            if errors > 0:
                errors_dict[category.name()] = errors

    return errors_dict


if __name__ == "__main__":
    rdb_path = pathlib.Path("/home/jmatres/Downloads/demo.rdb")
    errors = count_drc(rdb_path)
    # error_count = count_drc(rdb_path)
