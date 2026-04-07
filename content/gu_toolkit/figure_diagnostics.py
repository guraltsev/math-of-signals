"""Figure-level runtime diagnostics and render instrumentation helpers."""

from __future__ import annotations

import logging
import time
import warnings
from typing import TYPE_CHECKING, Any

from .animation import get_default_animation_clock
from .figure_render_scheduler import RenderRequest
from .performance_monitor import format_performance_snapshot
from .runtime_support import (
    runtime_diagnostics as runtime_diagnostics_snapshot,
    runtime_support_performance_snapshot,
)

if TYPE_CHECKING:
    from .Figure import Figure


def figure_runtime_diagnostics(
    figure: "Figure",
    *,
    render_target_interval_ms: int,
) -> dict[str, Any]:
    """Work with figure runtime diagnostics.
    
    Full API
    --------
    ``figure_runtime_diagnostics(figure: 'Figure', *, render_target_interval_ms: int) -> dict[str, Any]``
    
    Parameters
    ----------
    figure : 'Figure'
        Figure instance that owns the relevant state. Required.
    
    render_target_interval_ms : int
        Value for ``render_target_interval_ms`` in this API. Required.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_diagnostics``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_diagnostics import figure_runtime_diagnostics
        result = figure_runtime_diagnostics(...)
    
    Discovery-oriented use::
    
        help(figure_runtime_diagnostics)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(figure_runtime_diagnostics)`` and inspect sibling APIs in the same module.
    """

    diagnostics = runtime_diagnostics_snapshot()
    figure_state = figure._performance.snapshot(recent_limit=1).get("state", {})
    figure_widget_support = figure_state.get("widget_support")
    if isinstance(figure_widget_support, dict):
        diagnostics["plotly_widget_support"] = figure_widget_support
    diagnostics["figure"] = {
        "figure_id": figure._layout_debug_figure_id,
        "active_view_id": figure.views.current_id if figure._view_manager.views else None,
        "view_count": len(figure.views),
        "plot_count": len(figure.plots),
        "displayed": figure._has_been_displayed,
        "render_target_interval_ms": render_target_interval_ms,
        "current_widget_type": type(figure.figure_widget).__name__ if figure._view_manager.views else None,
    }
    return diagnostics


def figure_performance_snapshot(
    figure: "Figure",
    *,
    render_target_interval_ms: int,
    recent_event_limit: int = 25,
    include_layout_events: bool = False,
) -> dict[str, Any]:
    """Work with figure performance snapshot.
    
    Full API
    --------
    ``figure_performance_snapshot(figure: 'Figure', *, render_target_interval_ms: int, recent_event_limit: int=25, include_layout_events: bool=False) -> dict[str, Any]``
    
    Parameters
    ----------
    figure : 'Figure'
        Figure instance that owns the relevant state. Required.
    
    render_target_interval_ms : int
        Value for ``render_target_interval_ms`` in this API. Required.
    
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
    This callable lives in ``gu_toolkit.figure_diagnostics``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_diagnostics import figure_performance_snapshot
        result = figure_performance_snapshot(...)
    
    Discovery-oriented use::
    
        help(figure_performance_snapshot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(figure_performance_snapshot)`` and inspect sibling APIs in the same module.
    """

    animation_clock = get_default_animation_clock()
    snapshot = {
        "runtime": figure_runtime_diagnostics(
            figure,
            render_target_interval_ms=render_target_interval_ms,
        ),
        "runtime_support": runtime_support_performance_snapshot(
            recent_event_limit=recent_event_limit
        ),
        "figure": figure._performance.snapshot(recent_limit=recent_event_limit),
        "parameters": figure._parameter_manager.performance_snapshot(
            recent_event_limit=recent_event_limit
        ),
        "animation_clock": animation_clock.performance_snapshot(
            recent_event_limit=recent_event_limit
        ),
        "render_scheduler": figure._render_scheduler.performance_snapshot(
            recent_event_limit=recent_event_limit
        ),
        "relayout_debouncer": figure._relayout_debouncer.performance_snapshot(
            recent_event_limit=recent_event_limit
        ),
        "plots": {
            plot_id: plot.performance_snapshot(recent_event_limit=recent_event_limit)
            for plot_id, plot in figure.plots.items()
        },
    }
    if include_layout_events:
        snapshot["layout_events"] = figure._layout_event_buffer.snapshot()[-recent_event_limit:]
    return snapshot


def figure_performance_report(
    figure: "Figure",
    *,
    render_target_interval_ms: int,
    recent_event_limit: int = 10,
    include_layout_events: bool = False,
) -> str:
    """Work with figure performance report.
    
    Full API
    --------
    ``figure_performance_report(figure: 'Figure', *, render_target_interval_ms: int, recent_event_limit: int=10, include_layout_events: bool=False) -> str``
    
    Parameters
    ----------
    figure : 'Figure'
        Figure instance that owns the relevant state. Required.
    
    render_target_interval_ms : int
        Value for ``render_target_interval_ms`` in this API. Required.
    
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
    This callable lives in ``gu_toolkit.figure_diagnostics``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_diagnostics import figure_performance_report
        result = figure_performance_report(...)
    
    Discovery-oriented use::
    
        help(figure_performance_report)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(figure_performance_report)`` and inspect sibling APIs in the same module.
    """

    runtime = figure_runtime_diagnostics(
        figure,
        render_target_interval_ms=render_target_interval_ms,
    )
    runtime_lines = [
        "Runtime diagnostics",
        f"  platform: {runtime.get('platform')}",
        f"  is_pyodide: {runtime.get('is_pyodide')}",
        f"  timer_backend: {runtime.get('timer_backend')}",
        f"  widget_support: {runtime.get('plotly_widget_support')}",
        f"  schedule_later: {runtime.get('schedule_later')}",
        f"  current_widget_type: {runtime.get('figure', {}).get('current_widget_type')}",
    ]
    runtime_support = runtime_support_performance_snapshot(
        recent_event_limit=recent_event_limit
    )
    sections = ["\n".join(runtime_lines)]
    sections.append(
        format_performance_snapshot(
            runtime_support["schedule_later"],
            title="Runtime support scheduler",
        )
    )
    sections.append(
        format_performance_snapshot(
            runtime_support["plotly_widget_support"],
            title="Runtime support widget checks",
        )
    )
    sections.append(
        format_performance_snapshot(
            figure._performance.snapshot(recent_limit=recent_event_limit),
            title=f"Figure {figure._layout_debug_figure_id}",
        )
    )
    sections.append(
        figure._parameter_manager.performance_report(
            recent_event_limit=recent_event_limit,
        )
    )
    sections.append(
        format_performance_snapshot(
            get_default_animation_clock().performance_snapshot(
                recent_event_limit=recent_event_limit
            ),
            title="Animation clock",
        )
    )
    sections.append(
        format_performance_snapshot(
            figure._render_scheduler.performance_snapshot(
                recent_event_limit=recent_event_limit
            ),
            title="Render scheduler",
        )
    )
    sections.append(
        format_performance_snapshot(
            figure._relayout_debouncer.performance_snapshot(
                recent_event_limit=recent_event_limit
            ),
            title="Relayout debouncer",
        )
    )
    for plot_id, plot in figure.plots.items():
        sections.append(
            format_performance_snapshot(
                plot.performance_snapshot(recent_event_limit=recent_event_limit),
                title=f"Plot {plot_id}",
            )
        )
    if include_layout_events:
        sections.append(
            f"Recent layout events: {figure._layout_event_buffer.snapshot()[-recent_event_limit:]}"
        )
    return "\n\n".join(section for section in sections if section)


def perform_render_request(figure: "Figure", request: RenderRequest) -> None:
    """Execute one coalesced render request immediately with instrumentation.
    
    Full API
    --------
    ``perform_render_request(figure: 'Figure', request: RenderRequest) -> None``
    
    Parameters
    ----------
    figure : 'Figure'
        Figure instance that owns the relevant state. Required.
    
    request : RenderRequest
        Structured request object consumed by this API. Required.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_diagnostics``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_diagnostics import perform_render_request
        perform_render_request(...)
    
    Discovery-oriented use::
    
        help(perform_render_request)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(perform_render_request)`` and inspect sibling APIs in the same module.
    """
    reason = request.reason
    trigger = request.trigger
    param_trigger = (
        request.latest_param_change_trigger
        if request.includes_param_change
        else None
    )
    figure._performance.increment("renders")
    if request.queued_count > 1:
        figure._performance.increment(
            "coalesced_render_requests",
            delta=request.queued_count - 1,
            reason=reason,
        )
    if request.includes_param_change:
        figure._performance.increment("parameter_change_renders")
    figure._performance.set_state(
        last_render_reason=reason,
        last_render_queued_count=request.queued_count,
        last_render_includes_param_change=request.includes_param_change,
        last_render_view_id=figure.views.current_id,
        last_render_trigger_type=(type(trigger).__name__ if trigger is not None else None),
    )
    render_started = time.perf_counter()

    figure._emit_layout_event(
        "render_started",
        source="Figure",
        phase="started",
        level=logging.INFO,
        reason=reason,
        queued_count=request.queued_count,
        includes_param_change=request.includes_param_change,
        trigger_type=(type(trigger).__name__ if trigger is not None else None),
    )
    figure._log_render(reason, trigger)

    current_view_id = figure.views.current_id
    refresh_started = time.perf_counter()
    figure._parameter_manager.refresh_render_parameter_context()
    figure._performance.record_duration(
        "render_parameter_refresh_ms",
        (time.perf_counter() - refresh_started) * 1000.0,
        reason=reason,
    )

    current_widget = figure.views[current_view_id].figure_widget
    plot_loop_started = time.perf_counter()
    with current_widget.batch_update():
        for plot in figure.plots.values():
            plot.render(
                view_id=current_view_id,
                use_batch_update=False,
                refresh_parameter_snapshot=False,
            )
    figure._performance.record_duration(
        "render_plot_loop_ms",
        (time.perf_counter() - plot_loop_started) * 1000.0,
        reason=reason,
        plot_count=len(figure.plots),
    )

    pane = figure.views[current_view_id].pane
    fallback_refresh_started = time.perf_counter()
    refreshed_fallback_display = bool(
        getattr(pane, "refresh_plot_display", lambda **_kwargs: False)(
            reason=f"figure_render:{reason}"
        )
    )
    if refreshed_fallback_display:
        figure._performance.increment("fallback_plot_refreshes", reason=reason)
        figure._performance.record_duration(
            "fallback_plot_refresh_ms",
            (time.perf_counter() - fallback_refresh_started) * 1000.0,
            reason=reason,
        )

    if request.includes_param_change:
        stale_started = time.perf_counter()
        for plot in figure.plots.values():
            for view_id in plot.views:
                if view_id != current_view_id:
                    figure._view_manager.mark_stale(view_id=view_id)
        figure._performance.record_duration(
            "render_stale_mark_ms",
            (time.perf_counter() - stale_started) * 1000.0,
            reason=reason,
        )

    if request.includes_param_change and param_trigger is not None:
        hooks_started = time.perf_counter()
        sound_change_handler = getattr(figure, "_sound", None)
        if sound_change_handler is not None:
            try:
                sound_change_handler.on_parameter_change(param_trigger)
            except Exception as e:
                figure._performance.increment("render_hook_failures", source="sound")
                warnings.warn(f"Sound refresh failed: {e}", stacklevel=2)
        hooks = figure._parameter_manager.get_hooks()
        for h_id, callback in list(hooks.items()):
            try:
                callback(param_trigger)
            except Exception as e:
                figure._performance.increment("render_hook_failures", source="parameter_hook", hook_id=h_id)
                warnings.warn(f"Hook {h_id} failed: {e}", stacklevel=2)
        figure._performance.record_duration(
            "render_hooks_ms",
            (time.perf_counter() - hooks_started) * 1000.0,
            reason=reason,
            hook_count=len(hooks),
        )

    info_started = time.perf_counter()
    figure._info.schedule_info_update(reason=reason, trigger=trigger)
    figure._performance.record_duration(
        "render_info_schedule_ms",
        (time.perf_counter() - info_started) * 1000.0,
        reason=reason,
    )
    figure._performance.record_duration(
        "render_total_ms",
        (time.perf_counter() - render_started) * 1000.0,
        reason=reason,
        queued_count=request.queued_count,
        plot_count=len(figure.plots),
    )
    figure._emit_layout_event(
        "render_completed",
        source="Figure",
        phase="completed",
        level=logging.INFO,
        reason=reason,
        queued_count=request.queued_count,
        includes_param_change=request.includes_param_change,
        view_id=current_view_id,
    )


__all__ = [
    "figure_runtime_diagnostics",
    "figure_performance_snapshot",
    "figure_performance_report",
    "perform_render_request",
]
