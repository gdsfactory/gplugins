import klayout.db as kdb


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
