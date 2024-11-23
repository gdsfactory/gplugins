import yaml
from gdsfactory.config import GDSDIR_TEMP

from gplugins import PATH
from gplugins.spice.spice_to_yaml import spice_to_yaml

spice_netlist_interconnect = """
*
* Component pathname : compound_1
*
.subckt COMPOUND_1 PORT_1 PORT_2 PORT_3 PORT_4 PORT_5 PORT_6 PORT_7 PORT_8
        X_dc_1 PORT_1 PORT_2 N$1 N$3 ebeam_dc_te1550 coupling_length=17.5u sch_x=-0.245 sch_y=1.205 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_dc_2 N$1 N$3 PORT_3 PORT_4 ebeam_dc_te1550 coupling_length=17.5u sch_x=0.79 sch_y=0.38 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_dc_3 PORT_5 PORT_7 N$11 N$13 ebeam_dc_te1550 coupling_length={%test_param1%*1e-6} sch_x=-1.3 sch_y=-1.585 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_ebeam_y_1550_1 N$8 N$13 N$11 ebeam_y_1550 sch_x=0.95 sch_y=-1.58 sch_r=180 sch_f=f lay_x=0 lay_y=0
        X_ebeam_y_1550_2 N$8 PORT_6 PORT_8 ebeam_y_1550 sch_x=1.89 sch_y=-1.58 sch_r=0 sch_f=f lay_x=0 lay_y=0
.ends COMPOUND_1

*
* MAIN CELL: Component pathname : root_element
*
        .MODEL ebeam_dc_te1550 radius=5u gap=0.2u note=".- The current model only supports "coupling_length" as an input parameter..- The other parameters
        (i.e., "wg_width", "gap", "radius") are now fixed but will be parameterized in the future."
        + wg_width=0.5u library="design_kit/ebeam"
        .MODEL ebeam_gc_te1550 MC_grid={%MC_grid%} MC_non_uniform={%MC_non_uniform%} MC_resolution_x={%MC_resolution_x%}
        + MC_resolution_y={%MC_resolution_y%} MC_uniformity_thickness={%MC_uniformity_thickness%} MC_uniformity_width={%MC_uniformity_width%}
        + library="design_kit/ebeam"
        .MODEL ebeam_y_1550 Model_Version="2016/04/07" MC_grid={%MC_grid%} MC_non_uniform={%MC_non_uniform%}
        + MC_resolution_x={%MC_resolution_x%} MC_resolution_y={%MC_resolution_y%} MC_uniformity_thickness={%MC_uniformity_thickness%}
        + MC_uniformity_width={%MC_uniformity_width%} library="design_kit/ebeam"
        .MODEL wg_heater wg_length=0.0001 library="design_kit/ebeam"
        X_COMPOUND_1 N$1 N$2 N$5 N$4 N$7 N$10 N$9 N$8 COMPOUND_1 test_param2=2 test_param1=3 sch_x=0.75 sch_y=0 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_ebeam_y_1550_1 N$6 N$1 N$2 ebeam_y_1550 sch_x=-0.22 sch_y=0.005 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_ebeam_y_1550_2 N$3 N$4 N$5 ebeam_y_1550 sch_x=2.795 sch_y=1.665 sch_r=180 sch_f=f lay_x=0 lay_y=0
        X_TE1550_SubGC_neg31_oxide_1 N$17 N$6 ebeam_gc_te1550 sch_x=-2.175 sch_y=-0.05 sch_r=180 sch_f=f lay_x=0 lay_y=0
        X_TE1550_SubGC_neg31_oxide_2 N$18 N$3 ebeam_gc_te1550 sch_x=4.435 sch_y=2.655 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_ebeam_y_1550_3 N$14 N$7 N$9 ebeam_y_1550 sch_x=-1.42 sch_y=-1.31 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_ebeam_y_1550_4 N$16 N$8 N$10 ebeam_y_1550 sch_x=4.525 sch_y=-1.395 sch_r=180 sch_f=f lay_x=0 lay_y=0
        X_wg_heater_1 N$12 N$11 N$13 N$15 wg_heater sch_x=2.11 sch_y=-3.82 sch_r=180 sch_f=f lay_x=0 lay_y=0
        X_wg_heater_2 N$11 N$12 N$16 N$14 wg_heater sch_x=2.085 sch_y=-2.645 sch_r=180 sch_f=f lay_x=0 lay_y=0
        X_TE1550_SubGC_neg31_oxide_3 N$19 N$13 ebeam_gc_te1550 sch_x=4.205 sch_y=-3.99 sch_r=0 sch_f=f lay_x=0 lay_y=0
        X_TE1550_SubGC_neg31_oxide_4 N$20 N$15 ebeam_gc_te1550 sch_x=-4.305 sch_y=-4.13 sch_r=180 sch_f=f lay_x=0 lay_y=0
*
.end

*# ebeam_dc_te1550 opt_1(opt) opt_2(opt) opt_3(opt) opt_4(opt)
*# ebeam_gc_te1550 opt_fiber(opt) opt_wg(opt)
*# ebeam_y_1550 opt_a1(opt) opt_b1(opt) opt_b(opt)
*# wg_heater ele_1(ele) ele_2(ele) opt_1(opt) opt_2(opt)
"""


def test_interconnect() -> None:
    netlist_path = GDSDIR_TEMP / "test_interconnect.sp"
    netlist_path.write_text(spice_netlist_interconnect)
    picyaml_path = GDSDIR_TEMP / "test_interconnect.sp"
    mapping_path = PATH.module / "lumerical" / "mapping_ubcpdk.yml"
    spice_to_yaml(
        netlist_path=netlist_path,
        picyaml_path=picyaml_path,
        mapping_path=mapping_path,
        pdk="ubcpdk",
    )
    s = yaml.safe_load(picyaml_path.read_text())
    # print(s)
    # print(len(s.instances))
    assert len(s["instances"]) == 1


if __name__ == "__main__":
    netlist_path = GDSDIR_TEMP / "test_interconnect.sp"
    netlist_path.write_text(spice_netlist_interconnect)
    picyaml_path = GDSDIR_TEMP / "test_interconnect.sp"
    mapping_path = PATH.module / "lumerical" / "mapping_ubcpdk.yml"
    spice_to_yaml(
        netlist_path=netlist_path,
        picyaml_path=picyaml_path,
        mapping_path=mapping_path,
        pdk="ubcpdk",
    )
    s = yaml.safe_load(picyaml_path.read_text())
    # print(s)
    # print(len(s.instances))
    assert len(s["instances"]) == 1
