"""Interactive plot-composer dialog used by the legend sidebar.

Purpose
-------
This module owns the notebook UI that lets users create and edit plots directly
from the legend area. The dialog is intentionally figure-centric: it reads the
current figure's views, infers parameters from entered expressions, and routes
successful submissions back through the existing public plotting methods.

Supported plot families
-----------------------
The composer currently supports five manual modes:

- cartesian curves ``y = f(x)``
- parametric curves ``(x(t), y(t))``
- contour plots ``z = f(x, y)``
- density plots (generic heatmaps)
- temperature plots (heatmaps with thermal defaults)

Architecture
------------
The module is split into two small layers:

- immutable :class:`PlotEditorDraft` values capture the form state in a
  testable, backend-friendly shape;
- :class:`PlotComposerDialog` manages widgets, validation messaging, and modal
  lifecycle.

The dialog deliberately avoids bypassing the public plotting API. Even editor-
created plots are applied through :meth:`Figure.plot`,
:meth:`Figure.parametric_plot`, :meth:`Figure.contour`,
:meth:`Figure.density`, and :meth:`Figure.temperature` so snapshotting,
codegen, legend updates, parameter inference, and render scheduling all stay
on the existing code paths.

Discoverability
---------------
See :mod:`gu_toolkit.figure_legend` for the toolbar/buttons that launch the
composer and :mod:`gu_toolkit._mathlive_widget` for the MathLive field wrapper.
"""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from ._mathlive_widget import MathLiveField
from ._widget_stubs import widgets
from .figure_color import color_for_trace_index, color_to_picker_hex
from .figure_field import ScalarFieldPlot
from .figure_parametric_plot import ParametricPlot
from .figure_plot import Plot
from .parameter_keys import parameter_name
from .ParseLaTeX import LatexParseError, parse_latex
from .widget_chrome import (
    ModalDialogBridge,
    TabListBridge,
    attach_host_children,
    build_action_bar,
    build_boolean_field,
    build_dialog_header,
    build_form_section,
    build_inline_alert,
    build_modal_overlay,
    build_modal_panel,
    build_readonly_value,
    build_tab_bar,
    configure_action_button,
    configure_control,
    configure_icon_button,
    full_width_layout,
    hosted_modal_dimensions,
    labelled_field,
    load_ui_css,
    responsive_row,
    set_tab_button_selected,
    set_widget_class_state,
    shared_style_widget,
    vbox,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .Figure import Figure


_PLOT_EDITOR_LOCAL_CSS = load_ui_css("plot_editor.css")


PlotEditorKind = Literal[
    "cartesian",
    "parametric",
    "contour",
    "density",
    "temperature",
]

PlotEditorTab = Literal[
    "expression",
    "style",
    "advanced",
]


_CURVE_DASH_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Solid", "solid"),
    ("Dot", "dot"),
    ("Dash", "dash"),
    ("Dash-dot", "dashdot"),
    ("Long dash", "longdash"),
    ("Long dash-dot", "longdashdot"),
)


@dataclass(frozen=True)
class PlotEditorDraft:
    """Detached snapshot of the plot-composer form state.
    
    Full API
    --------
    ``PlotEditorDraft(kind: PlotEditorKind, plot_id: str | None, label: str, view_ids: tuple[str, Ellipsis], cartesian_expression_latex: str, cartesian_var_latex: str, cartesian_samples: int, parametric_x_latex: str, parametric_y_latex: str, parameter_var_latex: str, parameter_min_latex: str, parameter_max_latex: str, parametric_samples: int, field_expression_latex: str, field_x_var_latex: str, field_y_var_latex: str, field_grid_x: int, field_grid_y: int, visible: bool=True, curve_color: str | None=None, curve_thickness: float | None=None, curve_opacity: float | None=None, curve_dash: str | None=None, curve_autonormalization: bool | None=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    kind : PlotEditorKind
        Value for ``kind`` in this API. Required.
    
    plot_id : str | None
        Stable plot identifier used for lookup or update. Required.
    
    label : str
        Human-readable label used in UI or plotting output. Required.
    
    view_ids : tuple[str, Ellipsis]
        Collection of view identifiers associated with this object or update. Required.
    
    cartesian_expression_latex : str
        Value for ``cartesian_expression_latex`` in this API. Required.
    
    cartesian_var_latex : str
        Value for ``cartesian_var_latex`` in this API. Required.
    
    cartesian_samples : int
        Value for ``cartesian_samples`` in this API. Required.
    
    parametric_x_latex : str
        Value for ``parametric_x_latex`` in this API. Required.
    
    parametric_y_latex : str
        Value for ``parametric_y_latex`` in this API. Required.
    
    parameter_var_latex : str
        Value for ``parameter_var_latex`` in this API. Required.
    
    parameter_min_latex : str
        Value for ``parameter_min_latex`` in this API. Required.
    
    parameter_max_latex : str
        Value for ``parameter_max_latex`` in this API. Required.
    
    parametric_samples : int
        Value for ``parametric_samples`` in this API. Required.
    
    field_expression_latex : str
        Value for ``field_expression_latex`` in this API. Required.
    
    field_x_var_latex : str
        Value for ``field_x_var_latex`` in this API. Required.
    
    field_y_var_latex : str
        Value for ``field_y_var_latex`` in this API. Required.
    
    field_grid_x : int
        Value for ``field_grid_x`` in this API. Required.
    
    field_grid_y : int
        Value for ``field_grid_y`` in this API. Required.
    
    visible : bool, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    curve_color : str | None, optional
        Value for ``curve_color`` in this API. Defaults to ``None``.
    
    curve_thickness : float | None, optional
        Value for ``curve_thickness`` in this API. Defaults to ``None``.
    
    curve_opacity : float | None, optional
        Value for ``curve_opacity`` in this API. Defaults to ``None``.
    
    curve_dash : str | None, optional
        Value for ``curve_dash`` in this API. Defaults to ``None``.
    
    curve_autonormalization : bool | None, optional
        Value for ``curve_autonormalization`` in this API. Defaults to ``None``.
    
    Returns
    -------
    PlotEditorDraft
        New ``PlotEditorDraft`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``curve_color=None``: Value for ``curve_color`` in this API.
    - ``curve_thickness=None``: Value for ``curve_thickness`` in this API.
    - ``curve_opacity=None``: Value for ``curve_opacity`` in this API.
    - ``curve_dash=None``: Value for ``curve_dash`` in this API.
    - ``curve_autonormalization=None``: Value for ``curve_autonormalization`` in this API.
    
    Architecture note
    -----------------
    ``PlotEditorDraft`` lives in ``gu_toolkit.figure_plot_editor``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot_editor import PlotEditorDraft
        obj = PlotEditorDraft(...)
    
    Discovery-oriented use::
    
        help(PlotEditorDraft)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(PlotEditorDraft)`` and ``dir(PlotEditorDraft)`` to inspect adjacent members.
    """

    kind: PlotEditorKind
    plot_id: str | None
    label: str
    view_ids: tuple[str, ...]
    cartesian_expression_latex: str
    cartesian_var_latex: str
    cartesian_samples: int
    parametric_x_latex: str
    parametric_y_latex: str
    parameter_var_latex: str
    parameter_min_latex: str
    parameter_max_latex: str
    parametric_samples: int
    field_expression_latex: str
    field_x_var_latex: str
    field_y_var_latex: str
    field_grid_x: int
    field_grid_y: int
    visible: bool = True
    curve_color: str | None = None
    curve_thickness: float | None = None
    curve_opacity: float | None = None
    curve_dash: str | None = None
    curve_autonormalization: bool | None = None


@dataclass(frozen=True)
class ParameterPreview:
    """Parameter-inference summary shown in the composer dialog.
    
    Full API
    --------
    ``ParameterPreview(will_create: tuple[str, Ellipsis], will_reuse: tuple[str, Ellipsis], error: str | None=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    will_create : tuple[str, Ellipsis]
        Value for ``will_create`` in this API. Required.
    
    will_reuse : tuple[str, Ellipsis]
        Value for ``will_reuse`` in this API. Required.
    
    error : str | None, optional
        Value for ``error`` in this API. Defaults to ``None``.
    
    Returns
    -------
    ParameterPreview
        New ``ParameterPreview`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``error=None``: Value for ``error`` in this API.
    
    Architecture note
    -----------------
    ``ParameterPreview`` lives in ``gu_toolkit.figure_plot_editor``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot_editor import ParameterPreview
        obj = ParameterPreview(...)
    
    Discovery-oriented use::
    
        help(ParameterPreview)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(ParameterPreview)`` and ``dir(ParameterPreview)`` to inspect adjacent members.
    """

    will_create: tuple[str, ...]
    will_reuse: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True)
class CurveStyleBaseline:
    """Effective style values shown by the plot-editor style tab.
    
    Full API
    --------
    ``CurveStyleBaseline(picker_color: str, thickness: float, opacity: float, dash: str, autonormalization: bool)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    picker_color : str
        Value for ``picker_color`` in this API. Required.
    
    thickness : float
        Value for ``thickness`` in this API. Required.
    
    opacity : float
        Opacity value applied to the rendered output. Required.
    
    dash : str
        Dash pattern used for contour or curve rendering. Required.
    
    autonormalization : bool
        Value for ``autonormalization`` in this API. Required.
    
    Returns
    -------
    CurveStyleBaseline
        New ``CurveStyleBaseline`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``CurveStyleBaseline`` lives in ``gu_toolkit.figure_plot_editor``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot_editor import CurveStyleBaseline
        obj = CurveStyleBaseline(...)
    
    Discovery-oriented use::
    
        help(CurveStyleBaseline)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(CurveStyleBaseline)`` and ``dir(CurveStyleBaseline)`` to inspect adjacent members.
    """

    picker_color: str
    thickness: float
    opacity: float
    dash: str
    autonormalization: bool



_PARSE_EXPR_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)
_LATEXISH_NAME_MAP: tuple[tuple[str, str], ...] = (
    (r"\alpha", "alpha"),
    (r"\beta", "beta"),
    (r"\gamma", "gamma"),
    (r"\delta", "delta"),
    (r"\epsilon", "epsilon"),
    (r"\varepsilon", "varepsilon"),
    (r"\theta", "theta"),
    (r"\vartheta", "vartheta"),
    (r"\lambda", "lambda"),
    (r"\mu", "mu"),
    (r"\nu", "nu"),
    (r"\phi", "phi"),
    (r"\varphi", "varphi"),
    (r"\psi", "psi"),
    (r"\omega", "omega"),
    (r"\rho", "rho"),
    (r"\sigma", "sigma"),
    (r"\tau", "tau"),
    (r"\pi", "pi"),
    (r"\sinh", "sinh"),
    (r"\cosh", "cosh"),
    (r"\tanh", "tanh"),
    (r"\sin", "sin"),
    (r"\cos", "cos"),
    (r"\tan", "tan"),
    (r"\cot", "cot"),
    (r"\sec", "sec"),
    (r"\csc", "csc"),
    (r"\log", "log"),
    (r"\ln", "log"),
    (r"\exp", "exp"),
)


def _extract_braced_group(text: str, start: int) -> tuple[str, int]:
    """Return the braced group that starts at ``start`` and the next index."""

    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected '{' while parsing LaTeX input.")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise ValueError("Unbalanced braces in LaTeX input.")


def _rewrite_group_command(text: str, command: str, *, arity: int) -> str:
    r"""Rewrite simple LaTeX group commands such as ``\frac`` and ``\sqrt``."""

    result: list[str] = []
    index = 0
    while index < len(text):
        if not text.startswith(command, index):
            result.append(text[index])
            index += 1
            continue

        cursor = index + len(command)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1

        groups: list[str] = []
        try:
            for _ in range(arity):
                group_text, cursor = _extract_braced_group(text, cursor)
                groups.append(_normalize_latexish_text(group_text))
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
        except ValueError:
            result.append(text[index])
            index += 1
            continue

        if command == r"\frac":
            result.append(f"(({groups[0]})/({groups[1]}))")
        elif command == r"\sqrt":
            result.append(f"sqrt({groups[0]})")
        else:  # pragma: no cover - defensive fallback
            result.append(" ".join(groups))
        index = cursor
    return "".join(result)


def _normalize_latexish_text(value: str) -> str:
    r"""Convert common MathLive/LaTeX-ish text into ``parse_expr`` input.

    The editor first tries the toolkit's dedicated LaTeX parser. This fallback
    exists for environments where that parser backend is unavailable or where
    MathLive emits lightweight LaTeX fragments such as ``2\pi`` or
    ``a\cos(t)`` that still map cleanly to SymPy syntax.
    """

    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace(r"\left", "").replace(r"\right", "")
    text = text.replace(r"\cdot", " * ").replace(r"\times", " * ").replace("·", " * ")
    text = _rewrite_group_command(text, r"\frac", arity=2)
    text = _rewrite_group_command(text, r"\sqrt", arity=1)
    for source, target in _LATEXISH_NAME_MAP:
        text = text.replace(source, f" {target}")
    text = text.replace("{", "(").replace("}", ")")
    text = re.sub(r"\\,|\\;|\\!|\\quad|\\qquad", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_plain_math_text(text: str) -> Expr:
    """Parse plain or lightly normalized mathematical text into SymPy."""

    parsed = parse_expr(
        text,
        transformations=_PARSE_EXPR_TRANSFORMS,
        evaluate=True,
    )
    if not isinstance(parsed, Expr):
        raise ValueError("Parsed value is not a SymPy expression.")
    return parsed


def _latex_to_expression(value: str, *, role: str) -> Expr:
    r"""Parse one MathLive/LaTeX field into a SymPy expression.

    Parsing first uses the toolkit's resilient LaTeX parser and then falls back
    to a lightweight MathLive/LaTeX normalizer plus :func:`parse_expr`. This
    keeps the editor usable even when users paste non-LaTeX expressions such as
    ``a*x + 1`` or lightweight MathLive output such as ``2\pi``.
    """

    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{role} is required.")

    latex_error: Exception | None = None
    try:
        parsed = parse_latex(text)
        if isinstance(parsed, Expr):
            return parsed
    except (LatexParseError, TypeError, ValueError, SyntaxError) as exc:
        latex_error = exc
    except Exception as exc:  # pragma: no cover - defensive parser guard
        latex_error = exc

    parse_errors: list[Exception] = []
    candidates = []
    normalized = _normalize_latexish_text(text)
    if normalized:
        candidates.append(normalized)
    if text not in candidates:
        candidates.append(text)

    for candidate in candidates:
        try:
            return _parse_plain_math_text(candidate)
        except Exception as exc:
            parse_errors.append(exc)

    detail = f" LaTeX parser error: {latex_error}" if latex_error is not None else ""
    if parse_errors:
        detail += f" Plain-text parser error: {parse_errors[-1]}"
    raise ValueError(f"Could not parse {role}.{detail}")


def _latex_to_symbol(value: str, *, role: str, default_latex: str | None = None) -> Symbol:
    """Parse a symbol-entry field and ensure it resolves to exactly one symbol."""

    source = str(value or "").strip() or str(default_latex or "").strip()
    if not source:
        raise ValueError(f"{role} is required.")
    parsed = _latex_to_expression(source, role=role)
    if not isinstance(parsed, Symbol):
        raise ValueError(f"{role} must be a single symbol, got {parsed!r}.")
    return parsed


def _to_latex(value: Any, *, default: str = "") -> str:
    """Serialize a symbolic or numeric value into LaTeX for editor fields."""

    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or default
    try:
        return sp.latex(sp.sympify(value))
    except Exception:
        text = str(value)
        return text if text else default


def _title_symbol_latex(value: str, *, default: str) -> str:
    """Return the compact LaTeX symbol string shown in responsive field titles."""

    source = str(value or "").strip()
    return source or default


def _parametric_axis_title_latex(axis_name: str, parameter_latex: str) -> str:
    """Return the compact label shown above ``x(t)``/``y(t)`` inputs."""

    parameter = _title_symbol_latex(parameter_latex, default="t")
    return rf"{axis_name}\left({parameter}\right)"


def _parametric_bound_title_latex(parameter_latex: str, *, bound: Literal["min", "max"]) -> str:
    """Return the compact label shown above parameter bound inputs."""

    parameter = _title_symbol_latex(parameter_latex, default="t")
    return rf"{parameter}_{{\mathrm{{{bound}}}}}"


def _mathjax_inline(latex: str) -> str:
    """Wrap one LaTeX fragment for inline MathJax rendering."""

    text = str(latex or "").strip()
    if not text:
        return ""
    return rf"\({text}\)"


def _math_field_label(latex: str) -> widgets.HTMLMath:
    """Return one MathJax-backed form label styled like the shared text labels."""

    label = widgets.HTMLMath(
        value=_mathjax_inline(latex),
        layout=widgets.Layout(margin="0px", min_width="0"),
    )
    label.add_class("gu-form-field-label")
    return label


def _safe_attr_text(value: Any) -> str:
    """Return ``value`` as a stripped text string when possible."""

    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _reference_trace_handle(plot: Any) -> Any:
    """Return a representative Plotly trace handle for ``plot`` when available."""

    getter = getattr(plot, "_reference_trace_handle", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            return None
    return None


def _trace_handle_line_color(trace_handle: Any) -> str:
    """Return an explicit line or marker color from one Plotly trace handle."""

    line_obj = getattr(trace_handle, "line", None)
    line_color = _safe_attr_text(getattr(line_obj, "color", None))
    if line_color:
        return line_color
    marker_obj = getattr(trace_handle, "marker", None)
    marker_color = _safe_attr_text(getattr(marker_obj, "color", None))
    return marker_color


def _trace_handle_colorway_fallback(trace_handle: Any) -> str:
    """Infer a default Plotly colorway entry for one existing trace handle."""

    parent = getattr(trace_handle, "_parent", None)
    traces = tuple(getattr(parent, "data", ())) if parent is not None else ()
    if not traces:
        return ""
    try:
        trace_index = traces.index(trace_handle)
    except ValueError:
        return ""
    return color_for_trace_index(parent, trace_index, fallback="")


def _next_auto_curve_color(figure: Figure) -> str:
    """Return the next color the active view would typically assign to a curve."""

    active_view = figure.views[figure.views.current_id]
    figure_widget = active_view.figure_widget
    return color_for_trace_index(
        figure_widget,
        len(tuple(getattr(figure_widget, "data", ()))),
        fallback="#636efa",
    )


def _plot_autonormalization_enabled(plot: Any) -> bool:
    """Return the current per-plot sound auto-normalization flag."""

    handler = getattr(plot, "autonormalization", None)
    if callable(handler):
        try:
            return bool(handler())
        except Exception:
            return False
    return bool(getattr(plot, "_sound_autonormalization", False))


def _curve_style_baseline_for_plot(plot: Any, *, figure: Figure | None = None) -> CurveStyleBaseline:
    """Return the effective curve style values shown in the style tab."""

    current_color = _safe_attr_text(getattr(plot, "color", None))
    if not current_color:
        trace_handle = _reference_trace_handle(plot)
        if trace_handle is not None:
            current_color = _trace_handle_line_color(trace_handle) or _trace_handle_colorway_fallback(trace_handle)
    if not current_color and figure is not None:
        current_color = _next_auto_curve_color(figure)

    raw_thickness = getattr(plot, "thickness", None)
    thickness = 2.0 if raw_thickness is None else float(raw_thickness)
    raw_opacity = getattr(plot, "opacity", None)
    opacity = 1.0 if raw_opacity is None else float(raw_opacity)
    raw_dash = _safe_attr_text(getattr(plot, "dash", None)) or "solid"
    allowed_dashes = {value for _label, value in _CURVE_DASH_STYLE_OPTIONS}
    dash = raw_dash if raw_dash in allowed_dashes else "solid"

    return CurveStyleBaseline(
        picker_color=color_to_picker_hex(current_color or "#636efa", fallback="#636efa"),
        thickness=thickness,
        opacity=opacity,
        dash=dash,
        autonormalization=_plot_autonormalization_enabled(plot),
    )


def _sorted_unique_names(symbols: set[Symbol]) -> tuple[str, ...]:
    """Return canonical parameter names in a stable, user-friendly order."""

    return tuple(sorted({parameter_name(symbol) for symbol in symbols}))


def _infer_draft_parameter_symbols(draft: PlotEditorDraft) -> set[Symbol]:
    """Return parameter-like free symbols implied by one editor draft.

    The helper mirrors the public plotting APIs while filling in one important
    gap: parametric range bounds can also contain symbols (for example
    ``(t, 0, 2*pi*a)``), so the editor includes those symbols in the inferred
    parameter set too.
    """

    excluded: set[Symbol]
    expressions: list[Expr]
    if draft.kind == "cartesian":
        expressions = [
            _latex_to_expression(
                draft.cartesian_expression_latex,
                role="Cartesian expression",
            )
        ]
        excluded = {
            _latex_to_symbol(
                draft.cartesian_var_latex,
                role="Cartesian free variable",
                default_latex="x",
            )
        }
    elif draft.kind == "parametric":
        excluded = {
            _latex_to_symbol(
                draft.parameter_var_latex,
                role="Parametric parameter",
                default_latex="t",
            )
        }
        parameter_min = _latex_to_expression(
            draft.parameter_min_latex,
            role="Parameter minimum",
        )
        parameter_max = _latex_to_expression(
            draft.parameter_max_latex,
            role="Parameter maximum",
        )
        bound_symbols = (set(parameter_min.free_symbols) | set(parameter_max.free_symbols)) - excluded
        if bound_symbols:
            names = ", ".join(_sorted_unique_names(bound_symbols))
            raise ValueError(
                "Parametric parameter bounds must currently be numeric; "
                f"symbolic bounds are not supported yet ({names})."
            )
        expressions = [
            _latex_to_expression(draft.parametric_x_latex, role="Parametric x(t)"),
            _latex_to_expression(draft.parametric_y_latex, role="Parametric y(t)"),
        ]
    else:
        expressions = [
            _latex_to_expression(
                draft.field_expression_latex,
                role="Scalar-field expression",
            )
        ]
        excluded = {
            _latex_to_symbol(
                draft.field_x_var_latex,
                role="Field x variable",
                default_latex="x",
            ),
            _latex_to_symbol(
                draft.field_y_var_latex,
                role="Field y variable",
                default_latex="y",
            ),
        }

    parameter_symbols: set[Symbol] = set()
    for expression in expressions:
        parameter_symbols.update(set(expression.free_symbols) - excluded)
    return parameter_symbols


def _draft_parameter_preview(figure: Figure, draft: PlotEditorDraft) -> ParameterPreview:
    """Infer which parameter symbols the draft would create or reuse."""

    try:
        names = _sorted_unique_names(_infer_draft_parameter_symbols(draft))
        if not names:
            return ParameterPreview((), ())
        existing_names = set(figure.parameters.keys())
        will_reuse = tuple(name for name in names if name in existing_names)
        will_create = tuple(name for name in names if name not in existing_names)
        return ParameterPreview(will_create=will_create, will_reuse=will_reuse)
    except ValueError as exc:
        return ParameterPreview((), (), error=str(exc))


def apply_plot_editor_draft(
    figure: Figure,
    draft: PlotEditorDraft,
    *,
    existing_plot: Any | None = None,
) -> Any:
    """Apply one validated editor draft through the public figure API.
    
    Full API
    --------
    ``apply_plot_editor_draft(figure: Figure, draft: PlotEditorDraft, *, existing_plot: Any | None=None) -> Any``
    
    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    
    draft : PlotEditorDraft
        Value for ``draft`` in this API. Required.
    
    existing_plot : Any | None, optional
        Value for ``existing_plot`` in this API. Defaults to ``None``.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``existing_plot=None``: Value for ``existing_plot`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_editor``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_editor import apply_plot_editor_draft
        result = apply_plot_editor_draft(...)
    
    Discovery-oriented use::
    
        help(apply_plot_editor_draft)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(apply_plot_editor_draft)`` and inspect sibling APIs in the same module.
    """

    plot_id = draft.plot_id or getattr(existing_plot, "id", None)
    if draft.view_ids:
        view_arg: str | tuple[str, ...] = (
            draft.view_ids[0] if len(draft.view_ids) == 1 else draft.view_ids
        )
    else:
        view_arg = figure.views.current_id

    is_edit = existing_plot is not None
    label_arg = draft.label if is_edit else (draft.label.strip() or None)
    common_kwargs: dict[str, Any] = {
        "id": plot_id,
        "label": label_arg,
        "view": view_arg,
        "visible": bool(draft.visible),
    }
    curve_style_kwargs: dict[str, Any] = {}
    if draft.curve_color is not None:
        curve_style_kwargs["color"] = draft.curve_color
    if draft.curve_thickness is not None:
        curve_style_kwargs["thickness"] = float(draft.curve_thickness)
    if draft.curve_opacity is not None:
        curve_style_kwargs["opacity"] = float(draft.curve_opacity)
    if draft.curve_dash is not None:
        curve_style_kwargs["dash"] = draft.curve_dash
    if draft.curve_autonormalization is not None:
        curve_style_kwargs["autonormalization"] = bool(draft.curve_autonormalization)

    if draft.kind == "cartesian":
        expression = _latex_to_expression(
            draft.cartesian_expression_latex,
            role="Cartesian expression",
        )
        variable = _latex_to_symbol(
            draft.cartesian_var_latex,
            role="Cartesian free variable",
            default_latex="x",
        )
        return figure.plot(
            expression,
            variable,
            samples=int(draft.cartesian_samples),
            **common_kwargs,
            **curve_style_kwargs,
        )

    if draft.kind == "parametric":
        x_expression = _latex_to_expression(draft.parametric_x_latex, role="Parametric x(t)")
        y_expression = _latex_to_expression(draft.parametric_y_latex, role="Parametric y(t)")
        parameter_var = _latex_to_symbol(
            draft.parameter_var_latex,
            role="Parametric parameter",
            default_latex="t",
        )
        parameter_min = _latex_to_expression(draft.parameter_min_latex, role="Parameter minimum")
        parameter_max = _latex_to_expression(draft.parameter_max_latex, role="Parameter maximum")
        parameter_symbols = tuple(
            sp.Symbol(name) for name in _sorted_unique_names(_infer_draft_parameter_symbols(draft))
        )
        return figure.parametric_plot(
            (x_expression, y_expression),
            (parameter_var, parameter_min, parameter_max),
            parameters=parameter_symbols or None,
            samples=int(draft.parametric_samples),
            **common_kwargs,
            **curve_style_kwargs,
        )

    field_expression = _latex_to_expression(
        draft.field_expression_latex,
        role="Scalar-field expression",
    )
    x_variable = _latex_to_symbol(
        draft.field_x_var_latex,
        role="Field x variable",
        default_latex="x",
    )
    y_variable = _latex_to_symbol(
        draft.field_y_var_latex,
        role="Field y variable",
        default_latex="y",
    )
    grid = (int(draft.field_grid_x), int(draft.field_grid_y))

    if draft.kind == "contour":
        return figure.contour(field_expression, x_variable, y_variable, grid=grid, **common_kwargs)
    if draft.kind == "temperature":
        return figure.temperature(field_expression, x_variable, y_variable, grid=grid, **common_kwargs)
    if draft.kind == "density":
        return figure.density(field_expression, x_variable, y_variable, grid=grid, **common_kwargs)
    raise ValueError(f"Unsupported plot editor kind: {draft.kind!r}")


class PlotComposerDialog:
    """Modal editor for creating and editing figure plots from the legend.
    
    Full API
    --------
    ``PlotComposerDialog(figure: Figure, modal_host: widgets.Box)``
    
    Public members exposed from this class: ``panel_visible``, ``open_for_new``, ``open_for_plot``, ``close``
    
    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    
    modal_host : widgets.Box
        Value for ``modal_host`` in this API. Required.
    
    Returns
    -------
    PlotComposerDialog
        New ``PlotComposerDialog`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``PlotComposerDialog`` lives in ``gu_toolkit.figure_plot_editor``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot_editor import PlotComposerDialog
        obj = PlotComposerDialog(...)
    
    Discovery-oriented use::
    
        help(PlotComposerDialog)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(PlotComposerDialog)`` and ``dir(PlotComposerDialog)`` to inspect adjacent members.
    """

    def __init__(self, figure: Figure, *, modal_host: widgets.Box) -> None:
        self._figure = figure
        self._modal_host = modal_host
        self._editing_plot_id: str | None = None
        self._is_open = False
        self._error_open = False
        self._suspend_observers = False
        self._active_tab: PlotEditorTab = "expression"
        self._tab_sync_lock = False
        self._modal_class = f"gu-plot-editor-modal-{uuid.uuid4().hex[:8]}"
        self._error_modal_class = f"{self._modal_class}-error"

        self._style = shared_style_widget(_PLOT_EDITOR_LOCAL_CSS, include_base=False)

        self._kind = widgets.Dropdown(
            options=(
                ("Function y = f(x)", "cartesian"),
                ("Parametric (x(t), y(t))", "parametric"),
                ("Contour z = f(x, y)", "contour"),
                ("Density heatmap", "density"),
                ("Temperature heatmap", "temperature"),
            ),
            value="cartesian",
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._kind, family="dropdown")
        self._id_text = widgets.Text(
            description="",
            placeholder="Auto",
            layout=full_width_layout(),
        )
        configure_control(self._id_text, family="text")
        self._label_text = widgets.Text(
            description="",
            placeholder="Legend label",
            layout=full_width_layout(),
        )
        configure_control(self._label_text, family="text")
        self._views = widgets.SelectMultiple(
            description="",
            options=(),
            value=(),
            layout=widgets.Layout(width="100%", min_width="0", max_width="100%", min_height="96px"),
        )
        configure_control(self._views, family="targets")
        self._visible_toggle = widgets.Checkbox(
            value=True,
            description="Visible",
            indent=False,
            layout=widgets.Layout(width="auto", min_width="0"),
        )
        configure_control(self._visible_toggle, family="checkbox")

        self._cartesian_expression = MathLiveField(
            placeholder=r"x^2 + a x + b",
            aria_label="Cartesian expression",
        )
        self._cartesian_variable = MathLiveField(
            value="x",
            placeholder="x",
            aria_label="Cartesian variable",
        )
        self._cartesian_samples = widgets.BoundedIntText(
            min=2,
            max=100000,
            value=max(int(self._figure.samples or 500), 2),
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._cartesian_samples, family="numeric")

        self._parametric_x = MathLiveField(
            placeholder=r"\cos(t)",
            aria_label="Parametric x(t)",
        )
        self._parametric_y = MathLiveField(
            placeholder=r"\sin(t)",
            aria_label="Parametric y(t)",
        )
        self._parameter_variable = MathLiveField(
            value="t",
            placeholder="t",
            aria_label="Parametric parameter",
        )
        self._parameter_min = MathLiveField(
            value="0",
            placeholder="0",
            aria_label="Parametric parameter minimum",
        )
        self._parameter_max = MathLiveField(
            value=r"2\pi",
            placeholder=r"2\pi",
            aria_label="Parametric parameter maximum",
        )
        self._parametric_samples = widgets.BoundedIntText(
            min=2,
            max=100000,
            value=max(int(self._figure.samples or 500), 2),
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._parametric_samples, family="numeric")

        self._field_expression = MathLiveField(
            placeholder=r"x^2 + y^2",
            aria_label="Scalar-field expression",
        )
        self._field_x_variable = MathLiveField(
            value="x",
            placeholder="x",
            aria_label="Scalar-field x variable",
        )
        self._field_y_variable = MathLiveField(
            value="y",
            placeholder="y",
            aria_label="Scalar-field y variable",
        )
        self._field_grid_x = widgets.BoundedIntText(
            min=2,
            max=10000,
            value=120,
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._field_grid_x, family="numeric")
        self._field_grid_y = widgets.BoundedIntText(
            min=2,
            max=10000,
            value=120,
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._field_grid_y, family="numeric")

        self._title = widgets.HTML(
            "Plot editor",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._title.add_class("gu-modal-title-text")
        self._title_context = widgets.HTML(
            "",
            layout=widgets.Layout(display="none", margin="0px", min_width="0"),
        )
        self._title_context.add_class("gu-modal-title-context")
        self._title_chip = self._title_context

        self._curve_style_color = widgets.ColorPicker(
            value="#636efa",
            description="",
            concise=True,
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        configure_control(self._curve_style_color, family="color")
        self._curve_style_thickness = widgets.BoundedFloatText(
            value=2.0,
            min=0.0,
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._curve_style_thickness, family="numeric")
        self._curve_style_opacity = widgets.BoundedFloatText(
            value=1.0,
            min=0.0,
            max=1.0,
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._curve_style_opacity, family="numeric")
        self._curve_style_dash = widgets.Dropdown(
            options=_CURVE_DASH_STYLE_OPTIONS,
            value="solid",
            description="",
            layout=full_width_layout(),
        )
        configure_control(self._curve_style_dash, family="dropdown")
        self._curve_style_autonormalization = widgets.Checkbox(
            value=False,
            description="Auto-normalize sound",
            indent=False,
            tooltip="Automatically scale louder sound chunks into [-1, 1]",
            layout=widgets.Layout(width="auto", min_width="0"),
        )
        configure_control(
            self._curve_style_autonormalization,
            family="checkbox",
            extra_classes=("gu-plot-editor-curve-autonormalization-control",),
        )
        self._curve_style_baseline = CurveStyleBaseline(
            picker_color="#636efa",
            thickness=2.0,
            opacity=1.0,
            dash="solid",
            autonormalization=False,
        )

        self._close_button = widgets.Button(
            description="Close plot editor",
            tooltip="Close plot editor",
        )
        configure_icon_button(
            self._close_button,
            role="close",
            size_px=28,
            extra_classes=("gu-plot-editor-close-button",),
        )
        self._close_button.on_click(lambda _button: self.close())

        self._expression_tab_button = widgets.Button(
            description="Expression",
            tooltip="Show expression fields",
            layout=widgets.Layout(flex="1 1 0", width="auto", min_width="0"),
        )
        configure_action_button(
            self._expression_tab_button,
            variant="tab",
            min_width_px=0,
            extra_classes=("gu-plot-editor-tab-button",),
        )
        self._expression_tab_button.on_click(lambda _button: self._set_tab("expression"))

        self._style_tab_button = widgets.Button(
            description="Style",
            tooltip="Show plot style fields",
            layout=widgets.Layout(flex="1 1 0", width="auto", min_width="0"),
        )
        configure_action_button(
            self._style_tab_button,
            variant="tab",
            min_width_px=0,
            extra_classes=("gu-plot-editor-tab-button",),
        )
        self._style_tab_button.on_click(lambda _button: self._set_tab("style"))

        self._settings_tab_button = widgets.Button(
            description="Advanced",
            tooltip="Show advanced plot settings",
            layout=widgets.Layout(flex="1 1 0", width="auto", min_width="0"),
        )
        configure_action_button(
            self._settings_tab_button,
            variant="tab",
            min_width_px=0,
            extra_classes=("gu-plot-editor-tab-button",),
        )
        self._settings_tab_button.on_click(lambda _button: self._set_tab("advanced"))

        self._cancel_button = widgets.Button(
            description="Cancel",
            tooltip="Discard plot editor changes",
        )
        configure_action_button(self._cancel_button, variant="secondary", min_width_px=88)
        self._cancel_button.on_click(lambda _button: self.close())

        self._apply_button = widgets.Button(
            description="Create",
            tooltip="Create the plot from the entered expressions",
        )
        configure_action_button(self._apply_button, variant="primary", min_width_px=96)
        self._apply_button.on_click(self._on_apply_clicked)

        self._error_message = widgets.HTML("", layout=full_width_layout())
        self._expression_alert = build_inline_alert(
            display="none",
            extra_classes=("gu-plot-editor-expression-alert",),
        )
        self._style_alert = build_inline_alert(
            display="none",
            extra_classes=("gu-plot-editor-style-alert",),
        )
        self._settings_alert = build_inline_alert(
            display="none",
            extra_classes=("gu-plot-editor-settings-alert",),
        )
        self._advanced_alert = self._settings_alert
        self._parameter_preview = widgets.HTML(
            "",
            layout=full_width_layout(display="none"),
        )
        self._parameter_preview.add_class("gu-help-text")
        self._status_bar = self._parameter_preview
        self._views_note = widgets.HTML(
            "",
            layout=full_width_layout(display="none"),
        )
        self._views_note.add_class("gu-views-note")
        self._id_readonly = build_readonly_value("", display="none")
        self._id_stack = vbox([self._id_text, self._id_readonly], gap="4px", extra_classes=("gu-plot-editor-id-stack",))
        self._invalid_widgets: list[widgets.Widget] = []
        self._focus_request_nonce = 0

        for control, class_name in (
            (self._kind, "gu-plot-editor-kind-control"),
            (self._views, "gu-plot-editor-views-control"),
            (self._label_text, "gu-plot-editor-label-control"),
            (self._id_text, "gu-plot-editor-id-control"),
            (self._cartesian_expression, "gu-plot-editor-cartesian-expression-control"),
            (self._cartesian_variable, "gu-plot-editor-cartesian-variable-control"),
            (self._parameter_variable, "gu-plot-editor-parameter-variable-control"),
            (self._parameter_min, "gu-plot-editor-parameter-min-control"),
            (self._parameter_max, "gu-plot-editor-parameter-max-control"),
            (self._parametric_x, "gu-plot-editor-parametric-x-control"),
            (self._parametric_y, "gu-plot-editor-parametric-y-control"),
            (self._field_expression, "gu-plot-editor-field-expression-control"),
            (self._field_x_variable, "gu-plot-editor-field-x-control"),
            (self._field_y_variable, "gu-plot-editor-field-y-control"),
            (self._cartesian_samples, "gu-plot-editor-cartesian-samples-control"),
            (self._parametric_samples, "gu-plot-editor-parametric-samples-control"),
            (self._field_grid_x, "gu-plot-editor-field-grid-x-control"),
            (self._field_grid_y, "gu-plot-editor-field-grid-y-control"),
            (self._curve_style_color, "gu-plot-editor-curve-color-control"),
            (self._curve_style_thickness, "gu-plot-editor-curve-thickness-control"),
            (self._curve_style_opacity, "gu-plot-editor-curve-opacity-control"),
            (self._curve_style_dash, "gu-plot-editor-curve-dash-control"),
        ):
            control.add_class(class_name)

        self._parametric_x_label = _math_field_label(r"x\left(t\right)")
        self._parametric_y_label = _math_field_label(r"y\left(t\right)")
        self._parameter_min_label = _math_field_label(r"t_{\mathrm{min}}")
        self._parameter_max_label = _math_field_label(r"t_{\mathrm{max}}")

        self._plot_type_field = labelled_field(
            "Plot type",
            self._kind,
            flex="0 1 260px",
        )
        self._cartesian_variable_field = labelled_field(
            "Variable",
            self._cartesian_variable,
            flex="0 1 180px",
        )
        self._cartesian_setup_row = responsive_row(
            [self._plot_type_field, self._cartesian_variable_field],
            gap="10px",
            extra_classes=("gu-plot-editor-setup-row", "gu-plot-editor-wrap-row"),
        )
        self._cartesian_expression_field = labelled_field("Expression", self._cartesian_expression)
        self._cartesian_box = vbox(
            [self._cartesian_setup_row, self._cartesian_expression_field],
            gap="10px",
        )

        self._parametric_x_field = labelled_field(self._parametric_x_label, self._parametric_x)
        self._parametric_y_field = labelled_field(self._parametric_y_label, self._parametric_y)
        self._parameter_variable_field = labelled_field(
            "Parameter",
            self._parameter_variable,
            flex="0 1 180px",
        )
        self._parameter_min_field = labelled_field(
            self._parameter_min_label,
            self._parameter_min,
            flex="1 1 160px",
        )
        self._parameter_max_field = labelled_field(
            self._parameter_max_label,
            self._parameter_max,
            flex="1 1 160px",
        )
        self._parametric_setup_row = responsive_row(
            [
                self._plot_type_field,
                self._parameter_variable_field,
                self._parameter_min_field,
                self._parameter_max_field,
            ],
            gap="10px",
            extra_classes=("gu-plot-editor-setup-row", "gu-plot-editor-wrap-row"),
        )
        self._parametric_box = vbox(
            [
                self._parametric_setup_row,
                self._parametric_x_field,
                self._parametric_y_field,
            ],
            gap="10px",
            display="none",
        )

        self._field_x_variable_field = labelled_field(
            "x variable",
            self._field_x_variable,
            flex="0 1 160px",
        )
        self._field_y_variable_field = labelled_field(
            "y variable",
            self._field_y_variable,
            flex="0 1 160px",
        )
        self._field_setup_row = responsive_row(
            [self._plot_type_field, self._field_x_variable_field, self._field_y_variable_field],
            gap="10px",
            extra_classes=("gu-plot-editor-setup-row", "gu-plot-editor-wrap-row"),
        )
        self._field_expression_field = labelled_field("Expression", self._field_expression)
        self._field_box = vbox(
            [self._field_setup_row, self._field_expression_field],
            gap="10px",
            display="none",
        )

        self._views_field = labelled_field(
            "Target views",
            self._views,
            extra_classes=("gu-control-targets",),
        )
        self._label_field = labelled_field("Label", self._label_text, flex="1 1 280px")
        self._id_field = labelled_field("Plot ID", self._id_stack, flex="0 1 220px")
        # Keep the boolean field inside a row container instead of mounting it
        # directly in the section VBox. A flex basis such as ``0 1 150px`` means
        # width inside a row, but it becomes a height basis inside a column
        # layout and creates the large blank band seen around the Visible toggle.
        self._visibility_field = build_boolean_field(
            self._visible_toggle,
            flex="0 1 150px",
            extra_classes=("gu-plot-editor-visibility-field",),
        )
        self._visibility_row = responsive_row(
            [self._visibility_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row", "gu-plot-editor-visibility-row"),
        )
        self._curve_style_color_field = labelled_field(
            "Color",
            self._curve_style_color,
            flex="0 1 180px",
        )
        self._curve_style_thickness_field = labelled_field(
            "Width",
            self._curve_style_thickness,
            flex="0 1 160px",
        )
        self._curve_style_opacity_field = labelled_field(
            "Opacity",
            self._curve_style_opacity,
            flex="0 1 160px",
        )
        self._curve_style_dash_field = labelled_field(
            "Dash",
            self._curve_style_dash,
            flex="0 1 180px",
        )
        self._curve_style_row = responsive_row(
            [
                self._curve_style_color_field,
                self._curve_style_thickness_field,
                self._curve_style_opacity_field,
                self._curve_style_dash_field,
            ],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row", "gu-plot-editor-curve-style-row"),
        )
        self._identity_row = responsive_row(
            [self._label_field, self._id_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )

        self._cartesian_resolution_field = labelled_field(
            "Samples",
            self._cartesian_samples,
            flex="0 1 190px",
        )
        self._cartesian_resolution_row = responsive_row(
            [self._cartesian_resolution_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
        )

        self._parametric_resolution_field = labelled_field(
            "Samples",
            self._parametric_samples,
            flex="0 1 190px",
        )
        self._parametric_resolution_row = responsive_row(
            [self._parametric_resolution_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
            display="none",
        )

        self._field_grid_x_field = labelled_field(
            "Grid x",
            self._field_grid_x,
            flex="0 1 190px",
        )
        self._field_grid_y_field = labelled_field(
            "Grid y",
            self._field_grid_y,
            flex="0 1 190px",
        )
        self._field_resolution_row = responsive_row(
            [self._field_grid_x_field, self._field_grid_y_field],
            gap="10px",
            extra_classes=("gu-plot-editor-wrap-row",),
            display="none",
        )

        self._placement_body = vbox(
            [self._views_field],
            gap="10px",
            extra_classes=("gu-plot-editor-placement-body",),
        )
        self._placement_section = build_form_section(
            "Placement",
            [self._placement_body],
            extra_classes=("gu-plot-editor-placement-section",),
        )
        self._visibility_section = build_form_section(
            "Display",
            [self._visibility_row],
            extra_classes=("gu-plot-editor-visibility-section",),
        )
        self._curve_style_section = build_form_section(
            "Line style",
            [self._curve_style_row],
            extra_classes=("gu-plot-editor-curve-style-section",),
        )
        self._curve_sound_section = build_form_section(
            "Sound",
            [build_boolean_field(self._curve_style_autonormalization)],
            extra_classes=("gu-plot-editor-curve-sound-section",),
        )
        self._identity_section = build_form_section(
            "Identity",
            [self._identity_row],
            extra_classes=("gu-plot-editor-identity-section",),
        )
        self._resolution_section = build_form_section(
            "Resolution",
            [
                self._cartesian_resolution_row,
                self._parametric_resolution_row,
                self._field_resolution_row,
            ],
            extra_classes=("gu-plot-editor-resolution-section",),
        )

        self._expression_tab = vbox(
            [
                self._expression_alert,
                self._cartesian_box,
                self._parametric_box,
                self._field_box,
                self._parameter_preview,
            ],
            gap="12px",
            extra_classes=("gu-plot-editor-tab-panel", "gu-tab-panel"),
        )
        self._style_tab = vbox(
            [
                self._style_alert,
                self._visibility_section,
                self._curve_style_section,
                self._curve_sound_section,
            ],
            gap="14px",
            display="none",
            extra_classes=("gu-plot-editor-tab-panel", "gu-tab-panel"),
        )
        self._settings_tab = vbox(
            [
                self._settings_alert,
                self._placement_section,
                self._identity_section,
                self._resolution_section,
            ],
            gap="14px",
            display="none",
            extra_classes=("gu-plot-editor-tab-panel", "gu-tab-panel"),
        )

        header = build_dialog_header(
            self._title,
            self._close_button,
            chip_widget=self._title_chip,
        )
        self._tab_bar = build_tab_bar(
            [self._expression_tab_button, self._style_tab_button, self._settings_tab_button],
            extra_classes=("gu-plot-editor-tab-bar",),
        )
        actions = build_action_bar(
            [self._cancel_button, self._apply_button],
            extra_classes=("gu-plot-editor-actions",),
        )

        panel_width, panel_min_width, panel_max_width = hosted_modal_dimensions(
            preferred_width_px=720,
            minimum_width_px=360,
        )
        self._panel = build_modal_panel(
            [
                header,
                self._tab_bar,
                self._expression_tab,
                self._style_tab,
                self._settings_tab,
                actions,
            ],
            width=panel_width,
            min_width=panel_min_width,
            max_width=panel_max_width,
            padding="16px",
            gap="12px",
            display="none",
            extra_classes=("gu-plot-editor-panel",),
        )
        self._modal = build_modal_overlay(
            self._panel,
            hosted=True,
            z_index="1002",
            background_color="rgba(15, 23, 42, 0.16)",
            modal_class=self._modal_class,
        )
        self._modal.add_class("gu-plot-editor-modal")

        self._error_title = widgets.HTML(
            "Could not apply plot",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._error_title.add_class("gu-modal-title-text")
        self._error_title.add_class("gu-plot-editor-error-title-text")
        self._error_close_button = widgets.Button(
            description="Close error dialog",
            tooltip="Close error dialog",
        )
        configure_icon_button(
            self._error_close_button,
            role="close",
            size_px=24,
            extra_classes=("gu-plot-editor-error-close-button",),
        )
        self._error_close_button.on_click(lambda _button: self._hide_error_dialog())
        self._error_ok_button = widgets.Button(
            description="OK",
            tooltip="Close error dialog",
        )
        configure_action_button(self._error_ok_button, variant="primary", min_width_px=72)
        self._error_ok_button.on_click(lambda _button: self._hide_error_dialog())
        self._error_box = self._error_message
        error_header = build_dialog_header(self._error_title, self._error_close_button)
        error_actions = build_action_bar([self._error_ok_button])
        error_width, error_min_width, error_max_width = hosted_modal_dimensions(
            preferred_width_px=420,
            minimum_width_px=300,
        )
        self._error_panel = build_modal_panel(
            [error_header, self._error_message, error_actions],
            width=error_width,
            min_width=error_min_width,
            max_width=error_max_width,
            padding="14px",
            gap="12px",
            display="none",
            extra_classes=("gu-plot-editor-error-panel",),
        )
        self._error_modal = build_modal_overlay(
            self._error_panel,
            hosted=True,
            z_index="1003",
            background_color="rgba(15, 23, 42, 0.22)",
            modal_class=self._error_modal_class,
        )

        zero_layout = widgets.Layout(width="0px", height="0px", margin="0px")
        self._modal_bridge = ModalDialogBridge(
            modal_class=self._modal_class,
            panel_selector=".gu-plot-editor-panel",
            close_selector=".gu-plot-editor-close-button",
            title_selector=".gu-modal-title-text",
            dialog_open=False,
            dialog_label="Plot editor",
            layout=zero_layout,
        )
        self._modal_bridge.on_msg(self._handle_main_dialog_message)
        self._error_bridge = ModalDialogBridge(
            modal_class=self._error_modal_class,
            panel_selector=".gu-plot-editor-error-panel",
            close_selector=".gu-plot-editor-error-close-button",
            title_selector=".gu-plot-editor-error-title-text",
            dialog_open=False,
            dialog_label="Plot editor error",
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._error_bridge.on_msg(self._handle_error_dialog_message)
        self._tab_bridge = TabListBridge(
            tablist_selector=".gu-plot-editor-tab-bar",
            tab_selector=".gu-plot-editor-tab-button",
            panel_selector=".gu-plot-editor-tab-panel",
            selected_index=0,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._tab_bridge.observe(self._on_tab_bridge_selected, names="selected_index")

        attach_host_children(
            self._modal_host,
            self._style,
            self._modal,
            self._error_modal,
            self._modal_bridge,
            self._error_bridge,
            self._tab_bridge,
        )

        # Backwards-compatible aliases for older tests/helpers.
        self._formula_tab_button = self._expression_tab_button
        self._style_tab_button_legacy = self._style_tab_button
        self._advanced_tab_button = self._settings_tab_button
        self._formula_tab = self._expression_tab
        self._style_tab_legacy = self._style_tab
        self._advanced_tab = self._settings_tab
        self._plot_type_row = self._cartesian_setup_row
        self._cartesian_variable_row = self._cartesian_setup_row
        self._parametric_parameter_row = self._parametric_setup_row
        self._field_variable_row = self._field_setup_row
        self._advanced_meta_row = self._identity_row
        self._cartesian_samples_row = self._cartesian_resolution_row
        self._parametric_samples_row = self._parametric_resolution_row
        self._field_grid_row = self._field_resolution_row
        self._kind.observe(self._on_kind_changed, names="value")
        self._parameter_variable.observe(self._on_parameter_variable_changed, names="value")

        self._update_parametric_prompt_copy()
        self._set_tab("expression")
        self._sync_section_visibility()
        self._update_parameter_preview()
        self._sync_open_state()

    @property
    def panel_visible(self) -> bool:
        """Return whether the modal is currently open.
        
        Full API
        --------
        ``obj.panel_visible -> bool``
        
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
        This member belongs to ``PlotComposerDialog``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotComposerDialog(...)
            current = obj.panel_visible
        
        Discovery-oriented use::
        
            help(PlotComposerDialog)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(PlotComposerDialog)`` and ``dir(PlotComposerDialog)`` to inspect adjacent members.
        """

        return self._is_open

    def open_for_new(self, *, default_kind: PlotEditorKind = "cartesian") -> None:
        """Open the dialog preloaded for creating a new plot.
        
        Full API
        --------
        ``obj.open_for_new(*, default_kind: PlotEditorKind='cartesian') -> None``
        
        Parameters
        ----------
        default_kind : PlotEditorKind, optional
            Value for ``default_kind`` in this API. Defaults to ``'cartesian'``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``default_kind='cartesian'``: Value for ``default_kind`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``PlotComposerDialog``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotComposerDialog(...)
            obj.open_for_new(...)
        
        Discovery-oriented use::
        
            help(PlotComposerDialog)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(PlotComposerDialog)`` and ``dir(PlotComposerDialog)`` to inspect adjacent members.
        """

        self._refresh_view_options(selected=(self._figure.views.current_id,))
        self._editing_plot_id = None
        self._id_text.disabled = False
        self._id_text.placeholder = "Auto"
        self._id_text.layout.display = "flex"
        self._id_readonly.value = ""
        self._id_readonly.layout.display = "none"
        self._title.value = "Plot editor"
        self._title_context.value = ""
        self._title_context.layout.display = "none"
        self._apply_button.description = "Create"
        self._apply_button.tooltip = "Create the plot from the entered expressions"
        self._modal_bridge.dialog_label = "Plot editor"
        self._clear_error()
        self._set_tab("expression")
        self._load_defaults(default_kind=default_kind)
        self._set_open(True)

    def open_for_plot(self, plot_id: str) -> None:
        """Open the dialog with fields loaded from an existing runtime plot.
        
        Full API
        --------
        ``obj.open_for_plot(plot_id: str) -> None``
        
        Parameters
        ----------
        plot_id : str
            Stable plot identifier used for lookup or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``PlotComposerDialog``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotComposerDialog(...)
            obj.open_for_plot(...)
        
        Discovery-oriented use::
        
            help(PlotComposerDialog)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(PlotComposerDialog)`` and ``dir(PlotComposerDialog)`` to inspect adjacent members.
        """

        plot = self._figure.plots.get(plot_id)
        if plot is None:
            raise KeyError(plot_id)

        self._editing_plot_id = plot_id
        self._id_text.disabled = False
        self._title.value = "Plot editor"
        self._apply_button.description = "Apply"
        self._apply_button.tooltip = "Update the plot from the entered expressions"
        self._modal_bridge.dialog_label = "Plot editor"
        self._clear_error()
        self._set_tab("expression")
        self._load_plot(plot)
        self._title_context.value = html.escape(f"Editing {plot_id}")
        self._title_context.layout.display = "block"
        self._id_text.layout.display = "none"
        self._id_readonly.value = html.escape(plot_id)
        self._id_readonly.layout.display = "block"
        self._set_open(True)

    def close(self) -> None:
        """Hide the dialog and clear transient error state.
        
        Full API
        --------
        ``obj.close() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``PlotComposerDialog``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotComposerDialog(...)
            obj.close(...)
        
        Discovery-oriented use::
        
            help(PlotComposerDialog)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(PlotComposerDialog)`` and ``dir(PlotComposerDialog)`` to inspect adjacent members.
        """

        self._clear_error()
        self._set_open(False)

    def _handle_main_dialog_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") == "close":
            self.close()

    def _handle_error_dialog_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") == "close":
            self._hide_error_dialog()

    def _set_open(self, value: bool) -> None:
        self._is_open = bool(value)
        self._sync_open_state()

    def _sync_open_state(self) -> None:
        self._panel.layout.display = "flex" if self._is_open else "none"
        self._modal.layout.display = "flex" if self._is_open else "none"
        self._error_panel.layout.display = "flex" if self._error_open else "none"
        self._error_modal.layout.display = "flex" if self._error_open else "none"
        if not self._is_open:
            self._modal_bridge.focus_selector = ""
        self._modal_bridge.dialog_open = self._is_open and not self._error_open
        self._error_bridge.dialog_open = self._error_open

    @staticmethod
    def _canonical_tab_name(tab_name: str) -> PlotEditorTab:
        """Map legacy/internal tab aliases onto the current three-tab layout."""

        lowered = str(tab_name or "").strip().lower()
        if lowered in {"expression", "formula"}:
            return "expression"
        if lowered == "style":
            return "style"
        if lowered in {"settings", "advanced"}:
            return "advanced"
        raise ValueError(f"Unknown plot editor tab: {tab_name!r}")

    def _set_tab(self, tab_name: str, *, sync_bridge: bool = True) -> None:
        canonical = self._canonical_tab_name(tab_name)
        self._active_tab = canonical
        self._expression_tab.layout.display = "flex" if canonical == "expression" else "none"
        self._style_tab.layout.display = "flex" if canonical == "style" else "none"
        self._settings_tab.layout.display = "flex" if canonical == "advanced" else "none"
        set_tab_button_selected(self._expression_tab_button, canonical == "expression")
        set_tab_button_selected(self._style_tab_button, canonical == "style")
        set_tab_button_selected(self._settings_tab_button, canonical == "advanced")
        if sync_bridge and getattr(self, "_tab_bridge", None) is not None:
            selected_index = {"expression": 0, "style": 1, "advanced": 2}[canonical]
            if int(self._tab_bridge.selected_index or 0) != selected_index:
                self._tab_sync_lock = True
                try:
                    self._tab_bridge.selected_index = selected_index
                finally:
                    self._tab_sync_lock = False

    def _on_tab_bridge_selected(self, change: dict[str, Any]) -> None:
        """Keep Python-side tab visibility in sync with arrow-key tab changes."""

        if self._tab_sync_lock:
            return
        new_index = int(change.get("new", 0) or 0)
        tab_name = {0: "expression", 1: "style", 2: "advanced"}.get(new_index, "expression")
        self._set_tab(tab_name, sync_bridge=False)

    def _on_parameter_variable_changed(self, _change: dict[str, Any]) -> None:
        """Refresh compact parametric labels when the parameter symbol changes."""

        if self._suspend_observers:
            return
        self._update_parametric_prompt_copy()
        self._update_parameter_preview()

    def _update_parametric_prompt_copy(self) -> None:
        """Keep compact parametric field titles in sync with the chosen parameter."""

        parameter_latex = _title_symbol_latex(self._parameter_variable.value, default="t")
        self._parametric_x_label.value = _mathjax_inline(
            _parametric_axis_title_latex("x", parameter_latex)
        )
        self._parametric_y_label.value = _mathjax_inline(
            _parametric_axis_title_latex("y", parameter_latex)
        )
        self._parameter_min_label.value = _mathjax_inline(
            _parametric_bound_title_latex(
            parameter_latex,
            bound="min",
            )
        )
        self._parameter_max_label.value = _mathjax_inline(
            _parametric_bound_title_latex(
            parameter_latex,
            bound="max",
            )
        )
        parameter_name = str(self._parameter_variable.value or "").strip() or "t"
        self._parametric_x.aria_label = f"Parametric x({parameter_name})"
        self._parametric_y.aria_label = f"Parametric y({parameter_name})"
        self._parameter_min.aria_label = f"Minimum value for {parameter_name}"
        self._parameter_max.aria_label = f"Maximum value for {parameter_name}"

    def _refresh_status_bar(self) -> None:
        """Backward-compatible alias for contextual parameter preview updates."""

        self._update_parameter_preview()

    def _set_curve_style_baseline(self, baseline: CurveStyleBaseline) -> None:
        """Load style-tab widgets from one effective curve-style baseline."""

        self._curve_style_baseline = baseline
        self._curve_style_color.value = baseline.picker_color
        self._curve_style_thickness.value = float(baseline.thickness)
        self._curve_style_opacity.value = float(baseline.opacity)
        self._curve_style_dash.value = baseline.dash
        self._curve_style_autonormalization.value = bool(baseline.autonormalization)

    def _curve_style_overrides(
        self,
    ) -> tuple[str | None, float | None, float | None, str | None, bool | None]:
        """Return only the curve-style fields that differ from the loaded baseline."""

        baseline = self._curve_style_baseline
        color_value = str(self._curve_style_color.value or "").strip()
        color_override = None if color_value == baseline.picker_color else color_value

        thickness_value = float(self._curve_style_thickness.value)
        thickness_override = None if thickness_value == float(baseline.thickness) else thickness_value

        opacity_value = float(self._curve_style_opacity.value)
        opacity_override = None if opacity_value == float(baseline.opacity) else opacity_value

        dash_value = str(self._curve_style_dash.value or "solid")
        dash_override = None if dash_value == baseline.dash else dash_value

        autonormalization_value = bool(self._curve_style_autonormalization.value)
        autonormalization_override = (
            None if autonormalization_value == bool(baseline.autonormalization) else autonormalization_value
        )

        return (
            color_override,
            thickness_override,
            opacity_override,
            dash_override,
            autonormalization_override,
        )

    def _load_defaults(self, *, default_kind: PlotEditorKind) -> None:
        """Populate a fresh new-plot form using figure defaults."""

        self._suspend_observers = True
        try:
            self._kind.value = default_kind
            self._id_text.value = ""
            self._label_text.value = ""
            self._visible_toggle.value = True
            self._cartesian_expression.value = ""
            self._cartesian_variable.value = "x"
            self._cartesian_samples.value = max(int(self._figure.samples or 500), 2)
            self._parametric_x.value = ""
            self._parametric_y.value = ""
            self._parameter_variable.value = "t"
            self._parameter_min.value = "0"
            self._parameter_max.value = r"2\pi"
            self._parametric_samples.value = max(int(self._figure.samples or 500), 2)
            self._field_expression.value = ""
            self._field_x_variable.value = "x"
            self._field_y_variable.value = "y"
            self._field_grid_x.value = 120
            self._field_grid_y.value = 120
            self._set_curve_style_baseline(
                CurveStyleBaseline(
                    picker_color=color_to_picker_hex(_next_auto_curve_color(self._figure), fallback="#636efa"),
                    thickness=2.0,
                    opacity=1.0,
                    dash="solid",
                    autonormalization=False,
                )
            )
        finally:
            self._suspend_observers = False
            self._update_parametric_prompt_copy()
            self._sync_section_visibility()
            self._update_parameter_preview()

    def _load_plot(self, plot: Any) -> None:
        """Load widget state from an existing plot runtime object."""

        selected_views = tuple(str(view_id) for view_id in getattr(plot, "views", ())) or (
            self._figure.views.current_id,
        )
        self._refresh_view_options(selected=selected_views)

        kind = self._kind_for_plot(plot)
        self._suspend_observers = True
        try:
            self._kind.value = kind
            self._id_text.value = str(getattr(plot, "id", ""))
            self._label_text.value = str(getattr(plot, "label", ""))
            self._visible_toggle.value = bool(getattr(plot, "visible", True))

            if kind == "cartesian":
                assert isinstance(plot, Plot)
                self._cartesian_expression.value = _to_latex(plot.symbolic_expression)
                self._cartesian_variable.value = _to_latex(plot._var, default="x")
                self._cartesian_samples.value = max(int(plot.samples or self._figure.samples or 500), 2)
            elif kind == "parametric":
                assert isinstance(plot, ParametricPlot)
                self._parametric_x.value = _to_latex(plot.x_expression)
                self._parametric_y.value = _to_latex(plot.y_expression)
                self._parameter_variable.value = _to_latex(plot.parameter_var, default="t")
                self._parameter_min.value = _to_latex(plot.parameter_domain[0], default="0")
                self._parameter_max.value = _to_latex(plot.parameter_domain[1], default=r"2\pi")
                self._parametric_samples.value = max(int(plot.samples or self._figure.samples or 500), 2)
            else:
                assert isinstance(plot, ScalarFieldPlot)
                self._field_expression.value = _to_latex(plot.symbolic_expression)
                self._field_x_variable.value = _to_latex(plot.x_var, default="x")
                self._field_y_variable.value = _to_latex(plot.y_var, default="y")
                grid_x, grid_y = plot.grid or plot.DEFAULT_GRID
                self._field_grid_x.value = max(int(grid_x), 2)
                self._field_grid_y.value = max(int(grid_y), 2)
            self._set_curve_style_baseline(_curve_style_baseline_for_plot(plot, figure=self._figure))
        finally:
            self._suspend_observers = False
            self._update_parametric_prompt_copy()
            self._sync_section_visibility()
            self._update_parameter_preview()

    @staticmethod
    def _kind_for_plot(plot: Any) -> PlotEditorKind:
        """Map one runtime plot object to the corresponding editor mode."""

        if isinstance(plot, ParametricPlot):
            return "parametric"
        if isinstance(plot, ScalarFieldPlot):
            if plot.render_mode == "contour":
                return "contour"
            if plot.preset == "temperature":
                return "temperature"
            return "density"
        return "cartesian"

    def _view_option_values(self) -> tuple[str, ...]:
        """Return current SelectMultiple option ids in a stable tuple form."""

        values: list[str] = []
        for option in tuple(self._views.options):
            if isinstance(option, tuple) and len(option) >= 2:
                values.append(str(option[1]))
            else:
                values.append(str(option))
        return tuple(values)

    def _refresh_view_options(self, *, selected: tuple[str, ...]) -> None:
        """Refresh view choices from the current figure registry."""

        options: list[tuple[str, str]] = []
        for view in self._figure.views.values():
            label = view.id if view.title == view.id else f"{view.id} — {view.title}"
            options.append((label, view.id))
        self._views.options = tuple(options)
        available = {value for _label, value in options}
        filtered = tuple(view_id for view_id in selected if view_id in available)
        fallback = (self._figure.views.current_id,) if self._figure.views.current_id in available else ()
        resolved = filtered or fallback
        self._views.value = resolved

        self._views_field.layout.display = "flex"
        self._views_field.layout.height = "auto"
        self._views_field.layout.min_height = "0px"
        self._views_field.layout.margin = "0px"
        self._views.layout.display = "flex"
        self._views.layout.height = "auto"
        self._views.layout.min_height = "96px"
        self._views_note.value = ""
        self._views_note.layout.display = "none"
        self._sync_placement_body()

    def _sync_placement_body(self) -> None:
        """Keep the advanced placement section mounted around the view selector."""

        self._placement_body.children = (self._views_field,)

    def _collect_draft(self) -> PlotEditorDraft:
        """Collect the current widget values into a detached draft."""

        view_ids = tuple(str(view_id) for view_id in self._views.value)
        (
            curve_color,
            curve_thickness,
            curve_opacity,
            curve_dash,
            curve_autonormalization,
        ) = self._curve_style_overrides()
        return PlotEditorDraft(
            kind=self._kind.value,
            plot_id=(self._id_text.value.strip() or None),
            label=self._label_text.value,
            view_ids=view_ids,
            visible=bool(self._visible_toggle.value),
            cartesian_expression_latex=self._cartesian_expression.value,
            cartesian_var_latex=self._cartesian_variable.value,
            cartesian_samples=int(self._cartesian_samples.value),
            parametric_x_latex=self._parametric_x.value,
            parametric_y_latex=self._parametric_y.value,
            parameter_var_latex=self._parameter_variable.value,
            parameter_min_latex=self._parameter_min.value,
            parameter_max_latex=self._parameter_max.value,
            parametric_samples=int(self._parametric_samples.value),
            field_expression_latex=self._field_expression.value,
            field_x_var_latex=self._field_x_variable.value,
            field_y_var_latex=self._field_y_variable.value,
            field_grid_x=int(self._field_grid_x.value),
            field_grid_y=int(self._field_grid_y.value),
            curve_color=curve_color,
            curve_thickness=curve_thickness,
            curve_opacity=curve_opacity,
            curve_dash=curve_dash,
            curve_autonormalization=curve_autonormalization,
        )

    def _request_focus(self, selector: str) -> None:
        """Ask the modal bridge to move focus to one control inside the dialog."""

        self._focus_request_nonce += 1
        self._modal_bridge.focus_selector = selector
        self._modal_bridge.focus_nonce = self._focus_request_nonce

    def _clear_invalid_state(self) -> None:
        """Remove invalid styling from any fields marked during the last apply."""

        for widget in self._invalid_widgets:
            set_widget_class_state(widget, "mod-invalid", False)
        self._invalid_widgets = []

    def _mark_invalid(self, *widgets_to_mark: widgets.Widget) -> None:
        """Apply invalid styling to the given controls or wrappers."""

        for widget in widgets_to_mark:
            if widget is None:
                continue
            set_widget_class_state(widget, "mod-invalid", True)
            self._invalid_widgets.append(widget)

    def _clear_inline_alerts(self) -> None:
        """Hide validation alerts on all plot-editor tabs."""

        self._expression_alert.value = ""
        self._expression_alert.layout.display = "none"
        self._style_alert.value = ""
        self._style_alert.layout.display = "none"
        self._settings_alert.value = ""
        self._settings_alert.layout.display = "none"

    def _show_validation_error(self, message: str) -> None:
        """Surface routine validation failures inline within the current dialog."""

        self._hide_error_dialog(clear_message=True)
        self._clear_invalid_state()
        self._clear_inline_alerts()
        tab_name = self._error_tab_name(message)
        self._set_tab(tab_name)
        alert = self._advanced_alert if tab_name == "advanced" else self._expression_alert
        alert.value = f"<div>{html.escape(message)}</div>"
        alert.layout.display = "flex"

        focus_selector = self._focus_selector_for_error(message, tab_name=tab_name)
        self._mark_invalid(*self._widgets_for_error(message, tab_name=tab_name))
        if focus_selector:
            self._request_focus(focus_selector)

    def _focus_selector_for_error(self, message: str, *, tab_name: Literal["expression", "advanced"]) -> str:
        """Return a selector for the control that should receive focus on error."""

        lowered = str(message or "").lower()
        if tab_name == "advanced":
            if "view" in lowered:
                return ".gu-plot-editor-views-control"
            if "plot id" in lowered or "identifier" in lowered or " id" in lowered:
                return ".gu-plot-editor-id-control"
            if "label" in lowered:
                return ".gu-plot-editor-label-control"
            if "sample" in lowered or "grid" in lowered:
                if self._kind.value in {"contour", "density", "temperature"}:
                    return ".gu-plot-editor-field-grid-x-control"
                return ".gu-plot-editor-cartesian-samples-control" if self._kind.value == "cartesian" else ".gu-plot-editor-parametric-samples-control"
            return ".gu-plot-editor-label-control"

        if self._kind.value == "cartesian":
            if "variable" in lowered:
                return ".gu-plot-editor-cartesian-variable-control"
            return ".gu-plot-editor-cartesian-expression-control"
        if self._kind.value == "parametric":
            if "minimum" in lowered:
                return ".gu-plot-editor-parameter-min-control"
            if "maximum" in lowered or "bound" in lowered:
                return ".gu-plot-editor-parameter-max-control"
            if "parameter" in lowered or "symbol" in lowered:
                return ".gu-plot-editor-parameter-variable-control"
            if "y(" in lowered or "parametric y" in lowered:
                return ".gu-plot-editor-parametric-y-control"
            return ".gu-plot-editor-parametric-x-control"
        if "x variable" in lowered:
            return ".gu-plot-editor-field-x-control"
        if "y variable" in lowered:
            return ".gu-plot-editor-field-y-control"
        return ".gu-plot-editor-field-expression-control"

    def _widgets_for_error(
        self,
        message: str,
        *,
        tab_name: Literal["expression", "advanced"],
    ) -> tuple[widgets.Widget, ...]:
        """Map one validation message to the most relevant controls."""

        lowered = str(message or "").lower()
        if tab_name == "advanced":
            if "view" in lowered:
                return (self._views, self._views_field)
            if "plot id" in lowered or "identifier" in lowered or " id" in lowered:
                return (self._id_text, self._id_field, self._id_readonly)
            if "label" in lowered:
                return (self._label_text, self._label_field)
            if "sample" in lowered and self._kind.value == "cartesian":
                return (self._cartesian_samples, self._cartesian_resolution_field)
            if "sample" in lowered and self._kind.value == "parametric":
                return (self._parametric_samples, self._parametric_resolution_field)
            if "grid" in lowered:
                return (
                    self._field_grid_x,
                    self._field_grid_y,
                    self._field_grid_x_field,
                    self._field_grid_y_field,
                )
            return (self._label_text, self._label_field)

        if self._kind.value == "cartesian":
            if "variable" in lowered:
                return (self._cartesian_variable, self._cartesian_variable_field)
            return (self._cartesian_expression, self._cartesian_expression_field)
        if self._kind.value == "parametric":
            if "minimum" in lowered:
                return (self._parameter_min, self._parameter_min_field)
            if "maximum" in lowered or "bound" in lowered:
                return (self._parameter_max, self._parameter_max_field)
            if "parameter" in lowered or "symbol" in lowered:
                return (self._parameter_variable, self._parameter_variable_field)
            if "y(" in lowered or "parametric y" in lowered:
                return (self._parametric_y, self._parametric_y_field)
            if "x(" in lowered or "parametric x" in lowered:
                return (self._parametric_x, self._parametric_x_field)
            return (self._parametric_x, self._parametric_x_field, self._parametric_y, self._parametric_y_field)
        if "x variable" in lowered:
            return (self._field_x_variable, self._field_x_variable_field)
        if "y variable" in lowered:
            return (self._field_y_variable, self._field_y_variable_field)
        return (self._field_expression, self._field_expression_field)

    def _set_error(self, message: str) -> None:
        """Open the fallback error dialog for unrecoverable apply failures."""

        self._show_error_dialog(message)

    def _clear_error(self) -> None:
        """Clear both inline validation UI and any secondary error dialog."""

        self._clear_inline_alerts()
        self._clear_invalid_state()
        self._hide_error_dialog(clear_message=True)

    def _show_error_dialog(self, message: str) -> None:
        self._error_message.value = (
            "<div class='gu-plot-editor-error-body'>"
            + html.escape(message)
            + "</div>"
        )
        self._error_open = True
        self._sync_open_state()

    def _hide_error_dialog(self, *, clear_message: bool = False) -> None:
        self._error_open = False
        if clear_message:
            self._error_message.value = ""
        self._sync_open_state()

    def _on_apply_clicked(self, _button: widgets.Button) -> None:
        """Validate the draft, apply it through Figure, and close on success."""

        draft = self._collect_draft()
        existing = (
            self._figure.plots.get(self._editing_plot_id)
            if self._editing_plot_id is not None
            else None
        )
        try:
            if not draft.view_ids:
                raise ValueError("Select at least one target view.")
            apply_plot_editor_draft(self._figure, draft, existing_plot=existing)
        except ValueError as exc:
            message = str(exc)
            if self._is_parse_error_message(message):
                self._set_error(message)
            else:
                self._show_validation_error(message)
            return
        except Exception as exc:
            self._set_error(str(exc))
            return
        self.close()

    def _on_kind_changed(self, _change: dict[str, Any]) -> None:
        """Switch visible sections when the selected plot family changes."""

        if self._suspend_observers:
            return
        self._update_parametric_prompt_copy()
        self._sync_section_visibility()
        self._update_parameter_preview()

    def _sync_section_visibility(self) -> None:
        """Show only the sections relevant to the selected plot family."""

        kind = self._kind.value
        is_field = kind in {"contour", "density", "temperature"}
        supports_curve_style = kind in {"cartesian", "parametric"}
        self._cartesian_box.layout.display = "flex" if kind == "cartesian" else "none"
        self._parametric_box.layout.display = "flex" if kind == "parametric" else "none"
        self._field_box.layout.display = "flex" if is_field else "none"
        self._cartesian_resolution_row.layout.display = "flex" if kind == "cartesian" else "none"
        self._parametric_resolution_row.layout.display = "flex" if kind == "parametric" else "none"
        self._field_resolution_row.layout.display = "flex" if is_field else "none"
        self._curve_style_section.layout.display = "flex" if supports_curve_style else "none"
        self._curve_sound_section.layout.display = "flex" if supports_curve_style else "none"

    def _update_parameter_preview(self) -> None:
        """Refresh compact parameter inference microcopy under the expression tab."""

        preview = _draft_parameter_preview(self._figure, self._collect_draft())
        if preview.error is not None:
            self._parameter_preview.value = ""
            self._parameter_preview.layout.display = "none"
            return

        parts: list[str] = []
        if preview.will_create:
            parts.append("create " + ", ".join(preview.will_create))
        if preview.will_reuse:
            parts.append("reuse " + ", ".join(preview.will_reuse))
        if not parts:
            self._parameter_preview.value = ""
            self._parameter_preview.layout.display = "none"
            return

        message = "; ".join(parts).capitalize() + "."
        self._parameter_preview.value = f"<div>{html.escape(message)}</div>"
        self._parameter_preview.layout.display = "block"

    @staticmethod
    def _is_parse_error_message(message: str) -> bool:
        """Return ``True`` when ``message`` represents an expression parsing failure."""

        lowered = str(message or "").lower()
        return any(
            token in lowered
            for token in (
                "could not parse",
                "parser error",
                "must be a single symbol",
                "sympy expression",
            )
        )

    @staticmethod
    def _error_tab_name(message: str) -> Literal["expression", "advanced"]:
        """Heuristically map one apply error to the most relevant tab."""

        lowered = str(message or "").lower()
        if any(token in lowered for token in ("view", "label", "plot id", "identifier", "sample", "grid")):
            return "advanced"
        return "expression"


__all__ = [
    "ParameterPreview",
    "PlotComposerDialog",
    "PlotEditorDraft",
    "PlotEditorKind",
    "apply_plot_editor_draft",
]
