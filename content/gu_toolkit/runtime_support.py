"""Runtime-adaptation helpers for timers, Plotly widget support, and environment diagnostics.

Public entry points
-------------------
``ScheduledCallback``, ``PlotlyWidgetSupportStatus``, ``warn_once``,
    ``is_pyodide_runtime``, ``describe_timer_backend``, ``schedule_later``,
    ``inspect_plotly_widget_support``, ``create_plotly_figure_widget``,
    ``runtime_support_performance_snapshot``, ``runtime_diagnostics``

Architecture note
-----------------
Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for the package-level task map.
- Guide: ``docs/guides/ui-layout-system.md``.
- Example notebook: ``examples/layout_debug.ipynb``.
- Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import warnings
from dataclasses import dataclass
from typing import Any, Callable

import plotly.graph_objects as go

from ._widget_stubs import ANYWIDGET_IMPORT_ERROR, ANYWIDGET_IS_FALLBACK
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_WARNED_KEYS: set[str] = set()
_SCHEDULE_MONITOR = PerformanceMonitor("runtime_support.schedule_later")
_WIDGET_MONITOR = PerformanceMonitor("runtime_support.plotly_widget_support")


@dataclass(frozen=True)
class ScheduledCallback:
    """Handle object returned when work is scheduled for later execution.
    
    Full API
    --------
    ``ScheduledCallback(handle: Any, backend: str)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    handle : Any
        Value for ``handle`` in this API. Required.
    
    backend : str
        Value for ``backend`` in this API. Required.
    
    Returns
    -------
    ScheduledCallback
        New ``ScheduledCallback`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``ScheduledCallback`` lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.runtime_support import ScheduledCallback
        obj = ScheduledCallback(...)
    
    Discovery-oriented use::
    
        help(ScheduledCallback)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(ScheduledCallback)`` and ``dir(ScheduledCallback)`` to inspect adjacent members.
    """

    handle: Any
    backend: str


@dataclass(frozen=True)
class PlotlyWidgetSupportStatus:
    """Structured status record describing Plotly widget support in the current runtime.
    
    Full API
    --------
    ``PlotlyWidgetSupportStatus(anywidget_available: bool, anywidget_is_fallback: bool, figurewidget_supported: bool, anywidget_mode: str, figurewidget_mode: str, reason: str | None=None)``
    
    Public members exposed from this class: ``to_dict``
    
    Parameters
    ----------
    anywidget_available : bool
        Value for ``anywidget_available`` in this API. Required.
    
    anywidget_is_fallback : bool
        Value for ``anywidget_is_fallback`` in this API. Required.
    
    figurewidget_supported : bool
        Value for ``figurewidget_supported`` in this API. Required.
    
    anywidget_mode : str
        Value for ``anywidget_mode`` in this API. Required.
    
    figurewidget_mode : str
        Value for ``figurewidget_mode`` in this API. Required.
    
    reason : str | None, optional
        Short machine/human-readable reason recorded for scheduling or rendering. Defaults to ``None``.
    
    Returns
    -------
    PlotlyWidgetSupportStatus
        New ``PlotlyWidgetSupportStatus`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``reason=None``: Short machine/human-readable reason recorded for scheduling or rendering.
    
    Architecture note
    -----------------
    ``PlotlyWidgetSupportStatus`` lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.runtime_support import PlotlyWidgetSupportStatus
        obj = PlotlyWidgetSupportStatus(...)
    
    Discovery-oriented use::
    
        help(PlotlyWidgetSupportStatus)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(PlotlyWidgetSupportStatus)`` and ``dir(PlotlyWidgetSupportStatus)`` to inspect adjacent members.
    """

    anywidget_available: bool
    anywidget_is_fallback: bool
    figurewidget_supported: bool
    anywidget_mode: str
    figurewidget_mode: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Work with to dict on ``PlotlyWidgetSupportStatus``.
        
        Full API
        --------
        ``obj.to_dict() -> dict[str, Any]``
        
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
        This member belongs to ``PlotlyWidgetSupportStatus``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotlyWidgetSupportStatus(...)
            result = obj.to_dict(...)
        
        Discovery-oriented use::
        
            help(PlotlyWidgetSupportStatus)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PlotlyWidgetSupportStatus)`` and ``dir(PlotlyWidgetSupportStatus)`` to inspect adjacent members.
        """

        return {
            "anywidget_available": self.anywidget_available,
            "anywidget_is_fallback": self.anywidget_is_fallback,
            "figurewidget_supported": self.figurewidget_supported,
            "anywidget_mode": self.anywidget_mode,
            "figurewidget_mode": self.figurewidget_mode,
            "reason": self.reason,
        }


class _BrowserTimeoutHandle:
    def __init__(self, js_module: Any, timer_id: Any, proxy: Any) -> None:
        self._js = js_module
        self._timer_id = timer_id
        self._proxy = proxy
        self._cancelled = False

    def cancel(self) -> None:
        """Work with cancel on ``_BrowserTimeoutHandle``.
        
        Full API
        --------
        ``obj.cancel() -> None``
        
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
        This member belongs to ``_BrowserTimeoutHandle``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _BrowserTimeoutHandle(...)
            obj.cancel(...)
        
        Discovery-oriented use::
        
            help(_BrowserTimeoutHandle)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(_BrowserTimeoutHandle)`` and ``dir(_BrowserTimeoutHandle)`` to inspect adjacent members.
        """

        if self._cancelled:
            return
        self._cancelled = True
        try:
            self._js.clearTimeout(self._timer_id)
        except Exception:
            logger.debug("clearTimeout failed", exc_info=True)
        destroy = getattr(self._proxy, "destroy", None)
        if callable(destroy):
            try:
                destroy()
            except Exception:
                logger.debug("destroy proxy failed", exc_info=True)


class _TornadoTimeoutHandle:
    def __init__(self, loop: Any, handle: Any) -> None:
        self._loop = loop
        self._handle = handle
        self._cancelled = False

    def cancel(self) -> None:
        """Work with cancel on ``_TornadoTimeoutHandle``.
        
        Full API
        --------
        ``obj.cancel() -> None``
        
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
        This member belongs to ``_TornadoTimeoutHandle``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _TornadoTimeoutHandle(...)
            obj.cancel(...)
        
        Discovery-oriented use::
        
            help(_TornadoTimeoutHandle)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(_TornadoTimeoutHandle)`` and ``dir(_TornadoTimeoutHandle)`` to inspect adjacent members.
        """

        if self._cancelled:
            return
        self._cancelled = True
        try:
            self._loop.remove_timeout(self._handle)
        except Exception:
            logger.debug("remove_timeout failed", exc_info=True)


def warn_once(
    key: str,
    message: str,
    *,
    category: type[Warning] = RuntimeWarning,
    stacklevel: int = 2,
) -> None:
    """Warn once about once.
    
    Full API
    --------
    ``warn_once(key: str, message: str, *, category: type[Warning]=RuntimeWarning, stacklevel: int=2) -> None``
    
    Parameters
    ----------
    key : str
        Value for ``key`` in this API. Required.
    
    message : str
        Value for ``message`` in this API. Required.
    
    category : type[Warning], optional
        Value for ``category`` in this API. Defaults to ``RuntimeWarning``.
    
    stacklevel : int, optional
        Value for ``stacklevel`` in this API. Defaults to ``2``.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    - ``category=RuntimeWarning``: Value for ``category`` in this API.
    - ``stacklevel=2``: Value for ``stacklevel`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import warn_once
        warn_once(...)
    
    Discovery-oriented use::
    
        help(warn_once)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(warn_once)`` and inspect sibling APIs in the same module.
    """

    marker = str(key)
    if marker in _WARNED_KEYS:
        return
    _WARNED_KEYS.add(marker)
    warnings.warn(message, category=category, stacklevel=stacklevel)


def is_pyodide_runtime() -> bool:
    """Return whether pyodide runtime.
    
    Full API
    --------
    ``is_pyodide_runtime() -> bool``
    
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
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import is_pyodide_runtime
        result = is_pyodide_runtime(...)
    
    Discovery-oriented use::
    
        help(is_pyodide_runtime)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(is_pyodide_runtime)`` and inspect sibling APIs in the same module.
    """

    return sys.platform == "emscripten" or bool(os.environ.get("PYODIDE"))


def _resolve_running_loop() -> tuple[Any | None, str | None]:
    try:
        return asyncio.get_running_loop(), "asyncio_running_loop"
    except RuntimeError:
        pass
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            loop = asyncio.get_event_loop_policy().get_event_loop()
    except Exception:
        return None, None
    is_running = getattr(loop, "is_running", None)
    if callable(is_running) and bool(is_running()):
        return loop, "asyncio_event_loop"
    return None, None


def _resolve_browser_timeout_primitives() -> tuple[Any | None, Any | None]:
    try:
        import js  # type: ignore[import-not-found]
        from pyodide.ffi import create_once_callable  # type: ignore[import-not-found]
    except Exception:
        return None, None
    return js, create_once_callable


def _resolve_tornado_ioloop() -> tuple[Any | None, str | None]:
    try:
        from tornado.ioloop import IOLoop
    except Exception:
        return None, None
    try:
        loop = IOLoop.current(instance=False)
    except Exception:
        return None, None
    if loop is None:
        return None, None
    asyncio_loop = getattr(loop, "asyncio_loop", None)
    if asyncio_loop is not None:
        is_running = getattr(asyncio_loop, "is_running", None)
        if callable(is_running) and not bool(is_running()):
            return None, None
    return loop, "tornado_ioloop"


def describe_timer_backend() -> str:
    """Describe timer backend.
    
    Full API
    --------
    ``describe_timer_backend() -> str``
    
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
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import describe_timer_backend
        result = describe_timer_backend(...)
    
    Discovery-oriented use::
    
        help(describe_timer_backend)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(describe_timer_backend)`` and inspect sibling APIs in the same module.
    """

    _loop, backend = _resolve_running_loop()
    if backend is not None:
        return backend
    js_module, create_once_callable = _resolve_browser_timeout_primitives()
    if js_module is not None and create_once_callable is not None:
        return "browser_set_timeout"
    _tornado_loop, tornado_backend = _resolve_tornado_ioloop()
    if tornado_backend is not None:
        return tornado_backend
    return "threading_timer"


def _record_schedule_backend(*, backend: str, owner: str, delay_s: float) -> None:
    delay_ms = float(delay_s) * 1000.0
    _SCHEDULE_MONITOR.increment("schedule_calls")
    _SCHEDULE_MONITOR.increment(f"backend_{backend}")
    _SCHEDULE_MONITOR.set_state(
        last_backend=str(backend),
        last_owner=str(owner),
        last_delay_ms=delay_ms,
    )
    _SCHEDULE_MONITOR.record_duration(
        "requested_delay_ms",
        delay_ms,
        backend=backend,
        owner=owner,
    )


def schedule_later(
    delay_s: float,
    callback: Callable[[], Any],
    *,
    owner: str = "timer",
    thread_timer_factory: Callable[[float, Callable[[], Any]], Any] | None = None,
) -> ScheduledCallback:
    """Schedule later.
    
    Full API
    --------
    ``schedule_later(delay_s: float, callback: Callable[[], Any], *, owner: str='timer', thread_timer_factory: Callable[[float, Callable[[], Any]], Any] | None=None) -> ScheduledCallback``
    
    Parameters
    ----------
    delay_s : float
        Value for ``delay_s`` in this API. Required.
    
    callback : Callable[[], Any]
        Callable that is invoked when the relevant event fires. Required.
    
    owner : str, optional
        Value for ``owner`` in this API. Defaults to ``'timer'``.
    
    thread_timer_factory : Callable[[float, Callable[[], Any]], Any] | None, optional
        Value for ``thread_timer_factory`` in this API. Defaults to ``None``.
    
    Returns
    -------
    ScheduledCallback
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``owner='timer'``: Value for ``owner`` in this API.
    - ``thread_timer_factory=None``: Value for ``thread_timer_factory`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import schedule_later
        result = schedule_later(...)
    
    Discovery-oriented use::
    
        help(schedule_later)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(schedule_later)`` and inspect sibling APIs in the same module.
    """

    delay_value = max(0.0, float(delay_s))
    loop, backend = _resolve_running_loop()
    if loop is not None:
        _record_schedule_backend(backend=str(backend), owner=owner, delay_s=delay_value)
        return ScheduledCallback(loop.call_later(delay_value, callback), str(backend))
    js_module, create_once_callable = _resolve_browser_timeout_primitives()
    if js_module is not None and create_once_callable is not None:
        _record_schedule_backend(
            backend="browser_set_timeout",
            owner=owner,
            delay_s=delay_value,
        )
        proxy = create_once_callable(callback)
        timer_id = js_module.setTimeout(proxy, int(round(delay_value * 1000.0)))
        return ScheduledCallback(
            _BrowserTimeoutHandle(js_module, timer_id, proxy),
            "browser_set_timeout",
        )
    tornado_loop, tornado_backend = _resolve_tornado_ioloop()
    if tornado_loop is not None and tornado_backend is not None:
        _record_schedule_backend(
            backend=str(tornado_backend),
            owner=owner,
            delay_s=delay_value,
        )
        handle = tornado_loop.call_later(delay_value, callback)
        return ScheduledCallback(
            _TornadoTimeoutHandle(tornado_loop, handle),
            str(tornado_backend),
        )
    if thread_timer_factory is None:
        raise RuntimeError(
            f"No runnable timer backend available for {owner!r}; a running event loop, browser timer, Tornado IOLoop, or thread timer factory is required."
        )
    if is_pyodide_runtime():
        _SCHEDULE_MONITOR.increment("pyodide_thread_timer_fallback")
        warn_once(
            "pyodide-threading-timer-fallback",
            "gu_toolkit fell back to threading.Timer while running in a Pyodide-like runtime. Interactive timing may be degraded; browser setTimeout support should normally be available in JupyterLite/Pyodide.",
            category=RuntimeWarning,
            stacklevel=3,
        )
    _record_schedule_backend(backend="threading_timer", owner=owner, delay_s=delay_value)
    timer = thread_timer_factory(delay_value, callback)
    if hasattr(timer, "daemon"):
        try:
            timer.daemon = True
        except Exception:
            logger.debug("Unable to mark timer daemon", exc_info=True)
    start = getattr(timer, "start", None)
    if callable(start):
        start()
    return ScheduledCallback(timer, "threading_timer")


def inspect_plotly_widget_support() -> PlotlyWidgetSupportStatus:
    """Inspect plotly widget support.
    
    Full API
    --------
    ``inspect_plotly_widget_support() -> PlotlyWidgetSupportStatus``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    PlotlyWidgetSupportStatus
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import inspect_plotly_widget_support
        result = inspect_plotly_widget_support(...)
    
    Discovery-oriented use::
    
        help(inspect_plotly_widget_support)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(inspect_plotly_widget_support)`` and inspect sibling APIs in the same module.
    """

    _WIDGET_MONITOR.increment("inspections")
    fallback_reason = None
    if ANYWIDGET_IS_FALLBACK:
        fallback_reason = (
            "anywidget is missing; gu_toolkit is using a local fallback stub. "
            "Plotly FigureWidget may still construct on the Python side, but frontend transport can be degraded until real anywidget is installed."
        )
        if ANYWIDGET_IMPORT_ERROR:
            fallback_reason = f"{fallback_reason} Import error: {ANYWIDGET_IMPORT_ERROR}"
    try:
        figure_widget = go.FigureWidget()
    except Exception as exc:
        status = PlotlyWidgetSupportStatus(
            anywidget_available=(not ANYWIDGET_IS_FALLBACK),
            anywidget_is_fallback=ANYWIDGET_IS_FALLBACK,
            figurewidget_supported=False,
            anywidget_mode=("fallback_stub" if ANYWIDGET_IS_FALLBACK else "real_package"),
            figurewidget_mode="plotly_figure_fallback",
            reason=(fallback_reason or f"FigureWidget creation failed: {exc}"),
        )
        _WIDGET_MONITOR.increment("figurewidget_unsupported")
        _WIDGET_MONITOR.set_state(**status.to_dict())
        return status
    status = PlotlyWidgetSupportStatus(
        anywidget_available=(not ANYWIDGET_IS_FALLBACK),
        anywidget_is_fallback=ANYWIDGET_IS_FALLBACK,
        figurewidget_supported=True,
        anywidget_mode=("fallback_stub" if ANYWIDGET_IS_FALLBACK else "real_package"),
        figurewidget_mode=type(figure_widget).__name__,
        reason=fallback_reason,
    )
    _WIDGET_MONITOR.increment("figurewidget_supported")
    if ANYWIDGET_IS_FALLBACK:
        _WIDGET_MONITOR.increment("figurewidget_supported_with_anywidget_fallback")
    _WIDGET_MONITOR.set_state(**status.to_dict())
    return status


def create_plotly_figure_widget() -> tuple[Any, PlotlyWidgetSupportStatus]:
    """Work with create plotly figure widget.
    
    Full API
    --------
    ``create_plotly_figure_widget() -> tuple[Any, PlotlyWidgetSupportStatus]``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    tuple[Any, PlotlyWidgetSupportStatus]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import create_plotly_figure_widget
        result = create_plotly_figure_widget(...)
    
    Discovery-oriented use::
    
        help(create_plotly_figure_widget)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(create_plotly_figure_widget)`` and inspect sibling APIs in the same module.
    """

    status = inspect_plotly_widget_support()
    if not status.figurewidget_supported:
        _WIDGET_MONITOR.increment("created_plotly_figure_fallback")
        return go.Figure(), status
    _WIDGET_MONITOR.increment("created_plotly_figurewidget")
    try:
        return go.FigureWidget(), status
    except Exception as exc:
        degraded_status = PlotlyWidgetSupportStatus(
            anywidget_available=status.anywidget_available,
            anywidget_is_fallback=status.anywidget_is_fallback,
            figurewidget_supported=False,
            anywidget_mode=status.anywidget_mode,
            figurewidget_mode="plotly_figure_fallback",
            reason=f"FigureWidget creation failed after support probe: {exc}",
        )
        _WIDGET_MONITOR.increment("created_plotly_figure_fallback_after_probe")
        _WIDGET_MONITOR.set_state(**degraded_status.to_dict())
        return go.Figure(), degraded_status


def runtime_support_performance_snapshot(*, recent_event_limit: int = 25) -> dict[str, Any]:
    """Work with runtime support performance snapshot.
    
    Full API
    --------
    ``runtime_support_performance_snapshot(*, recent_event_limit: int=25) -> dict[str, Any]``
    
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
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import runtime_support_performance_snapshot
        result = runtime_support_performance_snapshot(...)
    
    Discovery-oriented use::
    
        help(runtime_support_performance_snapshot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(runtime_support_performance_snapshot)`` and inspect sibling APIs in the same module.
    """

    return {
        "schedule_later": _SCHEDULE_MONITOR.snapshot(recent_limit=recent_event_limit),
        "plotly_widget_support": _WIDGET_MONITOR.snapshot(recent_limit=recent_event_limit),
    }


def runtime_diagnostics() -> dict[str, Any]:
    """Work with runtime diagnostics.
    
    Full API
    --------
    ``runtime_diagnostics() -> dict[str, Any]``
    
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
    This callable lives in ``gu_toolkit.runtime_support``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.runtime_support import runtime_diagnostics
        result = runtime_diagnostics(...)
    
    Discovery-oriented use::
    
        help(runtime_diagnostics)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(runtime_diagnostics)`` and inspect sibling APIs in the same module.
    """

    status = inspect_plotly_widget_support()
    support_perf = runtime_support_performance_snapshot(recent_event_limit=5)
    return {
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "is_pyodide": is_pyodide_runtime(),
        "timer_backend": describe_timer_backend(),
        "plotly_widget_support": status.to_dict(),
        "schedule_later": {
            "state": support_perf["schedule_later"].get("state", {}),
            "counters": support_perf["schedule_later"].get("counters", {}),
        },
    }


__all__ = [
    "PlotlyWidgetSupportStatus",
    "ScheduledCallback",
    "create_plotly_figure_widget",
    "describe_timer_backend",
    "inspect_plotly_widget_support",
    "is_pyodide_runtime",
    "runtime_diagnostics",
    "runtime_support_performance_snapshot",
    "schedule_later",
    "warn_once",
]
