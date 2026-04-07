"""Notebook convenience namespace for :mod:`gu_toolkit`.

This module defines the notebook-first symbols exposed by
``from gu_toolkit import *`` so interactive sessions start with a practical,
batteries-included namespace (SymPy, NumPy, optional pandas, symbolic helpers,
and display utilities).

Examples
--------
>>> from gu_toolkit.Notebook import sp, np, x, f  # doctest: +SKIP
>>> sp.sin(x) + np.pi  # doctest: +SKIP

Discoverability
---------------
- Use :mod:`gu_toolkit.__init__` when you want the same convenience surface
  from package-level imports.
- Use :mod:`gu_toolkit.Figure` for plotting primitives and rendering helpers.
"""

from __future__ import annotations

__all__ = []

import sympy as sp

__all__ += ["sp"]
from sympy import *

__all__ += list(getattr(sp, "__all__", []))

import numpy as np

__all__ += ["np"]


try:
    import pandas as pd
except ModuleNotFoundError:  # Optional dependency
    pd = None
else:
    __all__ += ["pd", "DataFrame"]
    from pandas import DataFrame



try:
    from .numeric_operations import NIntegrate, NReal_Fourier_Series, play
    from .Symbolic import (
        FunctionFamily,
        Infix,
        SymbolFamily,
        symbols,
        eq,
        ge,
        gt,
        le,
        lt,
    )
except ImportError:  # pragma: no cover
    from numeric_operations import NIntegrate, NReal_Fourier_Series, play
    from Symbolic import (
        FunctionFamily,
        Infix,
        SymbolFamily,
        symbols,
        eq,
        ge,
        gt,
        le,
        lt,
    )

__all__ += [
    "SymbolFamily",
    "FunctionFamily",
    "Infix",
    "symbols",
    "eq",
    "lt",
    "le",
    "gt",
    "ge",
    "NIntegrate",
    "NReal_Fourier_Series",
    "play",
]

for _ch in "abcdefghijklmnopqrstuvwxyz":
    globals()[_ch] = SymbolFamily(_ch)
for _ch in "fgh":
    globals()[_ch] = FunctionFamily(_ch)
for _ch in "klmnij":
    globals()[_ch] = SymbolFamily(_ch, integer=True)
__all__ += list("abcdefghijklmnopqrstuvwxyz")

for _ch in "ABCDEFGHIJKLOPQRSTUVWXYZ":
    globals()[_ch] = SymbolFamily(_ch)
for _ch in "MN":
    globals()[_ch] = SymbolFamily(_ch, integer=True)
for _ch in "FGH":
    globals()[_ch] = FunctionFamily(_ch)
__all__ += list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

alpha = SymbolFamily("alpha")
beta = SymbolFamily("beta")
gamma = SymbolFamily("gamma")
delta = SymbolFamily("delta")
epsilon = SymbolFamily("epsilon")
varepsilon = SymbolFamily("varepsilon")
zeta = SymbolFamily("zeta")
eta = SymbolFamily("eta")
theta = SymbolFamily("theta")
vartheta = SymbolFamily("vartheta")
kappa = SymbolFamily("kappa")
lam = SymbolFamily("lambda")
mu = SymbolFamily("mu")
nu = SymbolFamily("nu")
xi = SymbolFamily("xi")
rho = SymbolFamily("rho")
sigma = SymbolFamily("sigma")
varsigma = SymbolFamily("varsigma")
tau = SymbolFamily("tau")
phi = SymbolFamily("phi")
varphi = SymbolFamily("varphi")
chi = SymbolFamily("chi")
psi = SymbolFamily("psi")
omega = SymbolFamily("omega")

__all__ += [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "varepsilon",
    "zeta",
    "eta",
    "theta",
    "vartheta",
    "kappa",
    "lam",
    "mu",
    "nu",
    "xi",
    "rho",
    "sigma",
    "varsigma",
    "tau",
    "phi",
    "varphi",
    "chi",
    "psi",
    "omega",
]

del _ch

from pprint import pprint
from IPython.display import HTML, Latex, display, Markdown

__all__ += ["HTML", "Latex","Markdown", "display", "pprint"]
