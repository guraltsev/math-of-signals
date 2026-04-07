"""Parametric curve support built on top of :mod:`gu_toolkit.figure_plot`.

This module adds :class:`ParametricPlot`, a curve type for plotting points of
``(x(t), y(t))`` sampled over an explicit parameter interval. The implementation
intentionally reuses :class:`gu_toolkit.figure_plot.Plot` for trace ownership,
style application, visibility handling, view membership, and most update
semantics, while specializing only the data-generation path.

Design notes
------------
- The base :class:`Plot` class remains the owner of the Plotly trace handle and
  the y-component numeric expression.
- :class:`ParametricPlot` adds an independent x-component numeric expression and
  a dedicated parameter domain.
- Rendering samples the parameter variable ``t`` directly and then evaluates the
  x- and y-coordinate backends against the same parameter sample array.
- Snapshot/code generation support is implemented through extra metadata on
  :class:`gu_toolkit.PlotSnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .figure_color import explicit_style_color
from .figure_context import _FigureDefaultSentinel, _is_figure_default
from .figure_plot_normalization import PlotVarsSpec, normalize_parametric_plot_inputs
from .figure_plot_style import validate_style_kwargs
from .figure_plot_helpers import (
    normalize_view_ids,
    remove_plot_from_figure,
    resolve_plot_id,
)
from .figure_plot import Plot
from .figure_types import NumberLikeOrStr, VisibleSpec
from .InputConvert import InputConvert
from .numpify import DYNAMIC_PARAMETER, NumericFunction, numpify_cached
from .parameter_keys import ParameterKeyOrKeys, expand_parameter_keys_to_symbols
from .PlotSnapshot import PlotSnapshot

if TYPE_CHECKING:
    from .Figure import Figure


class ParametricPlot(Plot):
    """A plot whose screen coordinates are generated from ``(x(t), y(t))``.
    
    Full API
    --------
    ``ParametricPlot(parameter_var: Symbol, x_func: Expr, y_func: Expr, smart_figure: Figure, parameters: Sequence[Symbol]=(), parameter_domain: tuple[NumberLikeOrStr, NumberLikeOrStr]=(0.0, 1.0), sampling_points: int | str | _FigureDefaultSentinel | None=None, label: str='', visible: VisibleSpec=True, color: str | None=None, thickness: int | float | None=None, dash: str | None=None, line: Mapping[str, Any] | None=None, opacity: int | float | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, plot_id: str='', view_ids: Sequence[str] | None=None, x_numeric_function: NumericFunction | None=None, y_numeric_function: NumericFunction | None=None, samples: int | str | _FigureDefaultSentinel | None=None)``
    
    Public members exposed from this class: ``parameter_var``, ``parameter_domain``, ``x_expression``, ``y_expression``,
        ``symbolic_expressions``, ``x_numeric_expression``, ``y_numeric_expression``,
        ``parameters``, ``snapshot``, ``render``, ``update``
    
    Parameters
    ----------
    parameter_var : Symbol
        Symbol used as the parameter/sweep variable. Required.
    
    x_func : Expr
        Expression or callable that supplies x-values. Required.
    
    y_func : Expr
        Expression or callable that supplies y-values. Required.
    
    smart_figure : Figure
        Value for ``smart_figure`` in this API. Required.
    
    parameters : Sequence[Symbol], optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``()``.
    
    parameter_domain : tuple[NumberLikeOrStr, NumberLikeOrStr], optional
        Numeric domain used for a parametric sweep variable. Defaults to ``(0.0, 1.0)``.
    
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
    
    x_numeric_function : NumericFunction | None, optional
        Value for ``x_numeric_function`` in this API. Defaults to ``None``.
    
    y_numeric_function : NumericFunction | None, optional
        Value for ``y_numeric_function`` in this API. Defaults to ``None``.
    
    samples : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    Returns
    -------
    ParametricPlot
        New ``ParametricPlot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``parameters=()``: Parameter symbols/keys that should stay bound to this operation.
    - ``parameter_domain=(0.0, 1.0)``: Numeric domain used for a parametric sweep variable.
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
    - ``x_numeric_function=None``: Value for ``x_numeric_function`` in this API.
    - ``y_numeric_function=None``: Value for ``y_numeric_function`` in this API.
    - ``samples=None``: Sampling density used when evaluating a curve or field.
    
    Architecture note
    -----------------
    ``ParametricPlot`` lives in ``gu_toolkit.figure_parametric_plot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_parametric_plot import ParametricPlot
        obj = ParametricPlot(...)
    
    Discovery-oriented use::
    
        help(ParametricPlot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parametric-plotting.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
    - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
    """

    def __init__(
        self,
        parameter_var: Symbol,
        x_func: Expr,
        y_func: Expr,
        smart_figure: Figure,
        parameters: Sequence[Symbol] = (),
        parameter_domain: tuple[NumberLikeOrStr, NumberLikeOrStr] = (0.0, 1.0),
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
        x_numeric_function: NumericFunction | None = None,
        y_numeric_function: NumericFunction | None = None,
        samples: int | str | _FigureDefaultSentinel | None = None,
    ) -> None:
        self._parameter_symbols = tuple(parameters)
        self._parameter_domain = self._coerce_parameter_domain(parameter_domain)
        self._x_symbolic_expression = sp.sympify(x_func)
        self._x_numpified: NumericFunction | None = None
        self._x_live_numeric_expression: NumericFunction | None = None
        self._x_render_numeric_expression: NumericFunction | None = None
        self._parametric_ready = False

        # ``Plot`` owns trace creation, view membership, style state, and the
        # y-component numeric backend. Its eager ``render()`` call is suppressed
        # by our ``_parametric_ready`` guard until the x-component has been
        # fully initialized.
        super().__init__(
            var=parameter_var,
            func=y_func,
            smart_figure=smart_figure,
            parameters=parameters,
            x_domain=None,
            sampling_points=sampling_points,
            label=label,
            visible=visible,
            color=color,
            thickness=thickness,
            dash=dash,
            line=line,
            opacity=opacity,
            trace=trace,
            autonormalization=autonormalization,
            plot_id=plot_id,
            view_ids=view_ids,
            numeric_function=y_numeric_function,
            samples=samples,
        )

        self._set_x_component(
            parameter_var,
            x_func,
            parameters=parameters,
            numeric_function=x_numeric_function,
        )
        self._parametric_ready = True
        self.render()

    @staticmethod
    def _coerce_parameter_domain(
        value: tuple[NumberLikeOrStr, NumberLikeOrStr]
    ) -> tuple[float, float]:
        """Convert a raw parameter interval into validated floats."""
        parameter_min = float(InputConvert(value[0], float))
        parameter_max = float(InputConvert(value[1], float))
        if parameter_min > parameter_max:
            raise ValueError("parametric_plot() requires parameter_min <= parameter_max")
        return (parameter_min, parameter_max)

    @staticmethod
    def _bind_numeric_expression(
        numeric_fn: NumericFunction,
        *,
        parameter_var: Symbol,
        figure: Figure,
    ) -> tuple[NumericFunction, NumericFunction]:
        """Return live and render-bound numeric callables for one component."""
        dynamic_symbols = tuple(sym for sym in numeric_fn.all_vars if sym != parameter_var)
        if dynamic_symbols:
            dynamic_expression = numeric_fn.freeze(
                {sym: DYNAMIC_PARAMETER for sym in dynamic_symbols}
            )
            parameter_manager = figure.parameters
            live_context = parameter_manager.parameter_context
            render_context = getattr(
                parameter_manager, "render_parameter_context", live_context
            )
            return (
                dynamic_expression.set_parameter_context(live_context),
                dynamic_expression.set_parameter_context(render_context),
            )
        return numeric_fn, numeric_fn

    def _set_x_component(
        self,
        parameter_var: Symbol,
        x_func: Expr,
        *,
        parameters: Sequence[Symbol],
        numeric_function: NumericFunction | None,
    ) -> None:
        """Compile and bind the x-coordinate backend for this plot."""
        self._parameter_symbols = tuple(parameters)
        if numeric_function is None:
            self._x_symbolic_expression = sp.sympify(x_func)
            self._x_numpified = numpify_cached(
                self._x_symbolic_expression,
                vars=[parameter_var, *self._parameter_symbols],
            )
        else:
            self._x_numpified = numeric_function
            if numeric_function.symbolic is not None:
                self._x_symbolic_expression = sp.sympify(numeric_function.symbolic)
            else:
                self._x_symbolic_expression = sp.sympify(x_func)

        self._x_live_numeric_expression, self._x_render_numeric_expression = (
            self._bind_numeric_expression(
                self._x_numpified,
                parameter_var=parameter_var,
                figure=self._smart_figure,
            )
        )

    @property
    def parameter_var(self) -> Symbol:
        """Return the shared sampling variable used for this curve.
        
        Full API
        --------
        ``obj.parameter_var -> Symbol``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Symbol
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.parameter_var
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return self._var

    @property
    def parameter_domain(self) -> tuple[float, float]:
        """Return the inclusive sampling interval for ``parameter_var``.
        
        Full API
        --------
        ``obj.parameter_domain -> tuple[float, float]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.parameter_domain
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return self._parameter_domain

    @property
    def x_expression(self) -> Expr:
        """Return the symbolic x-coordinate expression.
        
        Full API
        --------
        ``obj.x_expression -> Expr``
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.x_expression
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return self._x_symbolic_expression

    @property
    def y_expression(self) -> Expr:
        """Return the symbolic y-coordinate expression.
        
        Full API
        --------
        ``obj.y_expression -> Expr``
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.y_expression
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return self._func

    @property
    def symbolic_expressions(self) -> tuple[Expr, Expr]:
        """Return ``(x_expression, y_expression)`` for introspection.
        
        Full API
        --------
        ``obj.symbolic_expressions -> tuple[Expr, Expr]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[Expr, Expr]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.symbolic_expressions
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return (self.x_expression, self.y_expression)

    @property
    def x_numeric_expression(self) -> NumericFunction:
        """Return the live numeric x-coordinate expression.
        
        Full API
        --------
        ``obj.x_numeric_expression -> NumericFunction``
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.x_numeric_expression
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        if self._x_live_numeric_expression is None:  # pragma: no cover - defensive
            raise RuntimeError("Parametric plot x-expression is not initialized.")
        return self._x_live_numeric_expression

    @property
    def y_numeric_expression(self) -> NumericFunction:
        """Return the live numeric y-coordinate expression.
        
        Full API
        --------
        ``obj.y_numeric_expression -> NumericFunction``
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.y_numeric_expression
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return self.numeric_expression

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        """Return the union of parameter symbols used by either component.
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            current = obj.parameters
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return tuple(self._parameter_symbols)

    def snapshot(self, *, id: str = "") -> PlotSnapshot:
        """Return a snapshot that round-trips this parametric curve.
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        return PlotSnapshot(
            id=id,
            var=self.parameter_var,
            func=self.y_expression,
            parameters=tuple(self.parameters),
            label=self.label,
            visible=self.visible,
            x_domain=None,
            sampling_points=self.samples,
            color=self.color,
            thickness=self.thickness,
            dash=self.dash,
            opacity=self.opacity,
            autonormalization=self.autonormalization(),
            views=self.views,
            kind="parametric",
            x_func=self.x_expression,
            parameter_domain=self.parameter_domain,
        )

    @staticmethod
    def _coerce_component_values(
        raw_values: Any,
        *,
        parameter_values: np.ndarray,
        axis_name: str,
    ) -> np.ndarray:
        """Normalize one rendered coordinate array.

        Scalar outputs are broadcast to the full parameter sample length. Vector
        outputs are flattened to one dimension and must contain exactly one
        coordinate per sampled parameter value.
        """
        values = np.asarray(raw_values, dtype=float)
        if values.ndim == 0:
            return np.full(parameter_values.shape, float(values), dtype=float)

        flattened = np.ravel(values)
        if flattened.shape[0] != parameter_values.shape[0]:
            raise ValueError(
                f"Parametric {axis_name}-component must evaluate to exactly one value per parameter sample."
            )
        return flattened.astype(float, copy=False)

    def render(
        self,
        view_id: str | None = None,
        *,
        use_batch_update: bool = True,
        refresh_parameter_snapshot: bool = True,
    ) -> None:
        """Compute and render the sampled parametric coordinates.
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            obj.render(...)
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        if not self._parametric_ready:
            return

        target_view = view_id or self._smart_figure.views.current_id
        self._set_visibility_for_target_view(target_view)
        if target_view not in self._view_ids:
            return
        if self._suspend_render or self._visible is not True:
            return

        fig = self._smart_figure
        if refresh_parameter_snapshot:
            refresh_context = getattr(
                fig.parameters, "refresh_render_parameter_context", None
            )
            if callable(refresh_context):
                refresh_context()

        if target_view != fig.views.current_id:
            fig.views[target_view].is_stale = True
            return

        num = self.samples or fig.samples or 500
        parameter_values = np.linspace(
            self._parameter_domain[0],
            self._parameter_domain[1],
            num=int(num),
        )
        if self._x_render_numeric_expression is None:  # pragma: no cover - defensive
            raise RuntimeError("Parametric plot x-expression is not initialized.")

        x_values = self._coerce_component_values(
            self._x_render_numeric_expression(parameter_values),
            parameter_values=parameter_values,
            axis_name="x",
        )
        y_values = self._coerce_component_values(
            self._render_numeric_expression(parameter_values),
            parameter_values=parameter_values,
            axis_name="y",
        )
        self._x_data = x_values.copy()
        self._y_data = y_values.copy()

        target_handle = self._handles[target_view].trace_handle
        if target_handle is None:
            return

        def _apply_trace_update() -> None:
            target_handle.x = x_values
            target_handle.y = y_values

        if use_batch_update:
            with fig.views[target_view].figure_widget.batch_update():
                _apply_trace_update()
        else:
            _apply_trace_update()

        pane = getattr(fig.views[target_view], "pane", None)
        getattr(pane, "refresh_plot_display", lambda **_kwargs: False)(
            reason=f"render:{type(self).__name__}"
        )

    def update(self, **kwargs: Any) -> None:
        """Update common plot state plus parametric-specific components.
        
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
        This member belongs to ``ParametricPlot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParametricPlot(...)
            obj.update(...)
        
        Discovery-oriented use::
        
            help(ParametricPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parametric-plotting.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
        - In a notebook or REPL, run ``help(ParametricPlot)`` and ``dir(ParametricPlot)`` to inspect adjacent members.
        """
        render_requested = False
        previous_suspend = self._suspend_render
        self._suspend_render = True
        try:
            common_keys = {
                "label",
                "visible",
                "samples",
                "sampling_points",
                "view",
                "color",
                "thickness",
                "width",
                "dash",
                "line",
                "opacity",
                "alpha",
                "trace",
                "autonormalization",
            }
            shared_kwargs = {key: kwargs[key] for key in common_keys if key in kwargs}
            if shared_kwargs:
                super().update(**shared_kwargs)
                render_requested = True

            if "parameter_domain" in kwargs:
                self._parameter_domain = self._coerce_parameter_domain(
                    kwargs["parameter_domain"]
                )
                render_requested = True

            function_keys = {
                "parameter_var",
                "parameters",
                "x_func",
                "y_func",
                "x_numeric_function",
                "y_numeric_function",
                "numeric_function",
            }
            if any(key in kwargs for key in function_keys):
                render_requested = True
                parameter_var = kwargs.get("parameter_var", self.parameter_var)
                parameters = tuple(kwargs.get("parameters", self.parameters))
                x_func = kwargs.get("x_func", self.x_expression)
                y_func = kwargs.get("y_func", self.y_expression)
                x_numeric_function = kwargs.get("x_numeric_function")
                y_numeric_function = kwargs.get(
                    "y_numeric_function", kwargs.get("numeric_function")
                )

                if y_numeric_function is not None:
                    self.set_numeric_function(
                        parameter_var,
                        y_numeric_function,
                        parameters=parameters,
                        symbolic_expression=y_func,
                    )
                else:
                    self.set_func(parameter_var, y_func, parameters)

                self._set_x_component(
                    parameter_var,
                    x_func,
                    parameters=parameters,
                    numeric_function=x_numeric_function,
                )
        finally:
            self._suspend_render = previous_suspend

        if render_requested:
            self.render()


def create_or_update_parametric_plot(
    figure: Figure,
    funcs: Sequence[Any],
    parameter_range: tuple[Any, Any, Any],
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: VisibleSpec = True,
    sampling_points: int | str | _FigureDefaultSentinel | None = None,
    color: str | None = None,
    thickness: int | float | None = None,
    width: int | float | None = None,
    dash: str | None = None,
    line: Mapping[str, Any] | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    trace: Mapping[str, Any] | None = None,
    autonormalization: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: PlotVarsSpec | None = None,
    samples: int | str | _FigureDefaultSentinel | None = None,
) -> Plot:
    """Create or update a :class:`ParametricPlot` on ``figure``.
    
    Full API
    --------
    ``create_or_update_parametric_plot(figure: Figure, funcs: Sequence[Any], parameter_range: tuple[Any, Any, Any], parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: VisibleSpec=True, sampling_points: int | str | _FigureDefaultSentinel | None=None, color: str | None=None, thickness: int | float | None=None, width: int | float | None=None, dash: str | None=None, line: Mapping[str, Any] | None=None, opacity: int | float | None=None, alpha: int | float | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, view: str | Sequence[str] | None=None, vars: PlotVarsSpec | None=None, samples: int | str | _FigureDefaultSentinel | None=None) -> Plot``
    
    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    
    funcs : Sequence[Any]
        Value for ``funcs`` in this API. Required.
    
    parameter_range : tuple[Any, Any, Any]
        Value for ``parameter_range`` in this API. Required.
    
    parameters : ParameterKeyOrKeys | None, optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``None``.
    
    id : str | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    label : str | None, optional
        Human-readable label used in UI or plotting output. Defaults to ``None``.
    
    visible : VisibleSpec, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    sampling_points : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    color : str | None, optional
        Explicit color value. Defaults to ``None``.
    
    thickness : int | float | None, optional
        Value for ``thickness`` in this API. Defaults to ``None``.
    
    width : int | float | None, optional
        Value for ``width`` in this API. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    line : Mapping[str, Any] | None, optional
        Value for ``line`` in this API. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    alpha : int | float | None, optional
        Value for ``alpha`` in this API. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    autonormalization : bool | None, optional
        Value for ``autonormalization`` in this API. Defaults to ``None``.
    
    view : str | Sequence[str] | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    vars : PlotVarsSpec | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    samples : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    Returns
    -------
    Plot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``parameters=None``: Parameter symbols/keys that should stay bound to this operation.
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``label=None``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``sampling_points=None``: Sampling density used when evaluating a curve or field.
    - ``color=None``: Explicit color value.
    - ``thickness=None``: Value for ``thickness`` in this API.
    - ``width=None``: Value for ``width`` in this API.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``line=None``: Value for ``line`` in this API.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``alpha=None``: Value for ``alpha`` in this API.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``autonormalization=None``: Value for ``autonormalization`` in this API.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    - ``vars=None``: Value for ``vars`` in this API.
    - ``samples=None``: Sampling density used when evaluating a curve or field.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_parametric_plot``. Parametric plots reuse the Figure/View pipeline but keep their own input normalization and snapshot semantics for x(t), y(t) curves.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_parametric_plot import create_or_update_parametric_plot
        result = create_or_update_parametric_plot(...)
    
    Discovery-oriented use::
    
        help(create_or_update_parametric_plot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parametric-plotting.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: inspect ``Figure.parametric_plot`` and the parametric-plotting guide for the x(t)/y(t) workflow.
    - In a notebook or REPL, run ``help(create_or_update_parametric_plot)`` and inspect sibling APIs in the same module.
    """
    id = resolve_plot_id(figure.plots, id)

    (
        parameter_var,
        x_func,
        y_func,
        x_numeric_fn,
        y_numeric_fn,
        inferred_parameters,
    ) = normalize_parametric_plot_inputs(
        funcs,
        parameter_range,
        vars=vars,
        id_hint=id,
    )

    if samples is not None and sampling_points is not None:
        lhs = None if _is_figure_default(samples) else figure._coerce_samples_value(samples)
        rhs = (
            None
            if _is_figure_default(sampling_points)
            else figure._coerce_samples_value(sampling_points)
        )
        if lhs != rhs:
            raise ValueError(
                "parametric_plot() received both samples= and sampling_points= with different values; use only one samples keyword."
            )

    samples_supplied = samples is not None or sampling_points is not None
    requested_samples = samples if samples is not None else sampling_points
    if requested_samples is None:
        explicit_plot_samples: int | str | _FigureDefaultSentinel | None = None
    elif _is_figure_default(requested_samples):
        explicit_plot_samples = "figure_default"
    else:
        explicit_plot_samples = figure._coerce_samples_value(requested_samples)

    opacity_supplied = opacity is not None or alpha is not None
    autonormalization_supplied = autonormalization is not None
    style_kwargs = validate_style_kwargs(
        {
            "color": color,
            "thickness": thickness,
            "width": width,
            "dash": dash,
            "line": line,
            "opacity": opacity,
            "alpha": alpha,
            "trace": trace,
            "autonormalization": autonormalization,
        },
        caller="parametric_plot()",
    )
    color = style_kwargs.get("color")
    thickness = style_kwargs.get("thickness")
    dash = style_kwargs.get("dash")
    line = style_kwargs.get("line")
    opacity = style_kwargs.get("opacity")
    trace = style_kwargs.get("trace")
    autonormalization = style_kwargs.get("autonormalization")

    if parameters is None:
        requested_parameter_keys: ParameterKeyOrKeys = tuple(inferred_parameters)
        plot_parameters = tuple(inferred_parameters)
    else:
        requested_parameter_keys = parameters
        plot_parameters = expand_parameter_keys_to_symbols(
            parameters,
            inferred_parameters,
            role="parametric plot parameters",
        )

    if requested_parameter_keys:
        figure.parameter(requested_parameter_keys)

    if figure._sync_sidebar_visibility():
        figure._request_active_view_reflow("sidebar_visibility")

    if id in figure.plots and not isinstance(figure.plots[id], ParametricPlot):
        remove_plot_from_figure(figure, id)

    requested_color = explicit_style_color(color=color, line=line, trace=trace)
    if id in figure.plots:
        update_dont_create = True
        if requested_color is None and figure.plots[id].color is None:
            color = figure._auto_plot_color(plot_id=id)
    else:
        update_dont_create = False
        if requested_color is None:
            color = figure._auto_plot_color()

    parameter_domain = (parameter_range[1], parameter_range[2])

    if update_dont_create:
        update_kwargs: dict[str, Any] = {
            "parameter_var": parameter_var,
            "parameter_domain": parameter_domain,
            "x_func": x_func,
            "y_func": y_func,
            "parameters": plot_parameters,
            "visible": visible,
            "samples": (explicit_plot_samples if samples_supplied else None),
            "color": color,
            "thickness": thickness,
            "dash": dash,
            "line": line,
            "trace": trace,
            "view": view,
        }
        if opacity_supplied:
            update_kwargs["opacity"] = opacity
        if autonormalization_supplied:
            update_kwargs["autonormalization"] = autonormalization
        if x_numeric_fn is not None:
            update_kwargs["x_numeric_function"] = x_numeric_fn
        if y_numeric_fn is not None:
            update_kwargs["y_numeric_function"] = y_numeric_fn
        if label is not None:
            update_kwargs["label"] = label
        figure.plots[id].update(**update_kwargs)
        plot = figure.plots[id]
        figure._legend.on_plot_updated(plot)
        if figure._sync_sidebar_visibility():
            figure._request_active_view_reflow("sidebar_visibility")
        return plot

    view_ids = normalize_view_ids(view, default_view_id=figure.views.current_id)
    create_plot_samples: int | str | _FigureDefaultSentinel | None = explicit_plot_samples
    if (
        not samples_supplied
        and figure._default_samples is not None
        and figure.default_samples != figure.samples
    ):
        create_plot_samples = figure.default_samples

    plot = ParametricPlot(
        parameter_var=parameter_var,
        x_func=x_func,
        y_func=y_func,
        smart_figure=figure,
        parameters=plot_parameters,
        parameter_domain=parameter_domain,
        samples=create_plot_samples,
        label=(id if label is None else label),
        visible=visible,
        color=color,
        thickness=thickness,
        dash=dash,
        line=line,
        opacity=opacity,
        trace=trace,
        autonormalization=autonormalization,
        plot_id=id,
        view_ids=view_ids,
        x_numeric_function=x_numeric_fn,
        y_numeric_function=y_numeric_fn,
    )
    figure.plots[id] = plot
    figure._legend.on_plot_added(plot)
    if figure._sync_sidebar_visibility():
        figure._request_active_view_reflow("sidebar_visibility")
    return plot
