"""Immutable snapshots of Figure parameter state.

Parameter snapshots are now *name-authoritative*: the canonical key for a
parameter is its string name (``symbol.name``). Symbol objects remain accepted
for lookup and helper APIs, but they are normalized to their name before the
snapshot resolves an entry.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any

from sympy.core.symbol import Symbol

from .parameter_keys import ParameterKey, parameter_name, parameter_symbol



def _normalize_snapshot_entries(
    entries: Mapping[ParameterKey, Mapping[str, Any]],
    *,
    symbols: Mapping[ParameterKey, Symbol] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Symbol]]:
    """Return deep-copied name-keyed entries plus canonical symbols.

    Duplicate canonical names are rejected because a name-authoritative snapshot
    can only contain one entry per logical parameter.
    """
    normalized_entries: dict[str, dict[str, Any]] = {}
    canonical_symbols: dict[str, Symbol] = {}

    for raw_key, entry in entries.items():
        name = parameter_name(raw_key, role="parameter")
        if name in normalized_entries:
            raise ValueError(
                f"Duplicate parameter name {name!r} in snapshot entries. "
                "Snapshots are keyed by parameter name."
            )
        normalized_entries[name] = deepcopy(dict(entry))
        canonical_symbols[name] = parameter_symbol(raw_key, role="parameter")

    if symbols is not None:
        for raw_key, symbol in symbols.items():
            name = parameter_name(raw_key, role="parameter")
            if name not in normalized_entries:
                raise KeyError(
                    f"Canonical symbol {name!r} does not correspond to a snapshot entry."
                )
            if not isinstance(symbol, Symbol):
                raise TypeError(
                    "Canonical symbols mapping must contain sympy.Symbol values."
                )
            if symbol.name != name:
                raise ValueError(
                    f"Canonical symbol {symbol!r} does not match parameter name {name!r}."
                )
            canonical_symbols[name] = symbol

    return normalized_entries, canonical_symbols


class _ParameterSnapshotBase:
    """Shared name-resolution helpers for parameter snapshots."""

    _symbols_by_name: dict[str, Symbol]

    def _resolve_name(self, key: ParameterKey) -> str:
        name = parameter_name(key, role="parameter")
        if name not in self._symbols_by_name:
            raise KeyError(
                f"Unknown parameter name {name!r}. "
                "Use one of the registered parameter names."
            )
        return name

    def __contains__(self, key: object) -> bool:  # pragma: no cover - trivial
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._symbols_by_name

    def symbol_for_name(self, key: ParameterKey) -> Symbol:
        """Return the canonical symbol recorded for ``key``.
        
        Full API
        --------
        ``obj.symbol_for_name(key: ParameterKey) -> Symbol``
        
        Parameters
        ----------
        key : ParameterKey
            Value for ``key`` in this API. Required.
        
        Returns
        -------
        Symbol
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``_ParameterSnapshotBase``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _ParameterSnapshotBase(...)
            result = obj.symbol_for_name(...)
        
        Discovery-oriented use::
        
            help(_ParameterSnapshotBase)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(_ParameterSnapshotBase)`` and ``dir(_ParameterSnapshotBase)`` to inspect adjacent members.
        """
        return self._symbols_by_name[self._resolve_name(key)]

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        """Return canonical symbols in snapshot order.
        
        Full API
        --------
        ``obj.symbols -> tuple[Symbol, Ellipsis]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[Symbol, Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``_ParameterSnapshotBase``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _ParameterSnapshotBase(...)
            current = obj.symbols
        
        Discovery-oriented use::
        
            help(_ParameterSnapshotBase)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(_ParameterSnapshotBase)`` and ``dir(_ParameterSnapshotBase)`` to inspect adjacent members.
        """
        return tuple(self._symbols_by_name[name] for name in self)  # type: ignore[misc]

    def symbol_items(self):
        """Iterate ``(canonical_symbol, value)`` pairs in snapshot order.
        
        Full API
        --------
        ``obj.symbol_items()``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``_ParameterSnapshotBase``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _ParameterSnapshotBase(...)
            result = obj.symbol_items(...)
        
        Discovery-oriented use::
        
            help(_ParameterSnapshotBase)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(_ParameterSnapshotBase)`` and ``dir(_ParameterSnapshotBase)`` to inspect adjacent members.
        """
        for name in self:  # type: ignore[misc]
            yield self._symbols_by_name[name], self[name]  # type: ignore[index]


class ParameterValueSnapshot(_ParameterSnapshotBase, Mapping[str, Any]):
    """Immutable name-keyed view of parameter values.
    
    Full API
    --------
    ``ParameterValueSnapshot(entries: Mapping[ParameterKey, Mapping[str, Any]], symbols: Mapping[ParameterKey, Symbol] | None=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    entries : Mapping[ParameterKey, Mapping[str, Any]]
        Value for ``entries`` in this API. Required.
    
    symbols : Mapping[ParameterKey, Symbol] | None, optional
        Parameter symbols, names, or other accepted parameter keys. Defaults to ``None``.
    
    Returns
    -------
    ParameterValueSnapshot
        New ``ParameterValueSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``symbols=None``: Parameter symbols, names, or other accepted parameter keys.
    
    Architecture note
    -----------------
    ``ParameterValueSnapshot`` lives in ``gu_toolkit.ParameterSnapshot``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.ParameterSnapshot import ParameterValueSnapshot
        obj = ParameterValueSnapshot(...)
    
    Discovery-oriented use::
    
        help(ParameterValueSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(ParameterValueSnapshot)`` and ``dir(ParameterValueSnapshot)`` to inspect adjacent members.
    """

    def __init__(
        self,
        entries: Mapping[ParameterKey, Mapping[str, Any]],
        *,
        symbols: Mapping[ParameterKey, Symbol] | None = None,
    ) -> None:
        normalized_entries, self._symbols_by_name = _normalize_snapshot_entries(
            entries,
            symbols=symbols,
        )
        self._values: dict[str, Any] = {
            name: deepcopy(entry["value"]) for name, entry in normalized_entries.items()
        }

    def __getitem__(self, key: ParameterKey) -> Any:
        name = self._resolve_name(key)
        return deepcopy(self._values[name])

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"ParameterValueSnapshot({self._values!r})"


class ParameterSnapshot(_ParameterSnapshotBase, Mapping[str, Mapping[str, Any]]):
    """Immutable ordered snapshot of parameter values and optional metadata.
    
    Full API
    --------
    ``ParameterSnapshot(entries: Mapping[ParameterKey, Mapping[str, Any]], symbols: Mapping[ParameterKey, Symbol] | None=None)``
    
    Public members exposed from this class: ``value_map``
    
    Parameters
    ----------
    entries : Mapping[ParameterKey, Mapping[str, Any]]
        Value for ``entries`` in this API. Required.
    
    symbols : Mapping[ParameterKey, Symbol] | None, optional
        Parameter symbols, names, or other accepted parameter keys. Defaults to ``None``.
    
    Returns
    -------
    ParameterSnapshot
        New ``ParameterSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``symbols=None``: Parameter symbols, names, or other accepted parameter keys.
    
    Architecture note
    -----------------
    ``ParameterSnapshot`` lives in ``gu_toolkit.ParameterSnapshot``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.ParameterSnapshot import ParameterSnapshot
        obj = ParameterSnapshot(...)
    
    Discovery-oriented use::
    
        help(ParameterSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(ParameterSnapshot)`` and ``dir(ParameterSnapshot)`` to inspect adjacent members.
    """

    def __init__(
        self,
        entries: Mapping[ParameterKey, Mapping[str, Any]],
        *,
        symbols: Mapping[ParameterKey, Symbol] | None = None,
    ) -> None:
        self._entries, self._symbols_by_name = _normalize_snapshot_entries(
            entries,
            symbols=symbols,
        )

    def __getitem__(self, key: ParameterKey) -> Mapping[str, Any]:
        name = self._resolve_name(key)
        return MappingProxyType(deepcopy(self._entries[name]))

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def value_map(self) -> ParameterValueSnapshot:
        """Return an immutable ``name -> value`` snapshot.
        
        Full API
        --------
        ``obj.value_map() -> ParameterValueSnapshot``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        ParameterValueSnapshot
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterSnapshot``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterSnapshot(...)
            result = obj.value_map(...)
        
        Discovery-oriented use::
        
            help(ParameterSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParameterSnapshot)`` and ``dir(ParameterSnapshot)`` to inspect adjacent members.
        """
        return ParameterValueSnapshot(self._entries, symbols=self._symbols_by_name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return NotImplemented
        return list(self.items()) == list(other.items())

    def __repr__(self) -> str:
        return f"ParameterSnapshot({self._entries!r})"
