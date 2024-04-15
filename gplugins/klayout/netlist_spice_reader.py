import hashlib
import re
from abc import ABC, abstractmethod
from collections.abc import MutableMapping, Sequence
from typing import Any

import klayout.db as kdb


class NetlistSpiceReaderDelegateWithStrings(kdb.NetlistSpiceReaderDelegate, ABC):
    """A KLayout SPICE reader delegate that supports string variables for ``Device`` through a hash map."""

    @property
    @abstractmethod
    def integer_to_string_map(self) -> MutableMapping[int, str]:
        pass


class NoCommentReader(kdb.NetlistSpiceReaderDelegate):
    """KLayout Spice reader without comments after $. This allows checking the netlist for HSPICE."""

    n_nodes: int = 0

    def parse_element(self, s: str, element: str) -> kdb.ParseElementData:
        if "$" in s:
            s, *_ = s.split("$")  # Don't take comments into account
        parsed = super().parse_element(s, element)
        # ensure uniqueness
        parsed.model_name = parsed.model_name + f"_{self.n_nodes}"
        self.n_nodes += 1
        return parsed


class CalibreSpiceReader(NetlistSpiceReaderDelegateWithStrings):
    """KLayout Spice reader for Calibre LVS extraction output.

    Considers parameter values for generic `X` devices that start with `WG`.
    Ignores comments after $ excluding location given with ``$X=number $Y=number``."""

    n_nodes: int = 0
    calibre_location_pattern: str = r"\$X=(-?\d+) \$Y=(-?\d+)"
    integer_to_string_map: MutableMapping[int, str] = {}

    def wants_subcircuit(self, name: str):
        """Model all SPICE models that start with `WG` as devices in order to support parameters."""
        return "WG" in name or super().wants_subcircuit(name)

    def parse_element(self, s: str, element: str) -> kdb.ParseElementData:
        x_value, y_value = None, None
        if "$" in s:
            if location_matches := re.search(self.calibre_location_pattern, s):
                x_value, y_value = (int(e) / 1000 for e in location_matches.group(1, 2))

            # Use default KLayout parser for rest of the SPICE
            s, *_ = s.split("$")

        parsed = super().parse_element(s, element)
        parsed.parameters |= {"x": x_value, "y": y_value}

        # ensure uniqueness
        parsed.model_name = parsed.model_name
        self.n_nodes += 1
        return parsed

    @staticmethod
    def hash_str_to_int(s: str) -> int:
        return int(hashlib.shake_128(s.encode()).hexdigest(4), 16)

    def element(
        self,
        circuit: kdb.Circuit,
        element: str,
        name: str,
        model: str,
        value: Any,
        nets: Sequence[kdb.Net],
        parameters: dict[str, int | float | str],
    ):
        # Handle non-'X' elements with standard KLayout processing
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
                if (
                    isinstance(value, str)
                    and value not in self.integer_to_string_map.values()
                ):
                    hashed_value = CalibreSpiceReader.hash_str_to_int(value)
                    self.integer_to_string_map[hashed_value] = value

            for i in range(len(nets)):
                clx.add_terminal(kdb.DeviceTerminalDefinition(str(i)))
            circuit.netlist().add(clx)

        device = circuit.create_device(clx, name)
        for i, net in enumerate(nets):
            device.connect_terminal(i, net)

        for key, value in parameters.items():
            device.set_parameter(
                key,
                (
                    CalibreSpiceReader.hash_str_to_int(value)
                    if isinstance(value, str)
                    else value
                ),
            )
