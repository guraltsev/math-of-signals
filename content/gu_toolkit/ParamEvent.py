"""Standardized parameter-change event payloads.

This module defines ``ParamEvent``, the immutable structure emitted by
``ParamRef.observe`` and consumed by SmartFigure parameter hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from sympy.core.symbol import Symbol

if TYPE_CHECKING:
    from .ParamRef import ParamRef


@dataclass(frozen=True)
class ParamEvent:
    """Normalized parameter change event emitted by ParamRef observers.

    Parameters
    ----------
    parameter : sympy.Symbol
        The symbol whose value changed.
    old : Any
        The previous value, if provided by the underlying widget.
    new : Any
        The updated value from the underlying widget.
    ref : ParamRef
        Reference object that exposes the widget and convenience accessors.
    raw : Any, optional
        Raw traitlets event payload (or ``None`` when synthesized).

    Notes
    -----
    This structure is produced by :meth:`ParamRef.observe` and passed through
    :class:`SmartFigure` hooks. Consumers should prefer ``parameter`` and
    ``new`` for stable semantics, and use ``raw`` only for debugging.

    Examples
    --------
    >>> import sympy as sp  # doctest: +SKIP
    >>> from ParamEvent import ParamEvent  # doctest: +SKIP
    >>> a = sp.symbols("a")  # doctest: +SKIP
    >>> # A synthetic event for testing or documentation purposes:
    >>> ParamEvent(parameter=a, old=0, new=1, ref=None, raw=None)  # doctest: +SKIP
    """
    parameter: Symbol
    old: Any
    new: Any
    ref: "ParamRef"
    raw: Any = None
