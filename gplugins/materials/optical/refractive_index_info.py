# type: ignore
"""Adapted from Lucas Heitzmann at https://gist.github.com/lucas-flexcompute/5186955dc04dc2d1918cd7c6b5d59d5e."""

import pathlib
import urllib.request

import numpy
import yaml
from numpy import pi

π = numpy.pi
c0 = 299792458
μ0 = 4e-7 * pi
ε0 = 1.0 / (c0**2 * μ0)
eta0 = c0 * μ0


class RefractiveIndex:
    """Refractive index as a wavelength function.

    Methods `n(lda)`, `dn(lda)` and `d2n(lda)` return, respectively, the
    refractive index, its first and its second derivatives with respect to the
    wavelength for a given wavelength `lda` (number or numpy.array).

    Args:
        name: Object name
        **kwargs: Refractive index definition.  Possible keyword arguments are:
            lda (numpy.array[N]): Sampled wavelengths.
            n (numpy.array[N]): Refractive index for each `lda`.
            lda_k (numpy.array[K]): Sampled wavelengths for k values.
            k (numpy.array[N or K]): Extinction coefficient for each `lda` or
            `lda_k`.
            eps (numpy.array[N]): Relative permittivity for each `lda`.
            tand (number): Loss tangent.
            sigma (number): Conductivity.
            lda_min (number): Minimal wavelength for which the function is
            defined.
            lda_max (number): Maximal wavelength for which the function is
            defined.
            formula (number): Formula identifier.  Possible values are:
            - 1 or 2: n² = c[0] + Σ c[i] / (1 - c[i+1] λ⁻²);
            - 3: n² = c[0] + Σ c[i] λ^c[i+1]
            - 4: n² = c[0] + c[1] λ^c[2] / (λ² - c[3])
                      + c[4] λ^c[5] / (λ² - c[6]) + Σ c[i] λ^c[i+1]
            - 5: n = c[0] + Σ c[i] λ^c[i+1]
            - 6: n = c[0] + Σ c[i] / (c[i+1] - λ⁻²)
            - 7: n = c[0] + c[1] / (λ² - r) + c[2] / (λ² - r)²
                     + Σ c[i] λ^(2i - 4);  r = 2.8×10⁻¹⁴
            - 8: n² = (1 + 2g) / (1 - g)
                 g = c[0] + c[1] λ² / (λ² - c[2]) + c[3] λ²
            - 9: n² = c[0] + c[1] / (λ² - c[2])
                      + c[3] (λ - c[4]) / ((λ - c[4])² +c[5])
            coefficients (list): Formula coefficients.
    """

    def __init__(self, name="", **kwargs):
        """Create refractive index."""
        self.name = name
        self.lda = None
        self.lda_k = None
        self.lda_min = 0
        self.lda_max = numpy.inf
        self.n = None
        self.k = None
        lda_min_set = False
        lda_max_set = False
        if "lda_min" in kwargs:
            self.lda_min = kwargs["lda_min"]
            lda_min_set = True
        if "lda_max" in kwargs:
            self.lda_max = kwargs["lda_max"]
            lda_max_set = True
        if "formula" in kwargs:
            self.k = lambda x: numpy.zeros_like(x)
            formula = kwargs["formula"]
            c = kwargs["coefficients"]
            if formula in [1, 2]:
                # n² = c[0] + Σ c[i] / (1 - c[i+1] λ⁻²)

                def n(x):
                    x2 = x**2
                    return (
                        c[0]
                        + sum(
                            c[i] / (1 - c[i + 1] / x2) for i in range(1, c.size - 1, 2)
                        )
                    ) ** 0.5

                def dn(x):
                    x2 = x**2
                    num = 0
                    for i in range(1, c.size - 1, 2):
                        y = 1 / (x2 - c[i + 1])
                        num += c[i] * x * y * (1 - x2 * y)
                    den = (
                        c[0]
                        + sum(
                            c[i] / (1 - c[i + 1] / x2) for i in range(1, c.size - 1, 2)
                        )
                    ) ** 0.5
                    return num / den

                def d2n(x):
                    x2 = x**2
                    x2_5 = 5 * x2
                    x4_4 = 4 * x2**2
                    num1 = 0
                    num2 = 0
                    for i in range(1, c.size - 1, 2):
                        y = 1 / (c[i + 1] - x2)
                        y2 = y**2
                        num1 += c[i] * (y + x2_5 * y2 + x4_4 * y**3)
                        num2 += c[i] * (y + x2 * y2)
                    den = c[0] + sum(
                        c[i] / (1 - c[i + 1] / x2) for i in range(1, c.size - 1, 2)
                    )
                    return -(num1 + (x * num2) ** 2 / den) / den**0.5

            elif formula == 3:
                # n² = c[0] + Σ c[i] λ^c[i+1]

                def n(x):
                    return (
                        c[0]
                        + sum(c[i] * x ** c[i + 1] for i in range(1, c.size - 1, 2))
                    ) ** 0.5

                def dn(x):
                    n2 = c[0]
                    res = 0
                    for i in range(1, c.size - 1, 2):
                        y = c[i] * x ** c[i + 1]
                        n2 += y
                        res += c[i + 1] * y
                    return res / (2 * x * n2**0.5)

                def d2n(x):
                    n2 = c[0]
                    y1 = 0
                    y2 = 0
                    for i in range(1, c.size - 1, 2):
                        fac = c[i] * x ** c[i + 1]
                        n2 += fac
                        fac2 = fac * c[i + 1]
                        y1 += fac2 * c[i + 1]
                        y2 += fac2
                    return (y1 - y2 - y2**2 / (2 * n2)) / (2 * x**2 * n2**0.5)

            elif formula == 4:
                # n² = c[0] + c[1] λ^c[2] / (λ² - c[3]) + c[4] λ^c[5] / (λ² - c[6]) + Σ c[i] λ^c[i+1]

                def n(x):
                    y = x**2
                    return (
                        c[0]
                        + c[1] * x ** c[2] / (y - c[3])
                        + c[4] * x ** x[5] / (y - c[6])
                        + sum(c[i] * x ** c[i + 1] for i in range(7, c.size - 1, 2))
                    ) ** 0.5

                def dn(x):
                    y = x**2
                    d3 = 1 / (y - c[3])
                    d6 = 1 / (y - c[6])
                    n1 = c[1] * d3 * x ** c[2]
                    n4 = c[4] * d6 * x ** c[5]
                    nsq = c[0] + n1 + n4
                    num = c[2] * n1 + c[5] * n4
                    for i in range(7, c.size - 1, 2):
                        fac = c[i] * x ** c[i + 1]
                        nsq += fac
                        num += fac * c[i + 1]
                    return (num / (2 * x) - x * (n1 * d3 + n4 * d6)) / nsq**0.5

                def d2n(x):
                    y = x**2
                    z = 1 / (2 * y)
                    d3 = 1 / (y - c[3])
                    d6 = 1 / (y - c[6])
                    n1 = c[1] * d3 * x ** c[2]
                    n4 = c[4] * d6 * x ** x[5]
                    nsq = c[0] + n1 + n4
                    num1 = (
                        c[2] * (c[2] - 1) * z - d3 * (2 * c[2] - 4 * y * d3 + 1)
                    ) * n1 + (
                        c[5] * (c[5] - 1) * z - d6 * (2 * c[5] - 4 * y * d6 + 1)
                    ) * n4
                    num2 = (n1 * c[2] + n4 * c[5]) / x - 2 * x * (n1 * d3 + n4 * d6)
                    for i in range(7, c.size - 1, 2):
                        fac = c[i] * x ** c[i + 1]
                        nsq += fac
                        num1 += (c[8] - 1) * c[8] * fac * z
                        num2 += c[8] * fac / x
                    n = nsq**0.5
                    return (num1 - (num2 / (2 * n)) ** 2) / n

            elif formula == 5:
                # n = c[0] + Σ c[i] λ^c[i+1]

                def n(x):
                    return c[0] + sum(
                        c[i] * x ** c[i + 1] for i in range(1, c.size - 1, 2)
                    )

                def dn(x):
                    return sum(
                        c[i] * c[i + 1] * x ** (c[i + 1] - 1)
                        for i in range(1, c.size - 1, 2)
                    )

                def d2n(x):
                    return sum(
                        c[i] * c[i + 1] * (c[i + 1] - 1) * x ** (c[i + 1] - 2)
                        for i in range(1, c.size - 1, 2)
                    )

            elif formula == 6:
                # n = c[0] + Σ c[i] / (c[i+1] - λ⁻²)

                def n(x):
                    z = x ** (-2)
                    return c[0] + sum(
                        c[i] / (c[i + 1] - z) for i in range(1, c.size - 1, 2)
                    )

                def dn(x):
                    z = x ** (-2)
                    return (
                        -2
                        * z
                        / x
                        * sum(
                            c[i] / (c[i + 1] - z) ** 2 for i in range(1, c.size - 1, 2)
                        )
                    )

                def d2n(x):
                    z = x ** (-2)
                    val = 0
                    for i in range(1, c.size - 1, 2):
                        fac = 1 / (c[i + 1] - z)
                        val += (3 + 4 * z * fac) * c[i] * fac**2
                    return 2 * z**2 * val

            elif formula == 7:
                # r = 2.8×10⁻¹⁴
                # n = c[0] + c[1] / (λ² - r) + c[2] / (λ² - r)² + Σ c[i] λ^(2i - 4)

                def n(x):
                    r = 2.8e-14
                    y = x**2
                    z = 1 / (y - r)
                    val = c[-1]
                    for i in range(c.size - 2, 2, -1):
                        val = y * val + c[i]
                    return c[0] + z * (c[1] + z * c[2]) + val * y

                def dn(x):
                    r = 2.8e-14
                    y = x**2
                    z = 1 / (y - r)
                    val = c[-1] * (c.size - 3)
                    for i in range(c.size - 2, 2, -1):
                        val = y * val + c[i] * (i - 2)
                    return 2 * x * (val - z**2 * (c[1] + 2 * c[2] * z))

                def d2n(x):
                    r = 2.8e-14
                    y = x**2
                    z = 1 / (y - r)
                    val = c[-1] * (2 * c.size - 7) * (2 * c.size - 6)
                    for i in range(c.size - 2, 2, -1):
                        val = y * val + c[i] * (2 * i - 5) * (2 * i - 4)
                    return val + 2 * z**2 * (
                        ((c[1] + 3 * c[2] * z) * 4 * y - 2 * c[2]) * z - c[1]
                    )

            elif formula == 8:
                # g = c[0] + c[1] λ² / (λ² - c[2]) + c[3] λ²
                # n² = (1 + 2g) / (1 - g)

                def n(x):
                    y = x**2
                    g = c[0] + c[1] * y / (y - c[2]) + c[3] * y
                    return ((1 + 2 * g) / (1 - g)) ** 0.5

                def dn(x):
                    y = x**2
                    z = 1 / (y - c[2])
                    g = c[0] + c[1] * y * z + c[3] * y
                    dg = 2 * x * (c[3] - c[1] * c[2] * z**2)
                    df = 3 * ((1 + 2 * g) / (1 - g)) ** 0.5 / (2 + g * (2 - 4 * g))
                    return df * dg

                def d2n(x):
                    y = x**2
                    z = 1 / (y - c[2])
                    w = z**2
                    g = c[0] + c[1] * y * z + c[3] * y
                    num = 1 + 2 * g
                    den = 1 - g
                    n = (num / den) ** 0.5
                    dg = 2 * x * (c[3] - c[1] * c[2] * w)
                    df = 3 * n / (2 + g * (2 - 4 * g))
                    d2g = 2 * c[3] + 2 * c[1] * z * (1 + y * w * (5 * c[2] - y))
                    d2f = n * (6 * g + 3 / 4) / (num * den) ** 2
                    return df * d2g + d2f * dg**2

            elif formula == 9:
                # n² = c[0] + c[1] / (λ² - c[2]) + c[3] (λ - c[4]) / ((λ - c[4])² +c[5])

                def n(x):
                    x4 = x - c[4]
                    return (
                        c[0] + c[1] / (x**2 - c[2]) + c[3] * x4 / (c[5] + x4**2)
                    ) ** 0.5

                def dn(x):
                    y = x**2
                    z = 1 / (y - c[2])
                    x4 = x - c[4]
                    y4 = x4**2
                    z4 = 1 / (c[5] + y4)
                    g = c[0] + c[1] * z + c[3] * x4 * z4
                    dg = -2 * x * c[1] * z**2 + c[3] * z4**2 * (c[5] - y4)
                    df = 1 / (2 * g**0.5)
                    return df * dg

                def d2n(x):
                    y = x**2
                    z = 1 / (y - c[2])
                    w = z**2
                    x4 = x - c[4]
                    y4 = x4**2
                    w4 = y4**2
                    z4 = 1 / (c[5] + y4)
                    g = c[0] + c[1] * z + c[3] * x4 * z4
                    dg = -2 * x * c[1] * w + c[3] * w4 * (c[5] - y4)
                    df = 1 / (2 * g**0.5)
                    d2g = 2 * (
                        (4 * y * z - 1) * c[1] * w + (4 * y4 * z4 - 3) * c[3] * x4 * w4
                    )
                    d2f = -1 / (4 * (g**0.5) ** 3)
                    return df * d2g + d2f * dg**2

            else:
                raise NotImplementedError(f"Formula {formula} not implemented.")
            self.n = n
            self.dn = dn
            self.d2n = d2n
        else:
            if "lda" in kwargs:
                self.lda = self.lda_k = kwargs["lda"]
                if self.lda[0] >= self.lda[-1]:
                    raise RuntimeError(
                        "Argument lda must be sorted in ascending order."
                    )
                if not lda_min_set:
                    self.lda_min = self.lda[0]
                    lda_min_set = True
                if not lda_max_set:
                    self.lda_max = self.lda[-1]
                    lda_max_set = True
                if "n" in kwargs:
                    self._set_n_list(self.lda, kwargs["n"])
                if "lda_k" not in kwargs and "k" in kwargs:
                    self._set_k_list(self.lda, kwargs["k"])
                if "eps" in kwargs:
                    eps = kwargs["eps"]
                    if "tand" in kwargs:
                        eps = eps * (1 - 1j * kwargs["tand"])
                    elif "sigma" in kwargs:
                        eps = eps * (
                            1 - 1j * kwargs["sigma"] * eta0 / (2 * π) * self.lda
                        )
                    self._set_eps_list(self.lda, eps)
            if "lda_k" in kwargs:
                self.lda_k = kwargs["lda_k"]
                if self.lda_k[0] >= self.lda_k[-1]:
                    raise RuntimeError(
                        "Argument lda_k must be sorted in ascending order."
                    )
                if not lda_min_set:
                    self.lda_min = self.lda_k[0]
                    lda_min_set = True
                if not lda_max_set:
                    self.lda_max = self.lda_k[-1]
                    lda_max_set = True
                self._set_k_list(self.lda_k, kwargs["k"])

    def __str__(self):
        """Return name."""
        return self.name

    def _set_n_list(self, lda, n):
        self.n = lambda x: numpy.interp(x, lda, n, left=numpy.nan, right=numpy.nan)
        g = numpy.gradient(n, lda)
        self.dn = lambda x: numpy.interp(x, lda, g, left=numpy.nan, right=numpy.nan)
        g2 = numpy.gradient(g, lda)
        self.d2n = lambda x: numpy.interp(x, lda, g2, left=numpy.nan, right=numpy.nan)
        self.k = lambda x: numpy.zeros_like(x)

    def _set_k_list(self, lda, k):
        self.k = lambda x: numpy.interp(x, lda, k, left=numpy.nan, right=numpy.nan)
        if self.n is None:
            self.n = lambda x: numpy.ones_like(x)
            self.dn = lambda x: numpy.zeros_like(x)
            self.d2n = lambda x: numpy.zeros_like(x)

    def _set_eps_list(self, lda, eps):
        nk = eps**0.5
        self.n = lambda x: numpy.interp(
            x, lda, nk.real, left=numpy.nan, right=numpy.nan
        )
        self.k = lambda x: numpy.interp(
            x, lda, nk.imag, left=numpy.nan, right=numpy.nan
        )
        g = numpy.gradient(nk.real, lda)
        self.dn = lambda x: numpy.interp(x, lda, g, left=numpy.nan, right=numpy.nan)
        g2 = numpy.gradient(g, lda)
        self.d2n = lambda x: numpy.interp(x, lda, g2, left=numpy.nan, right=numpy.nan)

    def dispersion(self, lda):
        """Material dispersion.

        D(λ) = -λ / c₀ d²n/dλ²
        Args:
            lda (number or numpy.array): Wavelength.
        """
        return lda * self.d2n(lda) / -c0

    def gvd(self, lda):
        """Group velocity dispersion.

        GVD(λ) = λ³ / (2π c₀²) d²n/dλ²
        Args:
            lda (number or numpy.array): Wavelength.
        """
        return lda**3 * self.d2n(lda) / (2 * π * c0**2)

    def ng(self, lda):
        """Group index.

        ng(λ) = n - λ dn/dλ
        Args:
            lda (number or numpy.array): Wavelength.
        """
        return self.n(lda) - lda * self.dn(lda)


def loadRefractiveIndexInfo(
    url=None,
    shelf=None,
    book=None,
    page=None,
    force_update=False,
    cache_dir="~/.cache/emu-cache",
    **kwargs,
):
    """Create a `RefractiveIndex` object from https://refractiveindex.info/.

    Args:
        *args: Material identifier.  Can be either the url for the material or
        3 strings for shelf, book and page.
        force_update (bool): Ignore the cached data (if any) and download a new
        version.
        cache_dir (str): Cache directory for downloaded data.  The tilde (~)
        character is replaced by the current user's home directory.
        **kwargs: Accepted values are book, shelf and page, identifying the
        material.
    """
    if url is not None:
        spec = dict(tuple(x.split("=")) for x in url.split("?")[1].split("&"))
        shelf = spec["shelf"]
        book = spec["book"]
        page = spec["page"]
    elif shelf is not None and book is not None and page is not None:
        shelf, book, page = shelf, book, page
    else:
        raise ValueError(
            "loadRefractiveIndexInfo needs (1) url (str) or (2) shelf (str), book (str), and page (str)."
        )
    name = f"{shelf}_{page}_{book}"

    cachedir = pathlib.Path(cache_dir.replace("~", str(pathlib.Path.home())))
    if not cachedir.exists():
        cachedir.mkdir(parents=True)

    cachefile = (cachedir / name).with_suffix(".npz")
    if (not force_update) and cachefile.exists():
        cache = numpy.load(cachefile)
        return RefractiveIndex(name, **cache)

    baseaddress = "https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/master/database/"
    lib = yaml.safe_load(
        urllib.request.urlopen(f"{baseaddress}library.yml").read().decode()
    )

    save = {}
    for s in lib:
        if "SHELF" in s and shelf == s["SHELF"]:
            for b in s["content"]:
                if "BOOK" in b and book == b["BOOK"]:
                    for p in b["content"]:
                        if "PAGE" in p and page == p["PAGE"]:
                            dataaddress = (baseaddress + "data/" + p["data"]).replace(
                                " ", "%20"
                            )
                            data = yaml.safe_load(
                                urllib.request.urlopen(dataaddress).read().decode()
                            )
                            save = {}
                            for d in data["DATA"]:
                                if d["type"] == "tabulated nk":
                                    val = numpy.array(
                                        [float(x) for x in d["data"].split()]
                                    )
                                    val = val.reshape((val.size // 3, 3))
                                    save["lda"] = val[:, 0] * 1e-6
                                    save["n"] = val[:, 1]
                                    save["k"] = val[:, 2]
                                elif d["type"] == "tabulated n":
                                    val = numpy.array(
                                        [float(x) for x in d["data"].split()]
                                    )
                                    val = val.reshape((val.size // 2, 2))
                                    save["lda"] = val[:, 0] * 1e-6
                                    save["n"] = val[:, 1]
                                elif d["type"] == "tabulated k":
                                    val = numpy.array(
                                        [float(x) for x in d["data"].split()]
                                    )
                                    val = val.reshape((val.size // 2, 2))
                                    save["lda_k"] = val[:, 0] * 1e-6
                                    save["k"] = val[:, 1]
                                else:
                                    formula = int(d["type"].split()[1])
                                    a, b = d["wavelength_range"].split()
                                    save["formula"] = formula
                                    save["lda_min"] = float(a) * 1e-6
                                    save["lda_max"] = float(b) * 1e-6
                                    c = numpy.array(
                                        [float(x) for x in d["coefficients"].split()]
                                    )
                                    if formula == 1:
                                        c[0] += 1
                                        c[2::2] = (c[2::2] * 1e-6) ** 2
                                    elif formula == 2:
                                        c[0] += 1
                                        c[2::2] = c[2::2] * 1e-12
                                    elif formula == 3 or formula == 5:
                                        c[1::2] *= 10 ** (6 * c[2::2])
                                    elif formula == 4:
                                        c[3] = c[3] ** c[4] * 1e-12
                                        c[7] = c[7] ** c[8] * 1e-12
                                        c[1] *= 10 ** (6 * c[2] - 12)
                                        c[5] *= 10 ** (6 * c[6] - 12)
                                        c[9::2] *= 10 ** (6 * c[10::2])
                                        c = numpy.hstack((c[:4], c[5:8], c[9:]))
                                    elif formula == 6:
                                        c[0] += 1
                                        c[1::] *= 1e12
                                    elif formula == 7:
                                        c[1] *= 1e-12
                                        c[2] *= 1e-24
                                        c[3::] *= 10 ** (12 * numpy.arange(c.size - 3))
                                    elif formula == 8:
                                        c[2] *= 1e-12
                                        c[3] *= 1e12
                                    elif formula == 9:
                                        c[1] *= 1e-12
                                        c[2] *= 1e-12
                                        c[3] *= 1e-6
                                        c[4] *= 1e-6
                                        c[5] *= 1e-12
                                    else:
                                        raise NotImplementedError(
                                            f"Formula {formula} not implemented."
                                        )
                                    save["coefficients"] = c
                            numpy.savez(cachefile, **save)
                            return RefractiveIndex(name, **save)


if __name__ == "__main__":
    print(
        loadRefractiveIndexInfo(
            "https://refractiveindex.info/?shelf=main&book=Si&page=Li-293K"
        ).n(1.55e-6)
    )
