import numpy as np
from scipy import interpolate

from gplugins.materials.optical.refractive_index_info import (
    loadRefractiveIndexInfo,
)


class OpticalMaterial:
    def __init__(
        self, ureg=None, load_source=None, lda_min=0, lda_max=np.inf, formula=1
    ) -> None:
        """Create optical material."""
        self.ureg = ureg
        if load_source is not None:
            self.n, self.k = self.fit_index_from_refractiveindexinfo(
                url=load_source, lda_min=lda_min, lda_max=lda_max, formula=formula
            )
        else:
            self.n = None
            self.k = None

    def fit_index_from_refractiveindexinfo(
        self,
        url=None,
        shelf=None,
        book=None,
        page=None,
        lda_min=0,
        lda_max=np.inf,
        formula=1,
    ):
        self.refractive_index = loadRefractiveIndexInfo(
            url=url,
            shelf=shelf,
            book=book,
            page=page,
            lda_min=lda_min,
            lda_max=lda_max,
            formula=formula,
        )
        return lambda wl: self.refractive_index.n(
            wl / self.ureg("meters")
        ), lambda wl: self.refractive_index.k(wl / self.ureg("meters"))

    def fit_index_from_wls_nk(self, wls, ns, ks=None) -> None:
        """Fit real and imaginary parts of the refractive to wavelength.

        Arguments:
            wls: wavelengths (in meters)
            ns: refractive indices
            ks: extinction coefficients
        """
        self.n = lambda wl: interpolate.interp1d(wls.to("meters").magnitude, ns)(
            wl.to("meters").magnitude
        )
        self.k = (
            lambda wl: interpolate.interp1d(wls.to("meters").magnitude, ks)(
                wl.to("meters").magnitude
            )
            if ks is not None
            else lambda x: 0.0
        )
