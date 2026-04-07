"""Figure-level render scheduling and request coalescing.

Purpose
-------
Owns the figure-level policy that batches hot render triggers to roughly one
render per animation frame (~60 Hz). The scheduler is intentionally small and
transport-neutral so :class:`gu_toolkit.Figure.Figure` can keep orchestration
logic focused on plotting concerns rather than timer bookkeeping.

Design contract
---------------
- ``request(..., force=False)`` stores or merges a pending render request and
  schedules one debounced dispatch.
- ``request(..., force=True)`` merges the request and attempts to dispatch the
  newest pending state synchronously.
- Coalescing preserves the *latest* ``reason`` / ``trigger`` for observability
  while also remembering whether any queued request represented a parameter
  change. This lets the figure keep hook and stale-view semantics intact even
  when multiple requests collapse into one actual render.
- The callback boundary is resilient: dispatch exceptions are logged, pending
  requests remain schedulable, and later requests can still execute.

Why a dedicated module?
-----------------------
Historically ``Figure.render()`` executed synchronously and directly. With a
60 Hz batching target the render path now has enough policy (coalescing,
forced flushes, re-entrancy handling, logging) to justify a focused helper.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .debouncing import QueuedDebouncer
from .layout_logging import (
    LOGGER_NAME,
    emit_layout_event,
    is_layout_logger_explicitly_enabled,
)
from .performance_monitor import PerformanceMonitor


@dataclass(frozen=True)
class RenderRequest:
    """Immutable description of one dispatched figure render.
    
    Full API
    --------
    ``RenderRequest(reason: str, trigger: Any=None, queued_count: int=1, includes_param_change: bool=False, latest_param_change_trigger: Any=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    reason : str
        Short machine/human-readable reason recorded for scheduling or rendering. Required.
    
    trigger : Any, optional
        Event object or trigger payload that caused the current action. Defaults to ``None``.
    
    queued_count : int, optional
        Value for ``queued_count`` in this API. Defaults to ``1``.
    
    includes_param_change : bool, optional
        Value for ``includes_param_change`` in this API. Defaults to ``False``.
    
    latest_param_change_trigger : Any, optional
        Value for ``latest_param_change_trigger`` in this API. Defaults to ``None``.
    
    Returns
    -------
    RenderRequest
        New ``RenderRequest`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``trigger=None``: Event object or trigger payload that caused the current action.
    - ``queued_count=1``: Value for ``queued_count`` in this API.
    - ``includes_param_change=False``: Value for ``includes_param_change`` in this API.
    - ``latest_param_change_trigger=None``: Value for ``latest_param_change_trigger`` in this API.
    
    Architecture note
    -----------------
    ``RenderRequest`` lives in ``gu_toolkit.figure_render_scheduler``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_render_scheduler import RenderRequest
        obj = RenderRequest(...)
    
    Discovery-oriented use::
    
        help(RenderRequest)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
    - In a notebook or REPL, run ``help(RenderRequest)`` and ``dir(RenderRequest)`` to inspect adjacent members.
    """

    reason: str
    trigger: Any = None
    queued_count: int = 1
    includes_param_change: bool = False
    latest_param_change_trigger: Any = None


@dataclass
class _PendingRenderRequest:
    """Mutable coalescing state used internally by the scheduler."""

    reason: str
    trigger: Any = None
    queued_count: int = 1
    includes_param_change: bool = False
    latest_param_change_trigger: Any = None

    @classmethod
    def from_request(cls, *, reason: str, trigger: Any = None) -> "_PendingRenderRequest":
        """Work with from request on ``_PendingRenderRequest``.
        
        Full API
        --------
        ``_PendingRenderRequest.from_request(*, reason: str, trigger: Any=None) -> '_PendingRenderRequest'``
        
        Parameters
        ----------
        reason : str
            Short machine/human-readable reason recorded for scheduling or rendering. Required.
        
        trigger : Any, optional
            Event object or trigger payload that caused the current action. Defaults to ``None``.
        
        Returns
        -------
        '_PendingRenderRequest'
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``trigger=None``: Event object or trigger payload that caused the current action.
        
        Architecture note
        -----------------
        This member belongs to ``_PendingRenderRequest``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            result = _PendingRenderRequest.from_request(...)
        
        Discovery-oriented use::
        
            help(_PendingRenderRequest)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(_PendingRenderRequest)`` and ``dir(_PendingRenderRequest)`` to inspect adjacent members.
        """

        includes_param_change = str(reason) == "param_change"
        return cls(
            reason=str(reason),
            trigger=trigger,
            queued_count=1,
            includes_param_change=includes_param_change,
            latest_param_change_trigger=(trigger if includes_param_change else None),
        )

    def merge(self, *, reason: str, trigger: Any = None) -> None:
        """Merge a newly requested render into the pending dispatch state.
        
        Full API
        --------
        ``obj.merge(*, reason: str, trigger: Any=None) -> None``
        
        Parameters
        ----------
        reason : str
            Short machine/human-readable reason recorded for scheduling or rendering. Required.
        
        trigger : Any, optional
            Event object or trigger payload that caused the current action. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``trigger=None``: Event object or trigger payload that caused the current action.
        
        Architecture note
        -----------------
        This member belongs to ``_PendingRenderRequest``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _PendingRenderRequest(...)
            obj.merge(...)
        
        Discovery-oriented use::
        
            help(_PendingRenderRequest)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(_PendingRenderRequest)`` and ``dir(_PendingRenderRequest)`` to inspect adjacent members.
        """
        self.reason = str(reason)
        self.trigger = trigger
        self.queued_count += 1
        if str(reason) == "param_change":
            self.includes_param_change = True
            self.latest_param_change_trigger = trigger

    def freeze(self) -> RenderRequest:
        """Return an immutable snapshot of the pending dispatch state.
        
        Full API
        --------
        ``obj.freeze() -> RenderRequest``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        RenderRequest
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``_PendingRenderRequest``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _PendingRenderRequest(...)
            result = obj.freeze(...)
        
        Discovery-oriented use::
        
            help(_PendingRenderRequest)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(_PendingRenderRequest)`` and ``dir(_PendingRenderRequest)`` to inspect adjacent members.
        """
        return RenderRequest(
            reason=self.reason,
            trigger=self.trigger,
            queued_count=self.queued_count,
            includes_param_change=self.includes_param_change,
            latest_param_change_trigger=self.latest_param_change_trigger,
        )


class FigureRenderScheduler:
    """Coalesce figure render requests and dispatch them on a fixed cadence.
    
    Full API
    --------
    ``FigureRenderScheduler(dispatch_callback: Callable[[RenderRequest], Any], execute_every_ms: int=16, name: str='Figure.render', event_sink: Callable[Ellipsis, Any] | None=None)``
    
    Public members exposed from this class: ``has_pending``, ``performance_snapshot``, ``request``, ``flush``
    
    Parameters
    ----------
    dispatch_callback : Callable[[RenderRequest], Any]
        Value for ``dispatch_callback`` in this API. Required.
    
    execute_every_ms : int, optional
        Value for ``execute_every_ms`` in this API. Defaults to ``16``.
    
    name : str, optional
        Human-readable or canonical name for the target object. Defaults to ``'Figure.render'``.
    
    event_sink : Callable[Ellipsis, Any] | None, optional
        Value for ``event_sink`` in this API. Defaults to ``None``.
    
    Returns
    -------
    FigureRenderScheduler
        New ``FigureRenderScheduler`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``execute_every_ms=16``: Value for ``execute_every_ms`` in this API.
    - ``name='Figure.render'``: Human-readable or canonical name for the target object.
    - ``event_sink=None``: Value for ``event_sink`` in this API.
    
    Architecture note
    -----------------
    ``FigureRenderScheduler`` lives in ``gu_toolkit.figure_render_scheduler``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_render_scheduler import FigureRenderScheduler
        obj = FigureRenderScheduler(...)
    
    Discovery-oriented use::
    
        help(FigureRenderScheduler)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
    - In a notebook or REPL, run ``help(FigureRenderScheduler)`` and ``dir(FigureRenderScheduler)`` to inspect adjacent members.
    """

    def __init__(
        self,
        dispatch_callback: Callable[[RenderRequest], Any],
        *,
        execute_every_ms: int = 16,
        name: str = "Figure.render",
        event_sink: Callable[..., Any] | None = None,
    ) -> None:
        if execute_every_ms <= 0:
            raise ValueError("execute_every_ms must be > 0")
        self._dispatch_callback = dispatch_callback
        self._name = str(name)
        self._event_sink = event_sink
        self._lock = threading.Lock()
        self._pending: _PendingRenderRequest | None = None
        self._dispatching = False
        self._performance = PerformanceMonitor(f"FigureRenderScheduler[{self._name}]")
        self._performance.set_state(
            execute_every_ms=int(execute_every_ms),
            dispatching=False,
            has_pending=False,
        )
        self._debouncer = QueuedDebouncer(
            self._dispatch_from_tick,
            execute_every_ms=execute_every_ms,
            drop_overflow=True,
            name=self._name,
            event_sink=event_sink,
        )

    def _emit(
        self,
        event: str,
        *,
        phase: str,
        level: int = logging.DEBUG,
        **fields: Any,
    ) -> None:
        if self._event_sink is not None:
            self._event_sink(
                event=event,
                source="FigureRenderScheduler",
                phase=phase,
                level=level,
                owner=self._name,
                **fields,
            )
            return
        scheduler_logger = logging.getLogger(f"{LOGGER_NAME}.render")
        if not is_layout_logger_explicitly_enabled(scheduler_logger):
            return
        emit_layout_event(
            scheduler_logger,
            event=event,
            source="FigureRenderScheduler",
            phase=phase,
            level=level,
            owner=self._name,
            **fields,
        )

    @property
    def has_pending(self) -> bool:
        """Whether a render request is currently waiting to be dispatched.
        
        Full API
        --------
        ``obj.has_pending -> bool``
        
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
        This member belongs to ``FigureRenderScheduler``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureRenderScheduler(...)
            current = obj.has_pending
        
        Discovery-oriented use::
        
            help(FigureRenderScheduler)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(FigureRenderScheduler)`` and ``dir(FigureRenderScheduler)`` to inspect adjacent members.
        """
        with self._lock:
            return self._pending is not None

    def performance_snapshot(self, *, recent_event_limit: int = 25) -> dict[str, Any]:
        """Work with performance snapshot on ``FigureRenderScheduler``.
        
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
        This member belongs to ``FigureRenderScheduler``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureRenderScheduler(...)
            result = obj.performance_snapshot(...)
        
        Discovery-oriented use::
        
            help(FigureRenderScheduler)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(FigureRenderScheduler)`` and ``dir(FigureRenderScheduler)`` to inspect adjacent members.
        """

        snapshot = self._performance.snapshot(recent_limit=recent_event_limit)
        snapshot["debouncer"] = self._debouncer.performance_snapshot(
            recent_event_limit=recent_event_limit
        )
        snapshot["state"]["debouncer_timer_backend"] = self._debouncer.timer_backend
        return snapshot

    def request(self, reason: str, trigger: Any = None, *, force: bool = False) -> None:
        """Queue or immediately flush a render request.
        
        Full API
        --------
        ``obj.request(reason: str, trigger: Any=None, *, force: bool=False) -> None``
        
        Parameters
        ----------
        reason : str
            Short machine/human-readable reason recorded for scheduling or rendering. Required.
        
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
        - ``trigger=None``: Event object or trigger payload that caused the current action.
        - ``force=False``: Flag that requests eager execution or bypasses normal guards/debouncing.
        
        Architecture note
        -----------------
        This member belongs to ``FigureRenderScheduler``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureRenderScheduler(...)
            obj.request(...)
        
        Discovery-oriented use::
        
            help(FigureRenderScheduler)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(FigureRenderScheduler)`` and ``dir(FigureRenderScheduler)`` to inspect adjacent members.
        """
        with self._lock:
            if self._pending is None:
                self._pending = _PendingRenderRequest.from_request(
                    reason=reason,
                    trigger=trigger,
                )
            else:
                self._pending.merge(reason=reason, trigger=trigger)
                self._performance.increment("coalesced_requests")
            snapshot = self._pending.freeze()
            dispatching = self._dispatching
            self._performance.increment("requests")
            if force:
                self._performance.increment("forced_requests")
            self._performance.set_state(
                has_pending=True,
                pending_reason=snapshot.reason,
                pending_queued_count=snapshot.queued_count,
                dispatching=dispatching,
            )

        self._emit(
            "render_request_queued",
            phase="queued",
            level=logging.INFO,
            reason=snapshot.reason,
            queued_count=snapshot.queued_count,
            includes_param_change=snapshot.includes_param_change,
            force=bool(force),
            trigger_type=(type(snapshot.trigger).__name__ if snapshot.trigger is not None else None),
        )

        if not dispatching:
            self._debouncer()

        if force:
            self.flush()

    def flush(self) -> None:
        """Synchronously dispatch the newest pending request, if any.
        
        Full API
        --------
        ``obj.flush() -> None``
        
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
        This member belongs to ``FigureRenderScheduler``. This module centralizes one slice of toolkit behavior so notebook helpers, views, and export/snapshot flows share the same invariants. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureRenderScheduler(...)
            obj.flush(...)
        
        Discovery-oriented use::
        
            help(FigureRenderScheduler)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Runtime discovery tip: use ``help(...)`` and inspect nearby module members to discover adjacent helpers.
        - In a notebook or REPL, run ``help(FigureRenderScheduler)`` and ``dir(FigureRenderScheduler)`` to inspect adjacent members.
        """
        self._performance.increment("flush_calls")
        self._dispatch_once(origin="flush")

    def _dispatch_from_tick(self) -> None:
        """Dispatch the newest pending request from the debounced tick."""
        self._dispatch_once(origin="tick")

    def _dispatch_once(self, *, origin: str) -> None:
        request: RenderRequest | None = None
        dispatch_started = time.perf_counter()
        with self._lock:
            if self._dispatching:
                self._performance.increment("dispatch_skipped_dispatching")
                self._emit(
                    "render_request_dispatch_skipped",
                    phase="skipped",
                    origin=origin,
                    outcome="already_dispatching",
                )
                return
            if self._pending is None:
                self._performance.increment("dispatch_skipped_empty")
                self._emit(
                    "render_request_dispatch_skipped",
                    phase="skipped",
                    origin=origin,
                    outcome="no_pending_request",
                )
                return
            request = self._pending.freeze()
            self._pending = None
            self._dispatching = True
            self._performance.increment("dispatches")
            self._performance.set_state(
                dispatching=True,
                has_pending=False,
                active_origin=origin,
                active_reason=request.reason,
                active_queued_count=request.queued_count,
            )

        self._emit(
            "render_request_dispatch_started",
            phase="started",
            level=logging.INFO,
            origin=origin,
            reason=request.reason,
            queued_count=request.queued_count,
            includes_param_change=request.includes_param_change,
            trigger_type=(type(request.trigger).__name__ if request.trigger is not None else None),
        )

        failed = False
        try:
            self._dispatch_callback(request)
        except Exception:  # pragma: no cover - defensive callback boundary
            failed = True
            self._performance.increment("dispatch_failures")
            self._emit(
                "render_request_dispatch_failed",
                phase="failed",
                origin=origin,
                level=logging.ERROR,
            )
            logging.getLogger(__name__).exception(
                "FigureRenderScheduler dispatch failed"
            )
        finally:
            duration_ms = (time.perf_counter() - dispatch_started) * 1000.0
            self._performance.record_duration(
                "dispatch_duration_ms",
                duration_ms,
                origin=origin,
                reason=(request.reason if request is not None else None),
                failed=failed,
            )
            with self._lock:
                self._dispatching = False
                needs_reschedule = self._pending is not None
                self._performance.set_state(
                    dispatching=False,
                    has_pending=needs_reschedule,
                    active_origin=None,
                )

        if not failed:
            self._emit(
                "render_request_dispatch_completed",
                phase="completed",
                level=logging.INFO,
                origin=origin,
                reason=request.reason,
                queued_count=request.queued_count,
                includes_param_change=request.includes_param_change,
            )

        if needs_reschedule:
            self._performance.increment("reschedules")
            self._emit(
                "render_request_rescheduled",
                phase="scheduled",
                origin=origin,
            )
            self._debouncer()


__all__ = ["FigureRenderScheduler", "RenderRequest"]
