"""Code generation engine for reproducing smart figures.

This module converts :class:`FigureSnapshot` objects into self-contained
Python source code that, when executed, recreates the figure with the same
plots, parameter values, styling, and info cards.

Two public helpers are provided:

- :func:`sympy_to_code` — Converts a single SymPy expression into a Python
  source fragment (assumes ``import sympy as sp`` and bare symbol locals).
- :func:`figure_to_code` — Converts a full :class:`FigureSnapshot` into a
  complete, runnable script.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import keyword
from typing import Literal

import sympy as sp
from sympy import Basic, Expr, Symbol
from sympy.core.numbers import (
    Float,
    Integer,
    Rational,
)
from sympy.printing.str import StrPrinter

from .FigureSnapshot import FigureSnapshot, InfoCardSnapshot
from .FieldPlotSnapshot import FieldPlotSnapshot
from .PlotSnapshot import PlotSnapshot

# ---------------------------------------------------------------------------
# SymPy expression → Python source
# ---------------------------------------------------------------------------


class _SpPrefixedPrinter(StrPrinter):
    """StrPrinter variant that prefixes SymPy functions/constants with ``sp.``.

    Symbols with valid Python identifiers are printed as bare names. Symbols
    with non-Python names (for example ``\alpha``) are inlined as
    ``sp.Symbol(...)`` expressions so the generated source remains executable.
    Everything else that requires SymPy is qualified with ``sp.``.
    """

    # -- atoms / constants --------------------------------------------------

    def _print_Symbol(self, expr: Symbol) -> str:  # noqa: N802
        return _symbol_ref(expr)

    def _print_Pi(self, expr: Basic) -> str:  # noqa: N802
        return "sp.pi"

    def _print_Exp1(self, expr: Basic) -> str:  # noqa: N802
        return "sp.E"

    def _print_ImaginaryUnit(self, expr: Basic) -> str:  # noqa: N802
        return "sp.I"

    def _print_Infinity(self, expr: Basic) -> str:  # noqa: N802
        return "sp.oo"

    def _print_NegativeInfinity(self, expr: Basic) -> str:  # noqa: N802
        return "-sp.oo"

    def _print_BooleanTrue(self, expr: Basic) -> str:  # noqa: N802
        return "sp.true"

    def _print_BooleanFalse(self, expr: Basic) -> str:  # noqa: N802
        return "sp.false"

    # -- numbers ------------------------------------------------------------

    def _print_Integer(self, expr: Integer) -> str:  # noqa: N802
        return str(int(expr))

    def _print_Rational(self, expr: Rational) -> str:  # noqa: N802
        if expr.q == 1:
            return str(int(expr.p))
        return f"sp.Rational({int(expr.p)}, {int(expr.q)})"

    def _print_Float(self, expr: Float) -> str:  # noqa: N802
        return repr(float(expr))

    def _print_NaN(self, expr: Basic) -> str:  # noqa: N802
        return "sp.nan"

    # -- generic function fallback ------------------------------------------

    def _print_Function(self, expr: Basic) -> str:  # noqa: N802
        func_name = expr.func.__name__
        args = ", ".join(self._print(a) for a in expr.args)
        if hasattr(sp, func_name) and getattr(sp, func_name) is expr.func:
            return f"sp.{func_name}({args})"
        return f"sp.Function({func_name!r})({args})"

    # -- common operations that the base printer handles but need care ------

    def _print_Pow(self, expr: Basic) -> str:  # noqa: N802
        base = self._print(expr.base)
        exp = self._print(expr.exp)

        # Wrap additions/subtractions in parens for the base
        if expr.base.is_Add:
            base = f"({base})"
        # Wrap negative or complex exponents in parens
        if expr.exp.is_Add or (expr.exp.is_Number and expr.exp < 0):
            exp = f"({exp})"

        # sqrt shortcut for readability
        if expr.exp == sp.Rational(1, 2):
            return f"sp.sqrt({self._print(expr.base)})"
        if expr.exp == sp.Rational(-1, 2):
            return f"1/sp.sqrt({self._print(expr.base)})"

        return f"{base}**{exp}"

    def _print_Abs(self, expr: Basic) -> str:  # noqa: N802
        return f"sp.Abs({self._print(expr.args[0])})"

    def _print_Piecewise(self, expr: Basic) -> str:  # noqa: N802
        pieces = ", ".join(
            f"({self._print(e)}, {self._print(c)})" for e, c in expr.args
        )
        return f"sp.Piecewise({pieces})"


_printer = _SpPrefixedPrinter()


def _is_valid_python_name(name: str) -> bool:
    """Return whether *name* is a safe bare identifier in generated code."""

    return bool(name) and name.isidentifier() and not keyword.iskeyword(name)


def _symbol_ref(sym: Symbol) -> str:
    """Return an executable Python reference for a SymPy symbol."""

    return sym.name if _is_valid_python_name(sym.name) else f"sp.Symbol({sym.name!r})"


@dataclass(frozen=True)
class CodegenOptions:
    """Configuration knobs for :func:`figure_to_code`.
    
    Full API
    --------
    ``CodegenOptions(include_imports: bool=True, include_symbol_definitions: bool=True, interface_style: Literal['figure_methods', 'context_manager']='context_manager', include_dynamic_info_as_commented_blocks: bool=True)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    include_imports : bool, optional
        Value for ``include_imports`` in this API. Defaults to ``True``.
    
    include_symbol_definitions : bool, optional
        Value for ``include_symbol_definitions`` in this API. Defaults to ``True``.
    
    interface_style : Literal['figure_methods', 'context_manager'], optional
        Value for ``interface_style`` in this API. Defaults to ``'context_manager'``.
    
    include_dynamic_info_as_commented_blocks : bool, optional
        Value for ``include_dynamic_info_as_commented_blocks`` in this API. Defaults to ``True``.
    
    Returns
    -------
    CodegenOptions
        New ``CodegenOptions`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``include_imports=True``: Value for ``include_imports`` in this API.
    - ``include_symbol_definitions=True``: Value for ``include_symbol_definitions`` in this API.
    - ``interface_style='context_manager'``: Value for ``interface_style`` in this API.
    - ``include_dynamic_info_as_commented_blocks=True``: Value for ``include_dynamic_info_as_commented_blocks`` in this API.
    
    Architecture note
    -----------------
    ``CodegenOptions`` lives in ``gu_toolkit.codegen``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.codegen import CodegenOptions
        obj = CodegenOptions(...)
    
    Discovery-oriented use::
    
        help(CodegenOptions)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(CodegenOptions)`` and ``dir(CodegenOptions)`` to inspect adjacent members.
    """

    include_imports: bool = True
    include_symbol_definitions: bool = True
    interface_style: Literal["figure_methods", "context_manager"] = "context_manager"
    include_dynamic_info_as_commented_blocks: bool = True

    def __post_init__(self) -> None:
        """Validate option values for deterministic code generation."""
        if self.interface_style not in {"figure_methods", "context_manager"}:
            raise ValueError(
                "interface_style must be one of {'figure_methods', 'context_manager'}"
            )


def sympy_to_code(expr: Expr) -> str:
    """Convert a SymPy expression to a Python source fragment.
    
    Full API
    --------
    ``sympy_to_code(expr: Expr) -> str``
    
    Parameters
    ----------
    expr : Expr
        Symbolic expression payload. Required.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.codegen``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.codegen import sympy_to_code
        result = sympy_to_code(...)
    
    Discovery-oriented use::
    
        help(sympy_to_code)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(sympy_to_code)`` and inspect sibling APIs in the same module.
    """
    return _printer.doprint(expr)


# ---------------------------------------------------------------------------
# Full figure → Python script
# ---------------------------------------------------------------------------


def _collect_symbols(snapshot: FigureSnapshot) -> list[Symbol]:
    """Return all unique symbols (params + plot vars) in a deterministic order."""
    seen: OrderedDict[str, Symbol] = OrderedDict()

    for sym in snapshot.parameters.symbols:
        seen[sym.name] = sym

    for ps in snapshot.plots.values():
        if getattr(ps, "is_field", False):
            for sym in (ps.x_var, ps.y_var, *ps.parameters):
                if sym.name not in seen:
                    seen[sym.name] = sym
        else:
            if ps.var.name not in seen:
                seen[ps.var.name] = ps.var
            for p in ps.parameters:
                if p.name not in seen:
                    seen[p.name] = p
            if ps.x_func is not None:
                for sym in sorted(ps.x_func.free_symbols, key=lambda s: s.sort_key()):
                    if sym.name not in seen:
                        seen[sym.name] = sym

    return list(seen.values())


def _snapshot_uses_parametric_plot(snapshot: FigureSnapshot) -> bool:
    """Return whether any plot snapshot requires ``parametric_plot`` imports."""
    return any(getattr(ps, "is_parametric", False) for ps in snapshot.plots.values())


def _snapshot_field_helpers(snapshot: FigureSnapshot) -> tuple[str, ...]:
    """Return the distinct scalar-field helper imports required by ``snapshot``."""
    helpers: list[str] = []
    for ps in snapshot.plots.values():
        if not getattr(ps, "is_field", False):
            continue
        if getattr(ps, "preset", None) == "temperature" and getattr(ps, "render_mode", None) == "heatmap":
            name = "temperature"
        elif getattr(ps, "render_mode", None) == "contour":
            name = "contour"
        else:
            name = "density"
        if name not in helpers:
            helpers.append(name)
    return tuple(helpers)


def _fmt_float(v: float) -> str:
    """Format a float for code output, dropping unnecessary trailing zeros."""
    if v == int(v):
        return f"{int(v)}.0"
    return repr(v)


def _main_view_snapshot(snapshot: FigureSnapshot):
    """Return the serialized main-view snapshot when present.

    Code generation intentionally reconstructs figure constructor defaults from
    the ``main`` view rather than from the currently active view. This keeps
    multi-view round-tripping correct when a snapshot was taken while another
    view was active.
    """
    return next((view for view in snapshot.views if view.id == "main"), None)


def _symbol_definitions(symbols: list[Symbol]) -> str:
    """Emit ``x = sp.Symbol('x')`` lines for valid bare Python identifiers."""

    valid = [sym for sym in symbols if _is_valid_python_name(sym.name)]
    if not valid:
        return ""
    if len(valid) == 1:
        s = valid[0]
        return f"{s.name} = sp.Symbol({s.name!r})"
    names = ", ".join(s.name for s in valid)
    quoted = " ".join(s.name for s in valid)
    return f"{names} = sp.symbols({quoted!r})"


def _parameter_call(
    sym: Symbol, meta: dict, *, style: Literal["figure_methods", "context_manager"]
) -> str:
    """Emit one parameter registration call."""
    parts = [_symbol_ref(sym)]
    for key in ("value", "min", "max", "step"):
        if key in meta:
            parts.append(f"{key}={_fmt_float(float(meta[key]))}")
    if style == "context_manager":
        return f"parameter({', '.join(parts)})"
    return f"fig.parameter({', '.join(parts)})"


def _plot_call(
    ps: PlotSnapshot | FieldPlotSnapshot,
    *,
    style: Literal["figure_methods", "context_manager"],
    figure_snapshot: FigureSnapshot | None = None,
) -> str:
    """Emit one plot or scalar-field call."""
    if getattr(ps, "is_field", False):
        expr_code = sympy_to_code(ps.func)
        x_arg = (
            f"({_symbol_ref(ps.x_var)}, {_fmt_float(ps.x_domain[0])}, {_fmt_float(ps.x_domain[1])})"
            if ps.x_domain is not None
            else _symbol_ref(ps.x_var)
        )
        y_arg = (
            f"({_symbol_ref(ps.y_var)}, {_fmt_float(ps.y_domain[0])}, {_fmt_float(ps.y_domain[1])})"
            if ps.y_domain is not None
            else _symbol_ref(ps.y_var)
        )
        if ps.preset == "temperature" and ps.render_mode == "heatmap":
            helper = "temperature"
        elif ps.render_mode == "contour":
            helper = "contour"
        else:
            helper = "density"
        callee = helper if style == "context_manager" else f"fig.{helper}"
        args = [expr_code, x_arg, y_arg, f"id={ps.id!r}", f"label={ps.label!r}"]
        if ps.visible is not True:
            args.append(f"visible={ps.visible!r}")
        if ps.grid is not None:
            args.append(f"grid={tuple(int(v) for v in ps.grid)!r}")
        if ps.colorscale is not None:
            args.append(f"colorscale={ps.colorscale!r}")
        if ps.z_range is not None:
            args.append(
                f"z_range=({_fmt_float(ps.z_range[0])}, {_fmt_float(ps.z_range[1])})"
            )
        if getattr(ps, "z_step", None) is not None:
            args.append(f"z_step={_fmt_float(ps.z_step)}")
        if getattr(ps, "under_color", None) is not None:
            args.append(f"under_color={ps.under_color!r}")
        if getattr(ps, "over_color", None) is not None:
            args.append(f"over_color={ps.over_color!r}")
        if ps.show_colorbar is not None:
            args.append(f"show_colorbar={ps.show_colorbar!r}")
        if ps.opacity is not None:
            args.append(f"opacity={_fmt_float(ps.opacity)}")
        if ps.reversescale:
            args.append("reversescale=True")
        if ps.colorbar is not None:
            args.append(f"colorbar={ps.colorbar!r}")
        if ps.trace is not None:
            args.append(f"trace={ps.trace!r}")
        if ps.render_mode == "contour":
            if ps.levels is not None:
                args.append(f"levels={int(ps.levels)}")
            if getattr(ps, "level_step", None) is not None:
                args.append(f"level_step={_fmt_float(ps.level_step)}")
            if getattr(ps, "level_start", None) is not None:
                args.append(f"level_start={_fmt_float(ps.level_start)}")
            if getattr(ps, "level_end", None) is not None:
                args.append(f"level_end={_fmt_float(ps.level_end)}")
            if ps.filled is not None:
                args.append(f"filled={ps.filled!r}")
            if ps.show_labels is not None:
                args.append(f"show_labels={ps.show_labels!r}")
            if ps.line_color is not None:
                args.append(f"line_color={ps.line_color!r}")
            if ps.line_width is not None:
                args.append(f"line_width={_fmt_float(ps.line_width)}")
            if getattr(ps, "line_dash", None) is not None:
                args.append(f"line_dash={ps.line_dash!r}")
        else:
            if ps.smoothing is not None:
                args.append(f"smoothing={ps.smoothing!r}")
        if ps.connectgaps is not None:
            args.append(f"connectgaps={ps.connectgaps!r}")
    elif ps.is_parametric:
        if ps.x_func is None or ps.parameter_domain is None:
            raise ValueError(
                "Parametric plot snapshots require x_func and parameter_domain metadata."
            )
        x_expr_code = sympy_to_code(ps.x_func)
        y_expr_code = sympy_to_code(ps.func)
        args = [
            f"({x_expr_code}, {y_expr_code})",
            (
                f"({_symbol_ref(ps.var)}, "
                f"{_fmt_float(ps.parameter_domain[0])}, "
                f"{_fmt_float(ps.parameter_domain[1])})"
            ),
            f"id={ps.id!r}",
            f"label={ps.label!r}",
        ]
        callee = (
            "parametric_plot" if style == "context_manager" else "fig.parametric_plot"
        )
        if ps.visible is not True:
            args.append(f"visible={ps.visible!r}")
        if ps.sampling_points is not None:
            args.append(f"samples={ps.sampling_points}")
        elif (
            figure_snapshot is not None
            and getattr(figure_snapshot, "default_samples", figure_snapshot.samples)
            != figure_snapshot.samples
        ):
            args.append("samples='figure_default'")
        if ps.color is not None:
            args.append(f"color={ps.color!r}")
        if ps.thickness is not None:
            args.append(f"thickness={_fmt_float(ps.thickness)}")
        if ps.dash is not None:
            args.append(f"dash={ps.dash!r}")
        if ps.opacity is not None:
            args.append(f"opacity={_fmt_float(ps.opacity)}")
        if getattr(ps, "autonormalization", False):
            args.append("autonormalization=True")
    else:
        expr_code = sympy_to_code(ps.func)
        args = [
            f"{expr_code}",
            f"{_symbol_ref(ps.var)}",
            f"id={ps.id!r}",
            f"label={ps.label!r}",
        ]
        if ps.x_domain is not None:
            args.append(
                f"x_domain=({_fmt_float(ps.x_domain[0])}, {_fmt_float(ps.x_domain[1])})"
            )
        callee = "plot" if style == "context_manager" else "fig.plot"
        if ps.visible is not True:
            args.append(f"visible={ps.visible!r}")
        if ps.sampling_points is not None:
            args.append(f"samples={ps.sampling_points}")
        elif (
            figure_snapshot is not None
            and getattr(figure_snapshot, "default_samples", figure_snapshot.samples)
            != figure_snapshot.samples
        ):
            args.append("samples='figure_default'")
        if ps.color is not None:
            args.append(f"color={ps.color!r}")
        if ps.thickness is not None:
            args.append(f"thickness={_fmt_float(ps.thickness)}")
        if ps.dash is not None:
            args.append(f"dash={ps.dash!r}")
        if ps.opacity is not None:
            args.append(f"opacity={_fmt_float(ps.opacity)}")
        if getattr(ps, "autonormalization", False):
            args.append("autonormalization=True")

    if getattr(ps, "views", ()):
        if len(ps.views) == 1:
            args.append(f"view={ps.views[0]!r}")
        else:
            args.append(f"view={tuple(ps.views)!r}")

    joined = ", ".join(args)
    call = f"{callee}({joined})"
    if len(call) <= 88:
        return call

    indent = "    "
    body = (",\n" + indent).join(args)
    return f"{callee}(\n{indent}{body},\n)"


def _info_card_lines(
    card: InfoCardSnapshot,
    *,
    style: Literal["figure_methods", "context_manager"],
    include_dynamic_comment_block: bool,
) -> list[str]:
    """Emit ``info(...)``/``fig.info(...)`` lines or dynamic info comments."""
    call = "info" if style == "context_manager" else "fig.info"
    has_dynamic = any(seg == "<dynamic>" for seg in card.segments)
    static_parts = [seg for seg in card.segments if seg != "<dynamic>"]

    view_suffix = f", view={card.view_id!r}" if card.view_id is not None else ""

    if has_dynamic:
        if not include_dynamic_comment_block:
            return ["# dynamic info omitted"]

        static_spec = (
            repr(static_parts[0]) if len(static_parts) == 1 else repr(static_parts)
        )
        suffix = f", id={card.id!r}" if card.id is not None else ""
        suffix += view_suffix
        lines = [
            f"# {call}({static_spec}{suffix})",
            "# NOTE: Dynamic info callable segments were omitted from this commented block.",
            "# NOTE: Define every callable referenced by this card in scope before enabling the line above.",
            "# import inspect",
            "# print(inspect.getsource(my_dynamic_func))",
        ]
        return lines

    if not static_parts:
        return []

    if len(static_parts) == 1:
        line = f"{call}({static_parts[0]!r}"
    else:
        parts_repr = ", ".join(repr(s) for s in static_parts)
        line = f"{call}([{parts_repr}]"

    if card.id is not None:
        line += f", id={card.id!r}"
    if card.view_id is not None:
        line += f", view={card.view_id!r}"
    line += ")"
    return [line]


def figure_to_code(
    snapshot: FigureSnapshot, options: CodegenOptions | None = None
) -> str:
    """Generate a self-contained Python script from a :class:`FigureSnapshot`.
    
    Full API
    --------
    ``figure_to_code(snapshot: FigureSnapshot, options: CodegenOptions | None=None) -> str``
    
    Parameters
    ----------
    snapshot : FigureSnapshot
        Snapshot object or snapshot payload used by this API. Required.
    
    options : CodegenOptions | None, optional
        Value for ``options`` in this API. Defaults to ``None``.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``options=None``: Value for ``options`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.codegen``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.codegen import figure_to_code
        result = figure_to_code(...)
    
    Discovery-oriented use::
    
        help(figure_to_code)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(figure_to_code)`` and inspect sibling APIs in the same module.
    """
    options = options or CodegenOptions()
    lines: list[str] = []

    # -- imports ------------------------------------------------------------
    if options.include_imports:
        lines.append("import sympy as sp")
        if options.interface_style == "context_manager":
            import_items = ["Figure", "parameter", "plot"]
            if _snapshot_uses_parametric_plot(snapshot):
                import_items.append("parametric_plot")
            import_items.extend(_snapshot_field_helpers(snapshot))
            import_items.append("info")
            lines.append("from gu_toolkit import " + ", ".join(import_items))
        else:
            lines.append("from gu_toolkit import Figure")
        lines.append("from IPython.display import display")
        lines.append("")

    # -- symbols ------------------------------------------------------------
    symbols = _collect_symbols(snapshot)
    if symbols and options.include_symbol_definitions:
        symbol_defs = _symbol_definitions(symbols)
        if symbol_defs:
            lines.append("# Symbols")
            lines.append(symbol_defs)
            lines.append("")

    # -- figure construction ------------------------------------------------
    lines.append("# Figure")
    main_view = _main_view_snapshot(snapshot)
    main_x_range = main_view.x_range if main_view is not None else snapshot.x_range
    main_y_range = main_view.y_range if main_view is not None else snapshot.y_range
    main_x_label = main_view.x_label if main_view is not None else ""
    main_y_label = main_view.y_label if main_view is not None else ""

    lines.append(
        "fig = Figure("
        f"title={snapshot.title!r}, "
        f"x_range=({_fmt_float(main_x_range[0])}, {_fmt_float(main_x_range[1])}), "
        f"y_range=({_fmt_float(main_y_range[0])}, {_fmt_float(main_y_range[1])}), "
        f"x_label={main_x_label!r}, y_label={main_y_label!r}, "
        f"samples={snapshot.samples})"
    )

    if getattr(snapshot, "default_x_range", main_x_range) != main_x_range:
        lines.append(
            f"fig.default_x_range = ({_fmt_float(snapshot.default_x_range[0])}, {_fmt_float(snapshot.default_x_range[1])})"
        )
    if getattr(snapshot, "default_y_range", main_y_range) != main_y_range:
        lines.append(
            f"fig.default_y_range = ({_fmt_float(snapshot.default_y_range[0])}, {_fmt_float(snapshot.default_y_range[1])})"
        )
    if getattr(snapshot, "default_samples", snapshot.samples) != snapshot.samples:
        lines.append(f"fig.default_samples = {snapshot.default_samples}")

    if main_view is not None and main_view.title != "main":
        lines.append(f"fig.views['main'].title = {main_view.title!r}")

    if getattr(snapshot, "views", ()):
        for view in snapshot.views:
            if view.id == "main":
                continue
            lines.append(
                "fig.add_view("
                f"{view.id!r}, title={view.title!r}, x_range=({_fmt_float(view.x_range[0])}, {_fmt_float(view.x_range[1])}), "
                f"y_range=({_fmt_float(view.y_range[0])}, {_fmt_float(view.y_range[1])}), "
                f"x_label={view.x_label!r}, y_label={view.y_label!r})"
            )

    for view in snapshot.views:
        if view.viewport_x_range is not None and view.viewport_x_range != view.x_range:
            lines.append(
                f"fig.views[{view.id!r}].current_x_range = "
                f"({_fmt_float(view.viewport_x_range[0])}, {_fmt_float(view.viewport_x_range[1])})"
            )
        if view.viewport_y_range is not None and view.viewport_y_range != view.y_range:
            lines.append(
                f"fig.views[{view.id!r}].current_y_range = "
                f"({_fmt_float(view.viewport_y_range[0])}, {_fmt_float(view.viewport_y_range[1])})"
            )

    if snapshot.active_view_id != "main":
        lines.append(f"fig.views.current_id = {snapshot.active_view_id!r}")

    lines.append("display(fig)")
    lines.append("")

    # -- operation body -----------------------------------------------------
    body_lines: list[str] = []

    if len(snapshot.parameters) > 0:
        body_lines.append("# Parameters")
        for sym, meta_view in snapshot.parameters.symbol_items():
            meta = dict(meta_view)
            body_lines.append(_parameter_call(sym, meta, style=options.interface_style))
        body_lines.append("")

    if snapshot.plots:
        body_lines.append("# Plots")
        for ps in snapshot.plots.values():
            body_lines.append(_plot_call(ps, style=options.interface_style, figure_snapshot=snapshot))
        body_lines.append("")

    info_lines: list[str] = []
    for card in snapshot.info_cards:
        info_lines.extend(
            _info_card_lines(
                card,
                style=options.interface_style,
                include_dynamic_comment_block=options.include_dynamic_info_as_commented_blocks,
            )
        )
    if info_lines:
        body_lines.append("# Info")
        body_lines.extend(info_lines)
        body_lines.append("")

    if options.interface_style == "context_manager":
        lines.append("with fig:")
        if not body_lines:
            lines.append("    pass")
            lines.append("")
        else:
            for line in body_lines:
                if not line:
                    lines.append("")
                else:
                    lines.append(f"    {line}")
    else:
        lines.extend(body_lines)

    return "\n".join(lines)
