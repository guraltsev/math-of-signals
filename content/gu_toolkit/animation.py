"""Parameter animation helpers for notebook controls.

The animation system is intentionally small and widget-friendly:

- a shared clock drives active animations at a fixed cadence,
- each control owns a lightweight :class:`AnimationController`,
- values are quantized to admissible slider values before being applied.

The controller keeps an internal continuous value so animation remains smooth
when the displayed control value is discretized by slider ``step``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from .performance_monitor import PerformanceMonitor
from .runtime_support import schedule_later

AnimationMode = Literal[">>", ">", "<>"]

DEFAULT_ANIMATION_HZ = 60.0
DEFAULT_ANIMATION_TIME = 5.0
_VALID_ANIMATION_MODES = (">>", ">", "<>")
_EPS = 1e-12


class AnimationClockLike(Protocol):
    """Minimal clock protocol used by :class:`AnimationController`.
    
    Full API
    --------
    ``AnimationClockLike()``
    
    Public members exposed from this class: ``subscribe``, ``unsubscribe``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    Any implementation of ``AnimationClockLike``
        Objects matching this protocol/interface can be passed anywhere the toolkit expects ``AnimationClockLike``.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``AnimationClockLike`` lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Implementation sketch::
    
        from gu_toolkit.animation import AnimationClockLike
    
        class MyAnimationClockLike(AnimationClockLike):
            ...
    
    Discovery-oriented use::
    
        help(AnimationClockLike)
        dir(MyAnimationClockLike)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(AnimationClockLike)`` and ``dir(AnimationClockLike)`` to inspect adjacent members.
    """

    def subscribe(self, callback: Callable[[float], None]) -> None:
        """Register a callback that receives the current monotonic time.
        
        Full API
        --------
        ``obj.subscribe(callback: Callable[[float], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[float], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationClockLike``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationClockLike(...)
            obj.subscribe(...)
        
        Discovery-oriented use::
        
            help(AnimationClockLike)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationClockLike)`` and ``dir(AnimationClockLike)`` to inspect adjacent members.
        """

    def unsubscribe(self, callback: Callable[[float], None]) -> None:
        """Unregister a previously registered callback.
        
        Full API
        --------
        ``obj.unsubscribe(callback: Callable[[float], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[float], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationClockLike``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationClockLike(...)
            obj.unsubscribe(...)
        
        Discovery-oriented use::
        
            help(AnimationClockLike)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationClockLike)`` and ``dir(AnimationClockLike)`` to inspect adjacent members.
        """


class AnimationTarget(Protocol):
    """Control contract required by :class:`AnimationController`.
    
    Full API
    --------
    ``AnimationTarget()``
    
    Public members exposed from this class: ``value``, ``min``, ``max``, ``step``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    Any implementation of ``AnimationTarget``
        Objects matching this protocol/interface can be passed anywhere the toolkit expects ``AnimationTarget``.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``AnimationTarget`` lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Implementation sketch::
    
        from gu_toolkit.animation import AnimationTarget
    
        class MyAnimationTarget(AnimationTarget):
            ...
    
    Discovery-oriented use::
    
        help(AnimationTarget)
        dir(MyAnimationTarget)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(AnimationTarget)`` and ``dir(AnimationTarget)`` to inspect adjacent members.
    """

    @property
    def value(self) -> float:
        """Current control value.
        
        Full API
        --------
        ``obj.value -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationTarget``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationTarget(...)
            current = obj.value
        
        Discovery-oriented use::
        
            help(AnimationTarget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationTarget)`` and ``dir(AnimationTarget)`` to inspect adjacent members.
        """

    @value.setter
    def value(self, value: float) -> None:
        """Apply a new control value.
        
        Full API
        --------
        ``obj.value = value``
        
        Parameters
        ----------
        value : float
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
        This member belongs to ``AnimationTarget``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationTarget(...)
            obj.value = value
        
        Discovery-oriented use::
        
            help(AnimationTarget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationTarget)`` and ``dir(AnimationTarget)`` to inspect adjacent members.
        """

    @property
    def min(self) -> float:
        """Lower bound of the control.
        
        Full API
        --------
        ``obj.min -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationTarget``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationTarget(...)
            current = obj.min
        
        Discovery-oriented use::
        
            help(AnimationTarget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationTarget)`` and ``dir(AnimationTarget)`` to inspect adjacent members.
        """

    @property
    def max(self) -> float:
        """Upper bound of the control.
        
        Full API
        --------
        ``obj.max -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationTarget``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationTarget(...)
            current = obj.max
        
        Discovery-oriented use::
        
            help(AnimationTarget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationTarget)`` and ``dir(AnimationTarget)`` to inspect adjacent members.
        """

    @property
    def step(self) -> float:
        """Step size used by the control.
        
        Full API
        --------
        ``obj.step -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationTarget``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationTarget(...)
            current = obj.step
        
        Discovery-oriented use::
        
            help(AnimationTarget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationTarget)`` and ``dir(AnimationTarget)`` to inspect adjacent members.
        """


@dataclass(frozen=True)
class AnimationDomain:
    """Numeric domain used for animation quantization and wrapping.
    
    Full API
    --------
    ``AnimationDomain(min: float, max: float, step: float)``
    
    Public members exposed from this class: ``span``
    
    Parameters
    ----------
    min : float
        Lower bound used by sliders, domains, or range validators. Required.
    
    max : float
        Upper bound used by sliders, domains, or range validators. Required.
    
    step : float
        Increment or resolution used for stepping through numeric values. Required.
    
    Returns
    -------
    AnimationDomain
        New ``AnimationDomain`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``AnimationDomain`` lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.animation import AnimationDomain
        obj = AnimationDomain(...)
    
    Discovery-oriented use::
    
        help(AnimationDomain)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(AnimationDomain)`` and ``dir(AnimationDomain)`` to inspect adjacent members.
    """

    min: float
    max: float
    step: float

    @property
    def span(self) -> float:
        """Return the non-negative numeric span of the domain.
        
        Full API
        --------
        ``obj.span -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationDomain``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationDomain(...)
            current = obj.span
        
        Discovery-oriented use::
        
            help(AnimationDomain)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationDomain)`` and ``dir(AnimationDomain)`` to inspect adjacent members.
        """
        return max(0.0, self.max - self.min)


def _validate_mode(mode: str) -> AnimationMode:
    if mode not in _VALID_ANIMATION_MODES:
        raise ValueError(
            f"animation_mode must be one of {_VALID_ANIMATION_MODES}, got {mode!r}."
        )
    return mode  # type: ignore[return-value]


def _coerce_domain(target: AnimationTarget) -> AnimationDomain:
    min_value = float(target.min)
    max_value = float(target.max)
    if max_value < min_value:
        min_value, max_value = max_value, min_value

    step_value = abs(float(target.step))
    if not math.isfinite(step_value) or step_value <= _EPS:
        step_value = max_value - min_value
        if step_value <= _EPS:
            step_value = 1.0

    return AnimationDomain(min=min_value, max=max_value, step=step_value)


def _is_close(a: float, b: float, *, step: float | None = None) -> bool:
    abs_tol = _EPS
    if step is not None and math.isfinite(step):
        abs_tol = max(abs_tol, abs(step) * 1e-12)
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=abs_tol)


def _admissible_candidates(value: float, domain: AnimationDomain) -> tuple[float, ...]:
    """Return nearby admissible values for quantization.

    The admissible set follows the slider grid ``min + n * step`` and always
    includes the exact range endpoints. Including ``max`` makes terminal modes
    such as ``">"`` reach the configured end cleanly even when ``step`` does
    not divide the range exactly.
    """
    lo = domain.min
    hi = domain.max
    step = domain.step

    if hi - lo <= _EPS:
        return (lo,)

    if not math.isfinite(value):
        value = lo

    offset = (value - lo) / step
    lower = math.floor(offset)
    upper = math.ceil(offset)

    candidates = {lo, hi}
    for index in (lower - 1, lower, upper, upper + 1):
        candidate = lo + float(index) * step
        if lo - _EPS <= candidate <= hi + _EPS:
            candidates.add(min(max(candidate, lo), hi))

    return tuple(sorted(candidates))


def quantize_to_admissible(
    value: float,
    domain: AnimationDomain,
    *,
    direction: float = 0.0,
) -> float:
    """Return the closest slider-compatible value for ``value``.
    
    Full API
    --------
    ``quantize_to_admissible(value: float, domain: AnimationDomain, *, direction: float=0.0) -> float``
    
    Parameters
    ----------
    value : float
        New or current value for the relevant property, control, or calculation. Required.
    
    domain : AnimationDomain
        Numeric domain or span that bounds an animation or sweep. Required.
    
    direction : float, optional
        Value for ``direction`` in this API. Defaults to ``0.0``.
    
    Returns
    -------
    float
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``direction=0.0``: Value for ``direction`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.animation import quantize_to_admissible
        result = quantize_to_admissible(...)
    
    Discovery-oriented use::
    
        help(quantize_to_admissible)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(quantize_to_admissible)`` and inspect sibling APIs in the same module.
    """
    candidates = _admissible_candidates(value, domain)
    if len(candidates) == 1:
        return candidates[0]

    best_distance = min(abs(candidate - value) for candidate in candidates)
    nearest = [
        candidate
        for candidate in candidates
        if _is_close(abs(candidate - value), best_distance)
    ]
    if len(nearest) == 1:
        return nearest[0]
    if direction > 0:
        return max(nearest)
    if direction < 0:
        return min(nearest)
    return min(nearest, key=lambda candidate: (abs(candidate - value), candidate))


class AnimationClock:
    """Shared cadence source for active parameter animations.
    
    Full API
    --------
    ``AnimationClock(frequency_hz: float=DEFAULT_ANIMATION_HZ, time_source: Callable[[], float]=time.monotonic)``
    
    Public members exposed from this class: ``frequency_hz``, ``subscribe``, ``unsubscribe``, ``performance_snapshot``
    
    Parameters
    ----------
    frequency_hz : float, optional
        Tick frequency in hertz. Defaults to ``DEFAULT_ANIMATION_HZ``.
    
    time_source : Callable[[], float], optional
        Value for ``time_source`` in this API. Defaults to ``time.monotonic``.
    
    Returns
    -------
    AnimationClock
        New ``AnimationClock`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``frequency_hz=DEFAULT_ANIMATION_HZ``: Tick frequency in hertz.
    - ``time_source=time.monotonic``: Value for ``time_source`` in this API.
    
    Architecture note
    -----------------
    ``AnimationClock`` lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.animation import AnimationClock
        obj = AnimationClock(...)
    
    Discovery-oriented use::
    
        help(AnimationClock)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(AnimationClock)`` and ``dir(AnimationClock)`` to inspect adjacent members.
    """

    def __init__(
        self,
        *,
        frequency_hz: float = DEFAULT_ANIMATION_HZ,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        self._frequency_hz = float(frequency_hz)
        self._interval_s = 1.0 / self._frequency_hz
        self._time_source = time_source
        self._lock = threading.Lock()
        self._timer: object | None = None
        self._ticking = False
        self._next_tick_deadline: float | None = None
        self._subscribers: set[Callable[[float], None]] = set()
        self._last_timer_backend = "uninitialized"
        self._last_tick_time: float | None = None
        self._performance = PerformanceMonitor("AnimationClock")
        self._performance.set_state(
            frequency_hz=self._frequency_hz,
            interval_ms=self._interval_s * 1000.0,
            timer_backend=self._last_timer_backend,
            ticking=False,
        )

    @property
    def frequency_hz(self) -> float:
        """Configured clock frequency.
        
        Full API
        --------
        ``obj.frequency_hz -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationClock``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationClock(...)
            current = obj.frequency_hz
        
        Discovery-oriented use::
        
            help(AnimationClock)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationClock)`` and ``dir(AnimationClock)`` to inspect adjacent members.
        """
        return self._frequency_hz

    def subscribe(self, callback: Callable[[float], None]) -> None:
        """Register a callback and start the cadence if needed.
        
        Full API
        --------
        ``obj.subscribe(callback: Callable[[float], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[float], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationClock``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationClock(...)
            obj.subscribe(...)
        
        Discovery-oriented use::
        
            help(AnimationClock)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationClock)`` and ``dir(AnimationClock)`` to inspect adjacent members.
        """
        with self._lock:
            previous_count = len(self._subscribers)
            self._subscribers.add(callback)
            if len(self._subscribers) > previous_count:
                self._performance.increment("subscriptions")
            self._performance.set_state(subscriber_count=len(self._subscribers), ticking=self._ticking)
            if self._timer is None and not self._ticking and self._subscribers:
                now = float(self._time_source())
                if self._next_tick_deadline is None:
                    self._next_tick_deadline = now + self._interval_s
                self._schedule_next_locked(now=now)

    def unsubscribe(self, callback: Callable[[float], None]) -> None:
        """Remove a callback from the active cadence.
        
        Full API
        --------
        ``obj.unsubscribe(callback: Callable[[float], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[float], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationClock``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationClock(...)
            obj.unsubscribe(...)
        
        Discovery-oriented use::
        
            help(AnimationClock)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationClock)`` and ``dir(AnimationClock)`` to inspect adjacent members.
        """
        with self._lock:
            previous_count = len(self._subscribers)
            self._subscribers.discard(callback)
            if len(self._subscribers) < previous_count:
                self._performance.increment("unsubscriptions")
            if not self._subscribers:
                handle = self._timer
                self._timer = None
                self._next_tick_deadline = None
                if handle is not None:
                    cancel = getattr(handle, "cancel", None)
                    if callable(cancel):
                        try:
                            cancel()
                        except Exception:
                            logging.getLogger(__name__).debug(
                                "Animation clock timer cancel failed",
                                exc_info=True,
                            )
                        else:
                            self._performance.increment("cancelled_timers")
            self._performance.set_state(subscriber_count=len(self._subscribers), ticking=self._ticking)

    def performance_snapshot(self, *, recent_event_limit: int = 25) -> dict[str, Any]:
        """Work with performance snapshot on ``AnimationClock``.
        
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
        This member belongs to ``AnimationClock``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationClock(...)
            result = obj.performance_snapshot(...)
        
        Discovery-oriented use::
        
            help(AnimationClock)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationClock)`` and ``dir(AnimationClock)`` to inspect adjacent members.
        """

        return self._performance.snapshot(recent_limit=recent_event_limit)

    def _schedule_next_locked(self, *, now: float | None = None) -> None:
        if self._timer is not None or self._ticking or not self._subscribers:
            return
        current_now = float(self._time_source()) if now is None else float(now)
        if self._next_tick_deadline is None:
            self._next_tick_deadline = current_now + self._interval_s
        delay_s = max(0.0, float(self._next_tick_deadline) - current_now)
        if delay_s <= 1.0e-9:
            self._performance.increment("zero_delay_schedules")
        scheduled = schedule_later(
            delay_s,
            self._on_tick,
            owner="AnimationClock",
            thread_timer_factory=threading.Timer,
        )
        self._timer = scheduled.handle
        self._last_timer_backend = scheduled.backend
        self._performance.increment("scheduled_ticks")
        self._performance.set_state(
            timer_backend=self._last_timer_backend,
            subscriber_count=len(self._subscribers),
            next_delay_ms=delay_s * 1000.0,
            ticking=self._ticking,
        )
        self._performance.record_duration(
            "scheduled_delay_ms",
            delay_s * 1000.0,
            subscriber_count=len(self._subscribers),
            timer_backend=self._last_timer_backend,
        )

    def _on_tick(self) -> None:
        with self._lock:
            self._timer = None
            subscribers = tuple(self._subscribers)
            expected_deadline = self._next_tick_deadline
            if not subscribers:
                self._next_tick_deadline = None
                self._performance.increment("empty_ticks")
                self._performance.set_state(subscriber_count=0, ticking=False)
                return
            self._ticking = True
            self._performance.set_state(subscriber_count=len(subscribers), ticking=True)

        now = self._time_source()
        if expected_deadline is not None:
            lateness_ms = max(0.0, (float(now) - float(expected_deadline)) * 1000.0)
            if lateness_ms > 0.0:
                self._performance.increment("overdue_ticks")
            self._performance.record_duration(
                "tick_lateness_ms",
                lateness_ms,
                subscriber_count=len(subscribers),
                timer_backend=self._last_timer_backend,
            )
        if self._last_tick_time is not None:
            self._performance.record_duration(
                "tick_spacing_ms",
                (float(now) - float(self._last_tick_time)) * 1000.0,
                subscriber_count=len(subscribers),
            )
        self._last_tick_time = float(now)

        tick_started = time.perf_counter()
        failures = 0
        for callback in subscribers:
            callback_started = time.perf_counter()
            try:
                callback(now)
            except Exception:  # pragma: no cover - defensive callback boundary
                failures += 1
                self._performance.increment("callback_failures")
                logging.getLogger(__name__).exception("Animation clock callback failed")
            finally:
                self._performance.record_duration(
                    "callback_duration_ms",
                    (time.perf_counter() - callback_started) * 1000.0,
                    subscriber_count=len(subscribers),
                )

        self._performance.increment("ticks")
        self._performance.record_duration(
            "tick_duration_ms",
            (time.perf_counter() - tick_started) * 1000.0,
            subscriber_count=len(subscribers),
            failure_count=failures,
        )

        reschedule_now = float(self._time_source())
        missed_intervals = 0
        with self._lock:
            self._ticking = False
            if self._subscribers and self._timer is None:
                if self._next_tick_deadline is None:
                    self._next_tick_deadline = reschedule_now + self._interval_s
                else:
                    next_deadline = float(self._next_tick_deadline) + self._interval_s
                    while next_deadline <= reschedule_now:
                        next_deadline += self._interval_s
                        missed_intervals += 1
                    self._next_tick_deadline = next_deadline
                self._schedule_next_locked(now=reschedule_now)
            else:
                self._next_tick_deadline = None
            self._performance.set_state(
                subscriber_count=len(self._subscribers),
                ticking=False,
            )

        if missed_intervals:
            self._performance.increment("missed_intervals", delta=missed_intervals)


_DEFAULT_CLOCK: AnimationClock | None = None


def get_default_animation_clock() -> AnimationClock:
    """Return the process-wide default animation clock.
    
    Full API
    --------
    ``get_default_animation_clock() -> AnimationClock``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    AnimationClock
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.animation import get_default_animation_clock
        result = get_default_animation_clock(...)
    
    Discovery-oriented use::
    
        help(get_default_animation_clock)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(get_default_animation_clock)`` and inspect sibling APIs in the same module.
    """
    global _DEFAULT_CLOCK
    if _DEFAULT_CLOCK is None:
        _DEFAULT_CLOCK = AnimationClock()
    return _DEFAULT_CLOCK


class AnimationController:
    """Widget-bound animation controller for a single parameter.
    
    Full API
    --------
    ``AnimationController(target: AnimationTarget, clock: AnimationClockLike | None=None, time_source: Callable[[], float]=time.monotonic, animation_time: float=DEFAULT_ANIMATION_TIME, animation_mode: AnimationMode='>>', state_change_callback: Callable[[bool], None] | None=None)``
    
    Public members exposed from this class: ``animation_time``, ``animation_mode``, ``running``, ``start``, ``stop``, ``toggle``,
        ``handle_value_change``, ``handle_domain_change``
    
    Parameters
    ----------
    target : AnimationTarget
        Value for ``target`` in this API. Required.
    
    clock : AnimationClockLike | None, optional
        Animation clock used to schedule ticks. Defaults to ``None``.
    
    time_source : Callable[[], float], optional
        Value for ``time_source`` in this API. Defaults to ``time.monotonic``.
    
    animation_time : float, optional
        Animation duration or time scale associated with a control. Defaults to ``DEFAULT_ANIMATION_TIME``.
    
    animation_mode : AnimationMode, optional
        Animation strategy used when a control is animated. Defaults to ``'>>'``.
    
    state_change_callback : Callable[[bool], None] | None, optional
        Value for ``state_change_callback`` in this API. Defaults to ``None``.
    
    Returns
    -------
    AnimationController
        New ``AnimationController`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``clock=None``: Animation clock used to schedule ticks.
    - ``time_source=time.monotonic``: Value for ``time_source`` in this API.
    - ``animation_time=DEFAULT_ANIMATION_TIME``: Animation duration or time scale associated with a control.
    - ``animation_mode='>>'``: Animation strategy used when a control is animated.
    - ``state_change_callback=None``: Value for ``state_change_callback`` in this API.
    
    Architecture note
    -----------------
    ``AnimationController`` lives in ``gu_toolkit.animation``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.animation import AnimationController
        obj = AnimationController(...)
    
    Discovery-oriented use::
    
        help(AnimationController)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
    """

    def __init__(
        self,
        target: AnimationTarget,
        *,
        clock: AnimationClockLike | None = None,
        time_source: Callable[[], float] = time.monotonic,
        animation_time: float = DEFAULT_ANIMATION_TIME,
        animation_mode: AnimationMode = ">>",
        state_change_callback: Callable[[bool], None] | None = None,
    ) -> None:
        self._target = target
        self._clock = clock if clock is not None else get_default_animation_clock()
        self._time_source = time_source
        self._state_change_callback = state_change_callback

        self._animation_time = DEFAULT_ANIMATION_TIME
        self._animation_mode: AnimationMode = ">>"
        self._running = False
        self._internal_value = float(target.value)
        self._direction = 1.0
        self._last_tick: float | None = None
        self._applying_animation = False

        self.animation_time = animation_time
        self.animation_mode = animation_mode

    @property
    def animation_time(self) -> float:
        """Seconds needed to traverse the current numeric range once.
        
        Full API
        --------
        ``obj.animation_time -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            current = obj.animation_time
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        return self._animation_time

    @animation_time.setter
    def animation_time(self, seconds: float) -> None:
        """Work with animation time on ``AnimationController``.
        
        Full API
        --------
        ``obj.animation_time = seconds``
        
        Parameters
        ----------
        seconds : float
            Value for ``seconds`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.animation_time = seconds
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """

        seconds_value = float(seconds)
        if not math.isfinite(seconds_value) or seconds_value <= 0:
            raise ValueError("animation_time must be a finite number > 0")
        self._animation_time = seconds_value

    @property
    def animation_mode(self) -> AnimationMode:
        """Current animation mode token.
        
        Full API
        --------
        ``obj.animation_mode -> AnimationMode``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        AnimationMode
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            current = obj.animation_mode
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        return self._animation_mode

    @animation_mode.setter
    def animation_mode(self, mode: str) -> None:
        """Work with animation mode on ``AnimationController``.
        
        Full API
        --------
        ``obj.animation_mode = mode``
        
        Parameters
        ----------
        mode : str
            Mode or strategy name controlling behavior. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.animation_mode = mode
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """

        validated = _validate_mode(mode)
        self._animation_mode = validated
        if validated in (">", ">>"):
            self._direction = 1.0

    @property
    def running(self) -> bool:
        """Whether the controller is currently subscribed to the clock.
        
        Full API
        --------
        ``obj.running -> bool``
        
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
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            current = obj.running
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        return self._running

    def start(self) -> None:
        """Start animating from the current internal value.
        
        Full API
        --------
        ``obj.start() -> None``
        
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
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.start(...)
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        if self._running:
            return
        self._internal_value = float(self._target.value)
        if self._animation_mode in (">", ">>"):
            self._direction = 1.0
        elif _is_close(self._internal_value, float(self._target.max)):
            self._direction = -1.0
        elif _is_close(self._internal_value, float(self._target.min)):
            self._direction = 1.0

        self._apply_discrete_value(quantize_to_admissible(
            self._internal_value,
            _coerce_domain(self._target),
            direction=self._direction,
        ))
        self._last_tick = self._time_source()
        self._running = True
        self._clock.subscribe(self._on_clock_tick)
        self._emit_state_change()

    def stop(self) -> None:
        """Stop animating and unsubscribe from the clock.
        
        Full API
        --------
        ``obj.stop() -> None``
        
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
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.stop(...)
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        if not self._running:
            return
        self._clock.unsubscribe(self._on_clock_tick)
        self._running = False
        self._last_tick = None
        self._emit_state_change()

    def toggle(self) -> None:
        """Toggle between running and paused states.
        
        Full API
        --------
        ``obj.toggle() -> None``
        
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
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.toggle(...)
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        if self._running:
            self.stop()
            return
        self.start()

    def handle_value_change(self, new_value: float) -> None:
        """Sync the internal animation state from an external value edit.
        
        Full API
        --------
        ``obj.handle_value_change(new_value: float) -> None``
        
        Parameters
        ----------
        new_value : float
            Value for ``new_value`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.handle_value_change(...)
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        if self._applying_animation:
            return
        self._internal_value = float(new_value)

    def handle_domain_change(self) -> None:
        """Adapt the animation to a changed slider range or step.
        
        Full API
        --------
        ``obj.handle_domain_change() -> None``
        
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
        This member belongs to ``AnimationController``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = AnimationController(...)
            obj.handle_domain_change(...)
        
        Discovery-oriented use::
        
            help(AnimationController)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(AnimationController)`` and ``dir(AnimationController)`` to inspect adjacent members.
        """
        domain = _coerce_domain(self._target)
        if self._internal_value < domain.min or self._internal_value > domain.max:
            self._internal_value = quantize_to_admissible(
                self._internal_value,
                domain,
                direction=self._direction,
            )
        discrete = quantize_to_admissible(
            self._internal_value,
            domain,
            direction=self._direction,
        )
        self._apply_discrete_value(discrete)

    def _emit_state_change(self) -> None:
        callback = self._state_change_callback
        if callback is None:
            return
        callback(self._running)

    def _on_clock_tick(self, now: float) -> None:
        if not self._running:
            return
        if self._last_tick is None:
            self._last_tick = now
            return

        elapsed_s = max(0.0, float(now) - float(self._last_tick))
        self._last_tick = float(now)
        self._advance_by(elapsed_s)

    def _advance_by(self, elapsed_s: float) -> None:
        if elapsed_s <= 0:
            return

        domain = _coerce_domain(self._target)
        span = domain.span
        if span <= _EPS:
            self._apply_discrete_value(domain.min)
            return

        distance = (span / self._animation_time) * elapsed_s
        new_internal = self._internal_value
        reached_terminal = False

        if self._animation_mode == ">>":
            offset = (self._internal_value - domain.min + distance) % span
            new_internal = domain.min + offset
            self._direction = 1.0
        elif self._animation_mode == ">":
            new_internal = min(domain.max, self._internal_value + distance)
            self._direction = 1.0
            reached_terminal = _is_close(new_internal, domain.max)
        else:
            phase = self._bounce_phase(domain)
            cycle = 2.0 * span
            phase = (phase + distance) % cycle
            if _is_close(phase, span):
                new_internal = domain.max
                self._direction = -1.0
            elif phase < span:
                new_internal = domain.min + phase
                self._direction = 1.0
            else:
                new_internal = domain.max - (phase - span)
                self._direction = -1.0

        self._internal_value = new_internal
        discrete = quantize_to_admissible(
            self._internal_value,
            domain,
            direction=self._direction,
        )
        self._apply_discrete_value(discrete)

        if reached_terminal:
            self.stop()

    def _bounce_phase(self, domain: AnimationDomain) -> float:
        span = domain.span
        if self._direction >= 0:
            return max(0.0, min(span, self._internal_value - domain.min))
        return span + max(0.0, min(span, domain.max - self._internal_value))

    def _apply_discrete_value(self, value: float) -> None:
        current = float(self._target.value)
        step = float(self._target.step)
        if _is_close(current, value, step=step):
            return

        self._applying_animation = True
        try:
            self._target.value = float(value)
        finally:
            self._applying_animation = False
