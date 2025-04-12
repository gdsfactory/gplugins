import hashlib
import re
from abc import ABC, abstractmethod
from collections.abc import MutableMapping, Sequence
from typing import Any

import gdsfactory as gf
import klayout.db as kdb
from typing_extensions import override


class NetlistSpiceReaderDelegateWithStrings(kdb.NetlistSpiceReaderDelegate, ABC):
    """A KLayout SPICE reader delegate that supports string variables for ``Device`` through a hash map."""

    @property
    @abstractmethod
    def integer_to_string_map(self) -> MutableMapping[int, str]:
        pass


class NoCommentReader(kdb.NetlistSpiceReaderDelegate):
    """KLayout Spice reader without comments after $. This allows checking the netlist for HSPICE."""

    n_nodes: int = 0

    @override
    def parse_element(self, s: str, element: str) -> kdb.ParseElementData:
        if "$" in s:
            s, *_ = s.split("$")  # Don't take comments into account

        parsed = super().parse_element(s, element)
        # ensure uniqueness
        parsed.model_name = f"{parsed.model_name}_{self.n_nodes}"
        self.n_nodes += 1
        return parsed


class CalibreSpiceReader(NetlistSpiceReaderDelegateWithStrings):
    """KLayout Spice reader for Calibre LVS extraction output.

    Considers parameter values for generic `X` devices that start with `WG`.
    Ignores comments after $ excluding location given with ``$X=number $Y=number``.
    """

    n_nodes: int = 0
    calibre_location_pattern: str = r"\$X=(-?\d+) \$Y=(-?\d+)"

    def __init__(self) -> None:
        """Calibre Spice reader."""
        super().__init__()
        self._integer_to_string_map: MutableMapping[int, str] = {}

    @property
    def integer_to_string_map(self) -> MutableMapping[int, str]:
        return self._integer_to_string_map

    @integer_to_string_map.setter
    def integer_to_string_map(self, value: MutableMapping[int, str]) -> None:
        self._integer_to_string_map = value

    @override
    def wants_subcircuit(self, name: str) -> bool:
        """Model all SPICE models that start with `WG` as devices in order to support parameters."""
        return "WG" in name or super().wants_subcircuit(name)

    @override
    def parse_element(self, s: str, element: str) -> kdb.ParseElementData:
        # Allow Calibre-style model name given as `$[model_name]` by removing the brackets
        # This is used for resistors and capacitors
        if element != "X":
            s = re.sub(r"\$\[([^\]]+)\]", r"\1", s)

        x_value, y_value = None, None
        if "$" in s:
            if location_matches := re.search(self.calibre_location_pattern, s):
                x_value, y_value = (int(e) / 1000 for e in location_matches.group(1, 2))

            # Use default KLayout parser for rest of the SPICE
            s, *_ = s.split(" $")

        parsed = super().parse_element(s, element)
        parsed.parameters |= {"x": x_value, "y": y_value}

        # ensure uniqueness
        self.n_nodes += 1
        return parsed

    @staticmethod
    def hash_str_to_int(s: str) -> int:
        return int(hashlib.shake_128(s.encode()).hexdigest(4), 16)

    def write_str_property_as_int(self, value: str) -> int:
        """Store string property in hash map and return integer hash value."""
        hashed_value = CalibreSpiceReader.hash_str_to_int(value)
        self.integer_to_string_map[hashed_value] = value
        return hashed_value

    @override
    def element(
        self,
        circuit: kdb.Circuit,
        element: str,
        name: str,
        model: str,
        value: Any,
        nets: Sequence[kdb.Net],
        parameters: dict[str, int | float | str],
    ) -> bool:
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
            for key in parameters:
                clx.add_parameter(kdb.DeviceParameterDefinition(key))

            for i in range(len(nets)):
                clx.add_terminal(kdb.DeviceTerminalDefinition(str(i)))
            circuit.netlist().add(clx)

        device = circuit.create_device(clx, name)
        for i, net in enumerate(nets):
            device.connect_terminal(i, net)

        for key, value in parameters.items():
            # map string variables to integers
            possibly_hashed_value = (
                self.write_str_property_as_int(value)
                if isinstance(value, str)
                else value
            )

            device.set_parameter(
                key,
                (
                    possibly_hashed_value
                    or 0  # default to 0 for None in order to still have the parameter field
                ),
            )

        return True


class GdsfactorySpiceReader(CalibreSpiceReader):
    """KLayout Spice reader for Gdsfactory-extracted KLayout LayoutToNetlist.

    By default, all netlist elements are treated as devices if a corresponding component name is found in `gdsfactory.components.__all__`.
    You should specify the components to not to be considered as devices but as subcircuits
    with the `components_as_subcircuits` argument upon initialization.
    """

    def __init__(
        self,
        components_as_subcircuits: Sequence[str] | None = None,
        components_as_devices: Sequence[str] | None = None,
    ) -> None:
        """Gdsfactory Spice reader.

        Args:
            components_as_subcircuits: components to not treat as their own devices but look into the internal subcircuits
            components_as_devices: components to treat as their own devices
        """
        super().__init__()
        # Define default components to not treat as their own devices but look into the internal subcircuits
        self.components_as_subcircuits = [
            cell.casefold() for cell in (components_as_subcircuits or [])
        ]
        self.components_as_devices = [
            cell.casefold() for cell in (components_as_devices or gf.components.__all__)
        ]

    @override
    def wants_subcircuit(self, name: str) -> bool:
        """Model all basic gdsfactory components as devices in order to support parameters."""
        return all(
            cell not in name.casefold() for cell in self.components_as_subcircuits
        ) and (
            any(cell in name.casefold() for cell in self.components_as_devices)
            or super().wants_subcircuit(name)
        )
