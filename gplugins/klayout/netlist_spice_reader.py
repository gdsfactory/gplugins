import klayout.db as kdb


class NoCommentReader(kdb.NetlistSpiceReaderDelegate):
    """KLayout Spice reader without comments after $. This allows checking the netlist for HSPICE"""

    def parse_element(self, s: str, element: str) -> kdb.ParseElementData:
        if "$" in s:
            s = s.split("$")[0]  # Don't take comments into account
        parsed = super().parse_element(s, element)
        return parsed
