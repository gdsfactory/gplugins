from __future__ import annotations

import re
from collections.abc import Sequence
from functools import partial
from itertools import combinations

import gdsfactory as gf
import matplotlib.pyplot as plt
import numpy as np


def _check_ports(sp: dict[str, np.ndarray], ports: Sequence[str]):
    """Ensure ports exist in Sparameters."""
    for port in ports:
        if port not in sp:
            raise ValueError(f"Did not find port {port!r} in {list(sp.keys())}")


def plot_sparameters(
    sp: dict[str, np.ndarray],
    logscale: bool = True,
    plot_phase: bool = False,
    keys: tuple[str, ...] | None = None,
    with_simpler_input_keys: bool = False,
    with_simpler_labels: bool = True,
) -> None:
    """Plots Sparameters from a dict of np.ndarrays.

    Args:
        sp: Sparameters np.ndarray.
        logscale: plots 20*log10(S).
        plot_phase: plots angle of Sparameters in degrees.
        keys: list of keys to plot, plots all by default.
        with_simpler_input_keys: You can use S12 keys instead of o1@0,o2@0.
        with_simpler_labels: uses S11, S12 in plot labels instead of o1@0,o2@0.

    """
    w = sp["wavelengths"] * 1e3
    keys = keys or [key for key in sp if not key.lower().startswith("wav")]

    for key in keys:
        if with_simpler_input_keys:
            key = f"o{key[1]}@0,o{key[2]}@0"
            if key not in sp:
                raise ValueError(f"{key!r} not in {list(sp.keys())}")

        if with_simpler_labels and "o" in key and "@" in key:
            port_mode1_port_mode2 = key.split(",")
            if len(port_mode1_port_mode2) != 2:
                raise ValueError(f"{key!r} needs to be 'portin@mode,portout@mode'")
            port_mode1, port_mode2 = port_mode1_port_mode2
            port1, _mode1 = port_mode1.split("@")
            port2, _mode2 = port_mode2.split("@")
            alias = f"S{port1[1:]}{port2[1:]}"
        else:
            alias = key

        if key not in sp:
            raise ValueError(f"{key!r} not in {list(sp.keys())}")
        y = sp[key]
        if plot_phase:
            y = np.angle(y)
            plt.ylabel("S (deg)")
        else:
            y = 20 * np.log10(np.abs(y)) if logscale else np.abs(y) ** 2
            plt.ylabel("|S| (dB)") if logscale else plt.ylabel("$|S|^2$")
        plt.plot(w, y, label=alias)
    plt.legend()
    plt.xlabel("wavelength (nm)")
    plt.show()


def plot_imbalance(
    sp: dict[str, np.ndarray], ports: Sequence[str], ax: plt.Axes | None = None
) -> None:
    """Plots imbalance in dB for coupler.
    The imbalance is always defined between two ports, so this function plots the
    imbalance between all unique port combinations.

    Args:
        sp: sparameters dict np.ndarray.
        ports: list of port name @ mode index. o1@0 is the fundamental mode for o1 port.
        ax: matplotlib axis object to draw into.

    """
    _check_ports(sp, ports)

    power = {port: np.abs(sp[port]) ** 2 for port in ports}
    x = sp["wavelengths"] * 1e3

    if ax is None:
        _, ax = plt.subplots()

    for p1, p2 in combinations(ports, 2):
        p1in, p1out = re.findall(r"\d+", p1)[::2]
        p2in, p2out = re.findall(r"\d+", p2)[::2]
        label = f"$S_{{{p1in}{p1out}}}, S_{{{p2in}{p2out}}}$"
        ax.plot(x, 10 * np.log10(1 - (power[p1] - power[p2])), label=label)

    ax.set_xlim((x[0], x[-1]))
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("imbalance (dB)")
    plt.legend()


def plot_loss(
    sp: dict[str, np.ndarray], ports: Sequence[str], ax: plt.Axes | None = None
) -> None:
    """Plots loss dB for coupler.

    Args:
        sp: sparameters dict np.ndarray.
        ports: list of port name @ mode index. o1@0 is the fundamental mode for o1 port.
        ax: matplotlib axis object to draw into.

    """
    _check_ports(sp, ports)

    power = {port: np.abs(sp[port]) ** 2 for port in ports}
    x = sp["wavelengths"] * 1e3

    if ax is None:
        _, ax = plt.subplots()

    for n, p in power.items():
        pin, pout = re.findall(r"\d+", n)[::2]
        ax.plot(x, 10 * np.log10(p), label=f"$|S_{{{pin}{pout}}}|^2$")
    if len(ports) > 1:
        ax.plot(x, 10 * np.log10(sum(power.values())), "k--", label="Total")
    ax.set_xlim((x[0], x[-1]))
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("excess loss (dB)")
    plt.legend()


def plot_reflection(
    sp: dict[str, np.ndarray], ports: Sequence[str], ax: plt.Axes | None = None
) -> None:
    """Plots reflection in dB for coupler.

    Args:
        sp: sparameters dict np.ndarray.
        ports: list of port name @ mode index. o1@0 is the fundamental mode for o1 port.
        ax: matplotlib axis object to draw into.

    """
    _check_ports(sp, ports)

    power = {port: np.abs(sp[port]) ** 2 for port in ports}
    x = sp["wavelengths"] * 1e3

    if ax is None:
        _, ax = plt.subplots()

    for n, p in power.items():
        pin, pout = re.findall(r"\d+", n)[::2]
        ax.plot(x, 10 * np.log10(p), label=f"$|S_{{{pin}{pout}}}|^2$")
    if len(ports) > 1:
        ax.plot(x, 10 * np.log10(sum(power.values())), "k--", label="Total")
    ax.set_xlim((x[0], x[-1]))
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("reflection (dB)")
    plt.legend()


plot_loss1x2 = partial(plot_loss, ports=["o1@0,o2@0", "o1@0,o3@0"])
plot_loss2x2 = partial(plot_loss, ports=["o1@0,o3@0", "o1@0,o4@0"])
plot_imbalance1x2 = partial(plot_imbalance, ports=["o1@0,o2@0", "o1@0,o3@0"])
plot_imbalance2x2 = partial(plot_imbalance, ports=["o1@0,o3@0", "o1@0,o4@0"])
plot_reflection1x2 = partial(plot_reflection, ports=["o1@0,o1@0"])
plot_reflection2x2 = partial(plot_reflection, ports=["o1@0,o1@0", "o2@0,o1@0"])

if __name__ == "__main__":
    import gplugins as sim

    sp = sim.get_sparameters_data_tidy3d(component=gf.components.mmi1x2)
    # plot_sparameters(sp, logscale=False, keys=["o1@0,o2@0"])
    # plot_sparameters(sp, logscale=False, keys=["S21"])
    # plt.show()
