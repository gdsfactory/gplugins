import re
from collections.abc import Mapping, Sequence
from typing import Any, override

import klayout.db as kdb


class CalibreSpiceReader(kdb.NetlistSpiceReaderDelegate):
    """KLayout Spice reader for Calibre LVS extraction output.

    Considers parameter values for generic `X` devices and ignores comments after $."""

    n_nodes: int = 0
    calibre_location_pattern: str = r"\$X=(-?\d+) \$Y=(-?\d+)"
    string_to_integer_map: Mapping[str, int] = dict()
    integer_to_string_map: Mapping[int, str] = dict()

    @override
    def wants_subcircuit(self, name: str):
        """Model all SPICE models that start with `WG` as devices in order to support parameters."""
        return "WG" in name or super().wants_subcircuit(name)

    @override
    def parse_element(self, s: str, element: str) -> kdb.ParseElementData:
        x_value, y_value = None, None
        if "$" in s:
            if location_matches := re.search(self.calibre_location_pattern, s):
                x_value, y_value = (int(e) / 1000 for e in location_matches.group(1, 2))

            # Use default KLayout parser for rest pf the SPICE
            s, *_ = s.split("$")

        parsed = super().parse_element(s, element)
        parsed.parameters |= {"x": x_value, "y": y_value}

        # ensure uniqueness
        # parsed.model_name = parsed.model_name + f"_{self.n_nodes}"
        self.n_nodes += 1
        return parsed

    @override
    def element(
        self,
        circuit: kdb.Circuit,
        element: str,
        name: str,
        model: str,
        value: Any,
        nets: Sequence[kdb.Net],
        parameters: Mapping[str, int | float | str],
    ):
        if element != "X":
            # Other devices with standard KLayout
            return super().element(
                circuit, element, name, model, value, nets, parameters
            )
        clx = circuit.netlist().device_class_by_name(model)

        # Create Device class on first occurrence
        if not clx:
            clx = kdb.DeviceClass()
            clx.name = model
            for key, value in parameters.items():
                clx.add_parameter(kdb.DeviceParameterDefinition(key))
                # map string variables to integers
                if isinstance(value, str) and value not in self.string_to_integer_map:
                    hashed_value = hash(value)
                    self.string_to_integer_map[value] = hashed_value
                    self.integer_to_string_map[hashed_value] = value

            for i, net in enumerate(nets):
                clx.add_terminal(kdb.DeviceTerminalDefinition(str(i)))
            circuit.netlist().add(clx)

        device = circuit.create_device(clx, name)
        for i, net in enumerate(nets):
            device.connect_terminal(i, net)

        for key, value in parameters.items():
            device.set_parameter(
                key, value if not isinstance(value, str) else hash(value)
            )
