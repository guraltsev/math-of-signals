"""Lightweight performance counters and timing summaries used across the toolkit.

Public entry points
-------------------
``TimingStats``, ``PerformanceMonitor``, ``format_performance_snapshot``

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

import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

Scalar = str | int | float | bool | None


@dataclass
class TimingStats:
    """Aggregate min/mean/max/count timing data for one measurement stream.
    
    Full API
    --------
    ``TimingStats(count: int=0, total_ms: float=0.0, last_ms: float | None=None, min_ms: float | None=None, max_ms: float | None=None)``
    
    Public members exposed from this class: ``add``, ``to_dict``
    
    Parameters
    ----------
    count : int, optional
        Value for ``count`` in this API. Defaults to ``0``.
    
    total_ms : float, optional
        Value for ``total_ms`` in this API. Defaults to ``0.0``.
    
    last_ms : float | None, optional
        Value for ``last_ms`` in this API. Defaults to ``None``.
    
    min_ms : float | None, optional
        Value for ``min_ms`` in this API. Defaults to ``None``.
    
    max_ms : float | None, optional
        Value for ``max_ms`` in this API. Defaults to ``None``.
    
    Returns
    -------
    TimingStats
        New ``TimingStats`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``count=0``: Value for ``count`` in this API.
    - ``total_ms=0.0``: Value for ``total_ms`` in this API.
    - ``last_ms=None``: Value for ``last_ms`` in this API.
    - ``min_ms=None``: Value for ``min_ms`` in this API.
    - ``max_ms=None``: Value for ``max_ms`` in this API.
    
    Architecture note
    -----------------
    ``TimingStats`` lives in ``gu_toolkit.performance_monitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.performance_monitor import TimingStats
        obj = TimingStats(...)
    
    Discovery-oriented use::
    
        help(TimingStats)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(TimingStats)`` and ``dir(TimingStats)`` to inspect adjacent members.
    """

    count: int = 0
    total_ms: float = 0.0
    last_ms: float | None = None
    min_ms: float | None = None
    max_ms: float | None = None

    def add(self, value_ms: float) -> None:
        """Work with add on ``TimingStats``.
        
        Full API
        --------
        ``obj.add(value_ms: float) -> None``
        
        Parameters
        ----------
        value_ms : float
            Value for ``value_ms`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``TimingStats``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = TimingStats(...)
            obj.add(...)
        
        Discovery-oriented use::
        
            help(TimingStats)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(TimingStats)`` and ``dir(TimingStats)`` to inspect adjacent members.
        """

        value = float(value_ms)
        self.count += 1
        self.total_ms += value
        self.last_ms = value
        self.min_ms = value if self.min_ms is None else min(self.min_ms, value)
        self.max_ms = value if self.max_ms is None else max(self.max_ms, value)

    def to_dict(self) -> dict[str, float | int | None]:
        """Work with to dict on ``TimingStats``.
        
        Full API
        --------
        ``obj.to_dict() -> dict[str, float | int | None]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, float | int | None]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``TimingStats``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = TimingStats(...)
            result = obj.to_dict(...)
        
        Discovery-oriented use::
        
            help(TimingStats)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(TimingStats)`` and ``dir(TimingStats)`` to inspect adjacent members.
        """

        mean_ms = (self.total_ms / self.count) if self.count else None
        return {
            "count": self.count,
            "last_ms": self.last_ms,
            "mean_ms": mean_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "total_ms": self.total_ms,
        }


def _normalize_value(value: Any) -> Scalar | list[Any] | dict[str, Any]:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _normalize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            coerced = item()
        except Exception:
            coerced = value
        if coerced is not value:
            return _normalize_value(coerced)
    return str(value)


class PerformanceMonitor:
    """Record counters, timers, and structured events for one subsystem.
    
    Full API
    --------
    ``PerformanceMonitor(name: str, max_events: int=250)``
    
    Public members exposed from this class: ``name``, ``set_state``, ``increment``, ``record_duration``, ``event``, ``snapshot``
    
    Parameters
    ----------
    name : str
        Human-readable or canonical name for the target object. Required.
    
    max_events : int, optional
        Value for ``max_events`` in this API. Defaults to ``250``.
    
    Returns
    -------
    PerformanceMonitor
        New ``PerformanceMonitor`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``max_events=250``: Value for ``max_events`` in this API.
    
    Architecture note
    -----------------
    ``PerformanceMonitor`` lives in ``gu_toolkit.performance_monitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.performance_monitor import PerformanceMonitor
        obj = PerformanceMonitor(...)
    
    Discovery-oriented use::
    
        help(PerformanceMonitor)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
    """

    def __init__(self, name: str, *, max_events: int = 250) -> None:
        self._name = str(name)
        self._lock = threading.Lock()
        self._timings: dict[str, TimingStats] = {}
        self._counters: dict[str, int] = {}
        self._state: dict[str, Any] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)

    @property
    def name(self) -> str:
        """Work with name on ``PerformanceMonitor``.
        
        Full API
        --------
        ``obj.name -> str``
        
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
        This member belongs to ``PerformanceMonitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PerformanceMonitor(...)
            current = obj.name
        
        Discovery-oriented use::
        
            help(PerformanceMonitor)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
        """

        return self._name

    def set_state(self, **fields: Any) -> None:
        """Set state.
        
        Full API
        --------
        ``obj.set_state(**fields: Any) -> None``
        
        Parameters
        ----------
        **fields : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``**fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``PerformanceMonitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PerformanceMonitor(...)
            obj.set_state(...)
        
        Discovery-oriented use::
        
            help(PerformanceMonitor)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
        """

        normalized = {str(key): _normalize_value(value) for key, value in fields.items()}
        with self._lock:
            self._state.update(normalized)

    def increment(self, counter: str, delta: int = 1, **fields: Any) -> None:
        """Work with increment on ``PerformanceMonitor``.
        
        Full API
        --------
        ``obj.increment(counter: str, delta: int=1, **fields: Any) -> None``
        
        Parameters
        ----------
        counter : str
            Value for ``counter`` in this API. Required.
        
        delta : int, optional
            Value for ``delta`` in this API. Defaults to ``1``.
        
        **fields : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``delta=1``: Value for ``delta`` in this API.
        - ``**fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``PerformanceMonitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PerformanceMonitor(...)
            obj.increment(...)
        
        Discovery-oriented use::
        
            help(PerformanceMonitor)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
        """

        payload = {
            "ts": round(time.time(), 6),
            "kind": "counter",
            "name": str(counter),
            "delta": int(delta),
        }
        if fields:
            payload["fields"] = {str(key): _normalize_value(value) for key, value in fields.items()}
        with self._lock:
            self._counters[str(counter)] = self._counters.get(str(counter), 0) + int(delta)
            self._events.append(payload)

    def record_duration(self, metric: str, duration_ms: float, **fields: Any) -> None:
        """Work with record duration on ``PerformanceMonitor``.
        
        Full API
        --------
        ``obj.record_duration(metric: str, duration_ms: float, **fields: Any) -> None``
        
        Parameters
        ----------
        metric : str
            Value for ``metric`` in this API. Required.
        
        duration_ms : float
            Value for ``duration_ms`` in this API. Required.
        
        **fields : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``**fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``PerformanceMonitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PerformanceMonitor(...)
            obj.record_duration(...)
        
        Discovery-oriented use::
        
            help(PerformanceMonitor)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
        """

        name = str(metric)
        payload = {
            "ts": round(time.time(), 6),
            "kind": "timing",
            "name": name,
            "duration_ms": float(duration_ms),
        }
        if fields:
            payload["fields"] = {str(key): _normalize_value(value) for key, value in fields.items()}
        with self._lock:
            stats = self._timings.get(name)
            if stats is None:
                stats = TimingStats()
                self._timings[name] = stats
            stats.add(float(duration_ms))
            self._events.append(payload)

    def event(self, event: str, **fields: Any) -> None:
        """Work with event on ``PerformanceMonitor``.
        
        Full API
        --------
        ``obj.event(event: str, **fields: Any) -> None``
        
        Parameters
        ----------
        event : str
            Event object describing what changed. Required.
        
        **fields : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``**fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``PerformanceMonitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PerformanceMonitor(...)
            obj.event(...)
        
        Discovery-oriented use::
        
            help(PerformanceMonitor)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
        """

        payload = {
            "ts": round(time.time(), 6),
            "kind": "event",
            "name": str(event),
        }
        if fields:
            payload["fields"] = {str(key): _normalize_value(value) for key, value in fields.items()}
        with self._lock:
            self._events.append(payload)

    def snapshot(self, *, recent_limit: int = 25) -> dict[str, Any]:
        """Work with snapshot on ``PerformanceMonitor``.
        
        Full API
        --------
        ``obj.snapshot(*, recent_limit: int=25) -> dict[str, Any]``
        
        Parameters
        ----------
        recent_limit : int, optional
            Value for ``recent_limit`` in this API. Defaults to ``25``.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_limit=25``: Value for ``recent_limit`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``PerformanceMonitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PerformanceMonitor(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(PerformanceMonitor)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(PerformanceMonitor)`` and ``dir(PerformanceMonitor)`` to inspect adjacent members.
        """

        with self._lock:
            timings = {name: stats.to_dict() for name, stats in sorted(self._timings.items())}
            counters = {name: value for name, value in sorted(self._counters.items())}
            state = dict(sorted(self._state.items()))
            events = list(self._events)[-max(0, int(recent_limit)) :]
        return {
            "name": self._name,
            "state": state,
            "counters": counters,
            "timings": timings,
            "recent_events": events,
        }


def format_performance_snapshot(snapshot: Mapping[str, Any], *, title: str | None = None, indent: str = "") -> str:
    """Format performance snapshot.
    
    Full API
    --------
    ``format_performance_snapshot(snapshot: Mapping[str, Any], *, title: str | None=None, indent: str='') -> str``
    
    Parameters
    ----------
    snapshot : Mapping[str, Any]
        Snapshot object or snapshot payload used by this API. Required.
    
    title : str | None, optional
        Human-readable title text shown in the UI or stored in snapshots. Defaults to ``None``.
    
    indent : str, optional
        Value for ``indent`` in this API. Defaults to ``''``.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``title=None``: Human-readable title text shown in the UI or stored in snapshots.
    - ``indent=''``: Value for ``indent`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.performance_monitor``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.performance_monitor import format_performance_snapshot
        result = format_performance_snapshot(...)
    
    Discovery-oriented use::
    
        help(format_performance_snapshot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(format_performance_snapshot)`` and inspect sibling APIs in the same module.
    """

    lines: list[str] = []
    heading = title or str(snapshot.get("name", "performance"))
    lines.append(f"{indent}{heading}")
    state = snapshot.get("state", {})
    if isinstance(state, Mapping) and state:
        lines.append(f"{indent}  state:")
        for key, value in state.items():
            lines.append(f"{indent}    {key}: {value}")
    counters = snapshot.get("counters", {})
    if isinstance(counters, Mapping) and counters:
        lines.append(f"{indent}  counters:")
        for key, value in counters.items():
            lines.append(f"{indent}    {key}: {value}")
    timings = snapshot.get("timings", {})
    if isinstance(timings, Mapping) and timings:
        lines.append(f"{indent}  timings:")
        for key, value in timings.items():
            if not isinstance(value, Mapping):
                lines.append(f"{indent}    {key}: {value}")
                continue
            mean_ms = value.get("mean_ms")
            last_ms = value.get("last_ms")
            max_ms = value.get("max_ms")
            count = value.get("count")
            mean_text = f"{float(mean_ms):.3f}" if isinstance(mean_ms, (int, float)) else "-"
            last_text = f"{float(last_ms):.3f}" if isinstance(last_ms, (int, float)) else "-"
            max_text = f"{float(max_ms):.3f}" if isinstance(max_ms, (int, float)) else "-"
            lines.append(
                f"{indent}    {key}: count={count} mean_ms={mean_text} last_ms={last_text} max_ms={max_text}"
            )
    recent_events = snapshot.get("recent_events", [])
    if isinstance(recent_events, list) and recent_events:
        lines.append(f"{indent}  recent_events:")
        for event in recent_events[-5:]:
            if not isinstance(event, Mapping):
                continue
            name = event.get("name")
            kind = event.get("kind")
            if kind == "timing":
                duration_ms = event.get("duration_ms")
                lines.append(f"{indent}    {name}: {duration_ms} ms")
            elif kind == "counter":
                lines.append(f"{indent}    {name}: +{event.get('delta')}")
            else:
                lines.append(f"{indent}    {name}")
    return "\n".join(lines)


__all__ = ["PerformanceMonitor", "TimingStats", "format_performance_snapshot"]
