API Design
===================================

************************
Meshing
************************

.. currentmodule:: gplugins.meshwell

.. rubric:: Meshing

.. autosummary::
   :toctree: _autosummary/

    get_meshwell_prisms


************************
Mode solvers
************************

.. currentmodule:: gplugins.tidy3d.modes

.. rubric:: Mode solver tidy3d

.. autosummary::
   :toctree: _autosummary/

   Waveguide
   WaveguideCoupler
   sweep_n_eff
   sweep_n_group
   sweep_bend_mismatch
   sweep_coupling_length

.. currentmodule:: gplugins.femwell.mode_solver

.. rubric:: Mode solver Femwell

.. autosummary::
   :toctree: _autosummary/

   compute_cross_section_modes

.. currentmodule:: gplugins.meow

.. rubric:: EME (Eigen Mode Expansion)

.. autosummary::
   :toctree: _autosummary/

    MEOW


************************
FDTD Simulation
************************

.. rubric:: Sparameter utils

.. currentmodule:: gplugins.common.utils.plot

.. autosummary::
   :toctree: _autosummary/

   plot_sparameters
   plot_imbalance2x2
   plot_loss2x2

.. rubric:: common FDTD functions

.. currentmodule:: gplugins.common.utils.get_effective_indices

.. autosummary::
   :toctree: _autosummary/

   get_effective_indices

.. currentmodule:: gplugins.common.utils.port_symmetries

.. autosummary::
   :toctree: _autosummary/

.. currentmodule:: gplugins.common.utils.convert_sparameters

.. autosummary::
   :toctree: _autosummary/

   pandas_to_float64
   pandas_to_numpy
   csv_to_npz
   convert_directory_csv_to_npz

.. autosummary::
   :toctree: _autosummary/

.. currentmodule:: gplugins.tidy3d

.. rubric:: FDTD tidy3d

.. autosummary::
   :toctree: _autosummary/

   write_sparameters
   write_sparameters_grating_coupler
   write_sparameters_grating_coupler_batch


.. currentmodule:: gplugins.lumerical

.. rubric:: FDTD lumerical

.. autosummary::
   :toctree: _autosummary/

   write_sparameters_lumerical

****************************
Circuit solver
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

**************
Electrostatics
**************

.. currentmodule:: gplugins.elmer

.. rubric:: Elmer

.. autosummary::
   :toctree: _autosummary/

   run_capacitive_simulation_elmer


.. currentmodule:: gplugins.palace

.. rubric:: Palace

.. autosummary::
   :toctree: _autosummary/

   run_capacitive_simulation_palace

************
Full-wave RF
************

.. currentmodule:: gplugins.palace

.. rubric:: Palace

.. autosummary::
   :toctree: _autosummary/

   run_scattering_simulation_palace
