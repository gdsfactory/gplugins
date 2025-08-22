"""Useful plot functions."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from pydantic import validate_call
from sax.saxtypes import Model


@validate_call
def plot_model(
    model: Model,
    port1: str = "o1",
    ports2: tuple[str, ...] | None = None,
    logscale: bool = True,
    min_db_range: float = 0.5,
    fig=None,
    wavelength_start: float = 1.5,
    wavelength_stop: float = 1.6,
    wavelength_points: int = 2000,
    phase: bool = False,
    title: str | None = None,
) -> None:
    """Plot Model Sparameters Magnitude.

    Args:
        model: function that returns SDict as function of wavelength.
        port1: input port name.
        ports2: list of ports.
        logscale: plots in dB logarithmic scale.
        min_db_range: minimum dB range. Set to 0 to disable.
        fig: matplotlib figure.
        wavelength_start: wavelength min (µm).
        wavelength_stop: wavelength max (µm).
        wavelength_points: number of wavelength steps.
        phase: plot phase instead of magnitude.
        title: plot title.

    .. plot::
        :include-source:

        import gplugins.sax as gs

        gs.plot_model(gs.models.straight, phase=True, port1="o1")

    """
    wavelengths = np.linspace(wavelength_start, wavelength_stop, wavelength_points)
    sdict = model(wl=wavelengths)

    ports = {ports[0] for ports in sdict.keys()}
    ports2 = ports2 or ports

    if port1 not in ports:
        raise ValueError(f"port1 {port1!r} not in {list(ports)}")

    for port in ports2:
        if port not in ports:
            raise ValueError(f"port2 {port!r} not in {list(ports)}")

    fig = fig or plt.subplot()
    ax = fig.axes

    for port2 in ports2:
        if (port1, port2) in sdict:
            if phase:
                y = np.angle(sdict[(port1, port2)])
                ylabel = "angle (rad)"
            else:
                y = np.abs(sdict[(port1, port2)])
                y = 20 * np.log10(y) if logscale else y
                ylabel = "|S (dB)|" if logscale else "|S|"
            ax.plot(wavelengths, y, label=f"{port1}→{port2}")

    if logscale:
        current_ylim = ax.get_ylim()
        if current_ylim[1] - current_ylim[0] < min_db_range:
            ax.set_ylim(y.mean() - min_db_range / 2, y.mean() + min_db_range / 2)

    if title:
        ax.set_title(title)
    else:
        # Handle functools.partial objects
        if hasattr(model, "func"):
            # It's a partial object
            model_name = getattr(model.func, "__name__", "model")
        else:
            # Regular function
            model_name = getattr(model, "__name__", "model")
        ax.set_title(f"{model_name} S-Parameters")
    ax.set_xlabel("wavelength (µm)")
    ax.set_ylabel(ylabel)
    plt.legend()
    return ax


if __name__ == "__main__":
    import gplugins.sax as gs

    plot_model(gs.models.straight, phase=True, port1="o1", ports2=("o1", "o2"))
    plt.show()
