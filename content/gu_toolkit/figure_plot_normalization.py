"""Plot input normalization helpers for :class:`gu_toolkit.Figure.Figure`.

Purpose
-------
This module isolates callable/expression input normalization used by
``Figure.plot``. It converts accepted plot-call forms into a canonical tuple
that Figure can orchestrate without embedding deep branching logic.

Architecture
------------
The normalizer is intentionally stateless and side-effect free. It is designed
as a focused boundary between user-facing plotting API grammar and the
coordinator layer. This keeps normalization behavior unit-testable independent
from widget/rendering concerns.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit.figure_plot_normalization import normalize_plot_inputs
>>> x, a = sp.symbols("x a")
>>> plot_var, expr, numeric_fn, params = normalize_plot_inputs(a * x, x)
>>> plot_var == x
True
>>> params == (a,)
True

Discoverability
---------------
If you need runtime plotting behavior after normalization, inspect
``figure_plot.py`` and ``Figure.py``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeAlias

import numpy as np
import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .numpify import NumericFunction, _normalize_vars

PlotVarsSpec: TypeAlias = (
    Symbol | Sequence[Symbol | Mapping[str, Symbol]] | Mapping[int | str, Symbol]
)


def coerce_symbol(value: Any, *, role: str) -> Symbol:
    """Return ``value`` as a SymPy symbol or raise a clear ``TypeError``.
    
    Full API
    --------
    ``coerce_symbol(value: Any, *, role: str) -> Symbol``
    
    Parameters
    ----------
    value : Any
        New or current value for the relevant property, control, or calculation. Required.
    
    role : str
        Value for ``role`` in this API. Required.
    
    Returns
    -------
    Symbol
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_normalization``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_normalization import coerce_symbol
        result = coerce_symbol(...)
    
    Discovery-oriented use::
    
        help(coerce_symbol)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(coerce_symbol)`` and inspect sibling APIs in the same module.
    """
    if isinstance(value, Symbol):
        return value
    raise TypeError(
        f"plot() expects {role} to be a sympy.Symbol, got {type(value).__name__}"
    )


def _expression_symbol_sort_key(symbol: Symbol) -> tuple[Any, ...]:
    """Return a deterministic sort key for expression-derived symbols.

    SymPy's ``sort_key()`` deliberately ignores assumption metadata for symbols
    that share the same name. Adding a small tie-break on assumption payload
    keeps parameter expansion stable when an expression mixes same-name symbols
    such as ``Symbol("q", real=True)`` and ``Symbol("q", integer=True)``.
    """
    assumptions = tuple(sorted(symbol.assumptions0.items()))
    return (symbol.sort_key(), len(assumptions), assumptions)


def rebind_numeric_function_vars(
    numeric_fn: NumericFunction,
    *,
    vars_spec: Any,
    source_callable: Callable[..., Any] | None = None,
) -> NumericFunction:
    """Return ``numeric_fn`` rebound to ``vars_spec`` order.
    
    Full API
    --------
    ``rebind_numeric_function_vars(numeric_fn: NumericFunction, *, vars_spec: Any, source_callable: Callable[..., Any] | None=None) -> NumericFunction``
    
    Parameters
    ----------
    numeric_fn : NumericFunction
        Value for ``numeric_fn`` in this API. Required.
    
    vars_spec : Any
        Value for ``vars_spec`` in this API. Required.
    
    source_callable : Callable[Ellipsis, Any] | None, optional
        Value for ``source_callable`` in this API. Defaults to ``None``.
    
    Returns
    -------
    NumericFunction
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``source_callable=None``: Value for ``source_callable`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_normalization``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_normalization import rebind_numeric_function_vars
        result = rebind_numeric_function_vars(...)
    
    Discovery-oriented use::
    
        help(rebind_numeric_function_vars)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(rebind_numeric_function_vars)`` and inspect sibling APIs in the same module.
    """
    fn = source_callable if source_callable is not None else numeric_fn._fn
    return NumericFunction(
        fn,
        vars=vars_spec,
        symbolic=numeric_fn.symbolic,
        source=numeric_fn.source,
    )


def normalize_plot_inputs(
    first: Any,
    second: Any,
    *,
    vars: PlotVarsSpec | None = None,
    id_hint: str | None = None,
) -> tuple[Symbol, Expr, NumericFunction | None, tuple[Symbol, ...]]:
    """Normalize callable-first ``plot()`` inputs.
    
    Full API
    --------
    ``normalize_plot_inputs(first: Any, second: Any, *, vars: PlotVarsSpec | None=None, id_hint: str | None=None) -> tuple[Symbol, Expr, NumericFunction | None, tuple[Symbol, ...]]``
    
    Parameters
    ----------
    first : Any
        Value for ``first`` in this API. Required.
    
    second : Any
        Value for ``second`` in this API. Required.
    
    vars : PlotVarsSpec | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    id_hint : str | None, optional
        Value for ``id_hint`` in this API. Defaults to ``None``.
    
    Returns
    -------
    tuple[Symbol, Expr, NumericFunction | None, tuple[Symbol, Ellipsis]]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``vars=None``: Value for ``vars`` in this API.
    - ``id_hint=None``: Value for ``id_hint`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_normalization``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_normalization import normalize_plot_inputs
        result = normalize_plot_inputs(...)
    
    Discovery-oriented use::
    
        help(normalize_plot_inputs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(normalize_plot_inputs)`` and inspect sibling APIs in the same module.
    """
    vars_spec: Any = None
    if vars is not None:
        normalized = _normalize_vars(sp.Integer(0), vars)
        vars_tuple = tuple(normalized["all"])
        if not vars_tuple:
            raise ValueError("plot() vars must not be empty when provided")
        vars_spec = normalized["spec"]
    else:
        vars_tuple = None

    f = first
    var_or_range = second

    numeric_fn: NumericFunction | None = None
    source_callable: Callable[..., Any] | None = None
    expr: Expr
    call_symbols: tuple[Symbol, ...]

    if isinstance(f, Expr):
        expr = f
        call_symbols = tuple(sorted(expr.free_symbols, key=_expression_symbol_sort_key))
    elif isinstance(f, NumericFunction):
        numeric_fn = f
        source_callable = f._fn
        call_symbols = tuple(f.free_vars)
        symbolic = f.symbolic
        if isinstance(symbolic, Expr):
            expr = symbolic
        else:
            fallback_name = id_hint or "f"
            expr = sp.Symbol(f"{fallback_name}_numeric")
    elif callable(f):
        source_callable = f
        sig = inspect.signature(f)
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
                "plot() callable does not support *args/**kwargs signatures"
            )
        call_symbols = tuple(sp.Symbol(p.name) for p in positional)
        numeric_fn = NumericFunction(
            f, vars=vars_spec if vars_spec is not None else call_symbols
        )
        if vars_spec is not None:
            call_symbols = tuple(numeric_fn.free_vars)
        expr = sp.Symbol(id_hint or getattr(f, "__name__", "f"))
    else:
        raise TypeError(
            "plot() expects first argument to be a SymPy expression, NumericFunction, or callable."
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

    if isinstance(var_or_range, tuple):
        if len(var_or_range) != 3:
            raise ValueError(
                "plot() range tuple must have shape (var, min, max), e.g. (x, -4, 4)"
            )
        plot_var = coerce_symbol(var_or_range[0], role="range tuple variable")
    elif var_or_range is None:
        if len(bound_symbols) == 1:
            plot_var = bound_symbols[0]
        else:
            raise ValueError(
                "plot() could not infer plotting variable for callable-first usage. "
                "Pass an explicit symbol or range tuple, e.g. plot(f, x) or plot(f, (x, -4, 4))."
            )
    else:
        plot_var = coerce_symbol(var_or_range, role="plot variable")

    if plot_var not in bound_symbols:
        allow_missing_plot_var = (
            numeric_fn is None
            or vars_tuple is not None
            or len(bound_symbols) == 0
        )

        if allow_missing_plot_var:
            if numeric_fn is not None:
                numeric_fn = _wrap_numeric_function_with_ignored_parameter(
                    numeric_fn,
                    parameter_var=plot_var,
                    symbolic_expression=expr,
                )
                bound_symbols = tuple(numeric_fn.free_vars)
            else:
                bound_symbols = (plot_var, *bound_symbols)
        elif len(bound_symbols) == 1:
            # Preserve callable-first ergonomics for single-argument callables
            # whose argument name differs from the explicit plotting symbol,
            # e.g. ``plot(lambda t: t**2, x)``. Multi-argument callables remain
            # ambiguous without ``vars=...``.
            bound_symbols = (plot_var,)
            if numeric_fn is not None:
                numeric_fn = rebind_numeric_function_vars(
                    numeric_fn,
                    vars_spec=bound_symbols,
                    source_callable=source_callable,
                )
        else:
            raise ValueError(
                f"plot() variable {plot_var!r} is not present in callable variables {bound_symbols!r}. "
                "Use vars=... to declare callable variable order explicitly."
            )

    parameters = tuple(sym for sym in bound_symbols if sym != plot_var)
    return plot_var, expr, numeric_fn, parameters


def _wrap_numeric_function_with_ignored_parameter(
    numeric_fn: NumericFunction,
    *,
    parameter_var: Symbol,
    symbolic_expression: Expr,
) -> NumericFunction:
    """Return ``numeric_fn`` wrapped to ignore and broadcast over one leading var.

    Plot-like renderers always sample a leading independent variable array. Some
    normalized callables are constant or parameter-only with respect to that
    variable, so they must accept the leading sample input, ignore it when
    calling the original function, and still broadcast scalar results to the
    sampled shape.
    """

    def wrapped(*args: Any) -> Any:
        result = numeric_fn(*args[1:])
        if not args:
            return result

        leading_shape = np.asarray(args[0]).shape
        if not leading_shape:
            return result

        result_array = np.asarray(result)
        if result_array.shape != ():
            return result

        return result_array + np.zeros(leading_shape)

    return NumericFunction(
        wrapped,
        vars=(parameter_var, *numeric_fn.free_vars),
        symbolic=symbolic_expression,
        source=numeric_fn.source,
    )


def _merge_unique_symbols(*sequences: Sequence[Symbol]) -> tuple[Symbol, ...]:
    """Merge symbol sequences while preserving first-seen order.

    Symbol identity, not just ``symbol.name``, is preserved here so later
    parameter expansion can still distinguish same-name symbols with different
    SymPy assumptions.
    """

    merged: list[Symbol] = []
    for sequence in sequences:
        for symbol in sequence:
            if symbol not in merged:
                merged.append(symbol)
    return tuple(merged)


def _normalize_parametric_component(
    component: Any,
    *,
    parameter_var: Symbol,
    vars: PlotVarsSpec | None = None,
    id_hint: str | None = None,
    component_name: str,
) -> tuple[Expr, NumericFunction | None, tuple[Symbol, ...]]:
    """Normalize one coordinate component for ``parametric_plot()``.

    Unlike scalar ``plot()``, a parametric coordinate component may legitimately
    be constant or may depend only on figure parameters. For that reason this
    normalizer allows the shared parameter variable to be absent and, when
    needed, wraps callable-backed numeric functions so they accept and ignore the
    sampled parameter array.
    """

    vars_spec: Any = None
    if vars is not None:
        normalized = _normalize_vars(sp.Integer(0), vars)
        vars_tuple = tuple(normalized["all"])
        if not vars_tuple:
            raise ValueError("parametric_plot() vars must not be empty when provided")
        vars_spec = normalized["spec"]
    else:
        vars_tuple = None

    numeric_fn: NumericFunction | None = None
    source_callable: Callable[..., Any] | None = None
    expr: Expr
    call_symbols: tuple[Symbol, ...]

    if isinstance(component, Expr):
        expr = component
        call_symbols = tuple(
            sorted(expr.free_symbols, key=_expression_symbol_sort_key)
        )
    elif isinstance(component, NumericFunction):
        numeric_fn = component
        source_callable = component._fn
        call_symbols = tuple(component.free_vars)
        symbolic = component.symbolic
        if isinstance(symbolic, Expr):
            expr = symbolic
        else:
            expr = sp.Symbol(id_hint or component_name)
    elif callable(component):
        source_callable = component
        sig = inspect.signature(component)
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
                "parametric_plot() callable does not support *args/**kwargs signatures"
            )
        call_symbols = tuple(sp.Symbol(p.name) for p in positional)
        numeric_fn = NumericFunction(
            component,
            vars=vars_spec if vars_spec is not None else call_symbols,
        )
        if vars_spec is not None:
            call_symbols = tuple(numeric_fn.free_vars)
        expr = sp.Symbol(id_hint or getattr(component, "__name__", component_name))
    else:
        raise TypeError(
            "parametric_plot() expects each component to be a SymPy expression, NumericFunction, or callable."
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

    if parameter_var not in bound_symbols:
        if numeric_fn is not None:
            numeric_fn = _wrap_numeric_function_with_ignored_parameter(
                numeric_fn,
                parameter_var=parameter_var,
                symbolic_expression=expr,
            )
        bound_symbols = (parameter_var, *bound_symbols)

    parameters = tuple(sym for sym in bound_symbols if sym != parameter_var)
    return expr, numeric_fn, parameters


def normalize_parametric_plot_inputs(
    components: Any,
    parameter_range: Any,
    *,
    vars: PlotVarsSpec | None = None,
    id_hint: str | None = None,
) -> tuple[
    Symbol,
    Expr,
    Expr,
    NumericFunction | None,
    NumericFunction | None,
    tuple[Symbol, ...],
]:
    """Normalize ``parametric_plot()`` inputs.
    
    Full API
    --------
    ``normalize_parametric_plot_inputs(components: Any, parameter_range: Any, *, vars: PlotVarsSpec | None=None, id_hint: str | None=None) -> tuple[Symbol, Expr, Expr, NumericFunction | None, NumericFunction | None, tuple[Symbol, ...]]``
    
    Parameters
    ----------
    components : Any
        Value for ``components`` in this API. Required.
    
    parameter_range : Any
        Value for ``parameter_range`` in this API. Required.
    
    vars : PlotVarsSpec | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    id_hint : str | None, optional
        Value for ``id_hint`` in this API. Defaults to ``None``.
    
    Returns
    -------
    tuple[Symbol, Expr, Expr, NumericFunction | None, NumericFunction | None, tuple[Symbol, Ellipsis]]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``vars=None``: Value for ``vars`` in this API.
    - ``id_hint=None``: Value for ``id_hint`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_normalization``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_normalization import normalize_parametric_plot_inputs
        result = normalize_parametric_plot_inputs(...)
    
    Discovery-oriented use::
    
        help(normalize_parametric_plot_inputs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(normalize_parametric_plot_inputs)`` and inspect sibling APIs in the same module.
    """

    if not isinstance(components, Sequence) or len(components) != 2:
        raise ValueError(
            "parametric_plot() expects coordinate components with shape (xexpr, yexpr)."
        )

    if not isinstance(parameter_range, tuple) or len(parameter_range) != 3:
        raise ValueError(
            "parametric_plot() range tuple must have shape (t, min, max), e.g. (t, 0, 1)."
        )

    parameter_var = coerce_symbol(
        parameter_range[0], role="parametric range tuple variable"
    )

    x_expr, x_numeric_fn, x_parameters = _normalize_parametric_component(
        components[0],
        parameter_var=parameter_var,
        vars=vars,
        id_hint=None if id_hint is None else f"{id_hint}_x",
        component_name="x",
    )
    y_expr, y_numeric_fn, y_parameters = _normalize_parametric_component(
        components[1],
        parameter_var=parameter_var,
        vars=vars,
        id_hint=None if id_hint is None else f"{id_hint}_y",
        component_name="y",
    )

    parameters = _merge_unique_symbols(x_parameters, y_parameters)
    return parameter_var, x_expr, y_expr, x_numeric_fn, y_numeric_fn, parameters
