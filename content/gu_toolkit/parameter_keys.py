"""Shared helpers for string-authoritative parameter identity.

The toolkit now treats the string form of a parameter (``symbol.name``) as the
canonical identifier across parameter registries, snapshots, and numeric
binding APIs. Symbol objects remain accepted for ergonomics, but they are first
normalized to their name before lookup or storage decisions are made.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Sequence
from typing import TypeAlias

import sympy as sp
from sympy.core.symbol import Symbol

ParameterKey: TypeAlias = str | Symbol
ParameterKeyOrKeys: TypeAlias = ParameterKey | Sequence[ParameterKey]


def parameter_name(key: ParameterKey, *, role: str = "parameter") -> str:
    """Return the canonical string identifier for *key*.
    
    Full API
    --------
    ``parameter_name(key: ParameterKey, *, role: str='parameter') -> str``
    
    Parameters
    ----------
    key : ParameterKey
        Value for ``key`` in this API. Required.
    
    role : str, optional
        Value for ``role`` in this API. Defaults to ``'parameter'``.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``role='parameter'``: Value for ``role`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.parameter_keys``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.parameter_keys import parameter_name
        result = parameter_name(...)
    
    Discovery-oriented use::
    
        help(parameter_name)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(parameter_name)`` and inspect sibling APIs in the same module.
    """
    if isinstance(key, str):
        return key
    if isinstance(key, Symbol):
        return key.name
    raise TypeError(
        f"{role} key must be a string or sympy.Symbol, got {type(key).__name__}"
    )


def parameter_symbol(key: ParameterKey, *, role: str = "parameter") -> Symbol:
    """Return a representative SymPy symbol for *key*.
    
    Full API
    --------
    ``parameter_symbol(key: ParameterKey, *, role: str='parameter') -> Symbol``
    
    Parameters
    ----------
    key : ParameterKey
        Value for ``key`` in this API. Required.
    
    role : str, optional
        Value for ``role`` in this API. Defaults to ``'parameter'``.
    
    Returns
    -------
    Symbol
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``role='parameter'``: Value for ``role`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.parameter_keys``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.parameter_keys import parameter_symbol
        result = parameter_symbol(...)
    
    Discovery-oriented use::
    
        help(parameter_symbol)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(parameter_symbol)`` and inspect sibling APIs in the same module.
    """
    if isinstance(key, Symbol):
        return key
    if isinstance(key, str):
        return sp.Symbol(key)
    raise TypeError(
        f"{role} key must be a string or sympy.Symbol, got {type(key).__name__}"
    )


def normalize_parameter_sequence(
    keys: ParameterKeyOrKeys,
    *,
    role: str = "parameters",
) -> tuple[tuple[tuple[str, Symbol], ...], bool]:
    """Normalize one-or-many parameter keys to unique ``(name, symbol)`` pairs.
    
    Full API
    --------
    ``normalize_parameter_sequence(keys: ParameterKeyOrKeys, *, role: str='parameters') -> tuple[tuple[tuple[str, Symbol], ...], bool]``
    
    Parameters
    ----------
    keys : ParameterKeyOrKeys
        Value for ``keys`` in this API. Required.
    
    role : str, optional
        Value for ``role`` in this API. Defaults to ``'parameters'``.
    
    Returns
    -------
    tuple[tuple[tuple[str, Symbol], Ellipsis], bool]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``role='parameters'``: Value for ``role`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.parameter_keys``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.parameter_keys import normalize_parameter_sequence
        result = normalize_parameter_sequence(...)
    
    Discovery-oriented use::
    
        help(normalize_parameter_sequence)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(normalize_parameter_sequence)`` and inspect sibling APIs in the same module.
    """
    if isinstance(keys, (str, Symbol)):
        raw_items = [keys]
        single = True
    else:
        raw_items = list(keys)
        single = False

    ordered: OrderedDict[str, Symbol] = OrderedDict()
    for raw_key in raw_items:
        name = parameter_name(raw_key, role=role)
        ordered.setdefault(name, parameter_symbol(raw_key, role=role))

    return tuple(ordered.items()), single


def group_symbols_by_name(symbols: Iterable[Symbol]) -> dict[str, tuple[Symbol, ...]]:
    """Group symbols by canonical parameter name while preserving input order.
    
    Full API
    --------
    ``group_symbols_by_name(symbols: Iterable[Symbol]) -> dict[str, tuple[Symbol, ...]]``
    
    Parameters
    ----------
    symbols : Iterable[Symbol]
        Parameter symbols, names, or other accepted parameter keys. Required.
    
    Returns
    -------
    dict[str, tuple[Symbol, Ellipsis]]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.parameter_keys``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.parameter_keys import group_symbols_by_name
        result = group_symbols_by_name(...)
    
    Discovery-oriented use::
    
        help(group_symbols_by_name)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(group_symbols_by_name)`` and inspect sibling APIs in the same module.
    """
    grouped: OrderedDict[str, list[Symbol]] = OrderedDict()
    for symbol in symbols:
        grouped.setdefault(symbol.name, []).append(symbol)
    return {name: tuple(group) for name, group in grouped.items()}


def expand_parameter_keys_to_symbols(
    keys: ParameterKeyOrKeys,
    candidates: Iterable[Symbol],
    *,
    role: str = "parameters",
) -> tuple[Symbol, ...]:
    """Resolve parameter keys against candidate symbols using canonical names.
    
    Full API
    --------
    ``expand_parameter_keys_to_symbols(keys: ParameterKeyOrKeys, candidates: Iterable[Symbol], *, role: str='parameters') -> tuple[Symbol, ...]``
    
    Parameters
    ----------
    keys : ParameterKeyOrKeys
        Value for ``keys`` in this API. Required.
    
    candidates : Iterable[Symbol]
        Value for ``candidates`` in this API. Required.
    
    role : str, optional
        Value for ``role`` in this API. Defaults to ``'parameters'``.
    
    Returns
    -------
    tuple[Symbol, Ellipsis]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``role='parameters'``: Value for ``role`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.parameter_keys``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.parameter_keys import expand_parameter_keys_to_symbols
        result = expand_parameter_keys_to_symbols(...)
    
    Discovery-oriented use::
    
        help(expand_parameter_keys_to_symbols)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(expand_parameter_keys_to_symbols)`` and inspect sibling APIs in the same module.
    """
    candidate_groups = group_symbols_by_name(candidates)
    requested, _single = normalize_parameter_sequence(keys, role=role)

    ordered: list[Symbol] = []
    seen: set[Symbol] = set()
    for name, original_symbol in requested:
        matched = candidate_groups.get(name)
        if matched:
            for symbol in matched:
                if symbol not in seen:
                    ordered.append(symbol)
                    seen.add(symbol)
            continue
        if original_symbol not in seen:
            ordered.append(original_symbol)
            seen.add(original_symbol)

    return tuple(ordered)
