"""Immutable snapshots of SmartFigure parameter state.

A snapshot captures a deep-copied mapping of ``Symbol -> metadata`` so code can
perform deterministic calculations without depending on mutable widget state.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Dict

from sympy.core.symbol import Symbol


class ParameterSnapshot(Mapping[Symbol, Mapping[str, Any]]):
    """Immutable ordered snapshot of parameter values and optional metadata.

    Parameters
    ----------
    entries : Mapping[sympy.Symbol, Mapping[str, Any]]
        Source mapping keyed by parameter symbols.
    """

    def __init__(self, entries: Mapping[Symbol, Mapping[str, Any]]) -> None:
        """Copy source entries deeply while preserving insertion order."""
        self._entries: Dict[Symbol, Dict[str, Any]] = {
            symbol: deepcopy(dict(entry)) for symbol, entry in entries.items()
        }

    def __getitem__(self, key: Symbol) -> Mapping[str, Any]:
        """Return read-only metadata for a symbol."""
        return MappingProxyType(deepcopy(self._entries[key]))

    def __iter__(self) -> Iterator[Symbol]:
        """Iterate symbols in insertion order."""
        return iter(self._entries)

    def __len__(self) -> int:
        """Return the number of parameter entries in the snapshot."""
        return len(self._entries)

    def value_map(self) -> Dict[Symbol, Any]:
        """Return a plain detached ``Symbol -> value`` dictionary.

        Returns
        -------
        dict[sympy.Symbol, Any]
            Plain detached dictionary containing only current parameter values.

        Examples
        --------
        >>> import sympy as sp
        >>> a = sp.Symbol("a")
        >>> snap = ParameterSnapshot({a: {"value": 1.5, "min": 0.0}})
        >>> snap.value_map()[a]
        1.5
        """
        return {symbol: deepcopy(entry["value"]) for symbol, entry in self._entries.items()}

    def __eq__(self, other: object) -> bool:
        """Compare snapshots by ordered item content."""
        if not isinstance(other, Mapping):
            return NotImplemented
        return list(self.items()) == list(other.items())

    def __repr__(self) -> str:
        """Return developer-friendly representation of stored payload."""
        return f"ParameterSnapshot({self._entries!r})"
