"""Per-curve plotting model used by :mod:`gu_toolkit.Figure`.

Purpose
-------
Defines ``Plot``, the unit that turns one symbolic expression into one Plotly
trace. The class handles expression compilation, domain sampling, numeric
execution, and trace updates.

Concepts and structure
----------------------
Each ``Plot`` instance owns:

- symbolic state (variable/expression/parameters),
- compiled numeric callable state (via ``numpify_cached``),
- rendering state (sampled x/y arrays and trace handle),
- style state (line/trace overrides).

Architecture notes
------------------
``Plot`` is intentionally scoped to curve-level concerns and is orchestrated by
``Figure``. Figure-level concerns (layout, parameter registry, batching,
context management) are outside this module.

Important gotchas
-----------------
- ``parameters`` defaults are immutable tuples to avoid cross-instance leakage.
- ``sampling_points`` can be ``None`` to inherit figure defaults.
- ``render()`` updates an existing trace in-place; consumers should not assume
  a new trace object is created on each render.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit.Figure import Figure
>>> x = sp.symbols("x")
>>> fig = Figure()
>>> p = fig.plot(x, sp.sin(x), id="sin")  # doctest: +SKIP
>>> p.sampling_points = 800  # doctest: +SKIP

Discoverability
---------------
See next:

- ``Figure.py`` for orchestration and public API.
- ``numpify.py`` for symbolic→numeric compilation.
- ``PlotSnapshot.py`` for serialization/reproducibility support.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .Figure import Figure

import numpy as np
import plotly.graph_objects as go
import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .figure_context import _FigureDefaultSentinel, _is_figure_default
from .figure_plot_style import validate_style_kwargs
from .figure_types import NumberLike, NumberLikeOrStr, RangeLike, VisibleSpec
from .InputConvert import InputConvert
from .numpify import DYNAMIC_PARAMETER, NumericFunction, numpify_cached
from .PlotSnapshot import PlotSnapshot
from .performance_monitor import PerformanceMonitor, format_performance_snapshot


@dataclass
class PlotHandle:
    """Per-view runtime handle for a plot trace binding.
    
    Full API
    --------
    ``PlotHandle(plot_id: str, view_id: str, trace_handle: go.Scatter | None, cached_x: np.ndarray | None=None, cached_y: np.ndarray | None=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    plot_id : str
        Stable plot identifier used for lookup or update. Required.
    
    view_id : str
        Identifier for the relevant view inside a figure. Required.
    
    trace_handle : go.Scatter | None
        Value for ``trace_handle`` in this API. Required.
    
    cached_x : np.ndarray | None, optional
        Value for ``cached_x`` in this API. Defaults to ``None``.
    
    cached_y : np.ndarray | None, optional
        Value for ``cached_y`` in this API. Defaults to ``None``.
    
    Returns
    -------
    PlotHandle
        New ``PlotHandle`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``cached_x=None``: Value for ``cached_x`` in this API.
    - ``cached_y=None``: Value for ``cached_y`` in this API.
    
    Architecture note
    -----------------
    ``PlotHandle`` lives in ``gu_toolkit.figure_plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot import PlotHandle
        obj = PlotHandle(...)
    
    Discovery-oriented use::
    
        help(PlotHandle)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(PlotHandle)`` and ``dir(PlotHandle)`` to inspect adjacent members.
    """

    plot_id: str
    view_id: str
    trace_handle: go.Scatter | None
    cached_x: np.ndarray | None = None
    cached_y: np.ndarray | None = None


# SECTION: Plot (The specific logic for one curve) [id: Plot]
# =============================================================================


class Plot:
    """A single plotted curve managed by a :class:`Figure`.
    
    Full API
    --------
    ``Plot(var: Symbol, func: Expr, smart_figure: Figure, parameters: Sequence[Symbol]=(), x_domain: RangeLike | None=None, sampling_points: int | str | _FigureDefaultSentinel | None=None, label: str='', visible: VisibleSpec=True, color: str | None=None, thickness: int | float | None=None, dash: str | None=None, line: Mapping[str, Any] | None=None, opacity: int | float | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, plot_id: str='', view_ids: Sequence[str] | None=None, numeric_function: NumericFunction | None=None, samples: int | str | _FigureDefaultSentinel | None=None)``
    
    Public members exposed from this class: ``set_func``, ``set_numeric_function``, ``symbolic_expression``, ``parameters``,
        ``views``, ``add_to_view``, ``remove_from_view``, ``add_views``, ``remove_views``,
        ``snapshot``, ``numeric_expression``, ``x_data``, ``y_data``, ``label``, ``color``,
        ``thickness``, ``dash``, ``opacity``, ``figure``, ``x_domain``, ``samples``,
        ``sampling_points``, ``visible``, ``sound``, ``autonormalization``,
        ``performance_snapshot``, ``performance_report``, ``render``, ``update``
    
    Parameters
    ----------
    var : Symbol
        Primary symbolic variable used for evaluation. Required.
    
    func : Expr
        Symbolic expression or callable to evaluate. Required.
    
    smart_figure : Figure
        Value for ``smart_figure`` in this API. Required.
    
    parameters : Sequence[Symbol], optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``()``.
    
    x_domain : RangeLike | None, optional
        Numeric x-domain used for evaluation or rendering. Defaults to ``None``.
    
    sampling_points : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    label : str, optional
        Human-readable label used in UI or plotting output. Defaults to ``''``.
    
    visible : VisibleSpec, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    color : str | None, optional
        Explicit color value. Defaults to ``None``.
    
    thickness : int | float | None, optional
        Value for ``thickness`` in this API. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    line : Mapping[str, Any] | None, optional
        Value for ``line`` in this API. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    autonormalization : bool | None, optional
        Value for ``autonormalization`` in this API. Defaults to ``None``.
    
    plot_id : str, optional
        Stable plot identifier used for lookup or update. Defaults to ``''``.
    
    view_ids : Sequence[str] | None, optional
        Collection of view identifiers associated with this object or update. Defaults to ``None``.
    
    numeric_function : NumericFunction | None, optional
        Precompiled numeric callable used during rendering or evaluation. Defaults to ``None``.
    
    samples : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    Returns
    -------
    Plot
        New ``Plot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``parameters=()``: Parameter symbols/keys that should stay bound to this operation.
    - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
    - ``sampling_points=None``: Sampling density used when evaluating a curve or field.
    - ``label=''``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``color=None``: Explicit color value.
    - ``thickness=None``: Value for ``thickness`` in this API.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``line=None``: Value for ``line`` in this API.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``autonormalization=None``: Value for ``autonormalization`` in this API.
    - ``plot_id=''``: Stable plot identifier used for lookup or update.
    - ``view_ids=None``: Collection of view identifiers associated with this object or update.
    - ``numeric_function=None``: Precompiled numeric callable used during rendering or evaluation.
    - ``samples=None``: Sampling density used when evaluating a curve or field.
    
    Architecture note
    -----------------
    ``Plot`` lives in ``gu_toolkit.figure_plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot import Plot
        obj = Plot(...)
    
    Discovery-oriented use::
    
        help(Plot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
    """

    def __init__(
        self,
        var: Symbol,
        func: Expr,
        smart_figure: Figure,
        parameters: Sequence[Symbol] = (),
        x_domain: RangeLike | None = None,
        sampling_points: int | str | _FigureDefaultSentinel | None = None,
        label: str = "",
        visible: VisibleSpec = True,
        color: str | None = None,
        thickness: int | float | None = None,
        dash: str | None = None,
        line: Mapping[str, Any] | None = None,
        opacity: int | float | None = None,
        trace: Mapping[str, Any] | None = None,
        autonormalization: bool | None = None,
        plot_id: str = "",
        view_ids: Sequence[str] | None = None,
        *,
        numeric_function: NumericFunction | None = None,
        samples: int | str | _FigureDefaultSentinel | None = None,
    ) -> None:
        """
        Create a new Plot instance. (Usually called by Figure.plot)

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable for the function.
        func : sympy.Expr
            Symbolic expression to plot.
        smart_figure : Figure
            Owning figure.
        parameters : sequence[sympy.Symbol], optional
            Parameter symbols used in the expression.
        x_domain : RangeLike or None, optional
            Optional domain override for this plot.
        sampling_points : int or str, optional
            Number of samples; use ``"figure_default"`` to inherit from the figure.
        label : str, optional
            Trace label shown in the legend.
        visible : bool, optional
            Plot visibility setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        trace : mapping or None, optional
            Extra full-trace style fields as a mapping (advanced usage).

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = Figure()  # doctest: +SKIP
        >>> plot = Plot(x, sp.sin(x), fig)  # doctest: +SKIP

        Notes
        -----
        End users typically call :meth:`Figure.plot` instead of instantiating
        ``Plot`` directly.
        """
        self._smart_figure = smart_figure
        self.id = plot_id or label or "plot"
        self._label = str(label)
        self._x_data: np.ndarray | None = None
        self._y_data: np.ndarray | None = None
        self._handles: dict[str, PlotHandle] = {}
        self._performance = PerformanceMonitor(f"Plot[{self.id}]")
        self._performance.increment("created")
        self._performance.set_state(
            plot_id=self.id,
            visible=visible,
            requested_view_ids=sorted(str(v) for v in (view_ids or (self._smart_figure.views.current_id,))),
            has_x_domain=(x_domain is not None),
            samples=samples,
            sampling_points=sampling_points,
        )
        self._view_ids = set(view_ids or (self._smart_figure.views.current_id,))
        self._visible: VisibleSpec = visible
        self._sound_autonormalization = bool(autonormalization)

        for view_id in sorted(self._view_ids):
            self._create_trace_handle(view_id=view_id, label=label)

        self._suspend_render = True
        self._update_line_style(color=color, thickness=thickness, dash=dash, line=line)
        self.opacity = opacity
        if trace:
            trace_update = dict(trace)
            for trace_handle in self._iter_trace_handles():
                trace_handle.update(**trace_update)

        # Symbolic compilation is the default path. When a precompiled
        # NumericFunction is supplied (callable-first plotting), skip the
        # symbolic compilation step and bind the numeric backend directly.
        if numeric_function is None:
            self.set_func(var, func, parameters)
        else:
            self.set_numeric_function(
                var,
                numeric_function,
                parameters=parameters,
                symbolic_expression=func,
            )
        self.x_domain = x_domain

        if samples is not None and sampling_points is not None:
            lhs = None if _is_figure_default(samples) else int(InputConvert(samples, int))
            rhs = (
                None
                if _is_figure_default(sampling_points)
                else int(InputConvert(sampling_points, int))
            )
            if lhs != rhs:
                raise ValueError(
                    "Plot() received both samples= and sampling_points= with different values; use only one samples keyword."
                )

        resolved_samples = samples if samples is not None else sampling_points
        self.samples = resolved_samples

        self._suspend_render = False

        self.render()

    def _create_trace_handle(self, *, view_id: str, label: str) -> PlotHandle:
        """Create and register a per-view Plotly trace handle."""
        style_source = self._reference_trace_handle()
        figure_widget = self._smart_figure.views[view_id].figure_widget
        figure_widget.add_scatter(
            x=[],
            y=[],
            mode="lines",
            name=label,
            visible=self._visible,
        )
        trace_handle = figure_widget.data[-1]
        if style_source is not None:
            style_payload = self._trace_style_payload(style_source)
            if style_payload:
                trace_handle.update(**style_payload)
            trace_handle.name = label
            trace_handle.visible = self._visible
        handle = PlotHandle(plot_id=self.id, view_id=view_id, trace_handle=trace_handle)
        self._handles[view_id] = handle
        return handle

    def _iter_trace_handles(self) -> Sequence[go.Scatter]:
        """Return all live Plotly trace handles for this plot."""
        return tuple(
            handle.trace_handle
            for handle in self._handles.values()
            if handle.trace_handle is not None
        )

    @staticmethod
    def _trace_style_payload(trace_handle: go.Scatter) -> dict[str, Any]:
        """Return visual style fields that should be cloned across views."""
        payload = trace_handle.to_plotly_json()
        return {
            key: value
            for key, value in payload.items()
            if key not in {"name", "type", "uid", "visible", "x", "y"}
        }

    def _reference_trace_handle(self) -> go.Scatter | None:
        """Return a representative trace handle for style/property reads."""
        active = self._handles.get(self._smart_figure.views.current_id)
        if active is not None and active.trace_handle is not None:
            return active.trace_handle
        for trace_handle in self._iter_trace_handles():
            return trace_handle
        return None

    def _set_visibility_for_target_view(self, target_view: str) -> None:
        """Apply visibility updates to the requested view trace only."""
        handle = self._handles.get(target_view)
        if handle is not None and handle.trace_handle is not None:
            handle.trace_handle.visible = self._visible

    def _remove_trace_handle(self, *, view_id: str) -> None:
        """Remove and detach the trace mapped to ``view_id`` if present."""
        handle = self._handles.get(view_id)
        if handle is None or handle.trace_handle is None:
            return
        figure_widget = self._smart_figure.views[view_id].figure_widget
        figure_widget.data = tuple(
            trace for trace in figure_widget.data if trace is not handle.trace_handle
        )
        handle.trace_handle = None

    def set_func(
        self, var: Symbol, func: Expr, parameters: Sequence[Symbol] = ()
    ) -> None:
        """Set the independent variable and symbolic function for this plot.
        
        Full API
        --------
        ``obj.set_func(var: Symbol, func: Expr, parameters: Sequence[Symbol]=()) -> None``
        
        Parameters
        ----------
        var : Symbol
            Primary symbolic variable used for evaluation. Required.
        
        func : Expr
            Symbolic expression or callable to evaluate. Required.
        
        parameters : Sequence[Symbol], optional
            Parameter symbols/keys that should stay bound to this operation. Defaults to ``()``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``parameters=()``: Parameter symbols/keys that should stay bound to this operation.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.set_func(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        parameters = list(parameters)
        # Compile
        self._numpified = numpify_cached(func, vars=[var] + parameters)
        # Store
        self._var = var
        self._func = func
        self._rebind_numeric_expressions()

    def set_numeric_function(
        self,
        var: Symbol,
        numeric_function: NumericFunction,
        parameters: Sequence[Symbol] = (),
        *,
        symbolic_expression: Expr | None = None,
    ) -> None:
        """Set a precompiled :class:`NumericFunction` backend for this plot.
        
        Full API
        --------
        ``obj.set_numeric_function(var: Symbol, numeric_function: NumericFunction, parameters: Sequence[Symbol]=(), *, symbolic_expression: Expr | None=None) -> None``
        
        Parameters
        ----------
        var : Symbol
            Primary symbolic variable used for evaluation. Required.
        
        numeric_function : NumericFunction
            Precompiled numeric callable used during rendering or evaluation. Required.
        
        parameters : Sequence[Symbol], optional
            Parameter symbols/keys that should stay bound to this operation. Defaults to ``()``.
        
        symbolic_expression : Expr | None, optional
            Symbolic expression stored for display, round-tripping, or regeneration. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``parameters=()``: Parameter symbols/keys that should stay bound to this operation.
        - ``symbolic_expression=None``: Symbolic expression stored for display, round-tripping, or regeneration.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.set_numeric_function(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._numpified = numeric_function
        self._var = var
        if numeric_function.symbolic is not None:
            self._func = sp.sympify(numeric_function.symbolic)
        elif symbolic_expression is not None:
            # Preserve meaningful labeling/snapshotting for callable-backed
            # plots even when the NumericFunction doesn't carry a symbolic form.
            self._func = sp.sympify(symbolic_expression)
        elif isinstance(getattr(self, "_func", None), sp.Expr):
            self._func = self._func
        else:
            self._func = sp.Symbol("f_numeric")
        self._rebind_numeric_expressions()

    def _rebind_numeric_expressions(self) -> None:
        """Cache live and render-bound numeric callables for this plot.

        The base compiled :class:`NumericFunction` stays shared/cached. This
        helper only derives the binding layers that supply dynamic parameter
        values. Those wrappers are created when the plot function changes rather
        than during every render, which keeps the hot render loop allocation
        free on the numeric-function side.
        """
        dynamic_symbols = tuple(
            sym for sym in self._numpified.all_vars if sym != self._var
        )
        if dynamic_symbols:
            dynamic_expression = self._numpified.freeze(
                {sym: DYNAMIC_PARAMETER for sym in dynamic_symbols}
            )
            parameter_manager = self._smart_figure.parameters
            live_context = parameter_manager.parameter_context
            render_context = getattr(
                parameter_manager, "render_parameter_context", live_context
            )
            self._live_numeric_expression = dynamic_expression.set_parameter_context(
                live_context
            )
            self._render_numeric_expression = dynamic_expression.set_parameter_context(
                render_context
            )
        else:
            self._live_numeric_expression = self._numpified
            self._render_numeric_expression = self._numpified

    @property
    def symbolic_expression(self) -> Expr:
        """Return the current symbolic expression used by this plot.
        
        Full API
        --------
        ``obj.symbolic_expression -> Expr``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Expr
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.symbolic_expression
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._func

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        """Return parameter symbols in deterministic numeric-argument order.
        
        Full API
        --------
        ``obj.parameters -> tuple[Symbol, Ellipsis]``
        
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
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.parameters
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return tuple(sym for sym in self._numpified.all_vars if sym != self._var)

    @property
    def views(self) -> tuple[str, ...]:
        """Return sorted view memberships for this plot.
        
        Full API
        --------
        ``obj.views -> tuple[str, Ellipsis]``
        
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
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.views
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return tuple(sorted(self._view_ids))

    def add_to_view(self, view_id: str) -> None:
        """Add this plot to a view membership set.
        
        Full API
        --------
        ``obj.add_to_view(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.add_to_view(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if view_id in self._view_ids:
            return
        self._view_ids.add(view_id)
        self._create_trace_handle(view_id=view_id, label=self.label)
        if view_id == self._smart_figure.views.current_id and self._visible is True:
            self.render(view_id=view_id)

    def remove_from_view(self, view_id: str) -> None:
        """Remove this plot from a view membership set.
        
        Full API
        --------
        ``obj.remove_from_view(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.remove_from_view(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if view_id not in self._view_ids:
            return
        self._view_ids.remove(view_id)
        self._remove_trace_handle(view_id=view_id)
        self._handles.pop(view_id, None)

    def add_views(self, views: str | Sequence[str]) -> None:
        """Add one or more views to this plot.
        
        Full API
        --------
        ``obj.add_views(views: str | Sequence[str]) -> None``
        
        Parameters
        ----------
        views : str | Sequence[str]
            Collection of view identifiers associated with this object or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.add_views(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if isinstance(views, str):
            self.add_to_view(views)
            return
        for view_id in views:
            self.add_to_view(view_id)

    def remove_views(self, views: str | Sequence[str]) -> None:
        """Remove one or more views from this plot.
        
        Full API
        --------
        ``obj.remove_views(views: str | Sequence[str]) -> None``
        
        Parameters
        ----------
        views : str | Sequence[str]
            Collection of view identifiers associated with this object or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.remove_views(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if isinstance(views, str):
            self.remove_from_view(views)
            return
        for view_id in views:
            self.remove_from_view(view_id)

    def snapshot(self, *, id: str = "") -> PlotSnapshot:
        """Return an immutable snapshot of this plot's reproducible state.
        
        Full API
        --------
        ``obj.snapshot(*, id: str='') -> PlotSnapshot``
        
        Parameters
        ----------
        id : str, optional
            Stable identifier used to create, update, or look up the target object. Defaults to ``''``.
        
        Returns
        -------
        PlotSnapshot
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``id=''``: Stable identifier used to create, update, or look up the target object.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return PlotSnapshot(
            id=id,
            var=self._var,
            func=self._func,
            parameters=tuple(self.parameters),
            label=self.label,
            visible=self.visible,
            x_domain=self.x_domain,
            sampling_points=self.samples,
            color=self.color,
            thickness=self.thickness,
            dash=self.dash,
            opacity=self.opacity,
            autonormalization=self.autonormalization(),
            views=self.views,
        )

    @property
    def numeric_expression(self) -> NumericFunction:
        """Return the cached live :class:`NumericFunction` for this plot.
        
        Full API
        --------
        ``obj.numeric_expression -> NumericFunction``
        
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
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.numeric_expression
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._live_numeric_expression

    @property
    def x_data(self) -> np.ndarray | None:
        """Return the last rendered x samples.
        
        Full API
        --------
        ``obj.x_data -> np.ndarray | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        np.ndarray | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.x_data
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if self._x_data is None:
            return None
        x_values = self._x_data.copy()
        x_values.flags.writeable = False
        return x_values

    @property
    def y_data(self) -> np.ndarray | None:
        """Return the last rendered y samples.
        
        Full API
        --------
        ``obj.y_data -> np.ndarray | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        np.ndarray | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.y_data
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if self._y_data is None:
            return None
        y_values = self._y_data.copy()
        y_values.flags.writeable = False
        return y_values

    @property
    def label(self) -> str:
        """Return the legend label for this plot.
        
        Full API
        --------
        ``obj.label -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.label
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        """Set the legend label for this plot.
        
        Full API
        --------
        ``obj.label = value``
        
        Parameters
        ----------
        value : str
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.label = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._label = str(value)
        for trace_handle in self._iter_trace_handles():
            trace_handle.name = value

    @property
    def color(self) -> str | None:
        """Return the current line color for this plot.
        
        Full API
        --------
        ``obj.color -> str | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.color
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        candidates: list[go.Scatter] = []
        ref = self._reference_trace_handle()
        if ref is not None:
            candidates.append(ref)
        for trace_handle in self._iter_trace_handles():
            if trace_handle not in candidates:
                candidates.append(trace_handle)
        for candidate in candidates:
            line_obj = getattr(candidate, "line", None)
            line_color = getattr(line_obj, "color", None)
            if line_color is not None:
                return line_color
        return None

    @color.setter
    def color(self, value: str | None) -> None:
        """Set the line color for this plot.
        
        Full API
        --------
        ``obj.color = value``
        
        Parameters
        ----------
        value : str | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.color = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._update_line_style(color=value)

    @property
    def thickness(self) -> float | None:
        """Return the current line thickness for this plot.
        
        Full API
        --------
        ``obj.thickness -> float | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.thickness
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        ref = self._reference_trace_handle()
        if ref is None or ref.line is None:
            return None
        return ref.line.width

    @thickness.setter
    def thickness(self, value: int | float | None) -> None:
        """Set the line thickness for this plot.
        
        Full API
        --------
        ``obj.thickness = value``
        
        Parameters
        ----------
        value : int | float | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.thickness = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._update_line_style(thickness=value)

    @property
    def dash(self) -> str | None:
        """Return the current line dash style for this plot.
        
        Full API
        --------
        ``obj.dash -> str | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.dash
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        ref = self._reference_trace_handle()
        if ref is None or ref.line is None:
            return None
        return ref.line.dash

    @dash.setter
    def dash(self, value: str | None) -> None:
        """Set the line dash style for this plot.
        
        Full API
        --------
        ``obj.dash = value``
        
        Parameters
        ----------
        value : str | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.dash = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._update_line_style(dash=value)

    @property
    def opacity(self) -> float | None:
        """Return the current trace opacity for this plot.
        
        Full API
        --------
        ``obj.opacity -> float | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.opacity
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        ref = self._reference_trace_handle()
        return None if ref is None else ref.opacity

    @opacity.setter
    def opacity(self, value: int | float | None) -> None:
        """Set the trace opacity for this plot (0.0 to 1.0).
        
        Full API
        --------
        ``obj.opacity = value``
        
        Parameters
        ----------
        value : int | float | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.opacity = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if value is None:
            for trace_handle in self._iter_trace_handles():
                trace_handle.opacity = None
            return
        opacity = float(InputConvert(value, float))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        for trace_handle in self._iter_trace_handles():
            trace_handle.opacity = opacity

    @property
    def figure(self) -> Figure:
        """Return the Figure that owns this plot.
        
        Full API
        --------
        ``obj.figure -> Figure``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Figure
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.figure
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._smart_figure

    @property
    def x_domain(self) -> tuple[float, float] | None:
        """Return the explicit x-domain override for this plot.
        
        Full API
        --------
        ``obj.x_domain -> tuple[float, float] | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float] | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.x_domain
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: RangeLike | None) -> None:
        """Set the explicit x-domain for this plot.
        
        Full API
        --------
        ``obj.x_domain = value``
        
        Parameters
        ----------
        value : RangeLike | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.x_domain = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """

        if value is None or _is_figure_default(value):
            self._x_domain = None
        else:
            raw_min, raw_max = value
            self._x_domain = (
                float(InputConvert(raw_min, float)),
                float(InputConvert(raw_max, float)),
            )
            if self._x_domain[0] > self._x_domain[1]:
                raise ValueError("x_min must be <= x_max")
        self.render()

    @property
    def samples(self) -> int | None:
        """Return the number of samples for this plot.
        
        Full API
        --------
        ``obj.samples -> int | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        int | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.samples
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._sampling_points

    @samples.setter
    def samples(self, value: int | str | _FigureDefaultSentinel | None) -> None:
        """Set the number of samples for this plot.
        
        Full API
        --------
        ``obj.samples = value``
        
        Parameters
        ----------
        value : int | str | _FigureDefaultSentinel | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.samples = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._sampling_points = (
            int(InputConvert(value, int))
            if value is not None and not _is_figure_default(value)
            else None
        )
        self.render()

    @property
    def sampling_points(self) -> int | None:
        """Compatibility alias for :attr:`samples`.
        
        Full API
        --------
        ``obj.sampling_points -> int | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        int | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.sampling_points
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self.samples

    @sampling_points.setter
    def sampling_points(self, value: int | str | _FigureDefaultSentinel | None) -> None:
        """Work with sampling points on ``Plot``.
        
        Full API
        --------
        ``obj.sampling_points = value``
        
        Parameters
        ----------
        value : int | str | _FigureDefaultSentinel | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.sampling_points = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """

        self.samples = value

    @property
    def visible(self) -> VisibleSpec:
        """Return Plotly's visibility state for the trace.
        
        Full API
        --------
        ``obj.visible -> VisibleSpec``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        VisibleSpec
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            current = obj.visible
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        return self._visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        """Set Plotly's visibility state for the trace.
        
        Full API
        --------
        ``obj.visible = value``
        
        Parameters
        ----------
        value : VisibleSpec
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.visible = value
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        self._visible = value
        for view_id in self._view_ids:
            self._set_visibility_for_target_view(view_id)
        if value is True:
            self.render()

    def sound(self, run: bool = True) -> None:
        """Start, stop, or restart streaming playback for this plot.
        
        Full API
        --------
        ``obj.sound(run: bool=True) -> None``
        
        Parameters
        ----------
        run : bool, optional
            Value for ``run`` in this API. Defaults to ``True``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``run=True``: Value for ``run`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.sound(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        sound_manager = getattr(self._smart_figure, "_sound", None)
        if sound_manager is None:
            raise RuntimeError("Figure sound manager is unavailable.")
        sound_manager.sound(self.id, run=bool(run))

    def autonormalization(self, enabled: bool | None = None) -> bool:
        """Query or set per-plot sound auto-normalization.
        
        Full API
        --------
        ``obj.autonormalization(enabled: bool | None=None) -> bool``
        
        Parameters
        ----------
        enabled : bool | None, optional
            Boolean flag that turns a feature on or off. Defaults to ``None``.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``enabled=None``: Boolean flag that turns a feature on or off.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            result = obj.autonormalization(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        if enabled is None:
            return self._sound_autonormalization

        next_enabled = bool(enabled)
        if next_enabled == self._sound_autonormalization:
            return self._sound_autonormalization

        self._sound_autonormalization = next_enabled
        sound_manager = getattr(self._smart_figure, "_sound", None)
        if (
            sound_manager is not None
            and getattr(sound_manager, "active_plot_id", None) == self.id
        ):
            sound_manager.on_parameter_change(
                {"reason": "plot_autonormalization_changed", "plot_id": self.id}
            )
        return self._sound_autonormalization

    def performance_snapshot(self, *, recent_event_limit: int = 25) -> dict[str, Any]:
        """Work with performance snapshot on ``Plot``.
        
        Full API
        --------
        ``obj.performance_snapshot(*, recent_event_limit: int=25) -> dict[str, Any]``
        
        Parameters
        ----------
        recent_event_limit : int, optional
            Value for ``recent_event_limit`` in this API. Defaults to ``25``.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_event_limit=25``: Value for ``recent_event_limit`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            result = obj.performance_snapshot(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """

        snapshot = self._performance.snapshot(recent_limit=recent_event_limit)
        snapshot["state"].update(
            {
                "view_ids": sorted(self._view_ids),
                "current_handle_views": sorted(self._handles),
                "has_x_data": self._x_data is not None,
                "has_y_data": self._y_data is not None,
                "visible": self._visible,
                "samples": self.samples,
            }
        )
        return snapshot

    def performance_report(self, *, recent_event_limit: int = 10) -> str:
        """Work with performance report on ``Plot``.
        
        Full API
        --------
        ``obj.performance_report(*, recent_event_limit: int=10) -> str``
        
        Parameters
        ----------
        recent_event_limit : int, optional
            Value for ``recent_event_limit`` in this API. Defaults to ``10``.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_event_limit=10``: Value for ``recent_event_limit`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            result = obj.performance_report(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """

        return format_performance_snapshot(
            self.performance_snapshot(recent_event_limit=recent_event_limit),
            title=f"Plot {self.id}",
        )

    def render(
        self,
        view_id: str | None = None,
        *,
        use_batch_update: bool = True,
        refresh_parameter_snapshot: bool = True,
    ) -> None:
        """Compute samples and update the Plotly trace for one view membership.
        
        Full API
        --------
        ``obj.render(view_id: str | None=None, *, use_batch_update: bool=True, refresh_parameter_snapshot: bool=True) -> None``
        
        Parameters
        ----------
        view_id : str | None, optional
            Identifier for the relevant view inside a figure. Defaults to ``None``.
        
        use_batch_update : bool, optional
            Value for ``use_batch_update`` in this API. Defaults to ``True``.
        
        refresh_parameter_snapshot : bool, optional
            Value for ``refresh_parameter_snapshot`` in this API. Defaults to ``True``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``view_id=None``: Identifier for the relevant view inside a figure.
        - ``use_batch_update=True``: Value for ``use_batch_update`` in this API.
        - ``refresh_parameter_snapshot=True``: Value for ``refresh_parameter_snapshot`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.render(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        target_view = view_id or self._smart_figure.views.current_id
        self._set_visibility_for_target_view(target_view)
        if target_view not in self._view_ids:
            return
        if self._suspend_render or self._visible is not True:
            return

        fig = self._smart_figure
        if refresh_parameter_snapshot:
            refresh_context = getattr(fig.parameters, "refresh_render_parameter_context", None)
            if callable(refresh_context):
                refresh_context()

        # Phase 2 keeps concrete rendering pinned to active view only.
        if target_view != fig.views.current_id:
            fig.views[target_view].is_stale = True
            return

        # 1. Determine Range
        viewport = fig.current_x_range or fig.x_range

        if self.x_domain is None:
            x_min, x_max = float(viewport[0]), float(viewport[1])
        else:
            x_min = min(float(viewport[0]), float(self.x_domain[0]))
            x_max = max(float(viewport[1]), float(self.x_domain[1]))

        # 2. Determine Sampling
        render_started = time.perf_counter()
        sample_count = int(self.samples or fig.samples or 500)
        target_handle = self._handles[target_view]
        trace_handle = target_handle.trace_handle
        cached_x = target_handle.cached_x
        reuse_x = (
            cached_x is not None
            and cached_x.shape == (sample_count,)
            and cached_x.size > 0
            and np.isclose(float(cached_x[0]), float(x_min))
            and np.isclose(float(cached_x[-1]), float(x_max))
        )
        self._performance.set_state(
            target_view=target_view,
            sample_count=sample_count,
            x_min=float(x_min),
            x_max=float(x_max),
            last_x_reused=reuse_x,
        )

        # 3. Compute
        x_prepare_started = time.perf_counter()
        if reuse_x:
            x_values = cached_x
            self._performance.increment("x_reuse_hits")
        else:
            x_values = np.linspace(x_min, x_max, num=sample_count)
            self._performance.increment("x_reuse_misses")
        self._performance.record_duration(
            "x_prepare_ms",
            (time.perf_counter() - x_prepare_started) * 1000.0,
            reused=reuse_x,
            sample_count=sample_count,
        )

        evaluate_started = time.perf_counter()
        y_values = np.asarray(self._render_numeric_expression(x_values))
        self._performance.record_duration(
            "evaluate_ms",
            (time.perf_counter() - evaluate_started) * 1000.0,
            sample_count=sample_count,
        )
        self._x_data = np.array(x_values, copy=True)
        self._y_data = np.array(y_values, copy=True)
        target_handle.cached_x = self._x_data.copy()
        target_handle.cached_y = self._y_data.copy()

        # 4. Update Trace
        if trace_handle is None:
            return

        def _apply_trace_update() -> None:
            if not reuse_x:
                trace_handle.x = x_values
            trace_handle.y = y_values

        trace_update_started = time.perf_counter()
        if use_batch_update:
            with fig.views[target_view].figure_widget.batch_update():
                _apply_trace_update()
        else:
            _apply_trace_update()
        self._performance.increment("renders")
        self._performance.record_duration(
            "trace_update_ms",
            (time.perf_counter() - trace_update_started) * 1000.0,
            reused_x=reuse_x,
            sample_count=sample_count,
        )
        self._performance.record_duration(
            "render_total_ms",
            (time.perf_counter() - render_started) * 1000.0,
            reused_x=reuse_x,
            sample_count=sample_count,
        )

        fallback_refresh_started = time.perf_counter()
        pane = getattr(fig.views[target_view], "pane", None)
        refreshed_fallback_display = bool(
            getattr(pane, "refresh_plot_display", lambda **_kwargs: False)(
                reason=f"plot_render:{self.id}"
            )
        )
        if refreshed_fallback_display:
            self._performance.increment("fallback_plot_refreshes")
            self._performance.record_duration(
                "fallback_plot_refresh_ms",
                (time.perf_counter() - fallback_refresh_started) * 1000.0,
                sample_count=sample_count,
            )

    def _update_line_style(
        self,
        *,
        color: str | None = None,
        thickness: int | float | None = None,
        dash: str | None = None,
        line: Mapping[str, Any] | None = None,
    ) -> None:
        """Apply incremental line-style updates to the backing Plotly trace."""

        def _coerce_line_value(value: Any) -> dict[str, Any]:
            """Normalize Plotly line-like structures to mutable dictionaries."""
            if not value:
                return {}
            if isinstance(value, Mapping):
                return dict(value)
            if hasattr(value, "to_plotly_json"):
                return value.to_plotly_json()
            try:
                return dict(value)
            except (TypeError, ValueError):
                return {}

        line_updates: dict[str, Any] = {}
        if line:
            line_updates.update(_coerce_line_value(line))
        if color is not None:
            line_updates["color"] = color
        if thickness is not None:
            line_updates["width"] = float(InputConvert(thickness, float))
        if dash is not None:
            line_updates["dash"] = dash
        if line_updates:
            for trace_handle in self._iter_trace_handles():
                current_line = _coerce_line_value(trace_handle.line)
                current_line.update(line_updates)
                trace_handle.line = current_line

    def update(self, **kwargs: Any) -> None:
        """Update multiple plot attributes at once.
        
        Full API
        --------
        ``obj.update(**kwargs: Any) -> None``
        
        Parameters
        ----------
        **kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``Plot``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Plot(...)
            obj.update(...)
        
        Discovery-oriented use::
        
            help(Plot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(Plot)`` and ``dir(Plot)`` to inspect adjacent members.
        """
        render_requested = False
        previous_suspend = self._suspend_render
        self._suspend_render = True
        try:
            if "label" in kwargs:
                self.label = kwargs["label"]

            if "visible" in kwargs:
                self.visible = kwargs["visible"]
                render_requested = render_requested or kwargs["visible"] is True

            if "x_domain" in kwargs:
                val = kwargs["x_domain"]
                if val is None:
                    # None means "no change" during in-place updates.
                    pass
                elif _is_figure_default(val):
                    self.x_domain = None
                    render_requested = True
                else:
                    x_min = InputConvert(val[0], float)
                    x_max = InputConvert(val[1], float)
                    self.x_domain = (x_min, x_max)
                    render_requested = True

            samples_key_present = "samples" in kwargs
            sampling_points_key_present = "sampling_points" in kwargs
            if samples_key_present and sampling_points_key_present:
                left = kwargs["samples"]
                right = kwargs["sampling_points"]
                lhs = None if _is_figure_default(left) else (
                    None if left is None else int(InputConvert(left, int))
                )
                rhs = None if _is_figure_default(right) else (
                    None if right is None else int(InputConvert(right, int))
                )
                if lhs != rhs:
                    raise ValueError(
                        "Plot.update() received both samples= and sampling_points= with different values; use only one samples keyword."
                    )

            if samples_key_present or sampling_points_key_present:
                val = kwargs["samples"] if samples_key_present else kwargs["sampling_points"]
                if val is None:
                    # None means "no change" during in-place updates.
                    pass
                elif _is_figure_default(val):
                    self.samples = None
                    render_requested = True
                else:
                    self.samples = InputConvert(val, int)
                    render_requested = True

            if "view" in kwargs:
                requested = kwargs["view"]
                if requested is not None:
                    render_requested = True
                    requested_views = (
                        {requested} if isinstance(requested, str) else set(requested)
                    )
                    # Add new view memberships before removing old ones so a
                    # fresh trace can clone the existing line style from a live
                    # handle instead of falling back to Plotly defaults.
                    for view_id in requested_views:
                        self.add_to_view(view_id)
                    for view_id in tuple(self._view_ids):
                        if view_id not in requested_views:
                            self.remove_from_view(view_id)

            style_kwargs = validate_style_kwargs(
                {
                    "color": kwargs.get("color"),
                    "thickness": kwargs.get("thickness"),
                    "width": kwargs.get("width"),
                    "dash": kwargs.get("dash"),
                    "line": kwargs.get("line"),
                    "opacity": kwargs.get("opacity"),
                    "alpha": kwargs.get("alpha"),
                    "trace": kwargs.get("trace"),
                "autonormalization": kwargs.get("autonormalization"),
                },
                caller="Plot.update()",
            )

            self._update_line_style(
                color=style_kwargs.get("color"),
                thickness=style_kwargs.get("thickness"),
                dash=style_kwargs.get("dash"),
                line=style_kwargs.get("line"),
            )
            if "opacity" in kwargs or "alpha" in kwargs:
                self.opacity = style_kwargs.get("opacity")
            if style_kwargs.get("trace"):
                trace_update = dict(style_kwargs["trace"])
                for trace_handle in self._iter_trace_handles():
                    trace_handle.update(**trace_update)
            if "autonormalization" in kwargs and style_kwargs.get("autonormalization") is not None:
                self.autonormalization(style_kwargs.get("autonormalization"))

            # Function update
            if any(k in kwargs for k in ("var", "func", "parameters", "numeric_function")):
                render_requested = True
                v = kwargs.get("var", self._var)
                f = kwargs.get("func", self._func)
                p = kwargs.get("parameters", self.parameters)
                numeric_fn = kwargs.get("numeric_function")
                if numeric_fn is not None:
                    self.set_numeric_function(
                        v,
                        numeric_fn,
                        parameters=p,
                        symbolic_expression=f,
                    )
                else:
                    self.set_func(v, f, p)
        finally:
            self._suspend_render = previous_suspend

        if render_requested:
            self.render()


# =============================================================================
