"""Scalar-field input normalization helpers for :class:`gu_toolkit.Figure.Figure`.

This module mirrors the callable/expression normalization contract used by
``plot()`` while targeting 2D scalar fields ``z = f(x, y)`` sampled on a
rectangular grid.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .figure_plot_normalization import (
    PlotVarsSpec,
    _expression_symbol_sort_key,
    _merge_unique_symbols,
    coerce_symbol,
    rebind_numeric_function_vars,
)
from .numpify import NumericFunction, _normalize_vars


FieldAxisSpec = Symbol | tuple[Symbol, Any, Any]


def _normalize_axis_var(axis_spec: Any, *, axis_name: str) -> Symbol:
    """Return the axis symbol extracted from one public axis spec."""
    if isinstance(axis_spec, tuple):
        if len(axis_spec) != 3:
            raise ValueError(
                f"scalar_field() {axis_name} range tuple must have shape "
                f"({axis_name}, min, max)."
            )
        return coerce_symbol(axis_spec[0], role=f"{axis_name} range tuple variable")
    return coerce_symbol(axis_spec, role=f"{axis_name} variable")


def _wrap_numeric_function_for_field_axes(
    numeric_fn: NumericFunction,
    *,
    x_var: Symbol,
    y_var: Symbol,
    symbolic_expression: Expr,
) -> NumericFunction:
    """Return ``numeric_fn`` rebound to canonical ``(x, y, *params)`` order.

    Callable-backed scalar fields may omit one or both axis variables (constant
    fields or parameter-only fields) or may declare a different argument order.
    Rendering always evaluates on ``(X, Y)`` mesh arrays, so this helper builds
    a wrapper that accepts ``x_var`` and ``y_var`` first and forwards only the
    arguments the original numeric function expects, in the original order.
    """

    original_symbols = tuple(numeric_fn.free_vars)
    canonical_symbols = _merge_unique_symbols((x_var, y_var), original_symbols)
    positions = tuple(canonical_symbols.index(sym) for sym in original_symbols)

    def wrapped(*args: Any) -> Any:
        return numeric_fn(*(args[pos] for pos in positions))

    return NumericFunction(
        wrapped,
        vars=canonical_symbols,
        symbolic=symbolic_expression,
        source=numeric_fn.source,
    )


def normalize_field_inputs(
    func: Any,
    x_spec: Any,
    y_spec: Any,
    *,
    vars: PlotVarsSpec | None = None,
    id_hint: str | None = None,
) -> tuple[Symbol, Symbol, Expr, NumericFunction | None, tuple[Symbol, ...]]:
    """Normalize callable/expression inputs for ``scalar_field()``.
    
    Full API
    --------
    ``normalize_field_inputs(func: Any, x_spec: Any, y_spec: Any, *, vars: PlotVarsSpec | None=None, id_hint: str | None=None) -> tuple[Symbol, Symbol, Expr, NumericFunction | None, tuple[Symbol, ...]]``
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x_spec : Any
        Value for ``x_spec`` in this API. Required.
    
    y_spec : Any
        Value for ``y_spec`` in this API. Required.
    
    vars : PlotVarsSpec | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    id_hint : str | None, optional
        Value for ``id_hint`` in this API. Defaults to ``None``.
    
    Returns
    -------
    tuple[Symbol, Symbol, Expr, NumericFunction | None, tuple[Symbol, Ellipsis]]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``vars=None``: Value for ``vars`` in this API.
    - ``id_hint=None``: Value for ``id_hint`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field_normalization``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field_normalization import normalize_field_inputs
        result = normalize_field_inputs(...)
    
    Discovery-oriented use::
    
        help(normalize_field_inputs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(normalize_field_inputs)`` and inspect sibling APIs in the same module.
    """
    x_var = _normalize_axis_var(x_spec, axis_name="x")
    y_var = _normalize_axis_var(y_spec, axis_name="y")
    if x_var == y_var:
        raise ValueError("scalar_field() requires distinct x and y variables.")

    vars_spec: Any = None
    if vars is not None:
        normalized = _normalize_vars(sp.Integer(0), vars)
        vars_tuple = tuple(normalized["all"])
        if not vars_tuple:
            raise ValueError("scalar_field() vars must not be empty when provided")
        vars_spec = normalized["spec"]
    else:
        vars_tuple = None

    numeric_fn: NumericFunction | None = None
    source_callable: Callable[..., Any] | None = None
    expr: Expr
    call_symbols: tuple[Symbol, ...]

    if isinstance(func, Expr):
        expr = func
        call_symbols = tuple(sorted(expr.free_symbols, key=_expression_symbol_sort_key))
    elif isinstance(func, NumericFunction):
        numeric_fn = func
        source_callable = func._fn
        call_symbols = tuple(func.free_vars)
        symbolic = func.symbolic
        if isinstance(symbolic, Expr):
            expr = symbolic
        else:
            fallback_name = id_hint or "field"
            expr = sp.Symbol(f"{fallback_name}_numeric")
    elif callable(func):
        source_callable = func
        sig = inspect.signature(func)
        positional = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in sig.parameters.values()
        ):
            raise TypeError(
                "scalar_field() callable does not support *args/**kwargs signatures"
            )
        call_symbols = tuple(sp.Symbol(p.name) for p in positional)
        numeric_fn = NumericFunction(
            func, vars=vars_spec if vars_spec is not None else call_symbols
        )
        if vars_spec is not None:
            call_symbols = tuple(numeric_fn.free_vars)
        expr = sp.Symbol(id_hint or getattr(func, "__name__", "field"))
    else:
        raise TypeError(
            "scalar_field() expects a SymPy expression, NumericFunction, or callable."
        )

    if vars_tuple is not None:
        bound_symbols = vars_tuple
        if numeric_fn is not None:
            numeric_fn = rebind_numeric_function_vars(
                numeric_fn,
                vars_spec=vars_spec if vars_spec is not None else bound_symbols,
                source_callable=source_callable,
            )
    else:
        bound_symbols = call_symbols

    canonical_symbols = _merge_unique_symbols((x_var, y_var), bound_symbols)
    if numeric_fn is not None:
        numeric_fn = _wrap_numeric_function_for_field_axes(
            numeric_fn,
            x_var=x_var,
            y_var=y_var,
            symbolic_expression=expr,
        )
        canonical_symbols = tuple(numeric_fn.free_vars)

    parameters = tuple(sym for sym in canonical_symbols if sym not in {x_var, y_var})
    return x_var, y_var, expr, numeric_fn, parameters


__all__ = ["FieldAxisSpec", "normalize_field_inputs"]
