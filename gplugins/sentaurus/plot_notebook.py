# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.15.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# +
import pandas as pd

n29 = pd.read_csv("n34_trans_0004_des.csv")
n29.Y = -n29.Y
n29.head()

# +
import numpy as np
import scipy.interpolate

X = np.sort(n29.X.unique())
Y = np.sort(n29.Y.unique())

XX, YY = np.meshgrid(X, Y)
eDensity = scipy.interpolate.griddata(
    n29[["X", "Y"]].values, n29["eDensity"].values, (XX, YY), method="linear"
)
hDensity = scipy.interpolate.griddata(
    n29[["X", "Y"]].values, n29["hDensity"].values, (XX, YY), method="linear"
)
# -

import matplotlib.pyplot as plt

im = plt.pcolor(XX, YY, np.log10(eDensity), cmap="hot")
plt.colorbar(im)
plt.xlim(-0.5, 0.5)
plt.ylim(-0.5, 0.2)
plt.title("log(eDensity [/cm^3])")
plt.show()

import matplotlib.pyplot as plt

im = plt.pcolor(XX, YY, np.log10(hDensity), cmap="hot")
plt.colorbar(im)
plt.xlim(-0.5, 0.5)
plt.ylim(-0.5, 0.2)
plt.title("log(hDensity [/cm^3])")
plt.show()

df_mode = pd.read_pickle("lumerical_MODE/8mu_bend_rib.gz", compression="gzip")

import numpy as np

first_freq = df_mode.frequency == df_mode.frequency.unique()[0]
df_uniq_freq = df_mode[first_freq]
xx, zz = np.meshgrid(df_uniq_freq.x.unique(), df_uniq_freq.z.unique())
E2 = df_uniq_freq.pivot(index="x", columns="z", values="E2").values.T
n = df_uniq_freq.pivot(index="x", columns="z", values="n").values.T

xx_mode = xx * 1e6
yy_mode = zz * 1e6 - 0.22  # y > 0 outwards from the ring. Curvature 8um

import matplotlib.pyplot as plt

im = plt.pcolor(xx_mode, yy_mode, E2, cmap="hot")
plt.colorbar(im)
plt.contour(xx_mode, yy_mode, n)
plt.xlim(-1, 1)
plt.ylim(-0.5, 0.2)
plt.show()

eDensity = scipy.interpolate.griddata(
    n29[["X", "Y"]].values, n29["eDensity"].values, (xx_mode, yy_mode), method="linear"
)
hDensity = scipy.interpolate.griddata(
    n29[["X", "Y"]].values, n29["hDensity"].values, (xx_mode, yy_mode), method="linear"
)

import matplotlib.pyplot as plt

im = plt.pcolor(xx_mode, yy_mode, np.arcsinh(eDensity), cmap="hot")
plt.colorbar(im)
plt.contour(xx_mode, yy_mode, n)
plt.xlim(-1, 1)
plt.ylim(-0.5, 0.2)
plt.title("asinh(eDensity [/cm^3])")
plt.show()

im = plt.pcolor(xx_mode, yy_mode, np.arcsinh(hDensity), cmap="hot")
plt.colorbar(im)
plt.contour(xx_mode, yy_mode, n)
plt.xlim(-1, 1)
plt.ylim(-0.5, 0.2)
plt.title("asinh(hDensity [/cm^3])")
plt.show()

eIntrinsic = 1.45e10
Δn = (
    -5.1e-22 * np.abs(eDensity - eIntrinsic) ** 1.011
    - 1.53e-18 * np.abs(hDensity - eIntrinsic) ** 0.838
)
im = plt.pcolor(xx_mode, yy_mode, Δn * E2, cmap="hot")
plt.colorbar(im)
plt.contour(xx_mode, yy_mode, n)
plt.xlim(-1, 1)
plt.ylim(-0.5, 0.2)
plt.title("Δn * E2")
plt.show()
