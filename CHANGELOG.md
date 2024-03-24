# CHANGELOG

## [Unreleased](https://github.com/gdsfactory/gplugins/compare/v0.11.0...main)

<!-- towncrier release notes start -->

## [0.11.0](https://github.com/gdsfactory/gplugins/releases/tag/v0.11.0) - 2024-03-24

- add more sax models [#364](https://github.com/gdsfactory/gplugins/pull/364)
- Add models [#357](https://github.com/gdsfactory/gplugins/pull/357)
- fix polygon hole not meshing [#362](https://github.com/gdsfactory/gplugins/pull/362)

## [0.10.2](https://github.com/gdsfactory/gplugins/releases/tag/v0.10.2) - 2024-03-06

- Update sax [#354](https://github.com/gdsfactory/gplugins/pull/354)

## [0.10.1](https://github.com/gdsfactory/gplugins/releases/tag/v0.10.1) - 2024-03-05

- fix grating prefix for tidy3d plugin [#351](https://github.com/gdsfactory/gplugins/pull/351)


## [0.10.0](https://github.com/gdsfactory/gplugins/releases/tag/v0.10.0) - 2024-03-05

- basic python-driven density analytics, using klayout tiling processor [#339](https://github.com/gdsfactory/gplugins/pull/339)
- Fix tidy3d grating couplers new port names and add drc samples [#350](https://github.com/gdsfactory/gplugins/pull/350)
- better pyproject [#342](https://github.com/gdsfactory/gplugins/pull/342)
- better global density estimation [#340](https://github.com/gdsfactory/gplugins/pull/340)
- Mention correct pinned pyvis version [#338](https://github.com/gdsfactory/gplugins/pull/338)
- fix xy meshing [#349](https://github.com/gdsfactory/gplugins/pull/349)
- add cellname parametrization, update pyproject for pre-commit to run [#343](https://github.com/gdsfactory/gplugins/pull/343)


## [0.9.13](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.13) - 2024-02-07

- pin older version of meshwell [#334](https://github.com/gdsfactory/gplugins/pull/334)
- pin latest working version of jax and jaxlib for sax to work [#332](https://github.com/gdsfactory/gplugins/pull/332)


## [0.9.12](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.12) - 2024-02-07

- background meshing [#319](https://github.com/gdsfactory/gplugins/pull/319)
- Mesh smoothing [#320](https://github.com/gdsfactory/gplugins/pull/320)
- Component with local layers [#318](https://github.com/gdsfactory/gplugins/pull/318)
- Update component.py [#315](https://github.com/gdsfactory/gplugins/pull/315)
- bump meow and sax [#308](https://github.com/gdsfactory/gplugins/pull/308)
- also ignore layers without thickness or zmin in geometry_layers [#311](https://github.com/gdsfactory/gplugins/pull/311)
- Switch to using a context manager for disable_print [#310](https://github.com/gdsfactory/gplugins/pull/310)
- fix sax notebook [#307](https://github.com/gdsfactory/gplugins/pull/307)
- Pyright remove unused expression [#304](https://github.com/gdsfactory/gplugins/pull/304)
- Include tqdm in project dependencies [#295](https://github.com/gdsfactory/gplugins/pull/295)
- require labels on PRs and remove stale [#329](https://github.com/gdsfactory/gplugins/pull/329)

## [0.9.11](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.11) - 2024-01-09

- fix path_length_analysis [#293](https://github.com/gdsfactory/gplugins/pull/293)

## [0.9.10](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.10) - 2024-01-07

- use notebooks for ease of use [#284](https://github.com/gdsfactory/gplugins/pull/284)
- update to work with latest gdsfactory >=7.10.1

## [0.9.9](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.9) - 2023-12-19

- [pre-commit.ci] pre-commit autoupdate [#282](https://github.com/gdsfactory/gplugins/pull/282)
- Add drc counter [#280](https://github.com/gdsfactory/gplugins/pull/280)
- Bump tidy3d from 2.5.0rc3 to 2.5.0 [#278](https://github.com/gdsfactory/gplugins/pull/278)
- fix docs  [#276](https://github.com/gdsfactory/gplugins/pull/276)
- [pre-commit.ci] pre-commit autoupdate [#274](https://github.com/gdsfactory/gplugins/pull/274)

## [0.9.8](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.8) - 2023-12-11

- Round port locations and layer centers to one picometer by default [#273](https://github.com/gdsfactory/gplugins/pull/273)


## [0.9.7](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.7) - 2023-12-05

- expose symmetry and other tidy3d simulation args [#269](https://github.com/gdsfactory/gplugins/pull/269)
- Update kfactory[git,ipy] requirement from <0.10,>=0.9.3 to >=0.9.3,<0.11 [#267](https://github.com/gdsfactory/gplugins/pull/267)

## [0.9.6](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.6) - 2023-12-04

- uping gdsfactory upper bound [#266](https://github.com/gdsfactory/gplugins/pull/266)

## [0.9.5](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.5) - 2023-12-03

- ask users to report version and fix kfactory pin [#263](https://github.com/gdsfactory/gplugins/pull/263)

## [0.9.4](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.4) - 2023-12-01

- allow complex materials and rely on tidy3d hash function [#261](https://github.com/gdsfactory/gplugins/pull/261)

## [0.9.3](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.3) - 2023-12-01

- Check for AbstractMedium instead of Medium in validator [#260](https://github.com/gdsfactory/gplugins/pull/260)

## [0.9.2](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.2) - 2023-11-30

- Fix port centers in z [#258](https://github.com/gdsfactory/gplugins/pull/258)
- fix plot center_z [#257](https://github.com/gdsfactory/gplugins/pull/257)


## [0.9.1](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.1) - 2023-11-30

- Add tidy3d plot epsilon [#256](https://github.com/gdsfactory/gplugins/pull/256)
- Fix mzi notebook and batch [#255](https://github.com/gdsfactory/gplugins/pull/255)

## [0.9.0](https://github.com/gdsfactory/gplugins/releases/tag/v0.9.0) - 2023-11-29

- remove webapp [#252](https://github.com/gdsfactory/gplugins/pull/252)
- remove black [#250](https://github.com/gdsfactory/gplugins/pull/250)
- [pre-commit.ci] pre-commit autoupdate [#241](https://github.com/gdsfactory/gplugins/pull/241)
- fix mpb cmap [#249](https://github.com/gdsfactory/gplugins/pull/249)
- Tidy3d rework2 [#239](https://github.com/gdsfactory/gplugins/pull/239)
- Support reducing nodes in plot nets [#245](https://github.com/gdsfactory/gplugins/pull/245)
- Treating E and H as complex while plotting abs(E) [#248](https://github.com/gdsfactory/gplugins/pull/248)

## [0.8.7](https://github.com/gdsfactory/gplugins/releases/tag/v0.8.7) - 2023-11-21

- Assorted changes in docs and support `.spi` files for `plot_nets` [#237](https://github.com/gdsfactory/gplugins/pull/237)
- Fix type annotation for port [#235](https://github.com/gdsfactory/gplugins/pull/235)
- fix sdl for vscode [#234](https://github.com/gdsfactory/gplugins/pull/234)
- Update vlsir requirement from <5.0.0,>=4.0.0 to >=4.0.0,<6.0.0 [#230](https://github.com/gdsfactory/gplugins/pull/230)
- Update vlsirtools requirement from <5.0.0,>=4.0.0 to >=4.0.0,<6.0.0 [#229](https://github.com/gdsfactory/gplugins/pull/229)
- add save_options argument when writing gds [#228](https://github.com/gdsfactory/gplugins/pull/228)
- [pre-commit.ci] pre-commit autoupdate [#227](https://github.com/gdsfactory/gplugins/pull/227)
- Gmeep: Multimode Simulations [#222](https://github.com/gdsfactory/gplugins/pull/222)
- fix docs [#226](https://github.com/gdsfactory/gplugins/pull/226)
- Ensure unique SPICE netlist elements with a counter [#224](https://github.com/gdsfactory/gplugins/pull/224)


## [0.8.6](https://github.com/gdsfactory/gplugins/releases/tag/v0.8.6) - 2023-11-08

- [pre-commit.ci] pre-commit autoupdate [#220](https://github.com/gdsfactory/gplugins/pull/220)
- Write output to a new library so we can reuse cell names [#219](https://github.com/gdsfactory/gplugins/pull/219)
- Remove HSPICE netlist comments for plot_nets [#218](https://github.com/gdsfactory/gplugins/pull/218)
- Improve dataprep [#216](https://github.com/gdsfactory/gplugins/pull/216)
- Layer to keep dict [#215](https://github.com/gdsfactory/gplugins/pull/215)
- Support multiple top cells and SPICE netlists in `plot_nets` [#214](https://github.com/gdsfactory/gplugins/pull/214)
- Add flake8-debugger checks to ruff [#210](https://github.com/gdsfactory/gplugins/pull/210)
- Export raw NumPy array capacitance matrix for ElectrostaticResults [#208](https://github.com/gdsfactory/gplugins/pull/208)
- Use temporary directory factory in session scope tests [#207](https://github.com/gdsfactory/gplugins/pull/207)
- Update get_material.py [#206](https://github.com/gdsfactory/gplugins/pull/206)
- Match labels to corresponding cells in netlist [#204](https://github.com/gdsfactory/gplugins/pull/204)
- Add interactive netlist plotting [#199](https://github.com/gdsfactory/gplugins/pull/199)
- Parametrize VLSIR netlist export test and cache Package [#200](https://github.com/gdsfactory/gplugins/pull/200)
- switch to mamba [#197](https://github.com/gdsfactory/gplugins/pull/197)
- Consider the case in `get_l2n` when no layer connections are given in PDK [#191](https://github.com/gdsfactory/gplugins/pull/191)
- Support non-fully-connected netlists in `plot_nets` [#194](https://github.com/gdsfactory/gplugins/pull/194)
- Fix Elmer & Palace tests [#195](https://github.com/gdsfactory/gplugins/pull/195)
- Generate technology and support layer connectivity in `get_l2n` [#185](https://github.com/gdsfactory/gplugins/pull/185)
- Rename gds_ports -> ports, fix port centers and remove port size calculation from base [#183](https://github.com/gdsfactory/gplugins/pull/183)
- improve ring docs [#182](https://github.com/gdsfactory/gplugins/pull/182)
- remove database [#181](https://github.com/gdsfactory/gplugins/pull/181)
- add derived layers [#180](https://github.com/gdsfactory/gplugins/pull/180)
- fix docs with conda [#178](https://github.com/gdsfactory/gplugins/pull/178)
- Polish some things in SPICE netlist extraction [#177](https://github.com/gdsfactory/gplugins/pull/177)
- add derived layers [#175](https://github.com/gdsfactory/gplugins/pull/175)
- layernames to physical labels dict [#174](https://github.com/gdsfactory/gplugins/pull/174)


## [0.8.5](https://github.com/gdsfactory/gplugins/releases/tag/v0.8.5) - 2023-10-09

- Move verification into klayout [#173](https://github.com/$OWNER/$REPOSITORY/pull/#173)
- Default sizemax [#170](https://github.com/$OWNER/$REPOSITORY/pull/#170)
- Bump actions/checkout from 3 to 4 [#168](https://github.com/$OWNER/$REPOSITORY/pull/#168)
- add `get_component_with_net_layers` [#167](https://github.com/$OWNER/$REPOSITORY/pull/#167)


## [0.8.4](https://github.com/gdsfactory/kfactory/releases/v0.8.4) - 2023-09-27

- added towncrier [#164](https://github.com/gdsfactory/gplugins/issues/164)


## [0.8.2](https://github.com/gdsfactory/gplugins/compare/v0.8.1...v0.8.2)

- compatible with latest gdsfactory [PR](https://github.com/gdsfactory/gplugins/pull/163)

## [0.8.1](https://github.com/gdsfactory/gplugins/compare/v0.8.0...v0.8.1) [PR](https://github.com/gdsfactory/gplugins/pull/157)

- consolidate meshwell plugin

## [0.8.0](https://github.com/gdsfactory/gplugins/compare/v0.7.0...v0.8.0) [PR](https://github.com/gdsfactory/gplugins/pull/159)

- update to latest tidy3d 2.4 and gdsfactory
- rename `layerstack` to `layer_stack` to be consistent with gdsfactory
- rename portnames to `port_names`  to be consistent with python convention
- fixes https://github.com/gdsfactory/gplugins/issues/153

## [0.7.0](https://github.com/gdsfactory/gplugins/compare/v0.6.0...v0.7.0)

- add `gmsh.to_gmsh` [PR](https://github.com/gdsfactory/gplugins/pull/150)
- create common folder [PR](https://github.com/gdsfactory/gplugins/pull/148)

## [0.6.0](https://github.com/gdsfactory/gplugins/compare/v0.5.0...v0.6.0)

- add fdtdz plugin
- add Full-wave driven simulations with Palace
- fix meep plugin

## [0.5.0](https://github.com/gdsfactory/gplugins/compare/v0.4.0...v0.5.0)

- add vlsir plugin

## [0.4.0](https://github.com/gdsfactory/gplugins/compare/v0.3.0...v0.4.0)

- port to pydantic2
- add plugins: palace and elmer

## [0.3.0](https://github.com/gdsfactory/gplugins/compare/v0.2.0...v0.3.0)

- improve meshing
- add verification

## [0.2.0](https://github.com/gdsfactory/gplugins/compare/v0.1.1...v0.2.0)

- fix serializer [PR](https://github.com/gdsfactory/gplugins/pull/28)
- add materials plugin
- add klayout dataprep and DRC

## [0.1.1](https://github.com/gdsfactory/gplugins/compare/v0.1.0...v0.1.1)

- move klayout/dataprep from gdsfactory into gplugins/klayout. Add tests.
- improve tidy3d plugin
    - Enable sidewall angles in FDTD simulations
    - improve tidy3d mode solver and tests [PR](https://github.com/gdsfactory/gplugins/pull/25)

## [0.1.0](https://github.com/gdsfactory/gplugins/compare/v0.0.3...v0.1.0)

- add support for tidy3d materials [PR](https://github.com/gdsfactory/gplugins/pull/17)

## [0.0.3](https://github.com/gdsfactory/gplugins/compare/v0.0.2...v0.0.3)

- add `path_length_analysis` notebook [PR](https://github.com/gdsfactory/gplugins/pull/3)
- Add scaling factor to meshing plugin [PR](https://github.com/gdsfactory/gplugins/pull/5)

## 0.0.2

- first release
