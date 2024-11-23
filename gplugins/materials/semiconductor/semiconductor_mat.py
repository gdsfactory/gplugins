class SemiconductorMaterial:
    def __init__(self, ureg=None) -> None:
        """Semiconductor parameters."""
        self.ureg = ureg
        self.m_e = None
        self.m_hh = None
        self.m_lh = None
        self.eps = None
        self.Eg = None
        self.ni = None
