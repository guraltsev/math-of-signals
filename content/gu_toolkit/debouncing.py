"""Queued debouncing utilities for callback-driven UI updates.

Purpose
-------
Provides ``QueuedDebouncer``, a small utility that buffers callback invocations
and executes them on a fixed cadence.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .layout_logging import LOGGER_NAME, emit_layout_event, is_layout_logger_explicitly_enabled
from .performance_monitor import PerformanceMonitor
from .runtime_support import schedule_later


@dataclass
class _QueuedCall:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class QueuedDebouncer:
    """Queue callback invocations and execute at a fixed cadence.
    
    Full API
    --------
    ``QueuedDebouncer(callback: Callable[Ellipsis, Any], execute_every_ms: int, drop_overflow: bool=True, name: str='QueuedDebouncer', event_sink: Callable[Ellipsis, Any] | None=None, time_source: Callable[[], float]=time.monotonic)``
    
    Public members exposed from this class: ``timer_backend``, ``performance_snapshot``
    
    Parameters
    ----------
    callback : Callable[Ellipsis, Any]
        Callable that is invoked when the relevant event fires. Required.
    
    execute_every_ms : int
        Value for ``execute_every_ms`` in this API. Required.
    
    drop_overflow : bool, optional
        Value for ``drop_overflow`` in this API. Defaults to ``True``.
    
    name : str, optional
        Human-readable or canonical name for the target object. Defaults to ``'QueuedDebouncer'``.
    
    event_sink : Callable[Ellipsis, Any] | None, optional
        Value for ``event_sink`` in this API. Defaults to ``None``.
    
    time_source : Callable[[], float], optional
        Value for ``time_source`` in this API. Defaults to ``time.monotonic``.
    
    Returns
    -------
    QueuedDebouncer
        New ``QueuedDebouncer`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``drop_overflow=True``: Value for ``drop_overflow`` in this API.
    - ``name='QueuedDebouncer'``: Human-readable or canonical name for the target object.
    - ``event_sink=None``: Value for ``event_sink`` in this API.
    - ``time_source=time.monotonic``: Value for ``time_source`` in this API.
    
    Architecture note
    -----------------
    ``QueuedDebouncer`` lives in ``gu_toolkit.debouncing``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.debouncing import QueuedDebouncer
        obj = QueuedDebouncer(...)
    
    Discovery-oriented use::
    
        help(QueuedDebouncer)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(QueuedDebouncer)`` and ``dir(QueuedDebouncer)`` to inspect adjacent members.
    """

    def __init__(
        self,
        callback: Callable[..., Any],
        *,
        execute_every_ms: int,
        drop_overflow: bool = True,
        name: str = "QueuedDebouncer",
        event_sink: Callable[..., Any] | None = None,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        if execute_every_ms <= 0:
            raise ValueError("execute_every_ms must be > 0")
        self._callback = callback
        self._execute_every_s = execute_every_ms / 1000.0
        self._drop_overflow = bool(drop_overflow)
        self._name = str(name)
        self._event_sink = event_sink
        self._time_source = time_source

        self._queue: deque[_QueuedCall] = deque()
        self._lock = threading.Lock()
        self._timer: Any | None = None
        self._executing = False
        self._next_tick_deadline: float | None = None
        self._last_timer_backend = "uninitialized"
        self._performance = PerformanceMonitor(f"QueuedDebouncer[{self._name}]")
        self._performance.set_state(
            execute_every_ms=int(execute_every_ms),
            drop_overflow=self._drop_overflow,
            timer_backend=self._last_timer_backend,
            executing=False,
        )

    def _emit(self, event: str, *, phase: str, level: int = logging.DEBUG, **fields: Any) -> None:
        if self._event_sink is not None:
            self._event_sink(event=event, source="QueuedDebouncer", phase=phase, level=level, owner=self._name, **fields)
            return
        debounce_logger = logging.getLogger(f"{LOGGER_NAME}.debounce")
        if not is_layout_logger_explicitly_enabled(debounce_logger):
            return
        emit_layout_event(
            debounce_logger,
            event=event,
            source="QueuedDebouncer",
            phase=phase,
            level=level,
            owner=self._name,
            **fields,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._queue.append(_QueuedCall(args=args, kwargs=dict(kwargs)))
            queue_depth = len(self._queue)
            self._performance.increment("enqueued_calls")
            if self._executing:
                self._performance.increment("enqueued_while_executing")
            self._performance.set_state(queue_depth=queue_depth, executing=self._executing)
            self._emit("debounce_enqueued", phase="queued", queue_depth=queue_depth)
            if self._timer is None and not self._executing:
                now = float(self._time_source())
                if self._next_tick_deadline is None:
                    self._next_tick_deadline = now + self._execute_every_s
                self._schedule_next_locked(now=now)

    @property
    def timer_backend(self) -> str:
        """Work with timer backend on ``QueuedDebouncer``.
        
        Full API
        --------
        ``obj.timer_backend -> str``
        
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
        This member belongs to ``QueuedDebouncer``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = QueuedDebouncer(...)
            current = obj.timer_backend
        
        Discovery-oriented use::
        
            help(QueuedDebouncer)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(QueuedDebouncer)`` and ``dir(QueuedDebouncer)`` to inspect adjacent members.
        """

        return self._last_timer_backend

    def performance_snapshot(self, *, recent_event_limit: int = 25) -> dict[str, Any]:
        """Work with performance snapshot on ``QueuedDebouncer``.
        
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
        This member belongs to ``QueuedDebouncer``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = QueuedDebouncer(...)
            result = obj.performance_snapshot(...)
        
        Discovery-oriented use::
        
            help(QueuedDebouncer)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(QueuedDebouncer)`` and ``dir(QueuedDebouncer)`` to inspect adjacent members.
        """

        return self._performance.snapshot(recent_limit=recent_event_limit)

    def _schedule_next_locked(self, *, now: float | None = None) -> None:
        if self._timer is not None or self._executing or not self._queue:
            return
        current_now = float(self._time_source()) if now is None else float(now)
        if self._next_tick_deadline is None:
            self._next_tick_deadline = current_now + self._execute_every_s
        delay_s = max(0.0, float(self._next_tick_deadline) - current_now)
        if delay_s <= 1.0e-9:
            self._performance.increment("zero_delay_schedules")
        scheduled = schedule_later(
            delay_s,
            self._on_tick,
            owner=self._name,
            thread_timer_factory=threading.Timer,
        )
        self._timer = scheduled.handle
        self._last_timer_backend = scheduled.backend
        queue_depth = len(self._queue)
        self._performance.increment("scheduled_ticks")
        self._performance.set_state(
            timer_backend=self._last_timer_backend,
            queue_depth=queue_depth,
            next_delay_ms=delay_s * 1000.0,
            executing=self._executing,
        )
        self._performance.record_duration(
            "scheduled_delay_ms",
            delay_s * 1000.0,
            queue_depth=queue_depth,
            timer_backend=self._last_timer_backend,
        )
        self._emit(
            "debounce_tick_scheduled",
            phase="scheduled",
            delay_ms=int(round(delay_s * 1000)),
            queue_depth=queue_depth,
            timer_backend=self._last_timer_backend,
        )

    def _on_tick(self) -> None:
        call: _QueuedCall | None = None
        remaining = 0
        dropped = 0
        tick_now = float(self._time_source())
        with self._lock:
            self._timer = None
            expected_deadline = self._next_tick_deadline
            if not self._queue:
                self._next_tick_deadline = None
                self._performance.increment("empty_ticks")
                self._performance.set_state(queue_depth=0, executing=False)
                return
            if self._drop_overflow and len(self._queue) > 1:
                dropped = len(self._queue) - 1
                last = self._queue[-1]
                self._queue.clear()
                self._queue.append(last)
                self._performance.increment("dropped_overflow_calls", delta=dropped)
                self._emit("debounce_drop_overflow", phase="queued", dropped_count=dropped)
            call = self._queue.popleft()
            remaining = len(self._queue)
            self._executing = True
            self._performance.set_state(queue_depth=remaining, executing=True)

        if expected_deadline is not None:
            lateness_ms = max(0.0, (tick_now - float(expected_deadline)) * 1000.0)
            if lateness_ms > 0.0:
                self._performance.increment("overdue_ticks")
            self._performance.record_duration(
                "tick_lateness_ms",
                lateness_ms,
                queue_depth=remaining + 1,
                timer_backend=self._last_timer_backend,
            )

        self._emit(
            "debounce_tick_started",
            phase="started",
            queue_depth=remaining + 1,
            timer_backend=self._last_timer_backend,
        )
        callback_started = time.perf_counter()
        failed = False
        try:
            self._callback(*call.args, **call.kwargs)
        except Exception:
            failed = True
            self._performance.increment("callback_failures")
            self._emit("debounce_tick_failed", phase="failed", level=logging.ERROR)
            logging.getLogger(__name__).exception("QueuedDebouncer callback failed")
        finally:
            callback_ms = (time.perf_counter() - callback_started) * 1000.0
            self._performance.record_duration(
                "callback_duration_ms",
                callback_ms,
                outcome=("failed" if failed else "completed"),
                queue_depth=remaining,
                dropped_count=dropped,
            )
            if not failed:
                self._performance.increment("executed_callbacks")
            reschedule_now = float(self._time_source())
            missed_intervals = 0
            with self._lock:
                self._executing = False
                if self._queue:
                    if self._next_tick_deadline is None:
                        self._next_tick_deadline = reschedule_now + self._execute_every_s
                    else:
                        next_deadline = float(self._next_tick_deadline) + self._execute_every_s
                        while next_deadline <= reschedule_now:
                            next_deadline += self._execute_every_s
                            missed_intervals += 1
                        self._next_tick_deadline = next_deadline
                    self._performance.set_state(queue_depth=len(self._queue), executing=False)
                    self._schedule_next_locked(now=reschedule_now)
                else:
                    self._next_tick_deadline = None
                    self._performance.set_state(queue_depth=0, executing=False)
            if missed_intervals:
                self._performance.increment("missed_intervals", delta=missed_intervals)
        if not failed:
            self._emit("debounce_tick_completed", phase="completed", queue_depth=remaining)


__all__ = ["QueuedDebouncer"]
