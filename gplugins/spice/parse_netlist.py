import re
from typing import Literal

# Your netlist text as a string
# TODO CHECK This is from lumerical interconnect right?
netlist_text = """
* Netlist generated with INTERCONNECT on Fri Dec 8 11:06:53 2023

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
SupportedSpiceTypes = Literal["lumerical", "xschem"]


def parse_netlist_and_extract_elements(
    netlist_text, spice_type: SupportedSpiceTypes = "lumerical"
):
    elements = []  # To store elements like components and subcircuits
    connections = []  # To store connections (routes) between elements
    settings = []  # To store settings like .MODEL definitions

    if spice_type == "lumerical":
        lines = netlist_text.split("\n")
        for line in lines:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("*"):
                continue

            # Handle .subckt, .ends, and .MODEL lines specifically
            if line.startswith(".subckt"):
                parts = re.split(r"\s+", line)
                subckt_name = parts[1]
                ports = parts[2:]
                elements.append({"type": "subckt", "name": subckt_name, "ports": ports})
            elif line.startswith(".ends"):
                continue
            elif line.startswith(".MODEL"):
                model_definition = re.split(pattern=r"\s+", string=line, maxsplit=1)[1]
                model_name, model_params = model_definition.split(" ", 1)
                elements.append(
                    {"type": "model", "name": model_name, "params": model_params}
                )
            else:
                # Assuming remaining lines are component instances
                parts = re.split(r"\s+", line)
                component_type = parts[0]
                component_name = parts[-1]
                # Extract connections from the nodes
                parts = parts[1:-1]
                nodes = []
                for i in range(len(parts) - 1):
                    if "=" not in parts[i + 1]:
                        nodes.append({"from": component_name, "to": parts[i]})
                    else:
                        component_name = parts[i]
                        settings.append(parts[i + 1 :])
                        break

                elements.append(
                    {
                        "type": "component",
                        "name": component_name,
                        "component_type": component_type,
                        "nodes": nodes,
                        "settings": settings,
                    }
                )

    elif spice_type == "xschem":
        lines = netlist_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith(
                "v {"
            ):  # Skip the version line and empty lines
                continue

            if line.startswith("C {"):
                parts = line.split(" ")
                component_info = parts[1].strip("{}")
                x, y = parts[2], parts[3]
                attributes_str = " ".join(parts[4:])
                match = re.search(
                    r"\{(.*)\}", attributes_str
                )  # Attempt to find the attributes

                if match:  # Check if a match was found
                    attributes = match.group(1)
                    name_match = re.search(r"name=([^ ]+)", attributes)
                    label_match = re.search(r"lab=([^}\n]+)", attributes)
                    name = name_match.group(1) if name_match else ""
                    label = label_match.group(1) if label_match else ""

                    additional_settings = re.findall(r"(\w+)=([^\s}]+)", attributes)
                    settings_dict = dict(additional_settings)

                    elements.append(
                        {
                            "type": "component",
                            "component_type": component_info,
                            "position": {"x": x, "y": y},
                            "name": name,
                            "label": label,
                            "settings": settings_dict,
                        }
                    )
                else:
                    # Handle lines that do not match the expected format
                    print(f"Warning: Line skipped due to unexpected format: {line}")
            elif line.startswith("N "):
                parts = line.split(" ")
                x1, y1, x2, y2 = parts[1], parts[2], parts[3], parts[4]
                attributes_str = " ".join(parts[5:])
                label_match = re.search(r"lab=([^}\n]+)", attributes_str)
                label = label_match.group(1) if label_match else ""

                connections.append(
                    {
                        "start": {"x": x1, "y": y1},
                        "end": {"x": x2, "y": y2},
                        "label": label,
                    }
                )

    return elements, connections, settings


if __name__ == "__main__":
    # Extract elements and connections
    elements, connections = parse_netlist_and_extract_elements(netlist_text)

    # Example output
    print("Elements:")
    for element in elements:
        print(element)

    print("\nConnections:")
    for connection in connections:
        print(connection)
