"""Structured layout-debug identifiers, emitters, and in-memory event capture.

Public entry points
-------------------
``LayoutEventBuffer``, ``new_debug_id``, ``new_request_id``,
    ``is_layout_logger_explicitly_enabled``, ``normalize_fields``,
    ``emit_layout_event``, ``make_event_emitter``, ``layout_value_snapshot``

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

import itertools
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

LOGGER_NAME = "gu_toolkit.layout"
logger = logging.getLogger(LOGGER_NAME)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_layout_id_counter = itertools.count(1)
_request_counter = itertools.count(1)


@dataclass
class LayoutEventBuffer:
    """Collect structured layout-debug events in memory for later inspection.
    
    Full API
    --------
    ``LayoutEventBuffer(maxlen: int=500, events: deque[dict[str, Any]]=field(default_factory=deque))``
    
    Public members exposed from this class: ``append``, ``snapshot``
    
    Parameters
    ----------
    maxlen : int, optional
        Value for ``maxlen`` in this API. Defaults to ``500``.
    
    events : deque[dict[str, Any]], optional
        Value for ``events`` in this API. Defaults to ``field(default_factory=deque)``.
    
    Returns
    -------
    LayoutEventBuffer
        New ``LayoutEventBuffer`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``maxlen=500``: Value for ``maxlen`` in this API.
    - ``events=field(default_factory=deque)``: Value for ``events`` in this API.
    
    Architecture note
    -----------------
    ``LayoutEventBuffer`` lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.layout_logging import LayoutEventBuffer
        obj = LayoutEventBuffer(...)
    
    Discovery-oriented use::
    
        help(LayoutEventBuffer)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(LayoutEventBuffer)`` and ``dir(LayoutEventBuffer)`` to inspect adjacent members.
    """

    maxlen: int = 500
    events: deque[dict[str, Any]] = field(default_factory=deque)

    def append(self, payload: dict[str, Any]) -> None:
        """Work with append on ``LayoutEventBuffer``.
        
        Full API
        --------
        ``obj.append(payload: dict[str, Any]) -> None``
        
        Parameters
        ----------
        payload : dict[str, Any]
            Value for ``payload`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LayoutEventBuffer``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LayoutEventBuffer(...)
            obj.append(...)
        
        Discovery-oriented use::
        
            help(LayoutEventBuffer)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(LayoutEventBuffer)`` and ``dir(LayoutEventBuffer)`` to inspect adjacent members.
        """

        if self.events.maxlen != self.maxlen:
            self.events = deque(self.events, maxlen=self.maxlen)
        self.events.append(dict(payload))

    def snapshot(self) -> list[dict[str, Any]]:
        """Work with snapshot on ``LayoutEventBuffer``.
        
        Full API
        --------
        ``obj.snapshot() -> list[dict[str, Any]]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        list[dict[str, Any]]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LayoutEventBuffer``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LayoutEventBuffer(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(LayoutEventBuffer)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(LayoutEventBuffer)`` and ``dir(LayoutEventBuffer)`` to inspect adjacent members.
        """

        return list(self.events)



def new_debug_id(prefix: str) -> str:
    """Create a new debug id.
    
    Full API
    --------
    ``new_debug_id(prefix: str) -> str``
    
    Parameters
    ----------
    prefix : str
        Value for ``prefix`` in this API. Required.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import new_debug_id
        result = new_debug_id(...)
    
    Discovery-oriented use::
    
        help(new_debug_id)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(new_debug_id)`` and inspect sibling APIs in the same module.
    """

    return f"{prefix}-{next(_layout_id_counter):04d}-{uuid.uuid4().hex[:6]}"



def new_request_id() -> str:
    """Create a new request id.
    
    Full API
    --------
    ``new_request_id() -> str``
    
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
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import new_request_id
        result = new_request_id(...)
    
    Discovery-oriented use::
    
        help(new_request_id)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(new_request_id)`` and inspect sibling APIs in the same module.
    """

    return f"req-{next(_request_counter):06d}"



def is_layout_logger_explicitly_enabled(logger_or_name: str | logging.Logger) -> bool:
    """Return whether layout instrumentation was explicitly enabled.
    
    Full API
    --------
    ``is_layout_logger_explicitly_enabled(logger_or_name: str | logging.Logger) -> bool``
    
    Parameters
    ----------
    logger_or_name : str | logging.Logger
        Value for ``logger_or_name`` in this API. Required.
    
    Returns
    -------
    bool
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import is_layout_logger_explicitly_enabled
        result = is_layout_logger_explicitly_enabled(...)
    
    Discovery-oriented use::
    
        help(is_layout_logger_explicitly_enabled)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(is_layout_logger_explicitly_enabled)`` and inspect sibling APIs in the same module.
    """
    if isinstance(logger_or_name, logging.Logger):
        logger_obj = logger_or_name
    else:
        logger_obj = logging.getLogger(logger_or_name)

    while logger_obj is not None:
        name = logger_obj.name or ""
        if name in {"root", ""}:
            return False
        if name == LOGGER_NAME or name.startswith(f"{LOGGER_NAME}."):
            if logger_obj.level != logging.NOTSET:
                return logger_obj.level <= logging.INFO
            logger_obj = logger_obj.parent
            continue
        logger_obj = logger_obj.parent
    return False



def normalize_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize fields.
    
    Full API
    --------
    ``normalize_fields(fields: Mapping[str, Any]) -> dict[str, Any]``
    
    Parameters
    ----------
    fields : Mapping[str, Any]
        Value for ``fields`` in this API. Required.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import normalize_fields
        result = normalize_fields(...)
    
    Discovery-oriented use::
    
        help(normalize_fields)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(normalize_fields)`` and inspect sibling APIs in the same module.
    """

    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float | str):
            payload[key] = value
        elif isinstance(value, Mapping):
            for sub_key, sub_val in value.items():
                payload[f"{key}_{sub_key}"] = sub_val
        elif isinstance(value, (list, tuple)):
            payload[key] = list(value)
        else:
            payload[key] = str(value)
    return payload



def emit_layout_event(
    logger: logging.Logger,
    *,
    event: str,
    source: str,
    phase: str,
    level: int = logging.DEBUG,
    buffer: LayoutEventBuffer | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Work with emit layout event.
    
    Full API
    --------
    ``emit_layout_event(logger: logging.Logger, *, event: str, source: str, phase: str, level: int=logging.DEBUG, buffer: LayoutEventBuffer | None=None, **fields: Any) -> dict[str, Any]``
    
    Parameters
    ----------
    logger : logging.Logger
        Value for ``logger`` in this API. Required.
    
    event : str
        Event object describing what changed. Required.
    
    source : str
        Value for ``source`` in this API. Required.
    
    phase : str
        Value for ``phase`` in this API. Required.
    
    level : int, optional
        Value for ``level`` in this API. Defaults to ``logging.DEBUG``.
    
    buffer : LayoutEventBuffer | None, optional
        Value for ``buffer`` in this API. Defaults to ``None``.
    
    **fields : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``level=logging.DEBUG``: Value for ``level`` in this API.
    - ``buffer=None``: Value for ``buffer`` in this API.
    - ``**fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import emit_layout_event
        result = emit_layout_event(...)
    
    Discovery-oriented use::
    
        help(emit_layout_event)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(emit_layout_event)`` and inspect sibling APIs in the same module.
    """

    payload = {
        "ts": round(time.time(), 6),
        "event": event,
        "source": source,
        "phase": phase,
    }
    payload.update(normalize_fields(fields))
    if buffer is not None:
        buffer.append(payload)
    logger.log(level, "%s", payload)
    return payload



def make_event_emitter(
    logger: logging.Logger,
    *,
    buffer: LayoutEventBuffer | None = None,
    base_fields: Mapping[str, Any] | None = None,
    seq_factory: Callable[[], int] | None = None,
) -> Callable[..., dict[str, Any]]:
    """Work with make event emitter.
    
    Full API
    --------
    ``make_event_emitter(logger: logging.Logger, *, buffer: LayoutEventBuffer | None=None, base_fields: Mapping[str, Any] | None=None, seq_factory: Callable[[], int] | None=None) -> Callable[..., dict[str, Any]]``
    
    Parameters
    ----------
    logger : logging.Logger
        Value for ``logger`` in this API. Required.
    
    buffer : LayoutEventBuffer | None, optional
        Value for ``buffer`` in this API. Defaults to ``None``.
    
    base_fields : Mapping[str, Any] | None, optional
        Value for ``base_fields`` in this API. Defaults to ``None``.
    
    seq_factory : Callable[[], int] | None, optional
        Value for ``seq_factory`` in this API. Defaults to ``None``.
    
    Returns
    -------
    Callable[Ellipsis, dict[str, Any]]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``buffer=None``: Value for ``buffer`` in this API.
    - ``base_fields=None``: Value for ``base_fields`` in this API.
    - ``seq_factory=None``: Value for ``seq_factory`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import make_event_emitter
        result = make_event_emitter(...)
    
    Discovery-oriented use::
    
        help(make_event_emitter)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(make_event_emitter)`` and inspect sibling APIs in the same module.
    """

    base = dict(base_fields or {})

    def _emit(*, event: str, source: str, phase: str, level: int = logging.DEBUG, **fields: Any) -> dict[str, Any]:
        merged = dict(base)
        merged.update(fields)
        if seq_factory is not None and "seq" not in merged:
            merged["seq"] = seq_factory()
        return emit_layout_event(
            logger,
            event=event,
            source=source,
            phase=phase,
            level=level,
            buffer=buffer,
            **merged,
        )

    return _emit



def layout_value_snapshot(layout: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Work with layout value snapshot.
    
    Full API
    --------
    ``layout_value_snapshot(layout: Any, fields: tuple[str, ...]) -> dict[str, Any]``
    
    Parameters
    ----------
    layout : Any
        Layout object or layout specification. Required.
    
    fields : tuple[str, Ellipsis]
        Value for ``fields`` in this API. Required.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.layout_logging``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.layout_logging import layout_value_snapshot
        result = layout_value_snapshot(...)
    
    Discovery-oriented use::
    
        help(layout_value_snapshot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(layout_value_snapshot)`` and inspect sibling APIs in the same module.
    """

    snap: dict[str, Any] = {}
    if layout is None:
        return snap
    for field in fields:
        try:
            value = getattr(layout, field)
        except Exception:
            continue
        if value not in (None, ""):
            snap[field] = value
    return snap
