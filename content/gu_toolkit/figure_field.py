"""Scalar-field runtime model for contour, density, and temperature plots.

This module introduces :class:`ScalarFieldPlot`, a sibling runtime type to the
existing 1D :class:`gu_toolkit.figure_plot.Plot`. Scalar fields render one
symbolic or callable expression ``z = f(x, y)`` over a rectangular 2D grid and
own either a Plotly ``Contour`` or ``Heatmap`` trace per view.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import plotly.graph_objects as go
from plotly.colors import get_colorscale, sample_colorscale
import sympy as sp
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

from .FieldPlotSnapshot import FieldPlotSnapshot
from .InputConvert import InputConvert
from .figure_context import _is_figure_default
from .figure_field_normalization import normalize_field_inputs
from .figure_field_style import field_palette_option_docs, field_style_option_docs, resolve_field_colorscale, validate_field_style_kwargs
from .figure_plot_helpers import normalize_view_ids, remove_plot_from_figure, resolve_plot_id
from .figure_types import RangeLike, VisibleSpec
from .numpify import DYNAMIC_PARAMETER, NumericFunction, numpify_cached
from .parameter_keys import ParameterKeyOrKeys, expand_parameter_keys_to_symbols

if TYPE_CHECKING:
    from .Figure import Figure

FieldRenderMode = Literal["contour", "heatmap"]
FieldGrid = tuple[int, int]


@dataclass
class FieldPlotHandle:
    """Per-view runtime handle for a scalar-field trace binding.
    
    Full API
    --------
    ``FieldPlotHandle(plot_id: str, view_id: str, trace_handle: go.Contour | go.Heatmap | None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    plot_id : str
        Stable plot identifier used for lookup or update. Required.
    
    view_id : str
        Identifier for the relevant view inside a figure. Required.
    
    trace_handle : go.Contour | go.Heatmap | None
        Value for ``trace_handle`` in this API. Required.
    
    Returns
    -------
    FieldPlotHandle
        New ``FieldPlotHandle`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``FieldPlotHandle`` lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_field import FieldPlotHandle
        obj = FieldPlotHandle(...)
    
    Discovery-oriented use::
    
        help(FieldPlotHandle)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(FieldPlotHandle)`` and ``dir(FieldPlotHandle)`` to inspect adjacent members.
    """

    plot_id: str
    view_id: str
    trace_handle: go.Contour | go.Heatmap | None


class ScalarFieldPlot:
    """A 2D scalar field rendered as a contour or heatmap trace.
    
    Full API
    --------
    ``ScalarFieldPlot(x_var: Symbol, y_var: Symbol, func: Expr, smart_figure: Figure, parameters: Sequence[Symbol]=(), x_domain: RangeLike | None=None, y_domain: RangeLike | None=None, grid: tuple[int | str, int | str] | None=None, label: str='', visible: VisibleSpec=True, render_mode: FieldRenderMode='heatmap', preset: str | None=None, colorscale: Any | None=None, z_range: RangeLike | None=None, z_step: int | float | None=None, under_color: str | None=None, over_color: str | None=None, show_colorbar: bool | None=None, opacity: int | float | None=None, reversescale: bool | None=None, colorbar: Mapping[str, Any] | None=None, trace: Mapping[str, Any] | None=None, levels: int | None=None, level_step: int | float | None=None, level_start: int | float | None=None, level_end: int | float | None=None, filled: bool | None=None, show_labels: bool | None=None, line_color: str | None=None, line_width: int | float | None=None, line_dash: str | None=None, smoothing: str | bool | None=None, connectgaps: bool | None=None, plot_id: str='', view_ids: Sequence[str] | None=None, numeric_function: NumericFunction | None=None)``
    
    Public members exposed from this class: ``set_func``, ``set_numeric_function``, ``figure``, ``render_mode``, ``preset``,
        ``x_var``, ``y_var``, ``symbolic_expression``, ``numeric_expression``,
        ``parameters``, ``views``, ``label``, ``color``, ``opacity``, ``colorscale``,
        ``z_range``, ``z_step``, ``under_color``, ``over_color``, ``show_colorbar``,
        ``reversescale``, ``colorbar``, ``levels``, ``level_step``, ``level_start``,
        ``level_end``, ``filled``, ``show_labels``, ``line_color``, ``line_width``,
        ``line_dash``, ``dash``, ``smoothing``, ``connectgaps``, ``x_domain``, ``y_domain``,
        ``grid``, ``visible``, ``x_data``, ``y_data``, ``z_data``, ``add_to_view``,
        ``remove_from_view``, ``add_views``, ``remove_views``, ``snapshot``, ``render``,
        ``update``
    
    Parameters
    ----------
    x_var : Symbol
        Symbol used as the horizontal variable. Required.
    
    y_var : Symbol
        Symbol used as the vertical variable. Required.
    
    func : Expr
        Symbolic expression or callable to evaluate. Required.
    
    smart_figure : Figure
        Value for ``smart_figure`` in this API. Required.
    
    parameters : Sequence[Symbol], optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``()``.
    
    x_domain : RangeLike | None, optional
        Numeric x-domain used for evaluation or rendering. Defaults to ``None``.
    
    y_domain : RangeLike | None, optional
        Numeric y-domain used for evaluation or rendering. Defaults to ``None``.
    
    grid : tuple[int | str, int | str] | None, optional
        Grid resolution or grid specification used for field sampling. Defaults to ``None``.
    
    label : str, optional
        Human-readable label used in UI or plotting output. Defaults to ``''``.
    
    visible : VisibleSpec, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    render_mode : FieldRenderMode, optional
        Rendering mode or plot kind to create. Defaults to ``'heatmap'``.
    
    preset : str | None, optional
        Named preset that chooses a particular rendering style. Defaults to ``None``.
    
    colorscale : Any | None, optional
        Colorscale specification passed to the renderer. Defaults to ``None``.
    
    z_range : RangeLike | None, optional
        Numeric value range used for scalar-field color mapping. Defaults to ``None``.
    
    z_step : int | float | None, optional
        Numeric spacing between scalar-field contour or color levels. Defaults to ``None``.
    
    under_color : str | None, optional
        Color used below the represented scalar range. Defaults to ``None``.
    
    over_color : str | None, optional
        Color used above the represented scalar range. Defaults to ``None``.
    
    show_colorbar : bool | None, optional
        Boolean flag controlling whether a colorbar is shown. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    reversescale : bool | None, optional
        Boolean flag controlling whether the colorscale is reversed. Defaults to ``None``.
    
    colorbar : Mapping[str, Any] | None, optional
        Renderer-specific colorbar configuration mapping. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    levels : int | None, optional
        Number of contour or scalar levels to generate. Defaults to ``None``.
    
    level_step : int | float | None, optional
        Spacing between contour or scalar levels. Defaults to ``None``.
    
    level_start : int | float | None, optional
        First contour/scalar level to include. Defaults to ``None``.
    
    level_end : int | float | None, optional
        Last contour/scalar level to include. Defaults to ``None``.
    
    filled : bool | None, optional
        Boolean flag controlling whether contour regions are filled. Defaults to ``None``.
    
    show_labels : bool | None, optional
        Boolean flag controlling whether labels are drawn on contour lines. Defaults to ``None``.
    
    line_color : str | None, optional
        Explicit line color for contour or curve rendering. Defaults to ``None``.
    
    line_width : int | float | None, optional
        Line width used for contour or curve rendering. Defaults to ``None``.
    
    line_dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    smoothing : str | bool | None, optional
        Smoothing option passed to the renderer or interpolation layer. Defaults to ``None``.
    
    connectgaps : bool | None, optional
        Boolean flag controlling whether missing samples are connected. Defaults to ``None``.
    
    plot_id : str, optional
        Stable plot identifier used for lookup or update. Defaults to ``''``.
    
    view_ids : Sequence[str] | None, optional
        Collection of view identifiers associated with this object or update. Defaults to ``None``.
    
    numeric_function : NumericFunction | None, optional
        Precompiled numeric callable used during rendering or evaluation. Defaults to ``None``.
    
    Returns
    -------
    ScalarFieldPlot
        New ``ScalarFieldPlot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``parameters=()``: Parameter symbols/keys that should stay bound to this operation.
    - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
    - ``y_domain=None``: Numeric y-domain used for evaluation or rendering.
    - ``grid=None``: Grid resolution or grid specification used for field sampling.
    - ``label=''``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``render_mode='heatmap'``: Rendering mode or plot kind to create.
    - ``preset=None``: Named preset that chooses a particular rendering style.
    - ``colorscale=None``: Colorscale specification passed to the renderer.
    - ``z_range=None``: Numeric value range used for scalar-field color mapping.
    - ``z_step=None``: Numeric spacing between scalar-field contour or color levels.
    - ``under_color=None``: Color used below the represented scalar range.
    - ``over_color=None``: Color used above the represented scalar range.
    - ``show_colorbar=None``: Boolean flag controlling whether a colorbar is shown.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``reversescale=None``: Boolean flag controlling whether the colorscale is reversed.
    - ``colorbar=None``: Renderer-specific colorbar configuration mapping.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``levels=None``: Number of contour or scalar levels to generate.
    - ``level_step=None``: Spacing between contour or scalar levels.
    - ``level_start=None``: First contour/scalar level to include.
    - ``level_end=None``: Last contour/scalar level to include.
    - ``filled=None``: Boolean flag controlling whether contour regions are filled.
    - ``show_labels=None``: Boolean flag controlling whether labels are drawn on contour lines.
    - ``line_color=None``: Explicit line color for contour or curve rendering.
    - ``line_width=None``: Line width used for contour or curve rendering.
    - ``line_dash=None``: Dash pattern used for contour or curve rendering.
    - ``smoothing=None``: Smoothing option passed to the renderer or interpolation layer.
    - ``connectgaps=None``: Boolean flag controlling whether missing samples are connected.
    - ``plot_id=''``: Stable plot identifier used for lookup or update.
    - ``view_ids=None``: Collection of view identifiers associated with this object or update.
    - ``numeric_function=None``: Precompiled numeric callable used during rendering or evaluation.
    
    Architecture note
    -----------------
    ``ScalarFieldPlot`` lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_field import ScalarFieldPlot
        obj = ScalarFieldPlot(...)
    
    Discovery-oriented use::
    
        help(ScalarFieldPlot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
    """

    DEFAULT_GRID: FieldGrid = (120, 120)
    supports_style_dialog: bool = False

    def __init__(
        self,
        x_var: Symbol,
        y_var: Symbol,
        func: Expr,
        smart_figure: Figure,
        parameters: Sequence[Symbol] = (),
        x_domain: RangeLike | None = None,
        y_domain: RangeLike | None = None,
        grid: tuple[int | str, int | str] | None = None,
        label: str = "",
        visible: VisibleSpec = True,
        render_mode: FieldRenderMode = "heatmap",
        preset: str | None = None,
        colorscale: Any | None = None,
        z_range: RangeLike | None = None,
        z_step: int | float | None = None,
        under_color: str | None = None,
        over_color: str | None = None,
        show_colorbar: bool | None = None,
        opacity: int | float | None = None,
        reversescale: bool | None = None,
        colorbar: Mapping[str, Any] | None = None,
        trace: Mapping[str, Any] | None = None,
        levels: int | None = None,
        level_step: int | float | None = None,
        level_start: int | float | None = None,
        level_end: int | float | None = None,
        filled: bool | None = None,
        show_labels: bool | None = None,
        line_color: str | None = None,
        line_width: int | float | None = None,
        line_dash: str | None = None,
        smoothing: str | bool | None = None,
        connectgaps: bool | None = None,
        plot_id: str = "",
        view_ids: Sequence[str] | None = None,
        *,
        numeric_function: NumericFunction | None = None,
    ) -> None:
        self._smart_figure = smart_figure
        self.id = plot_id or label or "field"
        self._label = str(label)
        self._handles: dict[str, FieldPlotHandle] = {}
        self._view_ids = set(view_ids or (self._smart_figure.views.current_id,))
        self._visible: VisibleSpec = visible
        self._x_axis_values: np.ndarray | None = None
        self._y_axis_values: np.ndarray | None = None
        self._z_data: np.ndarray | None = None
        self._suspend_render = True

        self._render_mode: FieldRenderMode = self._coerce_render_mode(render_mode)
        self._preset = self._coerce_preset(preset, render_mode=self._render_mode)
        self._colorscale: Any | None = None
        self._z_range: tuple[float, float] | None = None
        self._z_step: float | None = None
        self._under_color: str | None = None
        self._over_color: str | None = None
        self._show_colorbar: bool = self._default_show_colorbar(self._render_mode)
        self._opacity: float | None = None
        self._reversescale: bool = False
        self._colorbar: dict[str, Any] | None = None
        self._trace_overrides: dict[str, Any] | None = None
        self._levels: int | None = None
        self._level_step: float | None = None
        self._level_start: float | None = None
        self._level_end: float | None = None
        self._filled: bool = self._default_filled(self._render_mode)
        self._show_labels: bool = False
        self._line_color: str | None = None
        self._line_width: float | None = None
        self._line_dash: str | None = None
        self._smoothing: str | bool | None = None
        self._connectgaps: bool | None = None
        self._apply_creation_defaults(
            colorscale=colorscale,
            z_range=z_range,
            z_step=z_step,
            under_color=under_color,
            over_color=over_color,
            show_colorbar=show_colorbar,
            opacity=opacity,
            reversescale=reversescale,
            colorbar=colorbar,
            trace=trace,
            levels=levels,
            level_step=level_step,
            level_start=level_start,
            level_end=level_end,
            filled=filled,
            show_labels=show_labels,
            line_color=line_color,
            line_width=line_width,
            line_dash=line_dash,
            smoothing=smoothing,
            connectgaps=connectgaps,
        )

        for view_id in sorted(self._view_ids):
            self._create_trace_handle(view_id=view_id, label=label)

        if numeric_function is None:
            self.set_func(x_var, y_var, func, parameters)
        else:
            self.set_numeric_function(
                x_var,
                y_var,
                numeric_function,
                parameters=parameters,
                symbolic_expression=func,
            )

        self.x_domain = x_domain
        self.y_domain = y_domain
        self.grid = grid
        self._suspend_render = False
        self.render()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_render_mode(value: Any) -> FieldRenderMode:
        raw = str(value or "heatmap").strip().lower()
        if raw not in {"contour", "heatmap"}:
            raise ValueError(
                "scalar_field() render_mode must be 'contour' or 'heatmap'."
            )
        return raw  # type: ignore[return-value]

    @staticmethod
    def _coerce_preset(value: str | None, *, render_mode: FieldRenderMode) -> str | None:
        if value is None:
            return None
        raw = str(value).strip().lower()
        if raw == "temperature":
            if render_mode != "heatmap":
                raise ValueError("temperature preset requires render_mode='heatmap'.")
            return raw
        raise ValueError(f"Unknown scalar-field preset: {value!r}")

    @staticmethod
    def _default_show_colorbar(render_mode: FieldRenderMode) -> bool:
        return render_mode == "heatmap"

    @staticmethod
    def _default_filled(render_mode: FieldRenderMode) -> bool:
        return render_mode == "heatmap"

    @staticmethod
    def _coerce_optional_mapping(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return dict(value)

    @staticmethod
    def _coerce_optional_range(value: RangeLike | None, *, axis_name: str) -> tuple[float, float] | None:
        if value is None:
            return None
        lower = float(InputConvert(value[0], float))
        upper = float(InputConvert(value[1], float))
        if lower > upper:
            raise ValueError(f"{axis_name}_min must be <= {axis_name}_max")
        return (lower, upper)

    @staticmethod
    def _coerce_optional_float(value: int | float | str | None) -> float | None:
        if value is None:
            return None
        return float(InputConvert(value, float))

    @staticmethod
    def _coerce_grid(value: tuple[int | str, int | str] | None) -> FieldGrid | None:
        if value is None:
            return None
        if len(value) != 2:
            raise ValueError("scalar_field() grid must have shape (nx, ny).")
        nx = int(InputConvert(value[0], int))
        ny = int(InputConvert(value[1], int))
        if nx <= 0 or ny <= 0:
            raise ValueError("scalar_field() grid values must be positive integers.")
        return (nx, ny)

    def _apply_creation_defaults(
        self,
        *,
        colorscale: Any | None,
        z_range: RangeLike | None,
        z_step: int | float | None,
        under_color: str | None,
        over_color: str | None,
        show_colorbar: bool | None,
        opacity: int | float | None,
        reversescale: bool | None,
        colorbar: Mapping[str, Any] | None,
        trace: Mapping[str, Any] | None,
        levels: int | None,
        level_step: int | float | None,
        level_start: int | float | None,
        level_end: int | float | None,
        filled: bool | None,
        show_labels: bool | None,
        line_color: str | None,
        line_width: int | float | None,
        line_dash: str | None,
        smoothing: str | bool | None,
        connectgaps: bool | None,
    ) -> None:
        if self._preset == "temperature" and colorscale is None:
            colorscale = "hot"
        if self._preset == "temperature" and show_colorbar is None:
            show_colorbar = True
        if self._preset == "temperature" and colorbar is None:
            colorbar = {"title": {"text": "Temperature"}}

        if colorscale is not None:
            self._colorscale = colorscale
        self._z_range = self._coerce_optional_range(z_range, axis_name="z")
        self._z_step = self._coerce_optional_float(z_step)
        if under_color is not None:
            self._under_color = str(under_color)
        if over_color is not None:
            self._over_color = str(over_color)
        if show_colorbar is not None:
            self._show_colorbar = bool(show_colorbar)
        if opacity is not None:
            self._opacity = self._coerce_opacity(opacity)
        if reversescale is not None:
            self._reversescale = bool(reversescale)
        self._colorbar = self._coerce_optional_mapping(colorbar)
        self._trace_overrides = self._coerce_optional_mapping(trace)
        if levels is not None:
            self._levels = int(InputConvert(levels, int))
        self._level_step = self._coerce_optional_float(level_step)
        self._level_start = self._coerce_optional_float(level_start)
        self._level_end = self._coerce_optional_float(level_end)
        if filled is not None:
            self._filled = bool(filled)
        if show_labels is not None:
            self._show_labels = bool(show_labels)
        if line_color is not None:
            self._line_color = str(line_color)
        if line_width is not None:
            self._line_width = float(InputConvert(line_width, float))
        if line_dash is not None:
            self._line_dash = str(line_dash)
        if smoothing is not None:
            self._smoothing = smoothing
        if connectgaps is not None:
            self._connectgaps = bool(connectgaps)

    @staticmethod
    def _coerce_opacity(value: int | float | None) -> float | None:
        if value is None:
            return None
        opacity = float(InputConvert(value, float))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        return opacity

    @staticmethod
    def _finite_z_bounds(values: np.ndarray | None) -> tuple[float, float] | None:
        if values is None:
            return None
        array = np.asarray(values, dtype=float)
        finite_mask = np.isfinite(array)
        if not np.any(finite_mask):
            return None
        finite_values = array[finite_mask]
        return float(np.min(finite_values)), float(np.max(finite_values))

    def _resolved_base_colorscale(self, *, force_default: bool = False) -> Any | None:
        resolved = resolve_field_colorscale(self._colorscale)
        if resolved is not None:
            return resolved
        if not force_default:
            return None
        default_name = "hot" if self._preset == "temperature" else "Viridis"
        return resolve_field_colorscale(default_name)

    @staticmethod
    def _coerce_colorscale_stops(colorscale: Any | None) -> list[tuple[float, str]] | None:
        if colorscale is None:
            return None
        resolved = resolve_field_colorscale(colorscale)
        if isinstance(resolved, str):
            try:
                return [(float(stop), str(color)) for stop, color in get_colorscale(resolved)]
            except Exception:
                return None
        try:
            result = [(float(item[0]), str(item[1])) for item in list(resolved)]
        except Exception:
            return None
        return result or None

    @classmethod
    def _build_segmented_colorscale(
        cls,
        base_colorscale: Any,
        *,
        base_min: float,
        base_max: float,
        overall_min: float,
        overall_max: float,
        under_color: str | None,
        over_color: str | None,
    ) -> Any:
        if overall_max <= overall_min:
            return base_colorscale
        base_stops = cls._coerce_colorscale_stops(base_colorscale)
        if not base_stops:
            return base_colorscale

        span = overall_max - overall_min
        inner_start = (base_min - overall_min) / span
        inner_end = (base_max - overall_min) / span
        scale: list[tuple[float, str]] = []

        def add(stop: float, color: str) -> None:
            scale.append((max(0.0, min(1.0, float(stop))), str(color)))

        if under_color is not None:
            add(0.0, under_color)
            add(inner_start, under_color)

        if inner_end <= inner_start:
            midpoint_color = str(sample_colorscale(base_stops, [0.5])[0])
            add(inner_start, midpoint_color)
            add(inner_end, midpoint_color)
        else:
            for stop, color in base_stops:
                mapped = inner_start + float(stop) * (inner_end - inner_start)
                add(mapped, color)

        if over_color is not None:
            add(inner_end, over_color)
            add(1.0, over_color)

        return scale or base_colorscale

    @staticmethod
    def _build_discrete_colorscale(
        base_colorscale: Any,
        *,
        boundaries: np.ndarray,
        overall_min: float,
        overall_max: float,
        under_color: str | None,
        over_color: str | None,
    ) -> Any:
        if overall_max <= overall_min:
            return base_colorscale
        boundaries_array = np.asarray(boundaries, dtype=float)
        if boundaries_array.size < 2:
            return base_colorscale

        centers = (boundaries_array[:-1] + boundaries_array[1:]) / 2.0
        if centers.size == 0:
            return base_colorscale
        if boundaries_array[-1] == boundaries_array[0]:
            sample_points = [0.5] * int(centers.size)
        else:
            sample_points = [
                float((center - boundaries_array[0]) / (boundaries_array[-1] - boundaries_array[0]))
                for center in centers
            ]
        sampled_colors = [str(color) for color in sample_colorscale(base_colorscale, sample_points)]
        span = overall_max - overall_min
        scale: list[tuple[float, str]] = []

        def add(stop: float, color: str) -> None:
            scale.append((max(0.0, min(1.0, float(stop))), str(color)))

        if under_color is not None:
            transition = (boundaries_array[0] - overall_min) / span
            add(0.0, under_color)
            add(transition, under_color)

        for low, high, color in zip(boundaries_array[:-1], boundaries_array[1:], sampled_colors):
            start = (float(low) - overall_min) / span
            end = (float(high) - overall_min) / span
            add(start, color)
            add(end, color)

        if over_color is not None:
            transition = (boundaries_array[-1] - overall_min) / span
            add(transition, over_color)
            add(1.0, over_color)

        return scale or base_colorscale

    def _build_heatmap_style_config(
        self,
        z_values: np.ndarray | None,
    ) -> tuple[np.ndarray | None, Any | None, tuple[float, float] | None, dict[str, Any] | None]:
        special_heatmap = self._render_mode == "heatmap" and (
            self._z_step is not None or self._under_color is not None or self._over_color is not None
        )
        base_colorscale = self._resolved_base_colorscale(force_default=special_heatmap)
        colorbar_payload = None if self._colorbar is None else dict(self._colorbar)
        effective_range = self._z_range

        if not special_heatmap:
            return z_values, base_colorscale, effective_range, colorbar_payload

        if effective_range is None:
            effective_range = self._finite_z_bounds(z_values)
        if effective_range is None:
            return z_values, base_colorscale, None, colorbar_payload

        base_min, base_max = effective_range
        step = self._z_step
        if step is not None:
            step = float(step)
            if base_max == base_min:
                base_max = base_min + step

        span = base_max - base_min
        margin = step if step is not None else (span / 256.0 if span > 0 else 1.0)
        under_margin = margin if self._under_color is not None else 0.0
        over_margin = margin if self._over_color is not None else 0.0
        effective_min = base_min - under_margin
        effective_max = base_max + over_margin
        display_values = None if z_values is None else np.asarray(z_values, dtype=float).copy()

        if step is not None:
            boundaries: list[float] = [base_min]
            current = base_min
            tolerance = abs(step) * 1e-12
            while current + step < base_max - tolerance:
                current = current + step
                boundaries.append(current)
            if boundaries[-1] < base_max:
                boundaries.append(base_max)
            boundary_values = np.asarray(boundaries, dtype=float)
            if boundary_values.size < 2:
                boundary_values = np.asarray([base_min, base_max], dtype=float)
            centers = (boundary_values[:-1] + boundary_values[1:]) / 2.0

            if display_values is not None:
                raw = np.asarray(z_values, dtype=float)
                finite_mask = np.isfinite(raw)
                under_mask = finite_mask & (raw < base_min)
                over_mask = finite_mask & (raw > base_max)
                in_range_mask = finite_mask & ~under_mask & ~over_mask
                clipped = np.clip(raw, base_min, base_max)
                indices = np.floor((clipped - base_min) / step).astype(int)
                indices = np.clip(indices, 0, centers.size - 1)
                if np.any(in_range_mask):
                    display_values[in_range_mask] = centers[indices[in_range_mask]]
                if np.any(under_mask):
                    display_values[under_mask] = (
                        base_min - under_margin / 2.0
                        if self._under_color is not None
                        else centers[0]
                    )
                if np.any(over_mask):
                    display_values[over_mask] = (
                        base_max + over_margin / 2.0
                        if self._over_color is not None
                        else centers[-1]
                    )

            effective_colorscale = self._build_discrete_colorscale(
                base_colorscale,
                boundaries=boundary_values,
                overall_min=effective_min,
                overall_max=effective_max,
                under_color=self._under_color,
                over_color=self._over_color,
            )
            if colorbar_payload is None:
                colorbar_payload = {}
            colorbar_payload.setdefault("tickmode", "linear")
            colorbar_payload.setdefault("tick0", base_min)
            colorbar_payload.setdefault("dtick", step)
            return (
                display_values,
                effective_colorscale,
                (effective_min, effective_max),
                colorbar_payload,
            )

        if display_values is not None:
            raw = np.asarray(z_values, dtype=float)
            finite_mask = np.isfinite(raw)
            under_mask = finite_mask & (raw < base_min)
            over_mask = finite_mask & (raw > base_max)
            if np.any(under_mask):
                display_values[under_mask] = (
                    base_min - under_margin / 2.0 if self._under_color is not None else base_min
                )
            if np.any(over_mask):
                display_values[over_mask] = (
                    base_max + over_margin / 2.0 if self._over_color is not None else base_max
                )

        effective_colorscale = base_colorscale
        if self._under_color is not None or self._over_color is not None:
            effective_colorscale = self._build_segmented_colorscale(
                base_colorscale,
                base_min=base_min,
                base_max=base_max,
                overall_min=effective_min,
                overall_max=effective_max,
                under_color=self._under_color,
                over_color=self._over_color,
            )

        return (
            display_values,
            effective_colorscale,
            (effective_min, effective_max),
            colorbar_payload,
        )

    # ------------------------------------------------------------------
    # Trace/view ownership
    # ------------------------------------------------------------------

    def _iter_trace_handles(self) -> Sequence[go.Contour | go.Heatmap]:
        return tuple(
            handle.trace_handle
            for handle in self._handles.values()
            if handle.trace_handle is not None
        )

    def _reference_trace_handle(self) -> go.Contour | go.Heatmap | None:
        active = self._handles.get(self._smart_figure.views.current_id)
        if active is not None and active.trace_handle is not None:
            return active.trace_handle
        for trace_handle in self._iter_trace_handles():
            return trace_handle
        return None

    def _build_trace_style_payload(
        self,
        *,
        z_values: np.ndarray | None = None,
    ) -> tuple[dict[str, Any], np.ndarray | None]:
        payload: dict[str, Any] = {}
        display_values = z_values
        effective_colorscale = self._resolved_base_colorscale(force_default=False)
        effective_z_range = self._z_range
        colorbar_payload = None if self._colorbar is None else dict(self._colorbar)

        if self._render_mode == "heatmap":
            display_values, effective_colorscale, effective_z_range, colorbar_payload = (
                self._build_heatmap_style_config(z_values)
            )

        if effective_colorscale is not None:
            payload["colorscale"] = effective_colorscale
        if effective_z_range is not None:
            payload["zmin"] = effective_z_range[0]
            payload["zmax"] = effective_z_range[1]
        payload["showscale"] = self._show_colorbar
        if self._opacity is not None:
            payload["opacity"] = self._opacity
        if self._reversescale:
            payload["reversescale"] = True
        if colorbar_payload:
            payload["colorbar"] = dict(colorbar_payload)
        if self._connectgaps is not None:
            payload["connectgaps"] = self._connectgaps

        if self._render_mode == "contour":
            contours_payload: dict[str, Any] = {
                "coloring": "fill" if self._filled else "lines",
                "showlabels": self._show_labels,
            }
            if self._level_step is not None:
                contours_payload["size"] = self._level_step
                start = self._level_start if self._level_start is not None else None
                end = self._level_end if self._level_end is not None else None
                if start is None and self._z_range is not None:
                    start = self._z_range[0]
                if end is None and self._z_range is not None:
                    end = self._z_range[1]
                if start is not None:
                    contours_payload["start"] = start
                if end is not None:
                    contours_payload["end"] = end
            elif self._levels is not None:
                payload["ncontours"] = self._levels
            payload["contours"] = contours_payload
            line_payload: dict[str, Any] = {}
            if self._line_color is not None:
                line_payload["color"] = self._line_color
            if self._line_width is not None:
                line_payload["width"] = self._line_width
            if self._line_dash is not None:
                line_payload["dash"] = self._line_dash
            if line_payload:
                payload["line"] = line_payload
        else:
            if self._smoothing is not None:
                payload["zsmooth"] = self._smoothing

        if self._trace_overrides:
            payload.update(dict(self._trace_overrides))
        return payload, display_values

    def _create_trace_handle(self, *, view_id: str, label: str) -> FieldPlotHandle:
        figure_widget = self._smart_figure.views[view_id].figure_widget
        style_payload, _ = self._build_trace_style_payload()
        trace: go.Contour | go.Heatmap
        if self._render_mode == "contour":
            trace = go.Contour(
                x=[],
                y=[],
                z=[],
                name=label,
                visible=self._visible,
                **style_payload,
            )
        else:
            trace = go.Heatmap(
                x=[],
                y=[],
                z=[],
                name=label,
                visible=self._visible,
                **style_payload,
            )
        figure_widget.add_trace(trace)
        trace_handle = figure_widget.data[-1]
        handle = FieldPlotHandle(plot_id=self.id, view_id=view_id, trace_handle=trace_handle)
        self._handles[view_id] = handle
        return handle

    def _apply_style_to_all_trace_handles(self) -> None:
        style_payload, _ = self._build_trace_style_payload(z_values=self._z_data)
        for trace_handle in self._iter_trace_handles():
            trace_handle.update(**style_payload)
            trace_handle.visible = self._visible
            trace_handle.name = self.label

    def _set_visibility_for_target_view(self, target_view: str) -> None:
        handle = self._handles.get(target_view)
        if handle is not None and handle.trace_handle is not None:
            handle.trace_handle.visible = self._visible

    def _remove_trace_handle(self, *, view_id: str) -> None:
        handle = self._handles.get(view_id)
        if handle is None or handle.trace_handle is None:
            return
        figure_widget = self._smart_figure.views[view_id].figure_widget
        figure_widget.data = tuple(
            trace for trace in figure_widget.data if trace is not handle.trace_handle
        )
        handle.trace_handle = None

    # ------------------------------------------------------------------
    # Symbolic/numeric binding
    # ------------------------------------------------------------------

    def set_func(
        self,
        x_var: Symbol,
        y_var: Symbol,
        func: Expr,
        parameters: Sequence[Symbol] = (),
    ) -> None:
        """Set func.
        
        Full API
        --------
        ``obj.set_func(x_var: Symbol, y_var: Symbol, func: Expr, parameters: Sequence[Symbol]=()) -> None``
        
        Parameters
        ----------
        x_var : Symbol
            Symbol used as the horizontal variable. Required.
        
        y_var : Symbol
            Symbol used as the vertical variable. Required.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.set_func(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        parameters = list(parameters)
        self._numpified = numpify_cached(func, vars=[x_var, y_var, *parameters])
        self._x_var = x_var
        self._y_var = y_var
        self._func = sp.sympify(func)
        self._rebind_numeric_expressions()

    def set_numeric_function(
        self,
        x_var: Symbol,
        y_var: Symbol,
        numeric_function: NumericFunction,
        parameters: Sequence[Symbol] = (),
        *,
        symbolic_expression: Expr | None = None,
    ) -> None:
        """Set numeric function.
        
        Full API
        --------
        ``obj.set_numeric_function(x_var: Symbol, y_var: Symbol, numeric_function: NumericFunction, parameters: Sequence[Symbol]=(), *, symbolic_expression: Expr | None=None) -> None``
        
        Parameters
        ----------
        x_var : Symbol
            Symbol used as the horizontal variable. Required.
        
        y_var : Symbol
            Symbol used as the vertical variable. Required.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.set_numeric_function(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        self._numpified = numeric_function
        self._x_var = x_var
        self._y_var = y_var
        if numeric_function.symbolic is not None:
            self._func = sp.sympify(numeric_function.symbolic)
        elif symbolic_expression is not None:
            self._func = sp.sympify(symbolic_expression)
        elif isinstance(getattr(self, "_func", None), sp.Expr):
            self._func = self._func
        else:
            self._func = sp.Symbol("field_numeric")
        self._rebind_numeric_expressions()

    def _rebind_numeric_expressions(self) -> None:
        dynamic_symbols = tuple(
            sym for sym in self._numpified.all_vars if sym not in {self._x_var, self._y_var}
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

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def figure(self) -> Figure:
        """Work with figure on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.figure
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._smart_figure

    @property
    def render_mode(self) -> FieldRenderMode:
        """Render mode.
        
        Full API
        --------
        ``obj.render_mode -> FieldRenderMode``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        FieldRenderMode
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.render_mode
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._render_mode

    @property
    def preset(self) -> str | None:
        """Work with preset on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.preset -> str | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.preset
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._preset

    @property
    def x_var(self) -> Symbol:
        """Work with x var on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.x_var -> Symbol``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.x_var
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._x_var

    @property
    def y_var(self) -> Symbol:
        """Work with y var on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.y_var -> Symbol``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.y_var
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._y_var

    @property
    def symbolic_expression(self) -> Expr:
        """Work with symbolic expression on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.symbolic_expression
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._func

    @property
    def numeric_expression(self) -> NumericFunction:
        """Work with numeric expression on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.numeric_expression
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._live_numeric_expression

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        """Work with parameters on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.parameters
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return tuple(sym for sym in self._numpified.all_vars if sym not in {self._x_var, self._y_var})

    @property
    def views(self) -> tuple[str, ...]:
        """Work with views on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.views
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return tuple(sorted(self._view_ids))

    @property
    def label(self) -> str:
        """Work with label on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.label
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._label

    @label.setter
    def label(self, value: str) -> None:
        """Work with label on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.label = value
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        self._label = str(value)
        for trace_handle in self._iter_trace_handles():
            trace_handle.name = value

    @property
    def color(self) -> str | None:
        """Work with color on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.color
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if self._line_color:
            return self._line_color
        ref = self._reference_trace_handle()
        if ref is not None:
            trace_color = self._representative_colorscale_color(
                getattr(ref, "colorscale", None)
            )
            if trace_color:
                return trace_color
        return self._representative_colorscale_color(self._colorscale)

    @staticmethod
    def _representative_colorscale_color(colorscale: Any) -> str | None:
        if not colorscale:
            return None
        resolved = resolve_field_colorscale(colorscale)
        if isinstance(resolved, str):
            try:
                scale_items = list(get_colorscale(resolved))
            except Exception:
                return None
        else:
            try:
                scale_items = list(resolved)
            except TypeError:
                return None
        if not scale_items:
            return None
        middle = scale_items[len(scale_items) // 2]
        if isinstance(middle, (tuple, list)) and len(middle) >= 2:
            return str(middle[1])
        return None

    @property
    def opacity(self) -> float | None:
        """Work with opacity on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.opacity
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._opacity

    @opacity.setter
    def opacity(self, value: int | float | None) -> None:
        """Work with opacity on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.opacity = value
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        self._opacity = self._coerce_opacity(value)
        self._apply_style_to_all_trace_handles()

    @property
    def colorscale(self) -> Any | None:
        """Work with colorscale on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.colorscale -> Any | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Any | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.colorscale
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._colorscale

    @property
    def z_range(self) -> tuple[float, float] | None:
        """Work with z range on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.z_range -> tuple[float, float] | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.z_range
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._z_range

    @property
    def z_step(self) -> float | None:
        """Work with z step on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.z_step -> float | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.z_step
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._z_step

    @property
    def under_color(self) -> str | None:
        """Work with under color on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.under_color -> str | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.under_color
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._under_color

    @property
    def over_color(self) -> str | None:
        """Work with over color on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.over_color -> str | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.over_color
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._over_color

    @property
    def show_colorbar(self) -> bool:
        """Work with show colorbar on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.show_colorbar -> bool``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.show_colorbar
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._show_colorbar

    @property
    def reversescale(self) -> bool:
        """Work with reversescale on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.reversescale -> bool``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.reversescale
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._reversescale

    @property
    def colorbar(self) -> dict[str, Any] | None:
        """Work with colorbar on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.colorbar -> dict[str, Any] | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, Any] | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.colorbar
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return None if self._colorbar is None else dict(self._colorbar)

    @property
    def levels(self) -> int | None:
        """Work with levels on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.levels -> int | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.levels
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._levels

    @property
    def level_step(self) -> float | None:
        """Work with level step on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.level_step -> float | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.level_step
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._level_step

    @property
    def level_start(self) -> float | None:
        """Work with level start on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.level_start -> float | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.level_start
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._level_start

    @property
    def level_end(self) -> float | None:
        """Work with level end on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.level_end -> float | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.level_end
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._level_end

    @property
    def filled(self) -> bool:
        """Work with filled on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.filled -> bool``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.filled
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._filled

    @property
    def show_labels(self) -> bool:
        """Work with show labels on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.show_labels -> bool``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.show_labels
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._show_labels

    @property
    def line_color(self) -> str | None:
        """Work with line color on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.line_color -> str | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.line_color
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._line_color

    @property
    def line_width(self) -> float | None:
        """Work with line width on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.line_width -> float | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.line_width
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._line_width

    @property
    def line_dash(self) -> str | None:
        """Work with line dash on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.line_dash -> str | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.line_dash
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._line_dash

    @property
    def dash(self) -> str | None:
        """Work with dash on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.dash
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._line_dash

    @property
    def smoothing(self) -> str | bool | None:
        """Work with smoothing on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.smoothing -> str | bool | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str | bool | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.smoothing
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._smoothing

    @property
    def connectgaps(self) -> bool | None:
        """Work with connectgaps on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.connectgaps -> bool | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        bool | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.connectgaps
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._connectgaps

    @property
    def x_domain(self) -> tuple[float, float] | None:
        """Work with x domain on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.x_domain
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: RangeLike | None) -> None:
        """Work with x domain on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.x_domain = value
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if value is None or _is_figure_default(value):
            self._x_domain = None
        else:
            self._x_domain = self._coerce_optional_range(value, axis_name="x")
        self.render()

    @property
    def y_domain(self) -> tuple[float, float] | None:
        """Work with y domain on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.y_domain -> tuple[float, float] | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.y_domain
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._y_domain

    @y_domain.setter
    def y_domain(self, value: RangeLike | None) -> None:
        """Work with y domain on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.y_domain = value``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.y_domain = value
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if value is None or _is_figure_default(value):
            self._y_domain = None
        else:
            self._y_domain = self._coerce_optional_range(value, axis_name="y")
        self.render()

    @property
    def grid(self) -> FieldGrid | None:
        """Work with grid on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.grid -> FieldGrid | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        FieldGrid | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.grid
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._grid

    @grid.setter
    def grid(self, value: tuple[int | str, int | str] | None) -> None:
        """Work with grid on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.grid = value``
        
        Parameters
        ----------
        value : tuple[int | str, int | str] | None
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.grid = value
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        self._grid = self._coerce_grid(value)
        self.render()

    @property
    def visible(self) -> VisibleSpec:
        """Work with visible on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.visible
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return self._visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        """Work with visible on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.visible = value
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        self._visible = value
        for view_id in self._view_ids:
            self._set_visibility_for_target_view(view_id)
        if value is True:
            self.render()

    @property
    def x_data(self) -> np.ndarray | None:
        """Work with x data on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.x_data
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if self._x_axis_values is None:
            return None
        values = self._x_axis_values.copy()
        values.flags.writeable = False
        return values

    @property
    def y_data(self) -> np.ndarray | None:
        """Work with y data on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.y_data
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if self._y_axis_values is None:
            return None
        values = self._y_axis_values.copy()
        values.flags.writeable = False
        return values

    @property
    def z_data(self) -> np.ndarray | None:
        """Work with z data on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.z_data -> np.ndarray | None``
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            current = obj.z_data
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if self._z_data is None:
            return None
        values = self._z_data.copy()
        values.flags.writeable = False
        return values

    # ------------------------------------------------------------------
    # View membership and snapshots
    # ------------------------------------------------------------------

    def add_to_view(self, view_id: str) -> None:
        """Add to view.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.add_to_view(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if view_id in self._view_ids:
            return
        self._view_ids.add(view_id)
        self._create_trace_handle(view_id=view_id, label=self.label)
        if view_id == self._smart_figure.views.current_id and self._visible is True:
            self.render(view_id=view_id)

    def remove_from_view(self, view_id: str) -> None:
        """Remove from view.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.remove_from_view(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if view_id not in self._view_ids:
            return
        self._view_ids.remove(view_id)
        self._remove_trace_handle(view_id=view_id)
        self._handles.pop(view_id, None)

    def add_views(self, views: str | Sequence[str]) -> None:
        """Add views.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.add_views(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if isinstance(views, str):
            self.add_to_view(views)
            return
        for view_id in views:
            self.add_to_view(view_id)

    def remove_views(self, views: str | Sequence[str]) -> None:
        """Remove views.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.remove_views(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        if isinstance(views, str):
            self.remove_from_view(views)
            return
        for view_id in views:
            self.remove_from_view(view_id)

    def snapshot(self, *, id: str = "") -> FieldPlotSnapshot:
        """Work with snapshot on ``ScalarFieldPlot``.
        
        Full API
        --------
        ``obj.snapshot(*, id: str='') -> FieldPlotSnapshot``
        
        Parameters
        ----------
        id : str, optional
            Stable identifier used to create, update, or look up the target object. Defaults to ``''``.
        
        Returns
        -------
        FieldPlotSnapshot
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``id=''``: Stable identifier used to create, update, or look up the target object.
        
        Architecture note
        -----------------
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
        """

        return FieldPlotSnapshot(
            id=id,
            render_mode=self.render_mode,
            preset=self.preset,
            x_var=self.x_var,
            y_var=self.y_var,
            func=self.symbolic_expression,
            parameters=tuple(self.parameters),
            label=self.label,
            visible=self.visible,
            x_domain=self.x_domain,
            y_domain=self.y_domain,
            grid=self.grid,
            colorscale=self.colorscale,
            z_range=self.z_range,
            z_step=self.z_step,
            under_color=self.under_color,
            over_color=self.over_color,
            show_colorbar=self.show_colorbar,
            opacity=self.opacity,
            reversescale=self.reversescale,
            colorbar=self.colorbar,
            trace=(None if self._trace_overrides is None else dict(self._trace_overrides)),
            views=self.views,
            levels=self.levels,
            level_step=self.level_step,
            level_start=self.level_start,
            level_end=self.level_end,
            filled=self.filled,
            show_labels=self.show_labels,
            line_color=self.line_color,
            line_width=self.line_width,
            line_dash=self.line_dash,
            smoothing=self.smoothing,
            connectgaps=self.connectgaps,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_grid_values(
        raw_values: Any,
        *,
        x_values: np.ndarray,
        y_values: np.ndarray,
    ) -> np.ndarray:
        target_shape = (y_values.shape[0], x_values.shape[0])
        values = np.asarray(raw_values, dtype=float)
        if values.ndim == 0:
            return np.full(target_shape, float(values), dtype=float)
        if values.shape == target_shape:
            return values.astype(float, copy=False)
        if values.shape == (target_shape[1], target_shape[0]):
            return values.T.astype(float, copy=False)
        if values.size == target_shape[0] * target_shape[1]:
            return np.ravel(values).astype(float, copy=False).reshape(target_shape)
        try:
            return np.broadcast_to(values, target_shape).astype(float, copy=False)
        except ValueError as exc:
            raise ValueError(
                "Scalar field expression must evaluate to a scalar or an array "
                f"broadcastable to grid shape {target_shape}."
            ) from exc

    def render(
        self,
        view_id: str | None = None,
        *,
        use_batch_update: bool = True,
        refresh_parameter_snapshot: bool = True,
    ) -> None:
        """Render value.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.render(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
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

        if target_view != fig.views.current_id:
            fig.views[target_view].is_stale = True
            return

        view = fig.views[target_view]
        x_viewport = view.current_x_range or view.x_range
        y_viewport = view.current_y_range or view.y_range
        x_domain = self.x_domain or x_viewport
        y_domain = self.y_domain or y_viewport
        nx, ny = self.grid or self.DEFAULT_GRID

        x_values = np.linspace(float(x_domain[0]), float(x_domain[1]), num=int(nx))
        y_values = np.linspace(float(y_domain[0]), float(y_domain[1]), num=int(ny))
        X, Y = np.meshgrid(x_values, y_values)
        z_values = self._coerce_grid_values(
            self._render_numeric_expression(X, Y),
            x_values=x_values,
            y_values=y_values,
        )

        self._x_axis_values = x_values.copy()
        self._y_axis_values = y_values.copy()
        self._z_data = z_values.copy()

        style_payload, display_z_values = self._build_trace_style_payload(z_values=z_values)
        if display_z_values is None:
            display_z_values = z_values

        target_handle = self._handles[target_view].trace_handle
        if target_handle is None:
            return

        def _apply_trace_update() -> None:
            target_handle.update(**style_payload)
            target_handle.visible = self._visible
            target_handle.name = self.label
            target_handle.x = x_values
            target_handle.y = y_values
            target_handle.z = display_z_values

        if use_batch_update:
            with fig.views[target_view].figure_widget.batch_update():
                _apply_trace_update()
        else:
            _apply_trace_update()

        pane = getattr(fig.views[target_view], "pane", None)
        getattr(pane, "refresh_plot_display", lambda **_kwargs: False)(
            reason=f"render:{type(self).__name__}"
        )

    # ------------------------------------------------------------------
    # In-place updates
    # ------------------------------------------------------------------

    def _apply_style_updates(self, style_kwargs: dict[str, Any]) -> None:
        if "colorscale" in style_kwargs:
            self._colorscale = style_kwargs.get("colorscale")
        if "z_range" in style_kwargs:
            self._z_range = self._coerce_optional_range(style_kwargs.get("z_range"), axis_name="z")
        if "z_step" in style_kwargs:
            self._z_step = self._coerce_optional_float(style_kwargs.get("z_step"))
        if "under_color" in style_kwargs:
            under_color = style_kwargs.get("under_color")
            self._under_color = None if under_color is None else str(under_color)
        if "over_color" in style_kwargs:
            over_color = style_kwargs.get("over_color")
            self._over_color = None if over_color is None else str(over_color)
        if "show_colorbar" in style_kwargs:
            self._show_colorbar = bool(style_kwargs.get("show_colorbar"))
        if "opacity" in style_kwargs:
            self._opacity = self._coerce_opacity(style_kwargs.get("opacity"))
        if "reversescale" in style_kwargs:
            self._reversescale = bool(style_kwargs.get("reversescale"))
        if "colorbar" in style_kwargs:
            self._colorbar = self._coerce_optional_mapping(style_kwargs.get("colorbar"))
        if "trace" in style_kwargs:
            self._trace_overrides = self._coerce_optional_mapping(style_kwargs.get("trace"))
        if "levels" in style_kwargs:
            levels = style_kwargs.get("levels")
            self._levels = None if levels is None else int(InputConvert(levels, int))
        if "level_step" in style_kwargs:
            self._level_step = self._coerce_optional_float(style_kwargs.get("level_step"))
        if "level_start" in style_kwargs:
            self._level_start = self._coerce_optional_float(style_kwargs.get("level_start"))
        if "level_end" in style_kwargs:
            self._level_end = self._coerce_optional_float(style_kwargs.get("level_end"))
        if "filled" in style_kwargs:
            self._filled = bool(style_kwargs.get("filled"))
        if "show_labels" in style_kwargs:
            self._show_labels = bool(style_kwargs.get("show_labels"))
        if "line_color" in style_kwargs:
            line_color = style_kwargs.get("line_color")
            self._line_color = None if line_color is None else str(line_color)
        if "line_width" in style_kwargs:
            width = style_kwargs.get("line_width")
            self._line_width = None if width is None else float(InputConvert(width, float))
        if "line_dash" in style_kwargs:
            line_dash = style_kwargs.get("line_dash")
            self._line_dash = None if line_dash is None else str(line_dash)
        if "smoothing" in style_kwargs:
            self._smoothing = style_kwargs.get("smoothing")
        if "connectgaps" in style_kwargs:
            connectgaps = style_kwargs.get("connectgaps")
            self._connectgaps = None if connectgaps is None else bool(connectgaps)
        self._apply_style_to_all_trace_handles()

    def update(self, **kwargs: Any) -> None:
        """Work with update on ``ScalarFieldPlot``.
        
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
        This member belongs to ``ScalarFieldPlot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ScalarFieldPlot(...)
            obj.update(...)
        
        Discovery-oriented use::
        
            help(ScalarFieldPlot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(ScalarFieldPlot)`` and ``dir(ScalarFieldPlot)`` to inspect adjacent members.
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
                    pass
                elif _is_figure_default(val):
                    self.x_domain = None
                    render_requested = True
                else:
                    self.x_domain = val
                    render_requested = True

            if "y_domain" in kwargs:
                val = kwargs["y_domain"]
                if val is None:
                    pass
                elif _is_figure_default(val):
                    self.y_domain = None
                    render_requested = True
                else:
                    self.y_domain = val
                    render_requested = True

            if "grid" in kwargs:
                val = kwargs["grid"]
                if val is None:
                    pass
                else:
                    self.grid = val
                    render_requested = True

            if "view" in kwargs:
                requested = kwargs["view"]
                if requested is not None:
                    render_requested = True
                    requested_views = {requested} if isinstance(requested, str) else set(requested)
                    for view_id in tuple(self._view_ids):
                        if view_id not in requested_views:
                            self.remove_from_view(view_id)
                    for view_id in requested_views:
                        self.add_to_view(view_id)

            raw_style_kwargs: dict[str, Any] = {}
            for key in (
                "colorscale",
                "z_range",
                "z_step",
                "under_color",
                "over_color",
                "show_colorbar",
                "showscale",
                "opacity",
                "alpha",
                "reversescale",
                "colorbar",
                "trace",
                "levels",
                "level_step",
                "level_start",
                "level_end",
                "filled",
                "show_labels",
                "line_color",
                "line_width",
                "line_dash",
                "dash",
                "smoothing",
                "zsmooth",
                "connectgaps",
            ):
                if key in kwargs:
                    raw_style_kwargs[key] = kwargs[key]
            if raw_style_kwargs:
                style_kwargs = validate_field_style_kwargs(
                    raw_style_kwargs,
                    caller="ScalarFieldPlot.update()",
                )
                if self._render_mode == "heatmap" and any(
                    key in style_kwargs
                    for key in ("z_range", "z_step", "under_color", "over_color")
                ):
                    render_requested = True
                self._apply_style_updates(style_kwargs)

            if any(k in kwargs for k in ("x_var", "y_var", "func", "parameters", "numeric_function")):
                render_requested = True
                x_var = kwargs.get("x_var", self.x_var)
                y_var = kwargs.get("y_var", self.y_var)
                func = kwargs.get("func", self.symbolic_expression)
                parameters = kwargs.get("parameters", self.parameters)
                numeric_fn = kwargs.get("numeric_function")
                if numeric_fn is not None:
                    self.set_numeric_function(
                        x_var,
                        y_var,
                        numeric_fn,
                        parameters=parameters,
                        symbolic_expression=func,
                    )
                else:
                    self.set_func(x_var, y_var, func, parameters)
        finally:
            self._suspend_render = previous_suspend

        if render_requested:
            self.render()


# ----------------------------------------------------------------------
# Figure-facing creation/update helpers
# ----------------------------------------------------------------------


def _normalize_axis_domain(
    axis_spec: Any,
    *,
    axis_name: str,
    domain: RangeLike | None,
    caller: str,
) -> tuple[Any, RangeLike | None]:
    if isinstance(axis_spec, tuple):
        if len(axis_spec) != 3:
            raise ValueError(
                f"{caller} {axis_name} range tuple must have shape ({axis_name}, min, max)."
            )
        if domain is not None:
            raise ValueError(
                f"{caller} cannot combine a {axis_name} range tuple with {axis_name}_domain=."
            )
        return axis_spec[0], (axis_spec[1], axis_spec[2])
    return axis_spec, domain



def create_or_update_scalar_field_plot(
    figure: Figure,
    func: Any,
    x: Any,
    y: Any,
    *,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: VisibleSpec = True,
    x_domain: RangeLike | None = None,
    y_domain: RangeLike | None = None,
    grid: tuple[int | str, int | str] | None = None,
    render_mode: FieldRenderMode = "heatmap",
    preset: str | None = None,
    colorscale: Any | None = None,
    z_range: RangeLike | None = None,
    z_step: int | float | None = None,
    under_color: str | None = None,
    over_color: str | None = None,
    show_colorbar: bool | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    reversescale: bool | None = None,
    colorbar: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    levels: int | None = None,
    level_step: int | float | None = None,
    level_start: int | float | None = None,
    level_end: int | float | None = None,
    filled: bool | None = None,
    show_labels: bool | None = None,
    line_color: str | None = None,
    line_width: int | float | None = None,
    line_dash: str | None = None,
    dash: str | None = None,
    smoothing: str | bool | None = None,
    zsmooth: str | bool | None = None,
    connectgaps: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: Any | None = None,
    caller: str = "scalar_field()",
) -> ScalarFieldPlot:
    """Create or update scalar field plot.
    
    Full API
    --------
    ``create_or_update_scalar_field_plot(figure: Figure, func: Any, x: Any, y: Any, *, parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: VisibleSpec=True, x_domain: RangeLike | None=None, y_domain: RangeLike | None=None, grid: tuple[int | str, int | str] | None=None, render_mode: FieldRenderMode='heatmap', preset: str | None=None, colorscale: Any | None=None, z_range: RangeLike | None=None, z_step: int | float | None=None, under_color: str | None=None, over_color: str | None=None, show_colorbar: bool | None=None, opacity: int | float | None=None, alpha: int | float | None=None, reversescale: bool | None=None, colorbar: Mapping[str, Any] | None=None, trace: Mapping[str, Any] | None=None, levels: int | None=None, level_step: int | float | None=None, level_start: int | float | None=None, level_end: int | float | None=None, filled: bool | None=None, show_labels: bool | None=None, line_color: str | None=None, line_width: int | float | None=None, line_dash: str | None=None, dash: str | None=None, smoothing: str | bool | None=None, zsmooth: str | bool | None=None, connectgaps: bool | None=None, view: str | Sequence[str] | None=None, vars: Any | None=None, caller: str='scalar_field()') -> ScalarFieldPlot``
    
    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    parameters : ParameterKeyOrKeys | None, optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``None``.
    
    id : str | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    label : str | None, optional
        Human-readable label used in UI or plotting output. Defaults to ``None``.
    
    visible : VisibleSpec, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    x_domain : RangeLike | None, optional
        Numeric x-domain used for evaluation or rendering. Defaults to ``None``.
    
    y_domain : RangeLike | None, optional
        Numeric y-domain used for evaluation or rendering. Defaults to ``None``.
    
    grid : tuple[int | str, int | str] | None, optional
        Grid resolution or grid specification used for field sampling. Defaults to ``None``.
    
    render_mode : FieldRenderMode, optional
        Rendering mode or plot kind to create. Defaults to ``'heatmap'``.
    
    preset : str | None, optional
        Named preset that chooses a particular rendering style. Defaults to ``None``.
    
    colorscale : Any | None, optional
        Colorscale specification passed to the renderer. Defaults to ``None``.
    
    z_range : RangeLike | None, optional
        Numeric value range used for scalar-field color mapping. Defaults to ``None``.
    
    z_step : int | float | None, optional
        Numeric spacing between scalar-field contour or color levels. Defaults to ``None``.
    
    under_color : str | None, optional
        Color used below the represented scalar range. Defaults to ``None``.
    
    over_color : str | None, optional
        Color used above the represented scalar range. Defaults to ``None``.
    
    show_colorbar : bool | None, optional
        Boolean flag controlling whether a colorbar is shown. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    alpha : int | float | None, optional
        Value for ``alpha`` in this API. Defaults to ``None``.
    
    reversescale : bool | None, optional
        Boolean flag controlling whether the colorscale is reversed. Defaults to ``None``.
    
    colorbar : Mapping[str, Any] | None, optional
        Renderer-specific colorbar configuration mapping. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    levels : int | None, optional
        Number of contour or scalar levels to generate. Defaults to ``None``.
    
    level_step : int | float | None, optional
        Spacing between contour or scalar levels. Defaults to ``None``.
    
    level_start : int | float | None, optional
        First contour/scalar level to include. Defaults to ``None``.
    
    level_end : int | float | None, optional
        Last contour/scalar level to include. Defaults to ``None``.
    
    filled : bool | None, optional
        Boolean flag controlling whether contour regions are filled. Defaults to ``None``.
    
    show_labels : bool | None, optional
        Boolean flag controlling whether labels are drawn on contour lines. Defaults to ``None``.
    
    line_color : str | None, optional
        Explicit line color for contour or curve rendering. Defaults to ``None``.
    
    line_width : int | float | None, optional
        Line width used for contour or curve rendering. Defaults to ``None``.
    
    line_dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    smoothing : str | bool | None, optional
        Smoothing option passed to the renderer or interpolation layer. Defaults to ``None``.
    
    zsmooth : str | bool | None, optional
        Value for ``zsmooth`` in this API. Defaults to ``None``.
    
    connectgaps : bool | None, optional
        Boolean flag controlling whether missing samples are connected. Defaults to ``None``.
    
    view : str | Sequence[str] | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    vars : Any | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    caller : str, optional
        Value for ``caller`` in this API. Defaults to ``'scalar_field()'``.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``parameters=None``: Parameter symbols/keys that should stay bound to this operation.
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``label=None``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
    - ``y_domain=None``: Numeric y-domain used for evaluation or rendering.
    - ``grid=None``: Grid resolution or grid specification used for field sampling.
    - ``render_mode='heatmap'``: Rendering mode or plot kind to create.
    - ``preset=None``: Named preset that chooses a particular rendering style.
    - ``colorscale=None``: Colorscale specification passed to the renderer.
    - ``z_range=None``: Numeric value range used for scalar-field color mapping.
    - ``z_step=None``: Numeric spacing between scalar-field contour or color levels.
    - ``under_color=None``: Color used below the represented scalar range.
    - ``over_color=None``: Color used above the represented scalar range.
    - ``show_colorbar=None``: Boolean flag controlling whether a colorbar is shown.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``alpha=None``: Value for ``alpha`` in this API.
    - ``reversescale=None``: Boolean flag controlling whether the colorscale is reversed.
    - ``colorbar=None``: Renderer-specific colorbar configuration mapping.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``levels=None``: Number of contour or scalar levels to generate.
    - ``level_step=None``: Spacing between contour or scalar levels.
    - ``level_start=None``: First contour/scalar level to include.
    - ``level_end=None``: Last contour/scalar level to include.
    - ``filled=None``: Boolean flag controlling whether contour regions are filled.
    - ``show_labels=None``: Boolean flag controlling whether labels are drawn on contour lines.
    - ``line_color=None``: Explicit line color for contour or curve rendering.
    - ``line_width=None``: Line width used for contour or curve rendering.
    - ``line_dash=None``: Dash pattern used for contour or curve rendering.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``smoothing=None``: Smoothing option passed to the renderer or interpolation layer.
    - ``zsmooth=None``: Value for ``zsmooth`` in this API.
    - ``connectgaps=None``: Boolean flag controlling whether missing samples are connected.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    - ``vars=None``: Value for ``vars`` in this API.
    - ``caller='scalar_field()'``: Value for ``caller`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field import create_or_update_scalar_field_plot
        result = create_or_update_scalar_field_plot(...)
    
    Discovery-oriented use::
    
        help(create_or_update_scalar_field_plot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(create_or_update_scalar_field_plot)`` and inspect sibling APIs in the same module.
    """

    id = resolve_plot_id(figure.plots, id)
    x_var_spec, x_domain = _normalize_axis_domain(
        x, axis_name="x", domain=x_domain, caller=caller
    )
    y_var_spec, y_domain = _normalize_axis_domain(
        y, axis_name="y", domain=y_domain, caller=caller
    )

    x_var, y_var, symbolic_expr, numeric_fn, inferred_parameters = normalize_field_inputs(
        func,
        x_var_spec,
        y_var_spec,
        vars=vars,
        id_hint=id,
    )

    raw_style_kwargs: dict[str, Any] = {}
    for key, value in (
        ("colorscale", colorscale),
        ("z_range", z_range),
        ("z_step", z_step),
        ("under_color", under_color),
        ("over_color", over_color),
        ("show_colorbar", show_colorbar),
        ("opacity", opacity),
        ("alpha", alpha),
        ("reversescale", reversescale),
        ("colorbar", colorbar),
        ("trace", trace),
        ("levels", levels),
        ("level_step", level_step),
        ("level_start", level_start),
        ("level_end", level_end),
        ("filled", filled),
        ("show_labels", show_labels),
        ("line_color", line_color),
        ("line_width", line_width),
        ("line_dash", line_dash),
        ("dash", dash),
        ("smoothing", smoothing),
        ("zsmooth", zsmooth),
        ("connectgaps", connectgaps),
    ):
        if value is not None:
            raw_style_kwargs[key] = value
    style_kwargs = validate_field_style_kwargs(raw_style_kwargs, caller=caller)
    render_mode = ScalarFieldPlot._coerce_render_mode(render_mode)
    preset = ScalarFieldPlot._coerce_preset(preset, render_mode=render_mode)

    if parameters is None:
        requested_parameter_keys: ParameterKeyOrKeys = tuple(inferred_parameters)
        plot_parameters = tuple(inferred_parameters)
    else:
        requested_parameter_keys = parameters
        plot_parameters = expand_parameter_keys_to_symbols(
            parameters,
            inferred_parameters,
            role="scalar-field parameters",
        )

    if requested_parameter_keys:
        figure.parameter(requested_parameter_keys)

    if figure._sync_sidebar_visibility():
        figure._request_active_view_reflow("sidebar_visibility")

    existing = figure.plots.get(id)
    if existing is not None and not isinstance(existing, ScalarFieldPlot):
        remove_plot_from_figure(figure, id)
        existing = None
    if existing is not None and (
        existing.render_mode != render_mode or existing.preset != preset
    ):
        remove_plot_from_figure(figure, id)
        existing = None

    if existing is not None:
        update_kwargs: dict[str, Any] = {
            "x_var": x_var,
            "y_var": y_var,
            "func": symbolic_expr,
            "parameters": plot_parameters,
            "visible": visible,
            "x_domain": x_domain,
            "y_domain": y_domain,
            "grid": grid,
            "view": view,
        }
        for key in (
            "colorscale",
            "z_range",
            "z_step",
            "under_color",
            "over_color",
            "show_colorbar",
            "opacity",
            "reversescale",
            "colorbar",
            "trace",
            "levels",
            "level_step",
            "level_start",
            "level_end",
            "filled",
            "show_labels",
            "line_color",
            "line_width",
            "line_dash",
            "smoothing",
            "connectgaps",
        ):
            if key in style_kwargs:
                update_kwargs[key] = style_kwargs[key]
        if numeric_fn is not None:
            update_kwargs["numeric_function"] = numeric_fn
        if label is not None:
            update_kwargs["label"] = label
        existing.update(**update_kwargs)
        plot = existing
        figure._legend.on_plot_updated(plot)
        if figure._sync_sidebar_visibility():
            figure._request_active_view_reflow("sidebar_visibility")
        return plot

    view_ids = normalize_view_ids(view, default_view_id=figure.views.current_id)
    plot = ScalarFieldPlot(
        x_var=x_var,
        y_var=y_var,
        func=symbolic_expr,
        smart_figure=figure,
        parameters=plot_parameters,
        x_domain=x_domain,
        y_domain=y_domain,
        grid=grid,
        label=(id if label is None else label),
        visible=visible,
        render_mode=render_mode,
        preset=preset,
        colorscale=style_kwargs.get("colorscale"),
        z_range=style_kwargs.get("z_range"),
        z_step=style_kwargs.get("z_step"),
        under_color=style_kwargs.get("under_color"),
        over_color=style_kwargs.get("over_color"),
        show_colorbar=style_kwargs.get("show_colorbar"),
        opacity=style_kwargs.get("opacity"),
        reversescale=style_kwargs.get("reversescale"),
        colorbar=style_kwargs.get("colorbar"),
        trace=style_kwargs.get("trace"),
        levels=style_kwargs.get("levels"),
        level_step=style_kwargs.get("level_step"),
        level_start=style_kwargs.get("level_start"),
        level_end=style_kwargs.get("level_end"),
        filled=style_kwargs.get("filled"),
        show_labels=style_kwargs.get("show_labels"),
        line_color=style_kwargs.get("line_color"),
        line_width=style_kwargs.get("line_width"),
        line_dash=style_kwargs.get("line_dash"),
        smoothing=style_kwargs.get("smoothing"),
        connectgaps=style_kwargs.get("connectgaps"),
        plot_id=id,
        view_ids=view_ids,
        numeric_function=numeric_fn,
    )
    figure.plots[id] = plot
    figure._legend.on_plot_added(plot)
    if figure._sync_sidebar_visibility():
        figure._request_active_view_reflow("sidebar_visibility")
    return plot


# ----------------------------------------------------------------------
# Figure method shims (attached in Figure.py to preserve coordinator size)
# ----------------------------------------------------------------------


def scalar_field_method(
    self: Figure,
    func: Any,
    x: Any,
    y: Any,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: VisibleSpec = True,
    x_domain: RangeLike | None = None,
    y_domain: RangeLike | None = None,
    grid: tuple[int | str, int | str] | None = None,
    render_mode: FieldRenderMode = "heatmap",
    preset: str | None = None,
    colorscale: Any | None = None,
    z_range: RangeLike | None = None,
    z_step: int | float | None = None,
    under_color: str | None = None,
    over_color: str | None = None,
    show_colorbar: bool | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    reversescale: bool | None = None,
    colorbar: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    levels: int | None = None,
    level_step: int | float | None = None,
    level_start: int | float | None = None,
    level_end: int | float | None = None,
    filled: bool | None = None,
    show_labels: bool | None = None,
    line_color: str | None = None,
    line_width: int | float | None = None,
    line_dash: str | None = None,
    dash: str | None = None,
    smoothing: str | bool | None = None,
    zsmooth: str | bool | None = None,
    connectgaps: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: Any | None = None,
) -> ScalarFieldPlot:
    """Work with scalar field method.
    
    Full API
    --------
    ``scalar_field_method(self: Figure, func: Any, x: Any, y: Any, parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: VisibleSpec=True, x_domain: RangeLike | None=None, y_domain: RangeLike | None=None, grid: tuple[int | str, int | str] | None=None, render_mode: FieldRenderMode='heatmap', preset: str | None=None, colorscale: Any | None=None, z_range: RangeLike | None=None, z_step: int | float | None=None, under_color: str | None=None, over_color: str | None=None, show_colorbar: bool | None=None, opacity: int | float | None=None, alpha: int | float | None=None, reversescale: bool | None=None, colorbar: Mapping[str, Any] | None=None, trace: Mapping[str, Any] | None=None, levels: int | None=None, level_step: int | float | None=None, level_start: int | float | None=None, level_end: int | float | None=None, filled: bool | None=None, show_labels: bool | None=None, line_color: str | None=None, line_width: int | float | None=None, line_dash: str | None=None, dash: str | None=None, smoothing: str | bool | None=None, zsmooth: str | bool | None=None, connectgaps: bool | None=None, view: str | Sequence[str] | None=None, vars: Any | None=None) -> ScalarFieldPlot``
    
    Parameters
    ----------
    self : Figure
        Value for ``self`` in this API. Required.
    
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    parameters : ParameterKeyOrKeys | None, optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``None``.
    
    id : str | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    label : str | None, optional
        Human-readable label used in UI or plotting output. Defaults to ``None``.
    
    visible : VisibleSpec, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    x_domain : RangeLike | None, optional
        Numeric x-domain used for evaluation or rendering. Defaults to ``None``.
    
    y_domain : RangeLike | None, optional
        Numeric y-domain used for evaluation or rendering. Defaults to ``None``.
    
    grid : tuple[int | str, int | str] | None, optional
        Grid resolution or grid specification used for field sampling. Defaults to ``None``.
    
    render_mode : FieldRenderMode, optional
        Rendering mode or plot kind to create. Defaults to ``'heatmap'``.
    
    preset : str | None, optional
        Named preset that chooses a particular rendering style. Defaults to ``None``.
    
    colorscale : Any | None, optional
        Colorscale specification passed to the renderer. Defaults to ``None``.
    
    z_range : RangeLike | None, optional
        Numeric value range used for scalar-field color mapping. Defaults to ``None``.
    
    z_step : int | float | None, optional
        Numeric spacing between scalar-field contour or color levels. Defaults to ``None``.
    
    under_color : str | None, optional
        Color used below the represented scalar range. Defaults to ``None``.
    
    over_color : str | None, optional
        Color used above the represented scalar range. Defaults to ``None``.
    
    show_colorbar : bool | None, optional
        Boolean flag controlling whether a colorbar is shown. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    alpha : int | float | None, optional
        Value for ``alpha`` in this API. Defaults to ``None``.
    
    reversescale : bool | None, optional
        Boolean flag controlling whether the colorscale is reversed. Defaults to ``None``.
    
    colorbar : Mapping[str, Any] | None, optional
        Renderer-specific colorbar configuration mapping. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    levels : int | None, optional
        Number of contour or scalar levels to generate. Defaults to ``None``.
    
    level_step : int | float | None, optional
        Spacing between contour or scalar levels. Defaults to ``None``.
    
    level_start : int | float | None, optional
        First contour/scalar level to include. Defaults to ``None``.
    
    level_end : int | float | None, optional
        Last contour/scalar level to include. Defaults to ``None``.
    
    filled : bool | None, optional
        Boolean flag controlling whether contour regions are filled. Defaults to ``None``.
    
    show_labels : bool | None, optional
        Boolean flag controlling whether labels are drawn on contour lines. Defaults to ``None``.
    
    line_color : str | None, optional
        Explicit line color for contour or curve rendering. Defaults to ``None``.
    
    line_width : int | float | None, optional
        Line width used for contour or curve rendering. Defaults to ``None``.
    
    line_dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    smoothing : str | bool | None, optional
        Smoothing option passed to the renderer or interpolation layer. Defaults to ``None``.
    
    zsmooth : str | bool | None, optional
        Value for ``zsmooth`` in this API. Defaults to ``None``.
    
    connectgaps : bool | None, optional
        Boolean flag controlling whether missing samples are connected. Defaults to ``None``.
    
    view : str | Sequence[str] | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    vars : Any | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``parameters=None``: Parameter symbols/keys that should stay bound to this operation.
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``label=None``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
    - ``y_domain=None``: Numeric y-domain used for evaluation or rendering.
    - ``grid=None``: Grid resolution or grid specification used for field sampling.
    - ``render_mode='heatmap'``: Rendering mode or plot kind to create.
    - ``preset=None``: Named preset that chooses a particular rendering style.
    - ``colorscale=None``: Colorscale specification passed to the renderer.
    - ``z_range=None``: Numeric value range used for scalar-field color mapping.
    - ``z_step=None``: Numeric spacing between scalar-field contour or color levels.
    - ``under_color=None``: Color used below the represented scalar range.
    - ``over_color=None``: Color used above the represented scalar range.
    - ``show_colorbar=None``: Boolean flag controlling whether a colorbar is shown.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``alpha=None``: Value for ``alpha`` in this API.
    - ``reversescale=None``: Boolean flag controlling whether the colorscale is reversed.
    - ``colorbar=None``: Renderer-specific colorbar configuration mapping.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``levels=None``: Number of contour or scalar levels to generate.
    - ``level_step=None``: Spacing between contour or scalar levels.
    - ``level_start=None``: First contour/scalar level to include.
    - ``level_end=None``: Last contour/scalar level to include.
    - ``filled=None``: Boolean flag controlling whether contour regions are filled.
    - ``show_labels=None``: Boolean flag controlling whether labels are drawn on contour lines.
    - ``line_color=None``: Explicit line color for contour or curve rendering.
    - ``line_width=None``: Line width used for contour or curve rendering.
    - ``line_dash=None``: Dash pattern used for contour or curve rendering.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``smoothing=None``: Smoothing option passed to the renderer or interpolation layer.
    - ``zsmooth=None``: Value for ``zsmooth`` in this API.
    - ``connectgaps=None``: Boolean flag controlling whether missing samples are connected.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    - ``vars=None``: Value for ``vars`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field import scalar_field_method
        result = scalar_field_method(...)
    
    Discovery-oriented use::
    
        help(scalar_field_method)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(scalar_field_method)`` and inspect sibling APIs in the same module.
    """

    return create_or_update_scalar_field_plot(
        self,
        func,
        x,
        y,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        x_domain=x_domain,
        y_domain=y_domain,
        grid=grid,
        render_mode=render_mode,
        preset=preset,
        colorscale=colorscale,
        z_range=z_range,
        z_step=z_step,
        under_color=under_color,
        over_color=over_color,
        show_colorbar=show_colorbar,
        opacity=opacity,
        alpha=alpha,
        reversescale=reversescale,
        colorbar=colorbar,
        trace=trace,
        levels=levels,
        level_step=level_step,
        level_start=level_start,
        level_end=level_end,
        filled=filled,
        show_labels=show_labels,
        line_color=line_color,
        line_width=line_width,
        line_dash=line_dash,
        dash=dash,
        smoothing=smoothing,
        zsmooth=zsmooth,
        connectgaps=connectgaps,
        view=view,
        vars=vars,
        caller="scalar_field()",
    )



def contour_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Work with contour method.
    
    Full API
    --------
    ``contour_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot``
    
    Parameters
    ----------
    self : Figure
        Value for ``self`` in this API. Required.
    
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field import contour_method
        result = contour_method(...)
    
    Discovery-oriented use::
    
        help(contour_method)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(contour_method)`` and inspect sibling APIs in the same module.
    """

    kwargs.setdefault("render_mode", "contour")
    kwargs.setdefault("filled", False)
    return create_or_update_scalar_field_plot(self, func, x, y, caller="contour()", **kwargs)



def density_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Work with density method.
    
    Full API
    --------
    ``density_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot``
    
    Parameters
    ----------
    self : Figure
        Value for ``self`` in this API. Required.
    
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field import density_method
        result = density_method(...)
    
    Discovery-oriented use::
    
        help(density_method)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(density_method)`` and inspect sibling APIs in the same module.
    """

    kwargs.setdefault("render_mode", "heatmap")
    return create_or_update_scalar_field_plot(self, func, x, y, caller="density()", **kwargs)



def temperature_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Work with temperature method.
    
    Full API
    --------
    ``temperature_method(self: Figure, func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot``
    
    Parameters
    ----------
    self : Figure
        Value for ``self`` in this API. Required.
    
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field import temperature_method
        result = temperature_method(...)
    
    Discovery-oriented use::
    
        help(temperature_method)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(temperature_method)`` and inspect sibling APIs in the same module.
    """

    kwargs.setdefault("render_mode", "heatmap")
    kwargs.setdefault("preset", "temperature")
    return create_or_update_scalar_field_plot(self, func, x, y, caller="temperature()", **kwargs)


__all__ = [
    "FieldGrid",
    "FieldPlotHandle",
    "FieldRenderMode",
    "ScalarFieldPlot",
    "create_or_update_scalar_field_plot",
    "field_palette_option_docs",
    "field_style_option_docs",
    "contour_method",
    "density_method",
    "scalar_field_method",
    "temperature_method",
]
