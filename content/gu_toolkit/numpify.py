"""
numpify: Compile SymPy expressions to NumPy-callable Python functions
====================================================================

Purpose
-------
Turn a SymPy expression into a callable Python function that evaluates using NumPy.

This module is intentionally small and "batteries included" for interactive research
workflows where you want:

- explicit argument order,
- fast vectorized evaluation via NumPy broadcasting,
- support for *custom* SymPy functions that carry a NumPy implementation (``f_numpy``),
- and inspectable generated source.

Supported Python versions
-------------------------
- Python >= 3.10

Dependencies
------------
- NumPy (required)
- SymPy (required)

Public API
----------
- :func:`numpify`
- :func:`numpify_cached`

How custom functions are handled
--------------------------------
SymPy's NumPy code printer cannot natively print arbitrary user-defined SymPy Functions.
When ``expr`` contains an unknown function call such as ``G(x)``, SymPy raises a
``PrintMethodNotImplementedError`` by default.

This module enables SymPy's ``allow_unknown_functions`` option so unknown functions are
printed as plain calls (``G(x)``). We then provide runtime bindings so that the name
``G`` resolves to a callable.

Bindings are resolved in this order:

1. Explicit bindings provided via the ``f_numpy`` argument (for function classes).
2. Auto-detection: for each function ``F`` appearing in the expression, if
   ``callable(getattr(F, "f_numpy", None))`` then that callable is used.

If an unknown function remains unbound, :func:`numpify` raises a clear error before code
generation.

Examples
--------
>>> import numpy as np
>>> import sympy as sp
>>> from numpify import numpify
>>> x = sp.Symbol("x")

Constant compiled with broadcasting:
>>> f = numpify(5, vars=x)
>>> float(f(0))
5.0
>>> f(np.array([1, 2, 3]))
array([5., 5., 5.])

Symbol binding (treat `a` as an injected constant):
>>> a = sp.Symbol("a")
>>> g = numpify(a * x, vars=x, f_numpy={a: 2.0})
>>> g(np.array([1, 2, 3]))
array([2., 4., 6.])

Logging
-------
This module uses Python's standard :mod:`logging` library and is silent by default.
To enable debug logging in a notebook session:

>>> import logging
>>> import numpify
>>> logging.basicConfig(level=logging.DEBUG)
>>> logging.getLogger(numpify.__name__).setLevel(logging.DEBUG)

If you import this file as part of a package (e.g. ``gu_toolkit.numpify``), use that
module name instead.
"""

from __future__ import annotations

import builtins
import inspect
import keyword
import logging
import textwrap
import time
from collections.abc import Callable, Iterable, Mapping
from functools import lru_cache
from typing import (
    Any,
    TypeAlias,
    cast,
)

import numpy as np
import sympy as sp
from sympy.core.function import FunctionClass
from sympy.printing.numpy import NumPyPrinter

from .parameter_keys import ParameterKey

__all__ = [
    "numpify",
    "numpify_cached",
    "DYNAMIC_PARAMETER",
    "UNFREEZE",
    "ParameterContext",
    "NumericFunction",
]


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


_SymBindingKey = sp.Symbol
_FuncBindingKey = FunctionClass | sp.Function
_BindingKey = _SymBindingKey | _FuncBindingKey
_SymBindings = dict[str, Any]
_FuncBindings = dict[str, Callable[..., Any]]


class _Sentinel:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


DYNAMIC_PARAMETER = _Sentinel("DYNAMIC_PARAMETER")
UNFREEZE = _Sentinel("UNFREEZE")


ParameterContext: TypeAlias = Mapping[ParameterKey, Any]


_VarsInput = (
    sp.Symbol
    | Iterable[sp.Symbol | Mapping[str, sp.Symbol]]
    | Mapping[int | str, sp.Symbol]
)


class _VarsView:
    """Backwards-compatible vars accessor.

    - Iterable/sequence view yields positional symbols (legacy behavior).
    - Callable view (`obj.vars()`) returns the round-trip vars specification.
    """

    __slots__ = ("_positional", "_roundtrip")

    def __init__(self, positional: tuple[sp.Symbol, ...], roundtrip: Any):
        self._positional = positional
        self._roundtrip = roundtrip

    def __iter__(self):
        return iter(self._positional)

    def __len__(self) -> int:
        return len(self._positional)

    def __getitem__(self, idx: Any) -> Any:
        return self._positional[idx]

    def __bool__(self) -> bool:
        return bool(self._positional)

    def __call__(self) -> Any:
        return self._roundtrip

    def __repr__(self) -> str:
        return repr(self._positional)


def _binding_values_match(lhs: Any, rhs: Any) -> bool:
    """Return whether two binding values should be treated as equivalent."""
    if lhs is rhs:
        return True
    try:
        result = lhs == rhs
    except Exception:
        return False
    if isinstance(result, np.ndarray):
        try:
            return bool(np.all(result))
        except Exception:
            return False
    try:
        return bool(result)
    except Exception:
        return False


def _try_mapping_lookup(mapping: Mapping[Any, Any], key: Any) -> tuple[bool, Any]:
    """Lookup helper that avoids relying on ``Mapping.__contains__`` semantics."""
    try:
        return True, mapping[key]
    except (LookupError, TypeError, ValueError):
        return False, None


class NumericFunction:
    """Compiled SymPy->NumPy callable with optional frozen/dynamic bindings.
    
    Full API
    --------
    ``NumericFunction(fn: Callable[Ellipsis, Any], vars: _VarsInput | None=None, symbolic: sp.Basic | None=None, call_signature: tuple[tuple[sp.Symbol, str], Ellipsis] | None=None, source: str='', keyed_symbols: tuple[tuple[str, sp.Symbol], Ellipsis] | None=None, vars_spec: Any=None, parameter_context: ParameterContext | None=None, frozen: Mapping[ParameterKey, Any] | None=None, dynamic: Iterable[ParameterKey] | None=None)``
    
    Public members exposed from this class: ``vars``, ``all_vars``, ``var_names``, ``freeze``, ``unfreeze``,
        ``set_parameter_context``, ``remove_parameter_context``, ``free_vars``,
        ``free_var_signature``, ``is_live``
    
    Parameters
    ----------
    fn : Callable[Ellipsis, Any]
        Value for ``fn`` in this API. Required.
    
    vars : _VarsInput | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    symbolic : sp.Basic | None, optional
        Value for ``symbolic`` in this API. Defaults to ``None``.
    
    call_signature : tuple[tuple[sp.Symbol, str], Ellipsis] | None, optional
        Value for ``call_signature`` in this API. Defaults to ``None``.
    
    source : str, optional
        Value for ``source`` in this API. Defaults to ``''``.
    
    keyed_symbols : tuple[tuple[str, sp.Symbol], Ellipsis] | None, optional
        Value for ``keyed_symbols`` in this API. Defaults to ``None``.
    
    vars_spec : Any, optional
        Value for ``vars_spec`` in this API. Defaults to ``None``.
    
    parameter_context : ParameterContext | None, optional
        Parameter context used when binding or freezing dynamic values. Defaults to ``None``.
    
    frozen : Mapping[ParameterKey, Any] | None, optional
        Value for ``frozen`` in this API. Defaults to ``None``.
    
    dynamic : Iterable[ParameterKey] | None, optional
        Value for ``dynamic`` in this API. Defaults to ``None``.
    
    Returns
    -------
    NumericFunction
        New ``NumericFunction`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``vars=None``: Value for ``vars`` in this API.
    - ``symbolic=None``: Value for ``symbolic`` in this API.
    - ``call_signature=None``: Value for ``call_signature`` in this API.
    - ``source=''``: Value for ``source`` in this API.
    - ``keyed_symbols=None``: Value for ``keyed_symbols`` in this API.
    - ``vars_spec=None``: Value for ``vars_spec`` in this API.
    - ``parameter_context=None``: Parameter context used when binding or freezing dynamic values.
    - ``frozen=None``: Value for ``frozen`` in this API.
    - ``dynamic=None``: Value for ``dynamic`` in this API.
    
    Architecture note
    -----------------
    ``NumericFunction`` lives in ``gu_toolkit.numpify``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.numpify import NumericFunction
        obj = NumericFunction(...)
    
    Discovery-oriented use::
    
        help(NumericFunction)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
    """

    __slots__ = (
        "_fn",
        "symbolic",
        "call_signature",
        "source",
        "_vars_spec",
        "_keyed_symbols",
        "_key_for_symbol",
        "_symbol_for_key",
        "_vars_view",
        "name_for_symbol",
        "symbol_for_name",
        "_parameter_name_for_symbol",
        "_symbols_for_parameter_name",
        "_parameter_context",
        "_frozen",
        "_dynamic",
    )

    def __init__(
        self,
        fn: Callable[..., Any],
        vars: _VarsInput | None = None,
        symbolic: sp.Basic | None = None,
        call_signature: tuple[tuple[sp.Symbol, str], ...] | None = None,
        source: str = "",
        *,
        keyed_symbols: tuple[tuple[str, sp.Symbol], ...] | None = None,
        vars_spec: Any = None,
        parameter_context: ParameterContext | None = None,
        frozen: Mapping[ParameterKey, Any] | None = None,
        dynamic: Iterable[ParameterKey] | None = None,
    ) -> None:
        if call_signature is None:
            normalized = _normalize_vars(
                symbolic if isinstance(symbolic, sp.Basic) else sp.Integer(0), vars
            )
            reserved = set(dir(builtins)) | {"numpy", "_sym_bindings"}
            call_signature = _build_call_signature(normalized["all"], reserved)
            keyed_symbols = normalized["keyed"]
            vars_spec = normalized["spec"]
        if keyed_symbols is None:
            keyed_symbols = ()
        if vars_spec is None:
            vars_spec = tuple(sym for sym, _ in call_signature)

        self._fn = fn
        self.symbolic = symbolic
        self.call_signature = call_signature
        self.source = source
        self._vars_spec = vars_spec
        self._keyed_symbols = keyed_symbols
        self._key_for_symbol = {sym: key for key, sym in keyed_symbols}
        self._symbol_for_key = dict(keyed_symbols)
        self._vars_view = _VarsView(
            tuple(sym for sym, _ in call_signature if sym not in self._key_for_symbol),
            self._vars_spec,
        )
        self.name_for_symbol = dict(call_signature)
        self.symbol_for_name = {name: sym for sym, name in call_signature}
        self._parameter_name_for_symbol = {sym: sym.name for sym, _ in call_signature}

        grouped_parameter_symbols: dict[str, list[sp.Symbol]] = {}
        for sym, _ in call_signature:
            grouped_parameter_symbols.setdefault(sym.name, []).append(sym)
        self._symbols_for_parameter_name = {
            name: tuple(group) for name, group in grouped_parameter_symbols.items()
        }

        self._parameter_context = parameter_context
        self._frozen: dict[str, Any] = {}
        self._dynamic: set[str] = set()
        if frozen:
            self._frozen.update(self._normalize_bindings(frozen, {}))
        if dynamic:
            self._dynamic.update(self._resolve_binding_name(key) for key in dynamic)
            for name in self._dynamic:
                self._frozen.pop(name, None)

    def _clone(self) -> NumericFunction:
        return NumericFunction(
            fn=self._fn,
            symbolic=self.symbolic,
            call_signature=self.call_signature,
            source=self.source,
            keyed_symbols=self._keyed_symbols,
            vars_spec=self._vars_spec,
            parameter_context=self._parameter_context,
            frozen=self._frozen,
            dynamic=self._dynamic,
        )

    def _resolve_binding_name(self, key: ParameterKey) -> str:
        if isinstance(key, sp.Symbol):
            name = key.name
            if name not in self._symbols_for_parameter_name:
                raise KeyError(f"Unknown parameter symbol name: {name!r}")
            return name

        if isinstance(key, str):
            if key in self._symbols_for_parameter_name:
                return key
            if key in self._symbol_for_key:
                return self._symbol_for_key[key].name
            if key in self.symbol_for_name:
                return self.symbol_for_name[key].name
            raise KeyError(f"Unknown parameter name or alias: {key!r}")

        raise TypeError(
            f"Parameter key must be Symbol or str, got {type(key).__name__}"
        )

    def _normalize_bindings(
        self,
        bindings: Mapping[ParameterKey, Any]
        | Iterable[tuple[ParameterKey, Any]]
        | None,
        kwargs: Mapping[str, Any],
    ) -> dict[str, Any]:
        items: list[tuple[ParameterKey, Any]] = []
        if bindings is None:
            pass
        elif isinstance(bindings, Mapping):
            items.extend(bindings.items())
        else:
            items.extend(tuple(bindings))
        items.extend(kwargs.items())

        resolved: dict[str, Any] = {}
        for key, value in items:
            name = self._resolve_binding_name(key)
            if name in resolved:
                if _binding_values_match(resolved[name], value):
                    continue
                symbols = ", ".join(
                    self.name_for_symbol[sym]
                    for sym in self._symbols_for_parameter_name[name]
                )
                raise ValueError(
                    f"Duplicate binding for parameter name {name!r} (vars: {symbols})"
                )
            resolved[name] = value
        return resolved

    def _lookup_parameter_context_value(
        self,
        parameter_name: str,
        *,
        sym: sp.Symbol,
        var_name: str,
    ) -> Any:
        if self._parameter_context is None:
            raise ValueError(
                f"Dynamic var {sym!r} ('{var_name}') requires parameter_context at call time"
            )

        candidates: list[Any] = [parameter_name]
        candidates.extend(self._symbols_for_parameter_name.get(parameter_name, (sym,)))

        key_alias = self._key_for_symbol.get(sym)
        if key_alias is not None and key_alias not in candidates:
            candidates.append(key_alias)
        if var_name not in candidates:
            candidates.append(var_name)

        seen: set[tuple[type[Any], Any]] = set()
        for candidate in candidates:
            marker = (type(candidate), candidate)
            if marker in seen:
                continue
            seen.add(marker)
            found, value = _try_mapping_lookup(self._parameter_context, candidate)
            if found:
                return value

        raise KeyError(
            "parameter_context is missing parameter "
            f"{parameter_name!r} for symbol {sym!r} ('{var_name}')"
        )

    def __call__(self, *positional_args: Any, **keyed_args: Any) -> Any:
        if not self._frozen and not self._dynamic:
            if keyed_args:
                full_args = list(positional_args)
                for key, _sym in self._keyed_symbols:
                    if key not in keyed_args:
                        raise TypeError(f"Missing keyed argument: {key!r}")
                    full_args.append(keyed_args[key])
                extra = set(keyed_args) - {k for k, _ in self._keyed_symbols}
                if extra:
                    raise TypeError(
                        f"Unknown keyed argument(s): {', '.join(sorted(extra))}"
                    )
                return self._fn(*full_args)
            return self._fn(*positional_args)

        full_values: list[Any] = []
        free_idx = 0
        missing: list[str] = []

        for sym, _ in self.call_signature:
            var_name = self.name_for_symbol[sym]
            canonical_name = self._parameter_name_for_symbol[sym]
            if canonical_name in self._frozen:
                full_values.append(self._frozen[canonical_name])
                continue

            if canonical_name in self._dynamic:
                full_values.append(
                    self._lookup_parameter_context_value(
                        canonical_name,
                        sym=sym,
                        var_name=var_name,
                    )
                )
                continue

            if sym in self._symbol_for_key:
                key_name = self._key_for_symbol[sym]
                if key_name not in keyed_args:
                    missing.append(f"{sym!r} ('{key_name}')")
                else:
                    full_values.append(keyed_args[key_name])
                continue

            if free_idx >= len(positional_args):
                missing.append(f"{sym!r} ('{var_name}')")
            else:
                full_values.append(positional_args[free_idx])
                free_idx += 1

        if missing:
            raise TypeError("Missing positional argument(s): " + ", ".join(missing))
        if free_idx != len(positional_args):
            raise TypeError(
                f"Too many positional arguments: expected {free_idx}, got {len(positional_args)}"
            )
        extra = set(keyed_args) - set(self._symbol_for_key)
        if extra:
            raise TypeError(f"Unknown keyed argument(s): {', '.join(sorted(extra))}")

        return self._fn(*full_values)

    @property
    def vars(self) -> _VarsView:
        """Work with vars on ``NumericFunction``.
        
        Full API
        --------
        ``obj.vars -> _VarsView``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        _VarsView
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            current = obj.vars
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        return self._vars_view

    @property
    def all_vars(self) -> tuple[sp.Symbol, ...]:
        """Work with all vars on ``NumericFunction``.
        
        Full API
        --------
        ``obj.all_vars -> tuple[sp.Symbol, Ellipsis]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[sp.Symbol, Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            current = obj.all_vars
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        return tuple(sym for sym, _ in self.call_signature)

    @property
    def var_names(self) -> tuple[str, ...]:
        """Work with var names on ``NumericFunction``.
        
        Full API
        --------
        ``obj.var_names -> tuple[str, Ellipsis]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[str, Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            current = obj.var_names
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        return tuple(name for _, name in self.call_signature)

    def freeze(
        self,
        bindings: Mapping[ParameterKey, Any]
        | Iterable[tuple[ParameterKey, Any]]
        | None = None,
        /,
        **kwargs: Any,
    ) -> NumericFunction:
        """Return a clone with updated frozen/dynamic variable bindings.
        
        Full API
        --------
        ``obj.freeze(bindings: Mapping[ParameterKey, Any] | Iterable[tuple[ParameterKey, Any]] | None=None, /, **kwargs: Any) -> NumericFunction``
        
        Parameters
        ----------
        bindings : Mapping[ParameterKey, Any] | Iterable[tuple[ParameterKey, Any]] | None, optional
            Value for ``bindings`` in this API. Defaults to ``None``.
        
        **kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        NumericFunction
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``bindings=None``: Value for ``bindings`` in this API.
        - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            result = obj.freeze(...)
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """
        updates = self._normalize_bindings(bindings, kwargs)
        out = self._clone()
        for name, value in updates.items():
            if value is DYNAMIC_PARAMETER:
                out._dynamic.add(name)
                out._frozen.pop(name, None)
            elif value is UNFREEZE:
                out._dynamic.discard(name)
                out._frozen.pop(name, None)
            else:
                out._frozen[name] = value
                out._dynamic.discard(name)
        return out

    def unfreeze(self, *keys: ParameterKey) -> NumericFunction:
        """Return a clone with selected frozen/dynamic bindings removed.
        
        Full API
        --------
        ``obj.unfreeze(*keys: ParameterKey) -> NumericFunction``
        
        Parameters
        ----------
        *keys : ParameterKey, optional
            Additional positional arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        NumericFunction
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``*keys``: Additional positional arguments are passed through when this API supports variadic input.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            result = obj.unfreeze(...)
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """
        if not keys:
            bound_names: list[str] = []
            seen: set[str] = set()
            for sym in self.all_vars:
                name = self._parameter_name_for_symbol[sym]
                if (name in self._frozen or name in self._dynamic) and name not in seen:
                    bound_names.append(name)
                    seen.add(name)
            return self.freeze(dict.fromkeys(bound_names, UNFREEZE))
        return self.freeze(dict.fromkeys(keys, UNFREEZE))

    def set_parameter_context(self, ctx: ParameterContext) -> NumericFunction:
        """Set parameter context.
        
        Full API
        --------
        ``obj.set_parameter_context(ctx: ParameterContext) -> NumericFunction``
        
        Parameters
        ----------
        ctx : ParameterContext
            Value for ``ctx`` in this API. Required.
        
        Returns
        -------
        NumericFunction
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            result = obj.set_parameter_context(...)
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        out = self._clone()
        out._parameter_context = ctx
        return out

    def remove_parameter_context(self) -> NumericFunction:
        """Remove parameter context.
        
        Full API
        --------
        ``obj.remove_parameter_context() -> NumericFunction``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        NumericFunction
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            result = obj.remove_parameter_context(...)
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        out = self._clone()
        out._parameter_context = None
        return out

    @property
    def free_vars(self) -> tuple[sp.Symbol, ...]:
        """Work with free vars on ``NumericFunction``.
        
        Full API
        --------
        ``obj.free_vars -> tuple[sp.Symbol, Ellipsis]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[sp.Symbol, Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            current = obj.free_vars
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        return tuple(
            sym
            for sym in self.all_vars
            if self._parameter_name_for_symbol[sym] not in self._frozen
            and self._parameter_name_for_symbol[sym] not in self._dynamic
        )

    @property
    def free_var_signature(self) -> tuple[tuple[sp.Symbol, str], ...]:
        """Work with free var signature on ``NumericFunction``.
        
        Full API
        --------
        ``obj.free_var_signature -> tuple[tuple[sp.Symbol, str], Ellipsis]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[tuple[sp.Symbol, str], Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            current = obj.free_var_signature
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        return tuple((sym, self.name_for_symbol[sym]) for sym in self.free_vars)

    @property
    def is_live(self) -> bool:
        """Return whether live.
        
        Full API
        --------
        ``obj.is_live -> bool``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``NumericFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = NumericFunction(...)
            current = obj.is_live
        
        Discovery-oriented use::
        
            help(NumericFunction)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(NumericFunction)`` and ``dir(NumericFunction)`` to inspect adjacent members.
        """

        return self._parameter_context is not None

    @property
    def __signature__(self) -> inspect.Signature:
        """Return a meaningful call signature for currently-free positional vars."""
        params = [
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_ONLY)
            for _, name in self.free_var_signature
        ]
        return inspect.Signature(parameters=params)

    def __repr__(self) -> str:
        vars_str = ", ".join(name for _, name in self.call_signature)
        return f"NumericFunction({self.symbolic!r}, vars=({vars_str}))"

def numpify(
    expr: Any,
    *,
    vars: _VarsInput | None = None,
    f_numpy: Mapping[_BindingKey, Any] | None = None,
    vectorize: bool = True,
    expand_definition: bool = True,
    cache: bool = True,
) -> NumericFunction:
    """Compile a SymPy expression into a NumPy-evaluable function.
    
    Full API
    --------
    ``numpify(expr: Any, *, vars: _VarsInput | None=None, f_numpy: Mapping[_BindingKey, Any] | None=None, vectorize: bool=True, expand_definition: bool=True, cache: bool=True) -> NumericFunction``
    
    Parameters
    ----------
    expr : Any
        Symbolic expression payload. Required.
    
    vars : _VarsInput | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    f_numpy : Mapping[_BindingKey, Any] | None, optional
        Value for ``f_numpy`` in this API. Defaults to ``None``.
    
    vectorize : bool, optional
        Value for ``vectorize`` in this API. Defaults to ``True``.
    
    expand_definition : bool, optional
        Value for ``expand_definition`` in this API. Defaults to ``True``.
    
    cache : bool, optional
        Value for ``cache`` in this API. Defaults to ``True``.
    
    Returns
    -------
    NumericFunction
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``vars=None``: Value for ``vars`` in this API.
    - ``f_numpy=None``: Value for ``f_numpy`` in this API.
    - ``vectorize=True``: Value for ``vectorize`` in this API.
    - ``expand_definition=True``: Value for ``expand_definition`` in this API.
    - ``cache=True``: Value for ``cache`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.numpify``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.numpify import numpify
        result = numpify(...)
    
    Discovery-oriented use::
    
        help(numpify)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(numpify)`` and inspect sibling APIs in the same module.
    """
    if cache:
        return numpify_cached(
            expr,
            vars=vars,
            f_numpy=f_numpy,
            vectorize=vectorize,
            expand_definition=expand_definition,
        )
    return _numpify_uncached(
        expr,
        vars=vars,
        f_numpy=f_numpy,
        vectorize=vectorize,
        expand_definition=expand_definition,
    )


def _is_valid_parameter_name(name: str) -> bool:
    return bool(name) and name.isidentifier() and not keyword.iskeyword(name)


def _mangle_base_name(name: str) -> str:
    cleaned = "".join(ch if (ch == "_" or ch.isalnum()) else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}__"
    return cleaned


def _build_call_signature(
    vars_tuple: tuple[sp.Symbol, ...], reserved_names: set[str]
) -> tuple[tuple[sp.Symbol, str], ...]:
    used = set(reserved_names)
    out: list[tuple[sp.Symbol, str]] = []
    for _idx, sym in enumerate(vars_tuple):
        base = (
            sym.name
            if _is_valid_parameter_name(sym.name)
            else _mangle_base_name(sym.name)
        )
        candidate = base
        suffix = 0
        while candidate in used or not _is_valid_parameter_name(candidate):
            candidate = f"{base}__{suffix}"
            suffix += 1
        used.add(candidate)
        out.append((sym, candidate))
    return tuple(out)


def _build_runtime_name_map(
    raw_names: Iterable[str], reserved_names: set[str]
) -> dict[str, str]:
    """Allocate valid Python identifiers for runtime-only names."""

    used = set(reserved_names)
    mapping: dict[str, str] = {}
    for raw_name in raw_names:
        base = raw_name if _is_valid_parameter_name(raw_name) else _mangle_base_name(raw_name)
        candidate = base
        suffix = 0
        while candidate in used or not _is_valid_parameter_name(candidate):
            candidate = f"{base}__{suffix}"
            suffix += 1
        used.add(candidate)
        mapping[raw_name] = candidate
    return mapping


def _numpify_uncached(
    expr: Any,
    *,
    vars: _VarsInput | None = None,
    f_numpy: Mapping[_BindingKey, Any] | None = None,
    vectorize: bool = True,
    expand_definition: bool = True,
) -> NumericFunction:
    """Compile a SymPy expression into a NumPy-evaluable Python function (uncached).

    Parameters
    ----------
    expr:
        A SymPy expression or anything convertible via :func:`sympy.sympify`.
    vars:
        Symbols treated as *positional arguments* of the compiled function.

        - If None (default), uses all free symbols of ``expr`` sorted by ``sympy.default_sort_key``.
        - If a single Symbol, that symbol is the only argument.
        - If an iterable, argument order is preserved.

    f_numpy:
        Optional bindings for:
        - **Symbols** (constants/objects injected by name into the generated function body).
          Example: ``{a: 2.0}`` binds the symbol ``a`` to the value ``2.0``.
        - **SymPy function classes** (or applications) to NumPy-callable implementations.
          Example: ``{G: G.f_numpy}`` binds ``G(x)`` to the callable.

        In addition, if a function class ``F`` appears in ``expr`` and has a callable
        attribute ``F.f_numpy``, it is auto-bound.

    vectorize:
        If True, each argument is converted via ``numpy.asarray`` to enable broadcasting.
        If False, arguments are left as-is (scalar evaluation).

    expand_definition:
        If True, attempts to rewrite custom functions via
        ``expr.rewrite("expand_definition")`` (repeated to a fixed point), and then applies
        ``sympy.expand(..., deep=True)``.

        If a function is opaque (its rewrite returns itself), the function call remains
        in the expression and must be bound via ``f_numpy`` or ``F.f_numpy``.

    Returns
    -------
    NumericFunction
        A generated callable wrapper with expression metadata and source text.

    Raises
    ------
    TypeError
        If ``vars`` is not a Symbol or an iterable of Symbols.
        If a function binding is provided but the value is not callable.
    ValueError
        If ``expr`` contains unbound symbols or unbound unknown functions.
        If symbol bindings overlap with argument symbols.

    Notes
    -----
    This function uses ``exec`` to define the generated function. Avoid calling it on
    untrusted expressions.
    """
    # 1) Normalize expr to SymPy.
    try:
        expr_sym = sp.sympify(expr)
    except Exception as e:
        raise TypeError(
            f"numpify expects a SymPy-compatible expression, got {type(expr)}"
        ) from e
    if not isinstance(expr_sym, sp.Basic):
        raise TypeError(f"numpify expects a SymPy expression, got {type(expr_sym)}")
    expr = cast(sp.Basic, expr_sym)

    # 2) Normalize vars.
    normalized_vars = _normalize_vars(expr, vars)
    vars_tuple = normalized_vars["all"]
    keyed_symbols = normalized_vars["keyed"]
    vars_spec = normalized_vars["spec"]

    log_debug = logger.isEnabledFor(logging.DEBUG)
    t_total0: float | None = time.perf_counter() if log_debug else None
    if log_debug:
        logger.debug("numpify: detected vars=%s", [a.name for a in vars_tuple])

    # 3) Optionally expand custom definitions.
    if expand_definition:
        expr = _rewrite_expand_definition(expr)
        expr = sp.expand(expr, deep=True)

    # 4) Parse bindings.
    sym_bindings, func_bindings = _parse_bindings(expr, f_numpy)

    # 5) Validate free symbols are accounted for (either vars or symbol bindings).
    free_names = {s.name for s in expr.free_symbols}
    var_names_set = {a.name for a in vars_tuple}
    missing_names = free_names - var_names_set - set(sym_bindings.keys())
    if missing_names:
        missing_str = ", ".join(sorted(missing_names))
        vars_str = ", ".join(a.name for a in vars_tuple)
        raise ValueError(
            "Expression contains unbound symbols: "
            f"{missing_str}. Provide them in vars=({vars_str}) or bind via f_numpy={{symbol: value}}."
        )

    # 6) Prevent accidental overwrites: symbol bindings cannot overlap with vars.
    overlap = {a.name for a in vars_tuple} & set(sym_bindings.keys())
    if overlap:
        raise ValueError(
            "Symbol bindings overlap with vars (would overwrite argument values): "
            + ", ".join(sorted(overlap))
        )

    # 7) Create printer (allow unknown functions to print as plain calls).
    printer = NumPyPrinter(
        settings={"user_functions": {}, "allow_unknown_functions": True}
    )

    # 8) Preflight: any function that prints as a *bare* call must be bound.
    _require_bound_unknown_functions(expr, printer, func_bindings)

    # 9) Build call signature and generate expression code/source.
    reserved_names = (
        set(keyword.kwlist) | set(dir(builtins)) | {"numpy", "np", "_sym_bindings"}
    )
    reserved_names |= {
        _mangle_base_name(name) for name in (*sym_bindings.keys(), *func_bindings.keys())
    }
    call_signature = _build_call_signature(vars_tuple, reserved_names)
    arg_names = [name for _, name in call_signature]
    replacement = {sym: sp.Symbol(name) for sym, name in call_signature}
    expr_codegen = expr.xreplace(replacement)

    runtime_reserved = reserved_names | set(arg_names)
    sym_binding_names = _build_runtime_name_map(sorted(sym_bindings.keys()), runtime_reserved)
    runtime_reserved |= set(sym_binding_names.values())
    func_binding_names = _build_runtime_name_map(sorted(func_bindings.keys()), runtime_reserved)

    if sym_binding_names:
        bound_symbol_replacements = {
            sym: sp.Symbol(sym_binding_names[sym.name])
            for sym in expr_codegen.free_symbols
            if sym.name in sym_binding_names
        }
        if bound_symbol_replacements:
            expr_codegen = expr_codegen.xreplace(bound_symbol_replacements)

    if func_binding_names:
        bound_function_replacements = {}
        for app in expr_codegen.atoms(sp.Function):
            raw_name = app.func.__name__
            if raw_name in func_binding_names:
                alias_func = sp.Function(func_binding_names[raw_name])
                bound_function_replacements[app] = alias_func(*app.args)
        if bound_function_replacements:
            expr_codegen = expr_codegen.xreplace(bound_function_replacements)

    # "Lambdification"-like code generation step: SymPy -> NumPy expression string.
    t_codegen0: float | None = time.perf_counter() if log_debug else None
    expr_code = printer.doprint(expr_codegen)
    t_codegen_s = (time.perf_counter() - t_codegen0) if t_codegen0 is not None else None
    used_arg_names = {name for sym, name in call_signature if sym in expr.free_symbols}
    needs_arg_broadcast = vectorize and len(arg_names) > 0 and (
        len(used_arg_names) < len(arg_names)
    )

    lines: list[str] = []
    lines.append("def _generated(" + ", ".join(arg_names) + "):")

    if vectorize:
        for nm in arg_names:
            lines.append(f"    {nm} = numpy.asarray({nm})")

    # Inject symbol bindings by name.
    for raw_name in sorted(sym_bindings.keys()):
        alias_name = sym_binding_names[raw_name]
        lines.append(f"    {alias_name} = _sym_bindings[{raw_name!r}]")

    if needs_arg_broadcast:
        lines.append(f"    _shape = numpy.broadcast({', '.join(arg_names)}).shape")
        lines.append(f"    return ({expr_code}) + numpy.zeros(_shape)")
    else:
        lines.append(f"    return {expr_code}")

    src = "\n".join(lines)

    # Runtime globals dict compilation (kept separate for timing / debugging).
    t_dict0: float | None = time.perf_counter() if log_debug else None
    glb: dict[str, Any] = {
        "numpy": np,
        "_sym_bindings": sym_bindings,
        **{func_binding_names[name]: func_bindings[name] for name in sorted(func_bindings)},
    }
    t_dict_s = (time.perf_counter() - t_dict0) if t_dict0 is not None else None

    loc: dict[str, Any] = {}

    t_exec0: float | None = time.perf_counter() if log_debug else None
    exec(src, glb, loc)
    t_exec_s = (time.perf_counter() - t_exec0) if t_exec0 is not None else None
    fn = cast(Callable[..., Any], loc["_generated"])

    fn.__doc__ = textwrap.dedent(
        f"""
        Auto-generated NumPy function from SymPy expression.

        expr: {repr(expr)}
        vars: {arg_names}

        Source:
        {src}
        """
    ).strip()

    if log_debug:
        t_total_s = (time.perf_counter() - t_total0) if t_total0 is not None else None
        logger.debug(
            "numpify timings (ms): codegen=%.2f dict=%.2f exec=%.2f total=%.2f",
            1000.0 * (t_codegen_s or 0.0),
            1000.0 * (t_dict_s or 0.0),
            1000.0 * (t_exec_s or 0.0),
            1000.0 * (t_total_s or 0.0),
        )

    return NumericFunction(
        fn=fn,
        symbolic=expr,
        call_signature=call_signature,
        source=src,
        keyed_symbols=keyed_symbols,
        vars_spec=vars_spec,
    )


def _freeze_vars_spec(spec: Any) -> Any:
    if isinstance(spec, tuple):
        return ("T", tuple(_freeze_vars_spec(x) for x in spec))
    if isinstance(spec, dict):
        items = sorted(
            ((k, _freeze_vars_spec(v)) for k, v in spec.items()),
            key=lambda item: (type(item[0]).__name__, repr(item[0])),
        )
        return ("D", tuple(items))
    return ("V", spec)


def _thaw_vars_spec(spec_key: Any) -> Any:
    tag, payload = spec_key
    if tag == "T":
        return tuple(_thaw_vars_spec(x) for x in payload)
    if tag == "D":
        return {k: _thaw_vars_spec(v) for k, v in payload}
    if tag == "V":
        return payload
    raise ValueError(f"Unknown vars spec key tag: {tag!r}")


def _normalize_vars(expr: sp.Basic, vars: _VarsInput | None) -> dict[str, Any]:
    """Normalize supported variable-spec forms into canonical call metadata.

    This helper is the shared variable-spec grammar used by :func:`numpify`
    and callable-first plotting in :meth:`Figure.plot`.

    Accepted ``vars`` forms
    -----------------------
    ``None``
        Use all free symbols from ``expr`` sorted by ``sympy.default_sort_key``.
    ``Symbol``
        Single positional variable.
    ``Iterable[Symbol]``
        Positional variables in iterable order.
    ``Mapping[int | str, Symbol]``
        Mixed positional + keyed mapping. Integer keys define positional
        entries and must be contiguous from ``0``. String keys define keyed
        argument names.
    ``(*symbols, mapping[str, Symbol])``
        Positional prefix plus trailing keyed mapping.

    Returns
    -------
    dict[str, Any]
        Canonical fields ``all``, ``keyed``, ``spec``, and ``spec_key``.
    """
    if vars is None:
        vars_tuple: tuple[sp.Symbol, ...] = tuple(
            sorted(expr.free_symbols, key=sp.default_sort_key)
        )
        return {
            "all": vars_tuple,
            "keyed": (),
            "spec": vars_tuple,
            "spec_key": _freeze_vars_spec(vars_tuple),
        }

    if isinstance(vars, sp.Symbol):
        spec = (vars,)
        return {
            "all": (vars,),
            "keyed": (),
            "spec": spec,
            "spec_key": _freeze_vars_spec(spec),
        }

    positional: list[sp.Symbol] = []
    keyed: list[tuple[str, sp.Symbol]] = []

    def _as_symbol(value: Any) -> sp.Symbol:
        sym = sp.sympify(value)
        if not isinstance(sym, sp.Symbol):
            raise TypeError(f"vars must contain only SymPy Symbols, got {type(sym)}")
        return sym

    if isinstance(vars, Mapping):
        int_entries = [(k, v) for k, v in vars.items() if isinstance(k, int)]
        non_int_entries = [(k, v) for k, v in vars.items() if not isinstance(k, int)]
        if int_entries:
            ordered_int_keys = sorted(k for k, _ in int_entries)
            expected = list(range(len(ordered_int_keys)))
            if ordered_int_keys != expected:
                raise ValueError("Integer vars keys must be contiguous and start at 0")
            by_key = {k: _as_symbol(v) for k, v in int_entries}
            positional.extend(by_key[i] for i in expected)
        for k, v in non_int_entries:
            if not isinstance(k, str):
                raise TypeError("Non-integer vars mapping keys must be strings")
            keyed.append((k, _as_symbol(v)))
        all_symbols = tuple(positional + [sym for _, sym in keyed])
        seen = set()
        for sym in all_symbols:
            if sym in seen:
                raise ValueError(f"Duplicate symbol in vars: {sym!r}")
            seen.add(sym)
        spec = dict(vars)
        return {
            "all": all_symbols,
            "keyed": tuple(keyed),
            "spec": spec,
            "spec_key": _freeze_vars_spec(spec),
        }

    try:
        items = tuple(vars)
    except TypeError as e:
        raise TypeError("vars must be a SymPy Symbol, mapping, or iterable") from e

    tail_mapping: Mapping[Any, Any] | None = None
    if items and isinstance(items[-1], Mapping):
        tail_mapping = cast(Mapping[Any, Any], items[-1])
        items = items[:-1]

    for item in items:
        positional.append(_as_symbol(item))

    if tail_mapping is not None:
        for k, v in tail_mapping.items():
            if isinstance(k, int):
                raise ValueError(
                    "Integer keys are not allowed in tuple+mapping vars form"
                )
            if not isinstance(k, str):
                raise TypeError("Keyed vars names must be strings")
            keyed.append((k, _as_symbol(v)))
        spec = (*items, dict(tail_mapping))
    else:
        spec = tuple(items)

    all_symbols = tuple(positional + [sym for _, sym in keyed])
    seen = set()
    for sym in all_symbols:
        if sym in seen:
            raise ValueError(f"Duplicate symbol in vars: {sym!r}")
        seen.add(sym)
    return {
        "all": all_symbols,
        "keyed": tuple(keyed),
        "spec": spec,
        "spec_key": _freeze_vars_spec(spec),
    }


def _rewrite_expand_definition(expr: sp.Basic, *, max_passes: int = 10) -> sp.Basic:
    """Rewrite using the 'expand_definition' target until stable (or max_passes)."""
    current = expr
    for _ in range(max_passes):
        nxt = current.rewrite("expand_definition")
        if nxt == current:
            break
        current = cast(sp.Basic, nxt)
    return current


def _parse_bindings(
    expr: sp.Basic, f_numpy: Mapping[_BindingKey, Any] | None
) -> tuple[_SymBindings, _FuncBindings]:
    """Split user-provided bindings into symbol and function bindings, plus auto-bindings."""
    sym_bindings: _SymBindings = {}
    func_bindings: _FuncBindings = {}

    if f_numpy:
        for key, value in f_numpy.items():
            if isinstance(key, sp.Symbol):
                sym_bindings[key.name] = value
                continue

            if isinstance(key, sp.Function):
                name = key.func.__name__
                if not callable(value):
                    raise TypeError(
                        f"Function binding for {name} must be callable, got {type(value)}"
                    )
                func_bindings[name] = cast(Callable[..., Any], value)
                continue

            if isinstance(key, FunctionClass):
                name = key.__name__
                if not callable(value):
                    raise TypeError(
                        f"Function binding for {name} must be callable, got {type(value)}"
                    )
                func_bindings[name] = cast(Callable[..., Any], value)
                continue

            raise TypeError(
                "f_numpy keys must be SymPy Symbols or SymPy function objects/classes. "
                f"Got {type(key)}."
            )

    # Auto-bind NamedFunction-style implementations (F.f_numpy) when present.
    for app in expr.atoms(sp.Function):
        impl = getattr(app.func, "f_numpy", None)
        if callable(impl) and app.func.__name__ not in func_bindings:
            func_bindings[app.func.__name__] = cast(Callable[..., Any], impl)

    return sym_bindings, func_bindings


def _require_bound_unknown_functions(
    expr: sp.Basic,
    printer: NumPyPrinter,
    func_bindings: Mapping[str, Callable[..., Any]],
) -> None:
    """Ensure any *bare* printed function calls have runtime bindings."""
    missing: set[str] = set()

    for app in expr.atoms(sp.Function):
        name = app.func.__name__
        try:
            code = printer.doprint(app).strip()
        except Exception:
            continue

        if code.startswith(f"{name}(") and name not in func_bindings:
            missing.add(name)

    if missing:
        missing_str = ", ".join(sorted(missing))
        raise ValueError(
            "Expression contains unknown SymPy function(s) that require a NumPy implementation: "
            f"{missing_str}. Define `<F>.f_numpy` on the function class (e.g. via @NamedFunction), "
            "or pass `f_numpy={F: callable}` to numpify."
        )


# ---------------------------------------------------------------------------
# Cached compilation
# ---------------------------------------------------------------------------

_NUMPIFY_CACHE_MAXSIZE = 256


def _freeze_value_marker(value: Any) -> tuple[str, Any]:
    """Return a hashable marker for *value*.

    We prefer using the value itself when it is hashable (stable semantics).
    If it is unhashable (e.g. NumPy arrays, dicts), fall back to object identity.

    Notes
    -----
    - Using ``id(value)`` means cache hits are session-local and depend on the
      specific object instance. This is usually what you want for injected
      constants like arrays.
    """
    try:
        hash(value)
    except Exception:
        return ("ID", id(value))
    else:
        return ("H", value)


def _freeze_f_numpy_key(
    f_numpy: Mapping[_BindingKey, Any] | None,
) -> tuple[tuple[Any, ...], ...]:
    """Normalize ``f_numpy`` to a hashable key for caching.

    The key is a sorted tuple of entries. Each entry includes:

    - a *normalized binding key* (symbol/function name identity)
    - a *value marker* (hashable value when possible, otherwise ``id(value)``)

    This function is intentionally conservative: it aims to prevent incorrect
    cache hits when bindings differ.
    """
    if not f_numpy:
        return ()

    frozen: list[tuple[Any, ...]] = []
    for k, v in f_numpy.items():
        if isinstance(k, sp.Symbol):
            k_norm = ("S", k.name)
        elif isinstance(k, sp.Function):
            # Bindings for applications behave like bindings for their function class.
            fc = k.func
            k_norm = (
                "F",
                getattr(fc, "__module__", ""),
                getattr(fc, "__qualname__", fc.__name__),
            )
        elif isinstance(k, FunctionClass):
            k_norm = (
                "F",
                getattr(k, "__module__", ""),
                getattr(k, "__qualname__", k.__name__),
            )
        else:
            # Should not happen: numpify() validates keys.
            k_norm = ("K", repr(k))

        v_mark = _freeze_value_marker(v)
        frozen.append((k_norm, v_mark))

    frozen.sort(key=lambda item: item[0])
    return tuple(tuple(x) for x in frozen)


class _FrozenFNumPy:
    """Small hashable wrapper around an ``f_numpy`` mapping.

    This exists solely so that :func:`functools.lru_cache` can cache compiled
    callables even when the mapping contains unhashable values (like NumPy arrays).

    The cache key is derived from a normalized, hashable view of the mapping.
    """

    __slots__ = ("mapping", "_key")

    def __init__(self, mapping: Mapping[_BindingKey, Any] | None):
        """Copy and normalize ``f_numpy`` mapping for cache-key construction."""
        self.mapping: dict[_BindingKey, Any] = {} if mapping is None else dict(mapping)
        self._key = _freeze_f_numpy_key(self.mapping)

    def __hash__(self) -> int:  # pragma: no cover
        """Return hash of the frozen normalized mapping key."""
        return hash(self._key)

    def __eq__(self, other: object) -> bool:  # pragma: no cover
        """Compare two frozen wrappers by their normalized binding keys."""
        return isinstance(other, _FrozenFNumPy) and self._key == other._key


@lru_cache(maxsize=_NUMPIFY_CACHE_MAXSIZE)
def _numpify_cached_impl(
    expr: sp.Basic,
    vars_tuple: tuple[sp.Symbol, ...],
    vars_spec_key: Any,
    frozen: _FrozenFNumPy,
    vectorize: bool,
    expand_definition: bool,
) -> NumericFunction:
    """Compile an expression on cache misses for :func:`numpify_cached`."""
    # NOTE: This function body only runs on cache *misses*.
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "numpify_cached: cache MISS (vars=%s, vectorize=%s, expand_definition=%s)",
            [a.name for a in vars_tuple],
            vectorize,
            expand_definition,
        )
    # Delegate to the uncached compiler for actual compilation.
    return _numpify_uncached(
        expr,
        vars=_thaw_vars_spec(vars_spec_key),
        f_numpy=frozen.mapping,
        vectorize=vectorize,
        expand_definition=expand_definition,
    )


def numpify_cached(
    expr: Any,
    *,
    vars: _VarsInput | None = None,
    f_numpy: Mapping[_BindingKey, Any] | None = None,
    vectorize: bool = True,
    expand_definition: bool = True,
) -> NumericFunction:
    """Cached version of :func:`numpify`.
    
    Full API
    --------
    ``numpify_cached(expr: Any, *, vars: _VarsInput | None=None, f_numpy: Mapping[_BindingKey, Any] | None=None, vectorize: bool=True, expand_definition: bool=True) -> NumericFunction``
    
    Parameters
    ----------
    expr : Any
        Symbolic expression payload. Required.
    
    vars : _VarsInput | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    f_numpy : Mapping[_BindingKey, Any] | None, optional
        Value for ``f_numpy`` in this API. Defaults to ``None``.
    
    vectorize : bool, optional
        Value for ``vectorize`` in this API. Defaults to ``True``.
    
    expand_definition : bool, optional
        Value for ``expand_definition`` in this API. Defaults to ``True``.
    
    Returns
    -------
    NumericFunction
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``vars=None``: Value for ``vars`` in this API.
    - ``f_numpy=None``: Value for ``f_numpy`` in this API.
    - ``vectorize=True``: Value for ``vectorize`` in this API.
    - ``expand_definition=True``: Value for ``expand_definition`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.numpify``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.numpify import numpify_cached
        result = numpify_cached(...)
    
    Discovery-oriented use::
    
        help(numpify_cached)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(numpify_cached)`` and inspect sibling APIs in the same module.
    """
    # Normalize to SymPy and vars tuple exactly as numpify() does.
    expr_sym = cast(sp.Basic, sp.sympify(expr))
    if not isinstance(expr_sym, sp.Basic):
        raise TypeError(
            f"numpify_cached expects a SymPy expression, got {type(expr_sym)}"
        )

    normalized_vars = _normalize_vars(expr_sym, vars)
    vars_tuple = normalized_vars["all"]
    vars_spec_key = normalized_vars["spec_key"]
    frozen = _FrozenFNumPy(f_numpy)

    return _numpify_cached_impl(
        expr_sym,
        vars_tuple,
        vars_spec_key,
        frozen,
        vectorize,
        expand_definition,
    )


# Expose cache controls on the public wrapper.
numpify_cached.cache_info = _numpify_cached_impl.cache_info  # type: ignore[attr-defined]
numpify_cached.cache_clear = _numpify_cached_impl.cache_clear  # type: ignore[attr-defined]
