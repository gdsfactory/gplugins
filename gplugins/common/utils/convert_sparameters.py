from __future__ import annotations

import pathlib
import re

import numpy as np
import pandas as pd
from gdsfactory.typings import PathType
from tqdm.auto import tqdm


def pandas_to_float64(
    df: pd.DataFrame,
    magnitude_suffix: str = "m",
    phase_suffix: str = "a",
) -> pd.DataFrame:
    """Converts a pandas CSV sparameters from complex128 format to 2x float64 format.

    Adds magnitude_suffix (default m) and phase_suffix (default a) to original keys.

    Args:
        df: pandas DataFrame.
        magnitude_suffix: m for module.
        phase_suffix: a for angle.
    """
    new_df = pd.DataFrame()

    for key in df.keys():
        if key != "wavelengths":
            new_df[f"{key}{magnitude_suffix}"] = df[key].real
            new_df[f"{key}{phase_suffix}"] = df[key].imag

    new_df["wavelengths"] = df["wavelengths"]

    return new_df


def pandas_to_numpy(df: pd.DataFrame, port_map=None) -> np.ndarray:
    """Converts a pandas CSV sparameters into a numpy array.

    Fundamental mode starts at 0.
    """
    s_headers = sorted({c[:-1] for c in df.columns if c.lower().startswith("s")})
    idxs = sorted({idx for c in s_headers for idx in _s_header_to_port_idxs(c)})

    if port_map is None:
        port_map = {f"o{i}@0": i for i in idxs}
    rev_port_map = {i: p for p, i in port_map.items()}
    assert len(rev_port_map) == len(
        port_map
    ), "Duplicate port indices found in port_map"

    s_map = {
        s: tuple(rev_port_map[i] for i in _s_header_to_port_idxs(s)) for s in s_headers
    }

    dfs = {
        s: df[["wavelengths", f"{s}m", f"{s}a"]]
        .copy()
        .rename(columns={f"{s}m": "magnitude", f"{s}a": "phase"})
        for s in s_map
    }

    S = dict(wavelengths=df["wavelengths"].values)
    for key, df in dfs.items():
        pm1, pm2 = s_map[key]
        (p1, m1), (p2, m2) = pm1.split("@"), pm2.split("@")
        name = f"{p1}@{m1},{p2}@{m2}"
        S[name] = df["magnitude"].values * np.exp(1j * df["phase"].values)

    return S


def csv_to_npz(filepath: PathType) -> pathlib.Path:
    """Convert CSV files into numpy."""
    df = pd.read_csv(filepath)
    sp = pandas_to_numpy(df)
    filepath_npz = pathlib.Path(filepath).with_suffix(".npz")
    np.savez_compressed(filepath_npz, **sp)
    return filepath_npz


def convert_directory_csv_to_npz(dirpath: PathType) -> None:
    """Convert CSV files from directory dirpath into numpy."""
    dirpath = pathlib.Path(dirpath)
    for filepath in tqdm(dirpath.glob("**/*.csv")):
        try:
            csv_to_npz(filepath)
        except Exception as e:
            print(filepath)
            print(e)


def _s_header_to_port_idxs(s):
    s = re.sub("[^0-9]", "", s)
    inp, out = (int(i) for i in s)
    return inp, out


if __name__ == "__main__":
    # import matplotlib.pyplot as plt
    from gdsfactory.config import PATH

    filepath = PATH.sparameters / "mmi1x2_d542be8a.csv"
    filepath = PATH.sparameters / "mmi1x2_00cc8908.csv"
    filepath = PATH.sparameters / "mmi1x2_1f90b7ca.csv"  # lumerical

    convert_directory_csv_to_npz(PATH.sparameters)

    # s = csv_to_npz(filepath)
    # plt.plot(s["wavelengths"], np.abs(s["o1@0,o2@0"]) ** 2)
    # plt.plot(s["wavelengths"], np.abs(s["o1@0,o3@0"]) ** 2)
    # plt.show()
