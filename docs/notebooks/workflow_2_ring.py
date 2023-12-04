# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: base
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Ring filter
#
# ## Calculations
#
# For a ring resonator we need to define:
#
# Optical parameters:
#
# - coupling coefficient: will define resonance extinction ratio for a particular ring loss.
# - Free spectral range.
#
# Electrical parameters:
#
# - VpiL
# - Resistance

# %%
import gdsfactory as gf
import numpy as np

gf.config.rich_output()
gf.CONF.display_type = "klayout"


def ring(
    wl: np.ndarray,
    wl0: float,
    neff: float,
    ng: float,
    ring_length: float,
    coupling: float,
    loss: float,
) -> np.ndarray:
    """Returns Frequency Domain Response of an all pass filter.

    Args:
        wl: wavelength in  um.
        wl0: center wavelength at which neff and ng are defined.
        neff: effective index.
        ng: group index.
        ring_length: in um.
        loss: dB/um.
    """
    transmission = 1 - coupling
    neff_wl = (
        neff + (wl0 - wl) * (ng - neff) / wl0
    )  # we expect a linear behavior with respect to wavelength
    out = np.sqrt(transmission) - 10 ** (-loss * ring_length / 20.0) * np.exp(
        2j * np.pi * neff_wl * ring_length / wl
    )
    out /= 1 - np.sqrt(transmission) * 10 ** (-loss * ring_length / 20.0) * np.exp(
        2j * np.pi * neff_wl * ring_length / wl
    )
    return abs(out) ** 2


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    loss = 0.03  # [dB/μm] (alpha) waveguide loss
    neff = 2.46  # Effective index of the waveguides
    wl0 = 1.55  # [μm] the wavelength at which neff and ng are defined
    radius = 5
    ring_length = 2 * np.pi * radius  # [μm] Length of the ring
    coupling = 0.5  # [] coupling of the coupler
    wl = np.linspace(1.5, 1.6, 1000)  # [μm] Wavelengths to sweep over
    wl = np.linspace(1.55, 1.60, 1000)  # [μm] Wavelengths to sweep over
    ngs = [4.182551, 4.169563, 4.172917]
    thicknesses = [210, 220, 230]

    # widths = np.array([0.4, 0.45, 0.5, 0.55, 0.6])
    # ngs = np.array([4.38215238, 4.27254985, 4.16956338, 4.13283219, 4.05791982])

    widths = np.array([0.495, 0.5, 0.505])
    neffs = np.array([2.40197253, 2.46586378, 2.46731758])
    ng = 4.2  # Group index of the waveguides

    for width, neff in zip(widths, neffs):
        p = ring(
            wl=wl,
            wl0=wl0,
            neff=neff,
            ng=ng,
            ring_length=ring_length,
            coupling=coupling,
            loss=loss,
        )
        plt.plot(wl, p, label=f"{int(width*1e3)}nm")

    plt.title("ring resonator vs waveguide width")
    plt.xlabel("wavelength (um)")
    plt.ylabel("Power Transmission")
    plt.grid()
    plt.legend()
    plt.show()

# %% [markdown]
# ## Layout
#
# gdsfactory easily enables you to layout Component with as many levels of hierarchy as you need.
#
# A `Component` is a canvas where we can add polygons, references to other components or ports.
#
# Lets add two references in a component.

# %%
import gdsfactory as gf
import toolz

c = gf.components.ring_single_heater(gap=0.2, radius=10, length_x=4)
c.plot()

# %%
scene = c.to_3d()
scene.show()

# %% [markdown]
# Lets define a ring function that also accepts other component specs for the subcomponents (straight, coupler, bend)

# %%
xs = gf.cross_section.metal3(width=5)

ring = gf.components.ring_single_heater(gap=0.2, radius=10, length_x=4)
ring_with_pads = gf.routing.add_pads_top(
    ring,
    port_names=["r_e3", "l_e1"],
    cross_section=xs,
    optical_routing_type=None,
    fanout_length=100,
)
ring_with_pads_grating_couplers = gf.routing.add_fiber_array(
    ring_with_pads, with_loopback=True
)
ring_with_pads_grating_couplers.show()
ring_with_pads_grating_couplers.plot()

# %%
ring = gf.components.ring_single_heater(gap=0.2, radius=10, length_x=4)
ring_with_grating_couplers = gf.routing.add_fiber_array(ring, with_loopback=True)
c = gf.routing.add_electrical_pads_top(
    ring_with_grating_couplers, port_names=["l_e1", "r_e3"]
)
c.plot()

# %% [markdown]
# ## Top reticle assembly
#
# Once you have your components and circuits defined, you can add them into a top reticle Component for fabrication.
#
# You need to consider:
#
# - what design variations do you want to include in the mask? You need to define your Design Of Experiment or DOE
# - obey DRC (Design rule checking) foundry rules for manufacturability. Foundry usually provides those rules for each layer (min width, min space, min density, max density)
# - make sure you will be able to test te devices after fabrication. Obey DFT (design for testing) rules. For example, if your test setup works only for fiber array, what is the fiber array spacing (127 or 250um?)
# - if you plan to package your device, make sure you follow your packaging guidelines from your packaging house (min pad size, min pad pitch, max number of rows for wire bonding ...)

# %%
nm = 1e-3
ring_te = toolz.compose(gf.routing.add_fiber_array, gf.components.ring_single)
rings = gf.grid([ring_te(radius=r) for r in [10, 20, 50]])

gaps = [210 * nm, 220 * nm, 230 * nm]
rings_heater = [
    gf.components.ring_single_heater(
        gap=0.2, radius=10, length_x=4, name=f"ring_heater_{int(gap*1e3)}"
    )
    for gap in gaps
]
rings_heater_with_grating_couplers = [
    gf.routing.add_fiber_array(ring) for ring in rings_heater
]
rings_with_pads = [
    gf.routing.add_electrical_pads_top(ring, name=f"{ring.name}_pads")
    for ring in rings_heater_with_grating_couplers
]


@gf.cell
def reticle(size=(1000, 1000)):
    c = gf.Component()
    r = c << rings
    m = c << gf.components.pack_doe(
        gf.components.mzi,
        settings=dict(delta_length=[100, 200]),
        function=gf.routing.add_fiber_single,
    )
    m.xmin = r.xmax + 10
    m.ymin = r.ymin
    _ = c << gf.components.seal_ring(c.bbox)
    return c


m = reticle()
gf.remove_from_cache(m)
m.plot()

# %%
nm = 1e-3
ring_te = toolz.compose(gf.routing.add_fiber_array, gf.components.ring_single)

gaps = [210 * nm, 220 * nm, 230 * nm]
rings = gf.grid([ring_te(gap=gap, decorator=gf.labels.add_label_json) for gap in gaps])

rings_heater = [
    gf.components.ring_single_heater(gap=gap, radius=10, length_x=4) for gap in gaps
]
rings_heater_with_grating_couplers = [
    gf.routing.add_fiber_array(ring) for ring in rings_heater
]
rings_with_pads = [
    gf.routing.add_electrical_pads_top(
        ring, port_names=["l_e1", "r_e3"], decorator=gf.labels.add_label_json
    )
    for ring in rings_heater_with_grating_couplers
]


@gf.cell
def reticle(size=(1000, 1000)):
    c = gf.Component()
    r = c << rings
    m = c << gf.pack(rings_with_pads)[0]
    m.xmin = r.xmax + 10
    m.ymin = r.ymin
    _ = c << gf.components.seal_ring(c.bbox)
    return c


m = reticle()
gf.remove_from_cache(m)
m.show()
m.plot()

# %%
gdspath = m.write_gds(gdspath="mask.gds", with_metadata=True)

# %% [markdown]
# Make sure you save the GDS with metadata so when the chip comes back you remember what you have on it.
#
# You can also save the labels for automatic testing.

# %%
labels_path = gdspath.with_suffix(".csv")
gf.labels.write_labels.write_labels_klayout(
    gdspath=gdspath, layer_label="TEXT", prefix=""
)
