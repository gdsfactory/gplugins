"""Convert SAX S-parameter models to Lumerical Interconnect DAT format."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

SPEED_OF_LIGHT = 299792458.0  # m/s


def sax_to_lumerical_dat(
    model: Callable[..., dict[tuple[str, str], Any]],
    filepath: str | Path,
    port_names: list[str] | None = None,
    port_map: dict[str, str] | None = None,
    wavelength_start: float = 1.2,
    wavelength_stop: float = 1.6,
    wavelength_points: int = 500,
    **model_kwargs,
) -> Path:
    """Write a SAX model's S-parameters in Lumerical Interconnect DAT format.

    Evaluates a SAX model over a wavelength sweep and writes the resulting
    S-parameters to a .dat file readable by Lumerical Interconnect.

    Args:
        model: SAX model callable that accepts ``wl`` and returns an SDict.
        filepath: output .dat file path.
        port_names: ordered port names for the DAT file header.
            If None, inferred from the model output keys.
        port_map: mapping from SAX port names to Lumerical port names,
            e.g. ``{"o1": "W0", "o2": "N0", "o3": "E0", "o4": "N1"}``.
            Applied after evaluating the model.
        wavelength_start: start wavelength in micrometers.
        wavelength_stop: stop wavelength in micrometers.
        wavelength_points: number of wavelength points.
        **model_kwargs: extra keyword arguments forwarded to the SAX model.

    Returns:
        Path to the written .dat file.
    """
    filepath = Path(filepath).with_suffix(".dat")

    wl = np.linspace(wavelength_start, wavelength_stop, wavelength_points)
    sdict = model(wl=wl, **model_kwargs)

    # Apply port renaming
    if port_map:
        sdict = {
            (port_map.get(p1, p1), port_map.get(p2, p2)): v
            for (p1, p2), v in sdict.items()
        }

    # Determine unique port names preserving order of first appearance
    if port_names is None:
        seen: set[str] = set()
        port_names = []
        for p1, p2 in sdict:
            for p in (p1, p2):
                if p not in seen:
                    seen.add(p)
                    port_names.append(p)

    n_wl = len(wl)

    # wavelength (um) -> frequency (Hz), reversed so frequency is ascending
    frequencies = SPEED_OF_LIGHT / (wl[::-1] * 1e-6)

    lines: list[str] = []

    # Port declarations
    for name in port_names:
        lines.append(f'["{name}",""]')

    # S-parameter blocks: iterate source then destination
    for src in port_names:
        for dst in port_names:
            key = (src, dst)
            if key in sdict:
                values = np.asarray(sdict[key], dtype=complex)
            else:
                # Missing entries (e.g. reflections) default to zero
                values = np.zeros(n_wl, dtype=complex)
            # Reverse to match ascending-frequency order
            values = values[::-1]
            magnitudes = np.abs(values)
            angles = np.angle(values)

            lines.append(f'("{src}","mode 1",1,"{dst}",1,"transmission")')
            lines.append(f"({wavelength_points}, 3)")
            for f, m, a in zip(frequencies, magnitudes, angles):
                lines.append(f"{f:.16e} {m:.16e} {a:.16e}")

    filepath.write_text("\n".join(lines) + "\n")
    return filepath


if __name__ == "__main__":
    from sax.models import coupler

    out = sax_to_lumerical_dat(
        model=coupler,
        filepath="coupler_test.dat",
        port_map={"o1": "W0", "o2": "N0", "o3": "E0", "o4": "N1"},
        wavelength_start=1.2,
        wavelength_stop=1.6,
        wavelength_points=500,
        length=15.7,
        coupling0=0.0,
        dn=0.02,
    )
    print(f"Wrote {out}")

    # Verify by reading back
    from gplugins.lumerical.read import read_sparameters_file

    port_names, F, S = read_sparameters_file(filepath=str(out), numports=4)
    print(f"Ports: {port_names}")
    print(f"Frequencies: {F.shape}, S-matrix: {S.shape}")
    print(f"Frequency range: {F[0]:.6e} - {F[-1]:.6e} Hz")
