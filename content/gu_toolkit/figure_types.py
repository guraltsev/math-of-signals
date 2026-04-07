"""Shared typing contracts for notebook-facing figure APIs.

This package accepts a few "friendly" input forms in public APIs:

* Numeric values are often allowed as ``int`` or ``float``.
* Some numeric inputs also accept strings such as ``"pi"`` or ``"pi/2"``.
  These are converted using :func:`gu_toolkit.InputConvert.InputConvert`.

The aliases in this module exist to:

* keep signatures readable across the figure entry point and its helper
  modules,
* ensure the same semantics are used everywhere (avoid drift),
* provide a single documentation location for these API contracts.

Notes
-----
These are *typing* contracts only. Runtime conversion is performed by
``InputConvert`` at the point where values are used.
"""

from __future__ import annotations

from typing import TypeAlias


# Public-ish type aliases (used in signatures and docs)
NumberLike: TypeAlias = int | float
"""A value that can be treated as a number without string conversion."""

NumberLikeOrStr: TypeAlias = int | float | str
"""A numeric value or a string that ``InputConvert(..., float)`` can parse."""

RangeLike: TypeAlias = tuple[NumberLikeOrStr, NumberLikeOrStr]
"""A ``(min, max)`` range where endpoints may be numeric or parseable strings."""

VisibleSpec: TypeAlias = bool
"""Visibility flag used by plotting APIs (strict ``True``/``False`` semantics)."""


__all__ = [
    "NumberLike",
    "NumberLikeOrStr",
    "RangeLike",
    "VisibleSpec",
]
