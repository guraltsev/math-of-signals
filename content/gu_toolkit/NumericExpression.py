"""Numeric-expression views built on top of numpified callables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

import sympy as sp
from sympy.core.symbol import Symbol

from .numpify import BoundNumpifiedFunction, NumpifiedFunction, ParameterProvider

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class PlotView:
    """Live view of a plot's numeric evaluation based on a provider-backed bind."""

    _numpified: NumpifiedFunction
    _provider: ParameterProvider

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        """Evaluate using current provider-backed parameter values."""
        return self._numpified.bind(self._provider)(x)

    def bind(self, values: dict[Symbol, Any]) -> BoundNumpifiedFunction:
        """Create a snapshot-bound expression from explicit values."""
        return self._numpified.bind(values)

    def unbind(self) -> NumpifiedFunction:
        """Return the underlying unbound numpified function."""
        return self._numpified

    @property
    def expr(self) -> sp.Basic:
        """Return underlying symbolic expression."""
        return self._numpified.expr

    @property
    def args(self) -> tuple[Symbol, ...]:
        """Return ordered function argument symbols."""
        return self._numpified.args
