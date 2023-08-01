gplugins
===================================

************************
Mode solver Plugins
************************

.. currentmodule:: gplugins.gtidy3d.modes

.. rubric:: Mode solver tidy3d

.. autosummary::
   :toctree: _autosummary/

   Waveguide
   WaveguideCoupler
   sweep_n_eff
   sweep_n_group
   sweep_bend_mismatch
   sweep_coupling_length

.. currentmodule:: gplugins.fem.mode_solver

.. rubric:: Mode solver Femwell

.. autosummary::
   :toctree: _autosummary/

   compute_cross_section_modes


.. currentmodule:: gplugins.modes

.. rubric:: Mode solver MPB

.. autosummary::
   :toctree: _autosummary/

    find_modes_waveguide
    find_modes_coupler
    find_neff_vs_width
    find_mode_dispersion
    find_coupling_vs_gap
    find_neff_ng_dw_dh
    plot_neff_ng_dw_dh
    plot_neff_vs_width
    plot_coupling_vs_gap

.. currentmodule:: gplugins.eme

.. rubric:: EME (Eigen Mode Expansion)

.. autosummary::
   :toctree: _autosummary/

    MEOW


************************
FDTD Simulation Plugins
************************

.. rubric:: common FDTD functions

.. currentmodule:: gplugins.plot

.. autosummary::
   :toctree: _autosummary/

   plot_sparameters
   plot_imbalance2x2
   plot_loss2x2

.. currentmodule:: gplugins

.. autosummary::
   :toctree: _autosummary/

   get_effective_indices


.. currentmodule:: gplugins.gmeep

.. rubric:: FDTD meep

.. autosummary::
   :toctree: _autosummary/

   write_sparameters_meep
   write_sparameters_meep_mpi
   write_sparameters_meep_batch
   write_sparameters_grating
   write_sparameters_grating_mpi
   write_sparameters_grating_batch

.. currentmodule:: gplugins.gtidy3d

.. rubric:: FDTD tidy3d

.. autosummary::
   :toctree: _autosummary/

   write_sparameters
   write_sparameters_batch
   write_sparameters_grating_coupler
   write_sparameters_grating_coupler_batch


.. currentmodule:: gplugins.lumerical

.. rubric:: FDTD lumerical

.. autosummary::
   :toctree: _autosummary/

   write_sparameters_lumerical

****************************
Circuit solver Plugins
****************************

.. currentmodule:: gplugins.sax

.. rubric:: SAX

.. autosummary::
   :toctree: _autosummary/

   read.model_from_csv
   read.model_from_component
   plot_model
   models


.. currentmodule:: gplugins.lumerical.interconnect

.. rubric:: Lumerical interconnect

.. autosummary::
   :toctree: _autosummary/

    install_design_kit
    add_interconnect_element
    get_interconnect_settings
    send_to_interconnect
    run_wavelength_sweep
    plot_wavelength_sweep
