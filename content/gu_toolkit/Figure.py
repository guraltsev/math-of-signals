"""Interactive figure coordinator and public API hub.

Glossary
--------
Figure
    Top-level notebook object that coordinates layout, plots, parameters,
    info content, legends, views, snapshots, and code generation.
View
    Named plotting workspace inside one figure. Each public :class:`View`
    owns one stable Plotly widget runtime, its default axis ranges, remembered
    viewport, and axis labels.
Sidebar
    The optional right-hand panel that can show the toolkit legend,
    parameter controls, and the Info section.
Info section / info card
    The Info section is the sidebar area for explanatory content. An info card
    is a small rich-text block created with :meth:`Figure.info` or the
    module-level :func:`info` helper. Cards may be global or scoped to a
    specific view.
Current figure
    Thread-local routing target used by module-level helpers. ``with fig:``
    makes a figure current. ``with fig.views["detail"]:`` makes the figure
    current *and* activates that view for the duration of the block.
Module-level helpers
    Convenience functions from :mod:`gu_toolkit.figure_api` such as ``plot``,
    ``parameter``, ``info``, ``set_x_range``, and ``render``. They delegate to
    the current figure and current active view; they do not store independent
    plotting state.

Navigation map
--------------
- :mod:`gu_toolkit.figure_view` defines the public :class:`View` object and the
  :class:`FigureViews` facade.
- :mod:`gu_toolkit.figure_layout` owns widget composition only.
- :mod:`gu_toolkit.figure_plot` owns per-curve numeric sampling and trace
  updates.
- :mod:`gu_toolkit.figure_parameters` owns parameter controls and hooks.
- :mod:`gu_toolkit.figure_info` owns the Info section and info cards.
- :mod:`gu_toolkit.figure_legend` owns the toolkit sidebar legend.
- :mod:`gu_toolkit.FigureSnapshot` and :mod:`gu_toolkit.codegen` own
  reproducible state and source generation.

Logging
-------
Use Python's standard :mod:`logging` module rather than ``Figure(debug=...)``::

    import logging
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("gu_toolkit.layout").setLevel(logging.DEBUG)
"""
from __future__ import annotations
import logging
import time
import warnings
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from typing import Any
from ._widget_stubs import widgets
import plotly.graph_objects as go
from IPython.display import display
from sympy.core.symbol import Symbol
from .codegen import CodegenOptions
from .figure_diagnostics import (
    figure_performance_report,
    figure_performance_snapshot,
    figure_runtime_diagnostics,
    perform_render_request,
)
from .layout_logging import (
    LayoutEventBuffer,
    is_layout_logger_explicitly_enabled,
    make_event_emitter,
    new_debug_id,
    new_request_id,
)
from .debouncing import QueuedDebouncer
from .figure_render_scheduler import FigureRenderScheduler, RenderRequest
from .figure_plot_normalization import (
    PlotVarsSpec,
    normalize_plot_inputs,
)
from .figure_plot_style import plot_style_option_docs, validate_style_kwargs
from .figure_color import color_for_trace_index, explicit_style_color
from .figure_plot_helpers import (
    normalize_view_ids,
    remove_plot_from_figure,
    resolve_plot_id,
)
from .FigureSnapshot import FigureSnapshot, ViewSnapshot
from .InputConvert import InputConvert
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .PlotlyPane import PlotlyPane, PlotlyPaneStyle
from .parameter_keys import ParameterKeyOrKeys, expand_parameter_keys_to_symbols
from .figure_types import RangeLike, VisibleSpec
from .performance_monitor import PerformanceMonitor
from .runtime_support import create_plotly_figure_widget, warn_once
# Module logger
# - Uses a NullHandler so importing this module never configures global logging.
# - Callers can enable logs via standard logging configuration.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
RENDER_TARGET_INTERVAL_MS = 10
from .figure_context import (
    _FigureDefaultSentinel,
    _is_figure_default,
    _pop_current_figure,
    _push_current_figure,
    _use_figure,
    current_figure,  # noqa: F401 - re-exported for __init__.py
)
from .figure_info import InfoPanelManager
from .figure_layout import FigureLayout
from .figure_legend import LegendPanelManager
from .figure_parameters import ParameterManager
from .figure_sound import FigureSoundManager
from .figure_parametric_plot import ParametricPlot, create_or_update_parametric_plot
from .figure_plot import Plot
from .figure_view import FigureViews, View
from .figure_view_manager import ViewManager
# SECTION: Figure (The Coordinator) [id: Figure]
# =============================================================================
class Figure:
    """Notebook-facing coordinator for interactive plotting.
    
    Full API
    --------
    ``Figure(title: str='', samples: int | str | _FigureDefaultSentinel | None=None, default_samples: int | str | _FigureDefaultSentinel | None=None, sampling_points: int | str | _FigureDefaultSentinel | None=None, default_x_range: RangeLike | None=None, default_y_range: RangeLike | None=None, x_label: str='', y_label: str='', show: bool=False, display: bool | None=None, x_range: RangeLike | None=None, y_range: RangeLike | None=None, **_deprecated_kwargs: Any)``
    
    Public members exposed from this class: ``title``, ``views``, ``active_view_id``, ``reflow_layout``, ``add_view``,
        ``set_active_view``, ``view``, ``remove_view``, ``figure_widget``,
        ``figure_widget_for``, ``pane``, ``pane_for``, ``runtime_diagnostics``,
        ``performance_snapshot``, ``performance_report``, ``parameters``, ``info_manager``,
        ``info_output``, ``x_range``, ``default_x_range``, ``y_range``, ``default_y_range``,
        ``current_x_range``, ``current_y_range``, ``samples``, ``default_samples``,
        ``sampling_points``, ``plot_style_options``, ``plot``, ``parametric_plot``,
        ``parameter``, ``render``, ``flush_render_queue``, ``snapshot``, ``to_code``,
        ``code``, ``get_code``, ``sound_generation_enabled``, ``info``,
        ``add_param_change_hook``, ``show``
    
    Parameters
    ----------
    title : str, optional
        Human-readable title text shown in the UI or stored in snapshots. Defaults to ``''``.
    
    samples : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    default_samples : int | str | _FigureDefaultSentinel | None, optional
        Value for ``default_samples`` in this API. Defaults to ``None``.
    
    sampling_points : int | str | _FigureDefaultSentinel | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    default_x_range : RangeLike | None, optional
        Default x-axis range used when a view is created or reset. Defaults to ``None``.
    
    default_y_range : RangeLike | None, optional
        Default y-axis range used when a view is created or reset. Defaults to ``None``.
    
    x_label : str, optional
        Horizontal-axis label text. Defaults to ``''``.
    
    y_label : str, optional
        Vertical-axis label text. Defaults to ``''``.
    
    show : bool, optional
        Boolean flag that requests immediate display in a notebook. Defaults to ``False``.
    
    display : bool | None, optional
        Compatibility display flag or display object, depending on the API. Defaults to ``None``.
    
    x_range : RangeLike | None, optional
        Range specification for the x-axis. Defaults to ``None``.
    
    y_range : RangeLike | None, optional
        Range specification for the y-axis. Defaults to ``None``.
    
    **_deprecated_kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Figure
        New ``Figure`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``title=''``: Human-readable title text shown in the UI or stored in snapshots.
    - ``samples=None``: Sampling density used when evaluating a curve or field.
    - ``default_samples=None``: Value for ``default_samples`` in this API.
    - ``sampling_points=None``: Sampling density used when evaluating a curve or field.
    - ``default_x_range=None``: Default x-axis range used when a view is created or reset.
    - ``default_y_range=None``: Default y-axis range used when a view is created or reset.
    - ``x_label=''``: Horizontal-axis label text.
    - ``y_label=''``: Vertical-axis label text.
    - ``show=False``: Boolean flag that requests immediate display in a notebook.
    - ``display=None``: Compatibility display flag or display object, depending on the API.
    - ``x_range=None``: Range specification for the x-axis.
    - ``y_range=None``: Range specification for the y-axis.
    - ``**_deprecated_kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Figure`` lives in ``gu_toolkit.Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.Figure import Figure
        obj = Figure(...)
    
    Discovery-oriented use::
    
        help(Figure)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
    """
    __slots__ = [
        "plots",
        "_layout",
        "_parameter_manager",
        "_info",
        "_legend",
        "_sound",
        "_view_manager",
        "_views",
        "_sampling_points",
        "_default_x_range",
        "_default_y_range",
        "_default_samples",
        "_render_info_last_log_t",
        "_render_debug_last_log_t",
        "_print_capture",
        "_context_depth",
        "_render_scheduler",
        "_relayout_debouncer",
        "_pending_relayout_view_id",
        "_layout_debug_figure_id",
        "_layout_debug_enabled",
        "_layout_event_buffer",
        "_layout_event_emitter",
        "_layout_event_seq",
        "_has_been_displayed",
        "_performance",
    ]
    @staticmethod
    def _coerce_range_tuple(value: RangeLike) -> tuple[float, float]:
        return (
            float(InputConvert(value[0], float)),
            float(InputConvert(value[1], float)),
        )
    @staticmethod
    def _coerce_samples_value(
        value: int | str | _FigureDefaultSentinel | None,
    ) -> int | None:
        return (
            int(InputConvert(value, int))
            if value is not None and not _is_figure_default(value)
            else None
        )
    def _auto_plot_color(self, *, plot_id: str | None = None) -> str:
        """Return a stable explicit color for a new or existing plot id."""
        if plot_id is None:
            trace_index = len(self.plots)
        else:
            plot_order = tuple(self.plots.keys())
            trace_index = (
                plot_order.index(str(plot_id)) if str(plot_id) in plot_order else len(plot_order)
            )
        return color_for_trace_index(self.figure_widget, trace_index)
    def __init__(
        self,
        *,
        title: str = "",
        samples: int | str | _FigureDefaultSentinel | None = None,
        default_samples: int | str | _FigureDefaultSentinel | None = None,
        sampling_points: int | str | _FigureDefaultSentinel | None = None,
        default_x_range: RangeLike | None = None,
        default_y_range: RangeLike | None = None,
        x_label: str = "",
        y_label: str = "",
        show: bool = False,
        display: bool | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        **_deprecated_kwargs: Any,
    ) -> None:
        # Handle backwards-compatible keyword arguments that were removed from
        # the public constructor.
        def _same_range(lhs: RangeLike, rhs: RangeLike) -> bool:
            return self._coerce_range_tuple(lhs) == self._coerce_range_tuple(rhs)
        def _same_samples(
            lhs: int | str | _FigureDefaultSentinel | None,
            rhs: int | str | _FigureDefaultSentinel | None,
        ) -> bool:
            return self._coerce_samples_value(lhs) == self._coerce_samples_value(rhs)
        debug = bool(_deprecated_kwargs.pop("debug", False))
        default_view_id = _deprecated_kwargs.pop("default_view_id", None)
        plotly_legend_mode = _deprecated_kwargs.pop("plotly_legend_mode", None)
        if _deprecated_kwargs:
            unexpected = ", ".join(sorted(_deprecated_kwargs))
            raise TypeError(f"Figure() got unexpected keyword argument(s): {unexpected}")
        if debug:
            warnings.warn(
                "Figure(debug=...) is deprecated. Configure logging instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            logging.getLogger("gu_toolkit.layout").setLevel(logging.DEBUG)
        if default_view_id is not None:
            warnings.warn(
                "Figure(default_view_id=...) is deprecated and ignored; view ids are managed via fig.views.",
                DeprecationWarning,
                stacklevel=2,
            )
        if plotly_legend_mode is not None:
            warnings.warn(
                "Figure(plotly_legend_mode=...) is deprecated; the toolkit uses a side-panel legend.",
                DeprecationWarning,
                stacklevel=2,
            )
        if x_range is not None:
            if default_x_range is not None and not _same_range(x_range, default_x_range):
                raise ValueError(
                    "Figure() received both x_range= and default_x_range= with different values; use only one initial x-range keyword."
                )
            default_x_range = x_range
        if y_range is not None:
            if default_y_range is not None and not _same_range(y_range, default_y_range):
                raise ValueError(
                    "Figure() received both y_range= and default_y_range= with different values; use only one initial y-range keyword."
                )
            default_y_range = y_range
        if samples is not None:
            if default_samples is not None and not _same_samples(samples, default_samples):
                raise ValueError(
                    "Figure() received both samples= and default_samples= with different values; use only one initial samples keyword."
                )
            if sampling_points is not None and not _same_samples(samples, sampling_points):
                raise ValueError(
                    "Figure() received both samples= and sampling_points= with different values; use only one initial samples keyword."
                )
            default_samples = samples
            sampling_points = samples
        elif default_samples is not None:
            if sampling_points is not None and not _same_samples(default_samples, sampling_points):
                raise ValueError(
                    "Figure() received both default_samples= and sampling_points= with different values; use only one initial samples keyword."
                )
            sampling_points = default_samples
        if display is not None:
            warnings.warn(
                "Figure(show=...) is deprecated; use Figure(show=...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if show is not False and bool(display) != bool(show):
                raise ValueError(
                    "Figure() received both show= and show= with different values; use only show=."
                )
            show = bool(display)

        if default_x_range is None:
            default_x_range = (-4, 4)
        if default_y_range is None:
            default_y_range = (-3, 3)

        resolved_samples = self._coerce_samples_value(sampling_points)
        if resolved_samples is None:
            resolved_samples = 500

        self._sampling_points = resolved_samples
        self._default_x_range = self._coerce_range_tuple(default_x_range)
        self._default_y_range = self._coerce_range_tuple(default_y_range)
        self._default_samples = None
        self.plots: dict[str, Plot] = {}
        self._print_capture: ExitStack | None = None
        self._context_depth = 0
        self._pending_relayout_view_id: str | None = None
        self._has_been_displayed = False
        self._layout_debug_figure_id = new_debug_id("figure")
        self._layout_debug_enabled = is_layout_logger_explicitly_enabled(
            "gu_toolkit.layout.figure"
        )
        self._layout_event_buffer = LayoutEventBuffer(maxlen=500)
        self._layout_event_seq = 0
        self._layout_event_emitter = make_event_emitter(
            logging.getLogger("gu_toolkit.layout.figure"),
            buffer=self._layout_event_buffer,
            base_fields={"figure_id": self._layout_debug_figure_id},
            seq_factory=self._next_layout_seq,
        )

        self._performance = PerformanceMonitor(f"Figure[{self._layout_debug_figure_id}]")
        self._performance.increment("figures_created")
        self._performance.set_state(
            title=title,
            default_x_range=self._default_x_range,
            default_y_range=self._default_y_range,
            samples=self._sampling_points,
            render_target_interval_ms=RENDER_TARGET_INTERVAL_MS,
        )

        # 1. Initialize Layout (View)
        self._layout = FigureLayout(title=title)
        if self._layout_debug_enabled:
            self._layout.bind_layout_debug(
                self._emit_layout_event, figure_id=self._layout_debug_figure_id
            )

        # 2. Initialize Managers
        # Note: we pass a callback for rendering so params can trigger updates
        self._parameter_manager = ParameterManager(
            self.render,
            self._layout.params_box,
            modal_host=self._layout.root_widget,
        )
        self._info = InfoPanelManager(self._layout.info_box)
        self._info.bind_figure(self)
        self._info.bind_layout_change_callback(self._on_info_panel_structure_changed)
        self._legend = LegendPanelManager(
            self._layout.legend_box,
            modal_host=self._layout.root_widget,
            root_widget=self._layout.root_widget,
            header_toolbar=self._layout.legend_header_toolbar,
            enable_plot_editor=False,
        )
        # Phase 0 decontamination deliberately removes the legend-launched plot
        # editor until a later rebuild phase reintroduces a smaller, auditable
        # input path.
        self._sound = FigureSoundManager(
            self,
            self._legend,
            root_widget=self._layout.root_widget,
        )
        self._render_scheduler = FigureRenderScheduler(
            self._perform_render_request,
            execute_every_ms=RENDER_TARGET_INTERVAL_MS,
            name="Figure.render",
            event_sink=(
                self._emit_layout_event if self._layout_debug_enabled else None
            ),
        )

        # 3. Figure-level relayout debouncer + layout observers
        self._relayout_debouncer = QueuedDebouncer(
            self._dispatch_relayout,
            execute_every_ms=RENDER_TARGET_INTERVAL_MS,
            drop_overflow=True,
            name="Figure.relayout",
            event_sink=(self._emit_layout_event if self._layout_debug_enabled else (lambda **_kwargs: None)),
        )
        self._emit_layout_event("relayout_debouncer_created", source="Figure", phase="completed", level=logging.INFO)
        self._layout.observe_view_selection(self.set_active_view)
        self._layout.observe_full_width_change(
            lambda _is_full: self._request_active_view_reflow("full_width_change")
        )
        self._layout.bind_view_reflow(self._request_view_reflow)

        # 4. Views facade and model registry
        self._view_manager = ViewManager()
        self._views = FigureViews(self)

        # 5. Set initial state
        self.add_view(
            self._view_manager.default_view_id,
            x_range=default_x_range,
            y_range=default_y_range,
            x_label=x_label,
            y_label=y_label,
        )
        self._legend.set_active_view(self.views.current_id)
        self._emit_layout_event("active_view_after_remove", source="Figure", phase="completed", view_id=self.views.current_id)
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

        self._emit_layout_event("figure_created", source="Figure", phase="completed", level=logging.INFO, title=title, samples=self.samples, default_samples=self.default_samples)

        # 6. Logging state
        self._render_info_last_log_t = 0.0
        self._render_debug_last_log_t = 0.0

        if show:
            self.show()

    def _next_layout_seq(self) -> int:
        self._layout_event_seq += 1
        return self._layout_event_seq

    def _emit_layout_event(self, event: str, *, source: str, phase: str, level: int = logging.DEBUG, **fields: Any) -> dict[str, Any]:
        if not self._layout_debug_enabled:
            return {}
        if "active_view_id" not in fields:
            fields["active_view_id"] = (
                self._view_manager.active_view_id
                if hasattr(self, "_view_manager")
                else None
            )
        return self._layout_event_emitter(
            event=event,
            source=source,
            phase=phase,
            level=level,
            **fields,
        )

    def _python_layout_snapshot(self, view_id: str | None = None) -> dict[str, Any]:
        active_id = view_id or (self.views.current_id if getattr(self, "_view_manager", None) and self._view_manager.views else None)
        snap = {
            "content_wrapper_display": self._layout.content_wrapper.layout.display,
            "content_wrapper_flex_flow": self._layout.content_wrapper.layout.flex_flow,
            "content_layout_mode": self._layout.content_layout_mode,
            "sidebar_display": self._layout.sidebar_container.layout.display,
            "view_stage_height": self._layout.view_stage.layout.height,
        }
        if active_id is not None and active_id in self.views:
            pane = self.views[active_id].pane
            snap.update(pane.debug_snapshot())
        return snap

    # --- Figure-level properties ---
    @property
    def title(self) -> str:
        """Return the title text shown above the figure.
        
        Full API
        --------
        ``obj.title -> str``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.title
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._layout.get_title()

    @title.setter
    def title(self, value: str) -> None:
        """Set the title text shown above the figure.
        
        Full API
        --------
        ``obj.title = value``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.title = value
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self._layout.set_title(value)

    # -------------------------------
    # Views
    # -------------------------------

    @property
    def views(self) -> FigureViews:
        """Mapping-like access to the figure's public :class:`View` objects.
        
        Full API
        --------
        ``obj.views -> FigureViews``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        FigureViews
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.views
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._views

    @property
    def active_view_id(self) -> str:
        """Return the currently active view id.
        
        Full API
        --------
        ``obj.active_view_id -> str``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.active_view_id
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        warnings.warn(
            "Figure.active_view_id is deprecated; use fig.views.current_id.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.views.current_id

    def _create_view(
        self,
        view_id: str,
        *,
        title: str | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
    ) -> View:
        """Create one public :class:`View` object with its stable runtime."""
        figure_widget, widget_status = create_plotly_figure_widget()
        self._performance.set_state(widget_support=widget_status.to_dict())
        if not widget_status.figurewidget_supported:
            warning_message = (
                "gu_toolkit could not create a real Plotly FigureWidget. Falling back to a plain plotly Figure. "
                "This commonly means anywidget is missing in the notebook kernel, and interactive animation/responsiveness will be degraded. Install anywidget to restore smooth FigureWidget updates."
            )
            warn_once(
                "missing-anywidget-figurewidget",
                warning_message,
                category=RuntimeWarning,
                stacklevel=3,
            )
            logging.getLogger(__name__).warning(
                "%s Runtime detail: %s",
                warning_message,
                widget_status.reason,
            )
            self._performance.increment("degraded_plotly_widget_runtime")
            self._emit_layout_event(
                "plotly_widget_degraded",
                source="Figure",
                phase="warning",
                level=logging.WARNING,
                reason=widget_status.reason,
                widget_mode=widget_status.figurewidget_mode,
            )
        elif widget_status.anywidget_is_fallback:
            warning_message = (
                "gu_toolkit detected that real anywidget is missing in the notebook kernel. "
                "A local fallback stub allowed Plotly FigureWidget to construct, but interactivity or performance can still be degraded until anywidget is installed."
            )
            warn_once(
                "missing-anywidget-fallback-figurewidget",
                warning_message,
                category=RuntimeWarning,
                stacklevel=3,
            )
            logging.getLogger(__name__).warning(
                "%s Runtime detail: %s",
                warning_message,
                widget_status.reason,
            )
            self._performance.increment("anywidget_fallback_runtime")
            self._emit_layout_event(
                "plotly_widget_anywidget_fallback",
                source="Figure",
                phase="warning",
                level=logging.WARNING,
                reason=widget_status.reason,
                widget_mode=widget_status.figurewidget_mode,
            )
        figure_widget.update_layout(**self._default_figure_layout())
        pane = PlotlyPane(
            figure_widget,
            style=PlotlyPaneStyle(
                padding_px=8,
                border="1px solid rgba(15,23,42,0.08)",
                border_radius_px=10,
                overflow="hidden",
            ),
            autorange_mode="none",
            defer_reveal=True,
        )
        view = View(
            figure=self,
            id=view_id,
            title=(str(view_id) if title is None else str(title)),
            x_label=(x_label or ""),
            y_label=(y_label or ""),
            default_x_range=(x_range if x_range is not None else self.default_x_range),
            default_y_range=(y_range if y_range is not None else self.default_y_range),
            figure_widget=figure_widget,
            pane=pane,
        )
        if self._layout_debug_enabled:
            pane.bind_layout_debug(self._emit_layout_event, figure_id=self._layout_debug_figure_id, view_id=view_id)
        self._emit_layout_event("view_runtime_created", source="Figure", phase="completed", view_id=view_id, pane_id=pane.debug_pane_id, default_x_range=view.default_x_range, default_y_range=view.default_y_range)
        return view

    def _attach_view_callbacks(self, view: View) -> None:
        """Attach figure-level relayout routing to one view widget."""
        view.figure_widget.layout.on_change(
            lambda *args, _view_id=view.id: self._queue_relayout(_view_id, *args),
            "xaxis.range",
            "yaxis.range",
        )

    def _request_view_reflow(self, view_id: str, reason: str) -> str | None:
        """Explicitly reflow one view pane after a geometry change."""
        if not self._view_manager.views:
            self._emit_layout_event(
                "reflow_requested",
                source="Figure",
                phase="skipped",
                level=logging.WARNING,
                reason=reason,
                outcome="no_views",
                view_id=view_id,
            )
            return None

        target_view_id = str(view_id)
        if target_view_id not in self.views:
            self._emit_layout_event(
                "reflow_requested",
                source="Figure",
                phase="skipped",
                level=logging.WARNING,
                reason=reason,
                outcome="unknown_view",
                view_id=target_view_id,
            )
            return None

        view = self.views[target_view_id]
        request_id = new_request_id()
        self._emit_layout_event(
            "reflow_requested",
            source="Figure",
            phase="requested",
            level=logging.INFO,
            reason=reason,
            request_id=request_id,
            view_id=view.id,
            pane_id=view.pane.debug_pane_id,
            snapshot=self._python_layout_snapshot(view.id),
        )
        try:
            view.pane.reflow(
                reason=reason,
                request_id=request_id,
                view_id=view.id,
                figure_id=self._layout_debug_figure_id,
            )
        except Exception:  # pragma: no cover - defensive widget boundary
            self._emit_layout_event(
                "reflow_send_failed",
                source="Figure",
                phase="failed",
                level=logging.ERROR,
                reason=reason,
                request_id=request_id,
                view_id=view.id,
                pane_id=view.pane.debug_pane_id,
            )
            logger.debug("View reflow failed", exc_info=True)
            return None
        return request_id

    def _request_active_view_reflow(self, reason: str) -> None:
        """Explicitly reflow the active view pane after geometry changes."""
        if not self._view_manager.views:
            self._request_view_reflow("", reason)
            return
        self._request_view_reflow(self.views.current_id, reason)

    def reflow_layout(self, *, reason: str = "manual", view_id: str | None = None) -> str | None:
        """Public helper to request a pane reflow for the active or named view.
        
        Full API
        --------
        ``obj.reflow_layout(*, reason: str='manual', view_id: str | None=None) -> str | None``
        
        Parameters
        ----------
        reason : str, optional
            Short machine/human-readable reason recorded for scheduling or rendering. Defaults to ``'manual'``.
        
        view_id : str | None, optional
            Identifier for the relevant view inside a figure. Defaults to ``None``.
        
        Returns
        -------
        str | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``reason='manual'``: Short machine/human-readable reason recorded for scheduling or rendering.
        - ``view_id=None``: Identifier for the relevant view inside a figure.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.reflow_layout(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        target_view_id = str(view_id) if view_id is not None else (self.views.current_id if self._view_manager.views else "")
        if not target_view_id:
            self._request_view_reflow(target_view_id, reason)
            return None
        return self._request_view_reflow(target_view_id, reason)

    def add_view(
        self,
        id: str,
        *,
        title: str | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        activate: bool = False,
    ) -> View:
        """Create and register a new plotting workspace.
        
        Full API
        --------
        ``obj.add_view(id: str, *, title: str | None=None, x_range: RangeLike | None=None, y_range: RangeLike | None=None, x_label: str | None=None, y_label: str | None=None, activate: bool=False) -> View``
        
        Parameters
        ----------
        id : str
            Stable identifier used to create, update, or look up the target object. Required.
        
        title : str | None, optional
            Human-readable title text shown in the UI or stored in snapshots. Defaults to ``None``.
        
        x_range : RangeLike | None, optional
            Range specification for the x-axis. Defaults to ``None``.
        
        y_range : RangeLike | None, optional
            Range specification for the y-axis. Defaults to ``None``.
        
        x_label : str | None, optional
            Horizontal-axis label text. Defaults to ``None``.
        
        y_label : str | None, optional
            Vertical-axis label text. Defaults to ``None``.
        
        activate : bool, optional
            Boolean flag that requests the newly created/updated object become active. Defaults to ``False``.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``title=None``: Human-readable title text shown in the UI or stored in snapshots.
        - ``x_range=None``: Range specification for the x-axis.
        - ``y_range=None``: Range specification for the y-axis.
        - ``x_label=None``: Horizontal-axis label text.
        - ``y_label=None``: Vertical-axis label text.
        - ``activate=False``: Boolean flag that requests the newly created/updated object become active.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.add_view(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        view_id = str(id)
        view = self._create_view(
            view_id,
            title=title,
            x_range=x_range,
            y_range=y_range,
            x_label=x_label,
            y_label=y_label,
        )
        self._view_manager.register_view(view)
        self._layout.ensure_view_page(view.id, view.title)
        self._layout.attach_view_widget(view.id, view.pane.widget)
        self._layout.set_view_order(tuple(self._view_manager.views.keys()))
        self._attach_view_callbacks(view)
        if view.is_active:
            self._layout.set_active_view(view.id)
            self._info.set_active_view(view.id)
            self._legend.set_active_view(view.id)
        else:
            self._layout.set_active_view(self.views.current_id)
        self._emit_layout_event("view_registered", source="Figure", phase="completed", level=logging.INFO, view_id=view.id, pane_id=view.pane.debug_pane_id, activate=activate)
        if activate and not view.is_active:
            self.set_active_view(view_id)
        else:
            self._request_active_view_reflow("view_added")
        return view

    def set_active_view(self, id: str) -> None:
        """Set the active view id and synchronize widget ranges.
        
        Full API
        --------
        ``obj.set_active_view(id: str) -> None``
        
        Parameters
        ----------
        id : str
            Stable identifier used to create, update, or look up the target object. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.set_active_view(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        view_id = str(id)
        if not self._view_manager.views:
            raise KeyError(f"Unknown view: {view_id}")

        current_view = self.views.current
        if current_view.id == view_id:
            self._layout.set_active_view(view_id)
            self._emit_layout_event("view_switch_requested", source="Figure", phase="completed", view_id=view_id, outcome="already_active")
            return

        self._emit_layout_event("view_switch_requested", source="Figure", phase="requested", level=logging.INFO, view_id=view_id, previous_view_id=current_view.id)
        current_view.current_x_range
        current_view.current_y_range
        self._emit_layout_event("viewport_captured", source="Figure", phase="completed", view_id=current_view.id, viewport_x_range=current_view.viewport_x_range, viewport_y_range=current_view.viewport_y_range)

        transition = self._view_manager.set_active_view(view_id)
        if transition is None:
            self._layout.set_active_view(view_id)
            self._emit_layout_event("active_view_changed", source="Figure", phase="completed", level=logging.INFO, view_id=view_id)
            return

        _, nxt = transition
        self._layout.set_active_view(view_id)
        self._info.set_active_view(view_id)
        self._legend.set_active_view(view_id)

        nxt.current_x_range = nxt.viewport_x_range or nxt.x_range
        nxt.current_y_range = nxt.viewport_y_range or nxt.y_range
        self._emit_layout_event("active_view_changed", source="Figure", phase="completed", level=logging.INFO, view_id=view_id, previous_view_id=current_view.id)
        self._emit_layout_event("viewport_restored", source="Figure", phase="completed", view_id=view_id, viewport_x_range=nxt.viewport_x_range, viewport_y_range=nxt.viewport_y_range)
        self._request_active_view_reflow("view_activated")
        self.render(reason="view_switch", force=True)
        if nxt.is_stale:
            self._view_manager.clear_stale(self.views.current_id)

        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

    @contextmanager
    def view(self, id: str) -> Iterator[Figure]:
        """Deprecated alias for ``with fig.views[id]:``.
        
        Full API
        --------
        ``obj.view(id: str) -> Iterator[Figure]``
        
        Parameters
        ----------
        id : str
            Stable identifier used to create, update, or look up the target object. Required.
        
        Returns
        -------
        Iterator[Figure]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.view(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        warnings.warn(
            "Figure.view(...) is deprecated; use `with fig.views[view_id]:` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        with self.views[str(id)]:
            yield self

    def remove_view(self, id: str) -> None:
        """Remove a view and drop plot memberships to it.
        
        Full API
        --------
        ``obj.remove_view(id: str) -> None``
        
        Parameters
        ----------
        id : str
            Stable identifier used to create, update, or look up the target object. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.remove_view(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        view_id = str(id)
        if view_id not in self._view_manager.views:
            return
        for plot in self.plots.values():
            plot.remove_from_view(view_id)
            self._legend.on_plot_updated(plot)
        self._emit_layout_event("view_removed", source="Figure", phase="requested", level=logging.INFO, view_id=view_id)
        self._view_manager.remove_view(view_id)
        self._layout.remove_view_page(view_id)
        self._layout.set_view_order(tuple(self._view_manager.views.keys()))
        self._layout.set_active_view(self.views.current_id)
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")
        else:
            self._request_active_view_reflow("view_removed")

    def _sync_sidebar_visibility(self) -> bool:
        """Apply consolidated sidebar section visibility from all managers."""
        changed = self._layout.update_sidebar_visibility(
            self._parameter_manager.has_params,
            self._info.has_info,
            self._legend.panel_visible,
        )
        self._emit_layout_event("sidebar_visibility_sync", source="Figure", phase="completed", changed=changed, params_visible=self._parameter_manager.has_params, info_visible=self._info.has_info, legend_visible=self._legend.panel_visible)
        return changed

    def _on_info_panel_structure_changed(self, reason: str) -> None:
        """Resync sidebar layout after direct ``info_manager`` mutations."""
        self._emit_layout_event(
            "info_panel_structure_changed",
            source="Figure",
            phase="completed",
            reason=reason,
        )
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")


    # --- Layout ---
    def _default_figure_layout(self) -> dict[str, Any]:
        """Return shared Plotly layout defaults copied into each view widget."""
        return {
            "autosize": True,
            "template": "plotly_white",
            # The toolkit provides a dedicated legend side panel. Keep Plotly's
            # built-in legend off by default to avoid duplication.
            "showlegend": False,
            "margin": {"l": 48, "r": 28, "t": 48, "b": 44},
            "font": {
                "family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                "size": 14,
                "color": "#1f2933",
            },
            "paper_bgcolor": "#ffffff",
            "plot_bgcolor": "#f8fafc",
            "legend": {
                "bgcolor": "rgba(255,255,255,0.7)",
                "bordercolor": "rgba(15,23,42,0.08)",
                "borderwidth": 1,
            },
            "xaxis": {
                "zeroline": True,
                "zerolinewidth": 1.5,
                "zerolinecolor": "#334155",
                "showline": True,
                "linecolor": "#94a3b8",
                "linewidth": 1,
                "mirror": True,
                "ticks": "outside",
                "tickcolor": "#94a3b8",
                "ticklen": 6,
                "showgrid": True,
                "gridcolor": "rgba(148,163,184,0.35)",
                "gridwidth": 1,
            },
            "yaxis": {
                "zeroline": True,
                "zerolinewidth": 1.5,
                "zerolinecolor": "#334155",
                "showline": True,
                "linecolor": "#94a3b8",
                "linewidth": 1,
                "mirror": True,
                "ticks": "outside",
                "tickcolor": "#94a3b8",
                "ticklen": 6,
                "showgrid": True,
                "gridcolor": "rgba(148,163,184,0.35)",
                "gridwidth": 1,
            },
        }

    @property
    def figure_widget(self) -> go.FigureWidget:
        """Access the current view's Plotly ``FigureWidget``.
        
        Full API
        --------
        ``obj.figure_widget -> go.FigureWidget``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        go.FigureWidget
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.figure_widget
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.views.current.figure_widget

    def figure_widget_for(self, view_id: str) -> go.FigureWidget:
        """Return the Plotly FigureWidget backing ``view_id``.
        
        Full API
        --------
        ``obj.figure_widget_for(view_id: str) -> go.FigureWidget``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        go.FigureWidget
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.figure_widget_for(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.views[str(view_id)].figure_widget

    @property
    def pane(self) -> PlotlyPane:
        """Access the active view's :class:`PlotlyPane`.
        
        Full API
        --------
        ``obj.pane -> PlotlyPane``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        PlotlyPane
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.pane
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.views.current.pane

    def pane_for(self, view_id: str) -> PlotlyPane:
        """Return the :class:`PlotlyPane` backing ``view_id``.
        
        Full API
        --------
        ``obj.pane_for(view_id: str) -> PlotlyPane``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        PlotlyPane
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.pane_for(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.views[str(view_id)].pane

    def runtime_diagnostics(self) -> dict[str, Any]:
        """Return runtime diagnostics for the current execution environment.
        
        Full API
        --------
        ``obj.runtime_diagnostics() -> dict[str, Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.runtime_diagnostics(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return figure_runtime_diagnostics(
            self,
            render_target_interval_ms=RENDER_TARGET_INTERVAL_MS,
        )

    def performance_snapshot(
        self,
        *,
        recent_event_limit: int = 25,
        include_layout_events: bool = False,
    ) -> dict[str, Any]:
        """Return nested performance counters and timing snapshots.
        
        Full API
        --------
        ``obj.performance_snapshot(*, recent_event_limit: int=25, include_layout_events: bool=False) -> dict[str, Any]``
        
        Parameters
        ----------
        recent_event_limit : int, optional
            Value for ``recent_event_limit`` in this API. Defaults to ``25``.
        
        include_layout_events : bool, optional
            Value for ``include_layout_events`` in this API. Defaults to ``False``.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_event_limit=25``: Value for ``recent_event_limit`` in this API.
        - ``include_layout_events=False``: Value for ``include_layout_events`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.performance_snapshot(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return figure_performance_snapshot(
            self,
            render_target_interval_ms=RENDER_TARGET_INTERVAL_MS,
            recent_event_limit=recent_event_limit,
            include_layout_events=include_layout_events,
        )

    def performance_report(
        self,
        *,
        recent_event_limit: int = 10,
        include_layout_events: bool = False,
    ) -> str:
        """Return a readable multi-section performance diagnostics report.
        
        Full API
        --------
        ``obj.performance_report(*, recent_event_limit: int=10, include_layout_events: bool=False) -> str``
        
        Parameters
        ----------
        recent_event_limit : int, optional
            Value for ``recent_event_limit`` in this API. Defaults to ``10``.
        
        include_layout_events : bool, optional
            Value for ``include_layout_events`` in this API. Defaults to ``False``.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_event_limit=10``: Value for ``recent_event_limit`` in this API.
        - ``include_layout_events=False``: Value for ``include_layout_events`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.performance_report(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return figure_performance_report(
            self,
            render_target_interval_ms=RENDER_TARGET_INTERVAL_MS,
            recent_event_limit=recent_event_limit,
            include_layout_events=include_layout_events,
        )


    # --- Parameters ---
    @property
    def parameters(self) -> ParameterManager:
        """The figure parameter manager.
        
        Full API
        --------
        ``obj.parameters -> ParameterManager``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        ParameterManager
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.parameters
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._parameter_manager

    @property
    def info_manager(self) -> InfoPanelManager:
        """Advanced access to the Info section manager.
        
        Full API
        --------
        ``obj.info_manager -> InfoPanelManager``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        InfoPanelManager
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.info_manager
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._info

    # --- Info Cards ---
    @property
    def info_output(self) -> Mapping[Hashable, widgets.Output]:
        """Compatibility view of raw info outputs keyed by id.
        
        Full API
        --------
        ``obj.info_output -> Mapping[Hashable, widgets.Output]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Mapping[Hashable, widgets.Output]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.info_output
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._info.outputs

    @property
    def x_range(self) -> tuple[float, float]:
        """Return the current view's default x-axis range.
        
        Full API
        --------
        ``obj.x_range -> tuple[float, float]``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.x_range
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.views.current.x_range

    @x_range.setter
    def x_range(self, value: RangeLike) -> None:
        """Set the current view's default x-axis range.
        
        Full API
        --------
        ``obj.x_range = value``
        
        Parameters
        ----------
        value : RangeLike
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.x_range = value
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self.views.current.x_range = value

    @property
    def default_x_range(self) -> tuple[float, float]:
        """Return the figure-level default x-range used for new views.
        
        Full API
        --------
        ``obj.default_x_range -> tuple[float, float]``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.default_x_range
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._default_x_range

    @default_x_range.setter
    def default_x_range(self, value: RangeLike) -> None:
        """Work with default x range on ``Figure``.
        
        Full API
        --------
        ``obj.default_x_range = value``
        
        Parameters
        ----------
        value : RangeLike
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.default_x_range = value
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """

        self._default_x_range = self._coerce_range_tuple(value)

    @property
    def y_range(self) -> tuple[float, float]:
        """Return the current view's default y-axis range.
        
        Full API
        --------
        ``obj.y_range -> tuple[float, float]``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.y_range
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.views.current.y_range

    @y_range.setter
    def y_range(self, value: RangeLike) -> None:
        """Set the current view's default y-axis range.
        
        Full API
        --------
        ``obj.y_range = value``
        
        Parameters
        ----------
        value : RangeLike
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.y_range = value
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self.views.current.y_range = value

    @property
    def default_y_range(self) -> tuple[float, float]:
        """Return the figure-level default y-range used for new views.
        
        Full API
        --------
        ``obj.default_y_range -> tuple[float, float]``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.default_y_range
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._default_y_range

    @default_y_range.setter
    def default_y_range(self, value: RangeLike) -> None:
        """Work with default y range on ``Figure``.
        
        Full API
        --------
        ``obj.default_y_range = value``
        
        Parameters
        ----------
        value : RangeLike
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.default_y_range = value
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """

        self._default_y_range = self._coerce_range_tuple(value)

    @property
    def _viewport_x_range(self) -> tuple[float, float] | None:
        """Control for the current viewport x-range.

        Reading this property queries the live Plotly widget viewport.
        Setting it pans/zooms the visible x-range without changing ``x_range``.
        """
        return self.views.current.current_x_range

    @_viewport_x_range.setter
    def _viewport_x_range(self, value: RangeLike | None) -> None:
        self.views.current.current_x_range = value

    @property
    def _viewport_y_range(self) -> tuple[float, float] | None:
        """Control for the current viewport y-range.

        Reading this property queries the live Plotly widget viewport.
        Setting it pans/zooms the visible y-range without changing ``y_range``.
        """
        return self.views.current.current_y_range

    @_viewport_y_range.setter
    def _viewport_y_range(self, value: RangeLike | None) -> None:
        self.views.current.current_y_range = value

    @property
    def current_x_range(self) -> tuple[float, float] | None:
        """Return the current viewport x-range.
        
        Full API
        --------
        ``obj.current_x_range -> tuple[float, float] | None``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.current_x_range
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._viewport_x_range

    @property
    def current_y_range(self) -> tuple[float, float] | None:
        """Return the current viewport y-range (read-only).
        
        Full API
        --------
        ``obj.current_y_range -> tuple[float, float] | None``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.current_y_range
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._viewport_y_range

    @property
    def samples(self) -> int | None:
        """Return the figure's current sample count for inherited plots.
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.samples
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._sampling_points

    @samples.setter
    def samples(self, val: int | str | _FigureDefaultSentinel | None) -> None:
        """Set the figure's current sample count for inherited plots.
        
        Full API
        --------
        ``obj.samples = val``
        
        Parameters
        ----------
        val : int | str | _FigureDefaultSentinel | None
            Value for ``val`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.samples = val
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self._sampling_points = self._coerce_samples_value(val)

    @property
    def default_samples(self) -> int | None:
        """Return the default sample count used for newly created plots.
        
        Full API
        --------
        ``obj.default_samples -> int | None``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.default_samples
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        if self._default_samples is None:
            return self.samples
        return self._default_samples

    @default_samples.setter
    def default_samples(self, val: int | str | _FigureDefaultSentinel | None) -> None:
        """Work with default samples on ``Figure``.
        
        Full API
        --------
        ``obj.default_samples = val``
        
        Parameters
        ----------
        val : int | str | _FigureDefaultSentinel | None
            Value for ``val`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.default_samples = val
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """

        if val is None or _is_figure_default(val):
            self._default_samples = None
            return
        self._default_samples = self._coerce_samples_value(val)

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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.sampling_points
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.samples

    @sampling_points.setter
    def sampling_points(self, val: int | str | _FigureDefaultSentinel | None) -> None:
        """Work with sampling points on ``Figure``.
        
        Full API
        --------
        ``obj.sampling_points = val``
        
        Parameters
        ----------
        val : int | str | _FigureDefaultSentinel | None
            Value for ``val`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.sampling_points = val
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """

        self.samples = val

    # --- Public API ---

    @staticmethod
    def plot_style_options() -> dict[str, str]:
        """Return discoverable help text for supported plot-style keywords.
        
        Full API
        --------
        ``Figure.plot_style_options() -> dict[str, str]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, str]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            result = Figure.plot_style_options(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return plot_style_option_docs()

    def plot(
        self,
        func: Any,
        var: Any,
        parameters: ParameterKeyOrKeys | None = None,
        id: str | None = None,
        label: str | None = None,
        visible: VisibleSpec = True,
        x_domain: RangeLike | None = None,
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
        """Plot an expression/callable on the figure (and keep it “live”).
        
        Full API
        --------
        ``obj.plot(func: Any, var: Any, parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: VisibleSpec=True, x_domain: RangeLike | None=None, sampling_points: int | str | _FigureDefaultSentinel | None=None, color: str | None=None, thickness: int | float | None=None, width: int | float | None=None, dash: str | None=None, line: Mapping[str, Any] | None=None, opacity: int | float | None=None, alpha: int | float | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, view: str | Sequence[str] | None=None, vars: PlotVarsSpec | None=None, samples: int | str | _FigureDefaultSentinel | None=None) -> Plot``
        
        Parameters
        ----------
        func : Any
            Symbolic expression or callable to evaluate. Required.
        
        var : Any
            Primary symbolic variable used for evaluation. Required.
        
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
        - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.plot(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        id = resolve_plot_id(self.plots, id)

        normalized_var, normalized_func, normalized_numeric_fn, inferred_parameters = (
            normalize_plot_inputs(
                func,
                var,
                vars=vars,
                id_hint=id,
            )
        )

        if isinstance(var, tuple) and len(var) == 3 and x_domain is not None:
            raise ValueError(
                "plot() cannot combine a range tuple with x_domain=. "
                "Use only one range source, e.g. plot(f, (x, -4, 4))."
            )

        if isinstance(var, tuple) and len(var) == 3:
            x_domain = (var[1], var[2])

        if samples is not None and sampling_points is not None:
            lhs = (
                None if _is_figure_default(samples) else self._coerce_samples_value(samples)
            )
            rhs = (
                None
                if _is_figure_default(sampling_points)
                else self._coerce_samples_value(sampling_points)
            )
            if lhs != rhs:
                raise ValueError(
                    "plot() received both samples= and sampling_points= with different values; use only one samples keyword."
                )

        samples_supplied = samples is not None or sampling_points is not None
        requested_samples = samples if samples is not None else sampling_points
        if requested_samples is None:
            explicit_plot_samples: int | str | _FigureDefaultSentinel | None = None
        elif _is_figure_default(requested_samples):
            explicit_plot_samples = "figure_default"
        else:
            explicit_plot_samples = self._coerce_samples_value(requested_samples)

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
            caller="plot()",
        )
        color = style_kwargs.get("color")
        thickness = style_kwargs.get("thickness")
        dash = style_kwargs.get("dash")
        line = style_kwargs.get("line")
        opacity = style_kwargs.get("opacity")
        trace = style_kwargs.get("trace")
        autonormalization = style_kwargs.get("autonormalization")

        # Parameter normalization
        if parameters is None:
            requested_parameter_keys: ParameterKeyOrKeys = tuple(inferred_parameters)
            plot_parameters = tuple(inferred_parameters)
        else:
            requested_parameter_keys = parameters
            plot_parameters = expand_parameter_keys_to_symbols(
                parameters,
                inferred_parameters,
                role="plot parameters",
            )

        # Ensure Parameters Exist (Delegate to Manager)
        if requested_parameter_keys:
            self.parameter(requested_parameter_keys)

        # Update UI visibility
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

        if id in self.plots and isinstance(self.plots[id], ParametricPlot):
            remove_plot_from_figure(self, id)

        # Create or Update Plot
        requested_color = explicit_style_color(color=color, line=line, trace=trace)
        if id in self.plots:
            update_dont_create = True
            if requested_color is None and self.plots[id].color is None:
                color = self._auto_plot_color(plot_id=id)
        else:
            update_dont_create = False
            if requested_color is None:
                color = self._auto_plot_color()

        if update_dont_create:
            update_kwargs: dict[str, Any] = {
                "var": normalized_var,
                "func": normalized_func,
                "parameters": plot_parameters,
                "visible": visible,
                "x_domain": x_domain,
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
            if normalized_numeric_fn is not None:
                update_kwargs["numeric_function"] = normalized_numeric_fn
            if label is not None:
                update_kwargs["label"] = label
            self.plots[id].update(**update_kwargs)
            plot = self.plots[id]
            self._legend.on_plot_updated(plot)
            if self._sync_sidebar_visibility():
                self._request_active_view_reflow("sidebar_visibility")
        else:
            view_ids = normalize_view_ids(
                view,
                default_view_id=self.views.current_id,
            )
            create_plot_samples: int | str | _FigureDefaultSentinel | None = explicit_plot_samples
            if (
                not samples_supplied
                and self._default_samples is not None
                and self.default_samples != self.samples
            ):
                create_plot_samples = self.default_samples

            plot = Plot(
                var=normalized_var,
                func=normalized_func,
                smart_figure=self,
                parameters=plot_parameters,
                x_domain=x_domain,
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
                numeric_function=normalized_numeric_fn,
            )
            self.plots[id] = plot
            self._legend.on_plot_added(plot)
            if self._sync_sidebar_visibility():
                self._request_active_view_reflow("sidebar_visibility")

        return plot

    def parametric_plot(
        self,
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
        """Plot a parametric curve ``(x(t), y(t))`` on the figure.
        
        Full API
        --------
        ``obj.parametric_plot(funcs: Sequence[Any], parameter_range: tuple[Any, Any, Any], parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: VisibleSpec=True, sampling_points: int | str | _FigureDefaultSentinel | None=None, color: str | None=None, thickness: int | float | None=None, width: int | float | None=None, dash: str | None=None, line: Mapping[str, Any] | None=None, opacity: int | float | None=None, alpha: int | float | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, view: str | Sequence[str] | None=None, vars: PlotVarsSpec | None=None, samples: int | str | _FigureDefaultSentinel | None=None) -> Plot``
        
        Parameters
        ----------
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.parametric_plot(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return create_or_update_parametric_plot(
            self,
            funcs,
            parameter_range,
            parameters=parameters,
            id=id,
            label=label,
            visible=visible,
            sampling_points=sampling_points,
            color=color,
            thickness=thickness,
            width=width,
            dash=dash,
            line=line,
            opacity=opacity,
            alpha=alpha,
            trace=trace,
            autonormalization=autonormalization,
            view=view,
            vars=vars,
            samples=samples,
        )

    def parameter(
        self,
        symbols: ParameterKeyOrKeys,
        *,
        control: Any | None = None,
        **control_kwargs: Any,
    ):
        """Create or ensure parameters and return refs.
        
        Full API
        --------
        ``obj.parameter(symbols: ParameterKeyOrKeys, *, control: Any | None=None, **control_kwargs: Any)``
        
        Parameters
        ----------
        symbols : ParameterKeyOrKeys
            Parameter symbols, names, or other accepted parameter keys. Required.
        
        control : Any | None, optional
            Control/widget style to construct when parameter widgets are created. Defaults to ``None``.
        
        **control_kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``control=None``: Control/widget style to construct when parameter widgets are created.
        - ``**control_kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.parameter(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        result = self._parameter_manager.parameter(
            symbols, control=control, **control_kwargs
        )
        self._emit_layout_event("parameter_controls_updated", source="Figure", phase="completed")
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")
        return result

    def render(
        self,
        reason: str = "manual",
        trigger: Any = None,
        *,
        force: bool = False,
    ) -> None:
        """Queue or synchronously execute a figure render.
        
        Full API
        --------
        ``obj.render(reason: str='manual', trigger: Any=None, *, force: bool=False) -> None``
        
        Parameters
        ----------
        reason : str, optional
            Short machine/human-readable reason recorded for scheduling or rendering. Defaults to ``'manual'``.
        
        trigger : Any, optional
            Event object or trigger payload that caused the current action. Defaults to ``None``.
        
        force : bool, optional
            Flag that requests eager execution or bypasses normal guards/debouncing. Defaults to ``False``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``reason='manual'``: Short machine/human-readable reason recorded for scheduling or rendering.
        - ``trigger=None``: Event object or trigger payload that caused the current action.
        - ``force=False``: Flag that requests eager execution or bypasses normal guards/debouncing.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.render(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self._performance.increment("render_requests")
        if force:
            self._performance.increment("forced_render_requests")
        self._performance.set_state(
            last_requested_reason=str(reason),
            last_requested_trigger_type=(type(trigger).__name__ if trigger is not None else None),
            render_queue_has_pending=self._render_scheduler.has_pending,
        )
        self._render_scheduler.request(reason=reason, trigger=trigger, force=force)

    def flush_render_queue(self) -> None:
        """Synchronously execute the newest pending queued render, if any.
        
        Full API
        --------
        ``obj.flush_render_queue() -> None``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.flush_render_queue(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self._performance.increment("render_queue_flushes")
        self._render_scheduler.flush()

    def _perform_render_request(self, request: RenderRequest) -> None:
        """Execute one coalesced render request immediately."""
        perform_render_request(self, request)

    def snapshot(self) -> FigureSnapshot:
        """Return an immutable snapshot of the entire figure state.
        
        Full API
        --------
        ``obj.snapshot() -> FigureSnapshot``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        FigureSnapshot
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        active_view = self.views.current
        active_view.current_x_range
        active_view.current_y_range
        main_view = self.views[self._view_manager.default_view_id]

        # The top-level x/y fields intentionally mirror main-view defaults so
        # snapshot/code generation is independent of whichever view happens to
        # be active when ``snapshot()`` is called.
        return FigureSnapshot(
            x_range=main_view.x_range,
            y_range=main_view.y_range,
            sampling_points=self.samples or 500,
            title=self.title or "",
            parameters=self._parameter_manager.snapshot(full=True),
            plots={pid: p.snapshot(id=pid) for pid, p in self.plots.items()},
            info_cards=self._info.snapshot(),
            views=tuple(
                ViewSnapshot(
                    id=view.id,
                    title=view.title,
                    x_label=view.x_label,
                    y_label=view.y_label,
                    x_range=view.x_range,
                    y_range=view.y_range,
                    viewport_x_range=view.viewport_x_range,
                    viewport_y_range=view.viewport_y_range,
                )
                for view in self.views.values()
            ),
            active_view_id=self.views.current_id,
            default_x_range=self.default_x_range,
            default_y_range=self.default_y_range,
            default_samples=self.default_samples or self.samples or 500,
        )

    def to_code(self, *, options: CodegenOptions | None = None) -> str:
        """Generate a self-contained Python script that recreates this figure.
        
        Full API
        --------
        ``obj.to_code(*, options: CodegenOptions | None=None) -> str``
        
        Parameters
        ----------
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.to_code(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        from .codegen import figure_to_code

        return figure_to_code(self.snapshot(), options=options)

    @property
    def code(self) -> str:
        """Read-only shorthand for :meth:`to_code`.
        
        Full API
        --------
        ``obj.code -> str``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            current = obj.code
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.to_code()

    def get_code(self, options: CodegenOptions | None = None) -> str:
        """Return generated figure code with optional serialization settings.
        
        Full API
        --------
        ``obj.get_code(options: CodegenOptions | None=None) -> str``
        
        Parameters
        ----------
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.get_code(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self.to_code(options=options)

    def sound_generation_enabled(self, enabled: bool | None = None) -> bool:
        """Query or set the figure-level sound generation toggle.
        
        Full API
        --------
        ``obj.sound_generation_enabled(enabled: bool | None=None) -> bool``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.sound_generation_enabled(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        return self._sound.sound_generation_enabled(enabled)

    def info(
        self,
        spec: str
        | Callable[[Figure, Any], str]
        | Sequence[str | Callable[[Figure, Any], str]],
        id: Hashable | None = None,
        *,
        view: str | None = None,
    ) -> None:
        """Create or replace a simple info card in the Info sidebar.
        
        Full API
        --------
        ``obj.info(spec: str | Callable[[Figure, Any], str] | Sequence[str | Callable[[Figure, Any], str]], id: Hashable | None=None, *, view: str | None=None) -> None``
        
        Parameters
        ----------
        spec : str | Callable[[Figure, Any], str] | Sequence[str | Callable[[Figure, Any], str]]
            Flexible specification object or shorthand accepted by this API. Required.
        
        id : Hashable | None, optional
            Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
        
        view : str | None, optional
            View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``id=None``: Stable identifier used to create, update, or look up the target object.
        - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.info(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self._info.set_simple_card(spec=spec, id=id, view=view)
        if self._sync_sidebar_visibility():
            self._request_active_view_reflow("sidebar_visibility")

    def add_param_change_hook(
        self,
        callback: Callable[[ParamEvent | None], Any],
        hook_id: Hashable | None = None,
        *,
        run_now: bool = True,
    ) -> Hashable:
        """Register a callback to run when *any* parameter value changes.
        
        Full API
        --------
        ``obj.add_param_change_hook(callback: Callable[[ParamEvent | None], Any], hook_id: Hashable | None=None, *, run_now: bool=True) -> Hashable``
        
        Parameters
        ----------
        callback : Callable[[ParamEvent | None], Any]
            Callable that is invoked when the relevant event fires. Required.
        
        hook_id : Hashable | None, optional
            Value for ``hook_id`` in this API. Defaults to ``None``.
        
        run_now : bool, optional
            Value for ``run_now`` in this API. Defaults to ``True``.
        
        Returns
        -------
        Hashable
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``hook_id=None``: Value for ``hook_id`` in this API.
        - ``run_now=True``: Value for ``run_now`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            result = obj.add_param_change_hook(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """

        def _wrapped(event: ParamEvent | None) -> Any:
            with _use_figure(self):
                return callback(event)

        hook_id = self._parameter_manager.add_hook(_wrapped, hook_id)

        if run_now:
            try:
                self.render(reason="manual", trigger=None, force=True)
                _wrapped(None)
            except Exception as e:
                warnings.warn(f"Hook failed on init: {e}", stacklevel=2)

        return hook_id

    # --- Internal / Plumbing ---

    def _throttled_relayout(self) -> None:
        """Compatibility shim for the debounced relayout trigger."""
        target_view_id = self.views.current_id if self._view_manager.views else ""
        self._queue_relayout(target_view_id)

    def _queue_relayout(self, view_id: str, *_: Any) -> None:
        """Queue a relayout event on the figure-level debouncer."""
        self._pending_relayout_view_id = str(view_id)
        self._emit_layout_event("plotly_relayout_queued", source="Figure", phase="queued", view_id=str(view_id))
        self._relayout_debouncer()

    def _dispatch_relayout(self) -> None:
        """Dispatch the most recent queued relayout event."""
        target_view = self._pending_relayout_view_id
        self._pending_relayout_view_id = None
        if target_view is None:
            self._emit_layout_event("plotly_relayout_dispatched", source="Figure", phase="skipped", outcome="no_pending_view")
            return
        if target_view not in self.views:
            self._emit_layout_event("plotly_relayout_dispatched", source="Figure", phase="skipped", outcome="missing_view", view_id=target_view)
            return
        if target_view == self.views.current_id:
            self._emit_layout_event("plotly_relayout_dispatched", source="Figure", phase="completed", view_id=target_view)
            self.render(reason="relayout", force=True)
        else:
            self._view_manager.mark_stale(view_id=target_view)
            self._emit_layout_event("inactive_view_marked_stale", source="Figure", phase="completed", view_id=target_view)

    def _log_render(self, reason: str, trigger: Any) -> None:
        """Log render information with rate-limiting.

        Parameters
        ----------
        reason : str
            Render reason string.
        trigger : Any
            Trigger payload (unused except for context).

        Returns
        -------
        None
        """
        self._emit_layout_event("render_debug", source="Figure", phase="completed", reason=reason, trigger_type=(type(trigger).__name__ if trigger is not None else None))
        # Simple rate-limited logging implementation
        now = time.monotonic()
        if (
            logger.isEnabledFor(logging.INFO)
            and (now - self._render_info_last_log_t) > 1.0
        ):
            self._render_info_last_log_t = now
            logger.info(f"render(reason={reason}) plots={len(self.plots)}")

        if (
            logger.isEnabledFor(logging.DEBUG)
            and (now - self._render_debug_last_log_t) > 0.5
        ):
            self._render_debug_last_log_t = now
            logger.debug(f"ranges x={self.x_range} y={self.y_range}")

    def _ipython_display_(self, **kwargs: Any) -> None:
        """
        Special method called by IPython to display the object.
        Uses IPython.display.display() to render the underlying widget.

        Parameters
        ----------
        **kwargs : Any
            Display keyword arguments forwarded by IPython (unused).

        Returns
        -------
        None

        Notes
        -----
        This method defines the display lifecycle contract used in notebooks:
        explicit display (for example ``display(fig)``) drives first render.
        ``Figure(...)`` construction itself is intentionally side-effect free.
        """
        del kwargs
        self._has_been_displayed = True
        self._emit_layout_event(
            "figure_displayed",
            source="Figure",
            phase="completed",
            level=logging.INFO,
            display_method="_ipython_display_",
        )
        display(self._layout.output_widget)

    def show(self) -> None:
        """Display the figure in IPython/Jupyter.
        
        Full API
        --------
        ``obj.show() -> None``
        
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
        This member belongs to ``Figure``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Figure(...)
            obj.show(...)
        
        Discovery-oriented use::
        
            help(Figure)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(Figure)`` and ``dir(Figure)`` to inspect adjacent members.
        """
        self._has_been_displayed = True
        self._emit_layout_event(
            "figure_displayed",
            source="Figure",
            phase="completed",
            level=logging.INFO,
            display_method="show",
        )
        display(self._layout.output_widget)

    def __enter__(self) -> Figure:
        """Enter a context where this figure becomes the current target.

        Nested ``with fig:`` and ``with fig.views[view_id]:`` blocks are safe:
        the figure keeps one shared output-capture context open until the
        outermost block exits.
        """
        _push_current_figure(self)
        self._context_depth += 1
        if self._context_depth == 1 and self._print_capture is None:
            stack = ExitStack()
            stack.enter_context(self._layout.print_output)
            self._print_capture = stack
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit the current-figure context.

        Parameters
        ----------
        exc_type : Any
            Exception type, if any.
        exc : Any
            Exception instance, if any.
        tb : Any
            Traceback, if any.

        Returns
        -------
        None

        Notes
        -----
        This removes the figure from the module-level stack used by
        :func:`plot` and :func:`parameter`.
        """
        try:
            _pop_current_figure(self)
        finally:
            if self._context_depth > 0:
                self._context_depth -= 1
            if self._context_depth == 0 and self._print_capture is not None:
                self._print_capture.close()
                self._print_capture = None


from . import figure_api as _figure_api
from .figure_field import ScalarFieldPlot, contour_method as _contour_method, density_method as _density_method, field_palette_option_docs as _field_palette_option_docs, field_style_option_docs as _field_style_option_docs, scalar_field_method as _scalar_field_method, temperature_method as _temperature_method

Figure.scalar_field = _scalar_field_method; Figure.contour = _contour_method; Figure.density = _density_method; Figure.temperature = _temperature_method; Figure.field_style_options = staticmethod(_field_style_option_docs); Figure.field_palette_options = staticmethod(_field_palette_option_docs)
(get_default_samples, get_default_x_range, get_default_y_range, get_samples, get_sampling_points, get_title, get_x_range, get_y_range, info, parameter, parameters, parametric_plot, plot, scalar_field, contour, density, temperature, plots, plot_style_options, field_style_options, field_palette_options, render, sound_generation_enabled, set_default_samples, set_default_x_range, set_default_y_range, set_samples, set_sampling_points, set_title, set_x_range, set_y_range) = (_figure_api.get_default_samples, _figure_api.get_default_x_range, _figure_api.get_default_y_range, _figure_api.get_samples, _figure_api.get_sampling_points, _figure_api.get_title, _figure_api.get_x_range, _figure_api.get_y_range, _figure_api.info, _figure_api.parameter, _figure_api.parameters, _figure_api.parametric_plot, _figure_api.plot, _figure_api.scalar_field, _figure_api.contour, _figure_api.density, _figure_api.temperature, _figure_api.plots, _figure_api.plot_style_options, _figure_api.field_style_options, _figure_api.field_palette_options, _figure_api.render, _figure_api.sound_generation_enabled, _figure_api.set_default_samples, _figure_api.set_default_x_range, _figure_api.set_default_y_range, _figure_api.set_samples, _figure_api.set_sampling_points, _figure_api.set_title, _figure_api.set_x_range, _figure_api.set_y_range)

__all__ = ["Figure", "FigureViews", "FigureLayout", "ParametricPlot", "Plot", "ScalarFieldPlot", "View", "FigureSnapshot", "ViewSnapshot", "current_figure", "parametric_plot", "plot", "scalar_field", "contour", "density", "temperature", "plots", "parameter", "parameters", "info", "render", "get_default_samples", "get_default_x_range", "get_default_y_range", "get_samples", "get_sampling_points", "set_default_samples", "set_default_x_range", "set_default_y_range", "set_samples", "set_sampling_points", "get_x_range", "set_x_range", "get_y_range", "set_y_range", "get_title", "set_title", "plot_style_options", "field_style_options", "field_palette_options", "sound_generation_enabled"]
