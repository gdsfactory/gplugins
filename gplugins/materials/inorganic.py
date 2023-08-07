from pint import UnitRegistry

from gplugins.materials.optical.optical_mat import OpticalMaterial
from gplugins.materials.semiconductor.semiconductor_mat import (
    SemiconductorMaterial,
)


class Si:
    def __init__(self, ureg=None) -> None:
        """Default silicon parameters."""
        # Instantiate (default) or reuse unit registry
        self.ureg = UnitRegistry() if ureg is None else ureg

        # Default optical data from https://refractiveindex.info/?shelf=main&book=Si&page=Li-293K
        load_source = "https://refractiveindex.info/?shelf=main&book=Si&page=Li-293K"
        self.optical = OpticalMaterial(ureg=self.ureg, load_source=load_source)

        # Default semiconductor data from http://www.ioffe.ru/SVA/NSM/Semicond/Si/index.html
        self.semiconductor = SemiconductorMaterial(ureg=self.ureg)
        self.semiconductor.Eg = 1.12 * self.ureg.electron_volt
        self.semiconductor.ni = 1e10 / (self.ureg.cm**3)
        self.semiconductor.epsStatic = 11.7


class SiO2:
    def __init__(self, ureg=None) -> None:
        """Default silicon dioxide parameters."""
        # Instantiate (default) or reuse unit registry
        self.ureg = UnitRegistry() if ureg else ureg

        # Default optical data from https://refractiveindex.info/?shelf=main&book=Si&page=Li-293K
        load_source = "https://refractiveindex.info/?shelf=main&book=SiO2&page=Malitson"
        self.optical = OpticalMaterial(self.ureg, load_source=load_source)

        # Default semiconductor data
        self.semiconductor = SemiconductorMaterial(self.ureg)
        self.semiconductor.epsStatic = (
            3.8  # https://www.iue.tuwien.ac.at/phd/filipovic/node26.html
        )


if __name__ == "__main__":
    ureg = UnitRegistry()
    si = Si(ureg=ureg)
