"""jlab_function_audio.player
===============================

JupyterLab widget and transport engine for callable-driven background audio.

Architecture
------------
This module is the integration point for the whole package.  It combines three
subsystems:

1. **Python transport engine**
   - owns the unwrapped playback position,
   - renders only short chunks ahead of the current position,
   - runs continuously in a background thread while playback is active.

2. **Phase-matched live updates**
   - `set_function(...)` installs a replacement callable at any time,
   - the replacement is aligned with :func:`jlab_function_audio.matching.phase_match_functions`,
   - the first replacement chunk is crossfaded to deterministically suppress
     boundary clicks.

3. **Browser playback in JupyterLab**
   - the class inherits from :class:`anywidget.AnyWidget`,
   - the front end receives binary float32 chunks via custom widget messages,
   - a Web Audio `AudioContext` schedules each chunk and applies attack/release
     ramps with a master gain node.

Functionality
-------------
`FunctionAudioPlayer` is the public class that satisfies the requested API:

- set the callable after construction with :meth:`set_function`,
- render a periodic 100-second signal without sampling past 100 seconds,
- control transport with :meth:`play`, :meth:`stop`, :meth:`restart`, and
  :meth:`seek`,
- update the callable while audio is already running,
- keep only a small amount of audio buffered ahead of playback.

Main implementation notes
-------------------------
The player keeps **unwrapped** time internally so buffering logic stays simple.
Only the final sample lookup wraps into the requested 100-second period.

Most browsers still require one ordinary user gesture before notebook audio may start.
The browser helper therefore attaches itself invisibly and opportunistically
unlocks audio from the next notebook click, key press, or slider drag. The
Python transport methods can still be called immediately; the player simply
reports a "waiting-for-browser-gesture" state until the browser unlocks
audio.

Examples
--------
Minimal notebook usage:

>>> import math
>>> player = FunctionAudioPlayer()
>>> _ = player.set_function(lambda t: 0.3 * math.sin(2 * math.pi * 220.0 * t))
>>> isinstance(player.configuration.period_duration, float)
True
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import anywidget
import numpy as np
import traitlets
from IPython.display import display

from .config import PlayerConfiguration
from .matching import PhaseMatchResult, phase_match_functions
from .normalization import (
    AutoNormalizationDiagnostics,
    AutoNormalizationState,
    apply_autonormalization,
)
from .sampling import (
    SignalCallable,
    crossfade_chunks,
    crossfade_chunks_raw,
    generate_chunk,
    generate_raw_chunk,
)


def _silence(_time_seconds: float) -> float:
    """Return silence.

    Parameters
    ----------
    _time_seconds:
        Unused sample time in seconds. The leading underscore makes it explicit
        that the value is ignored.

    Returns
    -------
    float
        Always returns ``0.0``.

    Examples
    --------
    >>> _silence(12.5)
    0.0
    """
    return 0.0


def _normalize_function_name(function: SignalCallable, explicit_name: str | None) -> str:
    """Choose a display name for a user-supplied callable.

    Parameters
    ----------
    function:
        Callable provided by the user.
    explicit_name:
        Optional explicit display name passed to :meth:`set_function`.

    Returns
    -------
    str
        Human-readable function name suitable for notebook status text.

    Examples
    --------
    >>> def my_signal(t):
    ...     return 0.0
    >>> _normalize_function_name(my_signal, None)
    'my_signal'
    >>> _normalize_function_name(my_signal, "custom name")
    'custom name'
    """
    if explicit_name:
        return str(explicit_name)
    inferred_name = getattr(function, "__name__", "") or ""
    if inferred_name and inferred_name != "<lambda>":
        return inferred_name
    if inferred_name == "<lambda>":
        return "lambda"
    return function.__class__.__name__


@dataclass(slots=True)
class _SignalState:
    """Internal description of one callable and its phase offset.

    Parameters
    ----------
    function:
        User-provided numeric callable.
    phase_offset:
        Phase offset, in seconds, applied before periodic sampling.
    name:
        Human-readable display name.

    Returns
    -------
    _SignalState
        Internal state object used by the transport thread.

    Examples
    --------
    >>> state = _SignalState(function=_silence, phase_offset=0.0, name="silence")
    >>> state.name
    'silence'
    """

    function: SignalCallable
    phase_offset: float
    name: str


@dataclass(slots=True)
class _PendingTransition:
    """Internal description of an upcoming live function replacement.

    Parameters
    ----------
    signal:
        Replacement callable together with the phase offset chosen for it.
    transition_unwrapped:
        Absolute transport time, in seconds, at which the replacement should
        become active.
    phase_result:
        Diagnostic information returned by the phase matcher.

    Returns
    -------
    _PendingTransition
        Internal object consumed by the next chunk render.

    Examples
    --------
    >>> transition = _PendingTransition(
    ...     signal=_SignalState(function=_silence, phase_offset=0.0, name="silence"),
    ...     transition_unwrapped=0.0,
    ...     phase_result=PhaseMatchResult.no_match(anchor_transport_time=0.0, notes="test"),
    ... )
    >>> transition.transition_unwrapped
    0.0
    """

    signal: _SignalState
    transition_unwrapped: float
    phase_result: PhaseMatchResult


class FunctionAudioPlayer(anywidget.AnyWidget):
    """Buffered callable-audio player for JupyterLab.

    Parameters
    ----------
    configuration:
        Optional validated configuration object. When omitted, the remaining
        keyword arguments are used to build one.
    function:
        Optional initial callable. The intended workflow is to install the
        callable later with :meth:`set_function`, but the constructor accepts an
        initial callable for convenience.
    function_name:
        Optional display name for `function`.
    auto_display:
        When ``True``, immediately display the widget after construction.
    sample_rate:
        Sample rate in hertz used when `configuration` is omitted.
    chunk_duration:
        Chunk size in seconds used when `configuration` is omitted.
    lookahead_duration:
        Browser queue lookahead in seconds used when `configuration` is omitted.
    attack_duration:
        Fade-in duration in seconds used when `configuration` is omitted.
    release_duration:
        Fade-out duration in seconds used when `configuration` is omitted.
    crossfade_duration:
        Function-swap crossfade duration in seconds used when `configuration` is
        omitted.
    period_duration:
        Fixed loop period in seconds. The request requires 100 seconds.
    gain:
        Master output gain used when `configuration` is omitted.
    pump_interval:
        Background pump sleep interval in seconds used when `configuration` is
        omitted.
    phase_search_candidates:
        Number of coarse phase-search candidates used when `configuration` is
        omitted.
    phase_top_candidates:
        Number of refined phase-search candidates used when `configuration` is
        omitted.
    phase_shape_window:
        Forward comparison window in seconds used when `configuration` is
        omitted.
    phase_shape_samples:
        Number of forward-window samples used when `configuration` is omitted.

    Returns
    -------
    FunctionAudioPlayer
        Displayable widget object that can render background audio in a
        JupyterLab notebook.

    Notes
    -----
    Most browsers still require one ordinary user gesture before audio may
    start. The helper remains invisible and listens for the next notebook
    interaction instead of exposing a dedicated button.

    Examples
    --------
    Basic use in a notebook:

    >>> import math
    >>> player = FunctionAudioPlayer()
    >>> result = player.set_function(
    ...     lambda t: 0.3 * math.sin(2 * math.pi * 220.0 * t),
    ...     function_name="220 Hz sine",
    ... )
    >>> isinstance(result, PhaseMatchResult)
    True
    """

    _esm = Path(__file__).with_name("_frontend.js")
    _css = Path(__file__).with_name("_frontend.css")

    sample_rate = traitlets.Int(48000).tag(sync=True)
    chunk_duration = traitlets.Float(0.025).tag(sync=True)
    lookahead_duration = traitlets.Float(0.075).tag(sync=True)
    attack_duration = traitlets.Float(0.01).tag(sync=True)
    release_duration = traitlets.Float(0.02).tag(sync=True)
    crossfade_duration = traitlets.Float(0.012).tag(sync=True)
    period_duration = traitlets.Float(100.0).tag(sync=True)
    gain = traitlets.Float(0.18).tag(sync=True)
    auto_normalize = traitlets.Bool(False).tag(sync=True)
    normalization_dc_time_constant = traitlets.Float(0.05).tag(sync=True)
    normalization_attack_lookahead_duration = traitlets.Float(0.025).tag(sync=True)
    normalization_release_time_constant = traitlets.Float(0.35).tag(sync=True)

    position_seconds = traitlets.Float(0.0).tag(sync=True)
    buffered_seconds = traitlets.Float(0.0).tag(sync=True)
    playback_state = traitlets.Unicode("stopped").tag(sync=True)
    frontend_state = traitlets.Unicode("not-displayed").tag(sync=True)
    current_function_name = traitlets.Unicode("silence").tag(sync=True)
    last_phase_summary = traitlets.Unicode("No phase match has run yet.").tag(sync=True)
    last_error = traitlets.Unicode("").tag(sync=True)
    frontend_ready = traitlets.Bool(False).tag(sync=True)
    audio_enabled = traitlets.Bool(False).tag(sync=True)

    def __init__(
        self,
        *,
        configuration: PlayerConfiguration | None = None,
        function: SignalCallable | None = None,
        function_name: str | None = None,
        auto_display: bool = True,
        sample_rate: int = 48000,
        chunk_duration: float = 0.025,
        lookahead_duration: float = 0.075,
        attack_duration: float = 0.01,
        release_duration: float = 0.02,
        crossfade_duration: float = 0.012,
        period_duration: float = 100.0,
        gain: float = 0.18,
        auto_normalize: bool = False,
        normalization_dc_time_constant: float = 0.05,
        normalization_attack_lookahead_duration: float = 0.025,
        normalization_release_time_constant: float = 0.35,
        pump_interval: float = 0.01,
        phase_search_candidates: int = 2048,
        phase_top_candidates: int = 12,
        phase_shape_window: float = 0.03,
        phase_shape_samples: int = 32,
    ) -> None:
        """Initialize the player and its background transport thread.

        Parameters
        ----------
        configuration:
            Optional validated configuration object.
        function:
            Optional initial callable to install immediately.
        function_name:
            Optional display name for `function`.
        auto_display:
            Whether to attach the hidden browser helper immediately after
            construction. The default keeps notebook control fully Python-driven
            without requiring an explicit `display(...)` call.
        sample_rate, chunk_duration, lookahead_duration, attack_duration, \
release_duration, crossfade_duration, period_duration, gain, pump_interval, \
phase_search_candidates, phase_top_candidates, phase_shape_window, \
phase_shape_samples:
            Convenience keyword arguments used only when `configuration` is
            omitted. Their meanings are identical to the corresponding fields on
            :class:`PlayerConfiguration`.

        Returns
        -------
        None
            The constructor initializes the widget, starts the background thread,
            and optionally installs an initial callable.

        Examples
        --------
        >>> player = FunctionAudioPlayer(sample_rate=48000, lookahead_duration=0.06)
        >>> player.configuration.sample_rate
        48000
        """
        self._configuration = configuration or PlayerConfiguration(
            sample_rate=sample_rate,
            chunk_duration=chunk_duration,
            lookahead_duration=lookahead_duration,
            attack_duration=attack_duration,
            release_duration=release_duration,
            crossfade_duration=crossfade_duration,
            period_duration=period_duration,
            gain=gain,
            auto_normalize=auto_normalize,
            normalization_dc_time_constant=normalization_dc_time_constant,
            normalization_attack_lookahead_duration=normalization_attack_lookahead_duration,
            normalization_release_time_constant=normalization_release_time_constant,
            pump_interval=pump_interval,
            phase_search_candidates=phase_search_candidates,
            phase_top_candidates=phase_top_candidates,
            phase_shape_window=phase_shape_window,
            phase_shape_samples=phase_shape_samples,
        )

        super().__init__(
            sample_rate=self._configuration.sample_rate,
            chunk_duration=self._configuration.actual_chunk_duration,
            lookahead_duration=self._configuration.lookahead_duration,
            attack_duration=self._configuration.attack_duration,
            release_duration=self._configuration.release_duration,
            crossfade_duration=self._configuration.crossfade_duration,
            period_duration=self._configuration.period_duration,
            gain=self._configuration.gain,
            auto_normalize=self._configuration.auto_normalize,
            normalization_dc_time_constant=self._configuration.normalization_dc_time_constant,
            normalization_attack_lookahead_duration=self._configuration.normalization_attack_lookahead_duration,
            normalization_release_time_constant=self._configuration.normalization_release_time_constant,
            position_seconds=0.0,
            buffered_seconds=0.0,
            playback_state="stopped",
            frontend_state="not-displayed",
            current_function_name="silence",
            last_phase_summary="No phase match has run yet.",
            last_error="",
            frontend_ready=False,
            audio_enabled=False,
        )

        import threading
        import time as _time

        self._threading = threading
        self._time = _time
        self._state_lock = threading.RLock()
        self._wake_event = threading.Event()
        self._shutdown_event = threading.Event()

        self._frontend_ready_flag = False
        self._audio_enabled_flag = False
        self._closed_flag = False
        self._auto_display_has_run = False

        self._is_playing = False
        self._position_unwrapped = 0.0
        self._play_anchor_unwrapped = 0.0
        self._play_started_monotonic = 0.0
        self._generated_until_unwrapped = 0.0

        self._chunk_counter = 0
        self._user_function_installed = False

        self._active_signal = _SignalState(function=_silence, phase_offset=0.0, name="silence")
        self._pending_transition: _PendingTransition | None = None
        self._last_phase_match_result: PhaseMatchResult | None = None
        self._auto_normalization_state = AutoNormalizationState()
        self._auto_normalization_hard_reset_pending = True
        self._last_auto_normalization_diagnostics: AutoNormalizationDiagnostics | None = None

        self.on_msg(self._handle_frontend_message)

        self._pump_thread = threading.Thread(
            target=self._pump_loop,
            name="jlab-function-audio-pump",
            daemon=True,
        )
        self._pump_thread.start()

        if function is not None:
            self.set_function(function, function_name=function_name)

        if auto_display:
            self.show()

    @property
    def configuration(self) -> PlayerConfiguration:
        """Return the immutable validated configuration used by the player.

        Parameters
        ----------
        None

        Returns
        -------
        PlayerConfiguration
            Validated configuration shared by the transport engine and the phase
            matcher.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.configuration.period_duration
        100.0
        """
        return self._configuration

    @property
    def is_playing(self) -> bool:
        """Return whether the transport is currently in the playing state.

        Parameters
        ----------
        None

        Returns
        -------
        bool
            ``True`` when the player is actively pumping chunks, ``False``
            otherwise.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.is_playing
        False
        """
        with self._state_lock:
            return bool(self._is_playing)

    @property
    def position(self) -> float:
        """Return the current transport position modulo the loop period.

        Parameters
        ----------
        None

        Returns
        -------
        float
            Current position in seconds in the interval ``[0, period_duration)``.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.position
        0.0
        """
        with self._state_lock:
            position_unwrapped = self._current_position_unwrapped_locked()
            return float(position_unwrapped % self._configuration.period_duration)

    @property
    def last_phase_match_result(self) -> PhaseMatchResult | None:
        """Return the most recent phase-matching result.

        Parameters
        ----------
        None

        Returns
        -------
        PhaseMatchResult or None
            Most recent result returned by :meth:`set_function`, or ``None``
            before any callable has been installed.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.last_phase_match_result is None
        True
        """
        with self._state_lock:
            return self._last_phase_match_result

    def _ensure_not_closed(self) -> None:
        """Raise if the widget has already been closed.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method raises a :class:`RuntimeError` when the player has been
            closed.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player._ensure_not_closed()
        """
        if self._closed_flag:
            raise RuntimeError("This FunctionAudioPlayer instance has already been closed.")

    def show(self) -> "FunctionAudioPlayer":
        """Attach the hidden browser helper in the current notebook output and return itself.

        Parameters
        ----------
        None

        Returns
        -------
        FunctionAudioPlayer
            The player itself so the method can be used fluently in notebooks.
            The rendered helper is intentionally invisible.

        Examples
        --------
        In a notebook:

        >>> player = FunctionAudioPlayer(auto_display=False)
        >>> shown = player.show()
        >>> shown is player
        True
        """
        display(self)
        self._auto_display_has_run = True
        return self

    def mark_embedded(self) -> "FunctionAudioPlayer":
        """Mark the widget as already attached by an external container.

        Full API
        --------
        ``obj.mark_embedded() -> FunctionAudioPlayer``

        Parameters
        ----------
        None

        Returns
        -------
        FunctionAudioPlayer
            The player itself so external widget containers can call the method
            fluently after attaching the hidden helper into an existing widget
            tree.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FunctionAudioPlayer``. The player usually
        displays itself lazily on the first :meth:`play` call. External widget
        containers may instead attach the helper themselves and then call this
        method so later :meth:`play` calls skip the automatic ``display(self)``
        path.

        Examples
        --------
        A container-managed embedding workflow::

            player = FunctionAudioPlayer(auto_display=False)
            container.children = tuple(container.children) + (player,)
            player.mark_embedded()

        Learn more / explore
        --------------------
        - README: see ``README.md`` beside this module.
        - Runtime implementation: this ``player.py`` module.
        - Frontend helper: ``_frontend.js`` beside this module.
        - In a notebook or REPL, run ``help(FunctionAudioPlayer.mark_embedded)``
          and inspect sibling transport methods on ``FunctionAudioPlayer``.
        """
        self._ensure_not_closed()
        self._auto_display_has_run = True
        return self

    def set_auto_normalize(self, enabled: bool) -> None:
        """Switch the player between clipped and bounded-autonormalized render modes.

        Full API
        --------
        ``obj.set_auto_normalize(enabled: bool) -> None``

        Parameters
        ----------
        enabled:
            Boolean flag that selects bounded streaming auto-normalization when
            ``True`` and clipped rendering when ``False``.

        Returns
        -------
        None
            The method updates the active render mode in place, preserves the
            current transport position and play intent, resets normalization
            state as needed, and flushes already-buffered audio rendered under
            the old mode.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FunctionAudioPlayer``. The player stores its
        immutable configuration object internally, so switching normalization
        mode requires replacing that configuration with an updated copy while
        leaving the browser helper instance and transport thread intact.

        Examples
        --------
        Toggle the existing player instance without recreating it::

            player = FunctionAudioPlayer(auto_display=False)
            player.set_auto_normalize(True)
            player.set_auto_normalize(False)

        Learn more / explore
        --------------------
        - README: see ``README.md`` beside this module.
        - Design note: ``autonormalization_design.md`` in the upstream archive.
        - Runtime implementation: this ``player.py`` module.
        - In a notebook or REPL, run ``help(FunctionAudioPlayer.set_auto_normalize)``
          and inspect sibling transport methods on ``FunctionAudioPlayer``.
        """
        self._ensure_not_closed()

        normalized_enabled = bool(enabled)

        with self._state_lock:
            if normalized_enabled == self._configuration.auto_normalize:
                self.auto_normalize = normalized_enabled
                self._update_status_locked()
                return

            current_unwrapped = self._current_position_unwrapped_locked()
            wrapped_position = float(current_unwrapped % self._configuration.period_duration)

            self.last_error = ""
            self._configuration = replace(self._configuration, auto_normalize=normalized_enabled)
            self.auto_normalize = normalized_enabled
            self._position_unwrapped = wrapped_position
            self._generated_until_unwrapped = wrapped_position
            self._pending_transition = None
            self._request_auto_normalization_hard_reset_locked()
            if self._is_playing:
                self._play_anchor_unwrapped = wrapped_position
                self._play_started_monotonic = self._time.monotonic()
            self._update_status_locked(wrapped_position)

        self._send_control_message("reset-queue", reason="set-auto-normalize")
        self._wake_event.set()

    def play(self) -> None:
        """Start buffered playback from the current transport position.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method updates the transport state and wakes the background pump.

        Notes
        -----
        The method ensures the hidden browser helper has been attached before
        playback begins. The helper does not render visible controls.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.play()
        >>> player.is_playing
        True
        """
        self._ensure_not_closed()

        if not self._auto_display_has_run:
            self.show()
            self._auto_display_has_run = True

        with self._state_lock:
            self.last_error = ""
            if self._is_playing:
                self._update_status_locked()
                return

            self._request_auto_normalization_hard_reset_locked()
            self._is_playing = True
            self._play_anchor_unwrapped = self._position_unwrapped
            self._play_started_monotonic = self._time.monotonic()
            self._generated_until_unwrapped = self._position_unwrapped
            self._pending_transition = None
            self._update_status_locked()

        self._send_control_message("reset-queue", reason="play")
        self._send_control_message("play")
        self._wake_event.set()

    def stop(self) -> None:
        """Stop playback with a short release ramp.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method stores the current transport position, stops background
            pumping, and requests a browser-side release ramp.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.play()
        >>> player.stop()
        >>> player.is_playing
        False
        """
        self._ensure_not_closed()

        with self._state_lock:
            current_unwrapped = self._current_position_unwrapped_locked()
            self._position_unwrapped = current_unwrapped
            self._generated_until_unwrapped = current_unwrapped
            self._pending_transition = None
            self._is_playing = False
            self._request_auto_normalization_hard_reset_locked()
            self._update_status_locked(current_unwrapped)

        self._send_control_message("stop")

    def restart(self) -> None:
        """Restart playback from transport time zero.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method seeks to zero and ensures playback is active afterward.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.restart()
        >>> player.is_playing
        True
        >>> player.position
        0.0
        """
        self.seek(0.0)
        self.play()

    def seek(self, position_seconds: float) -> None:
        """Move the transport to a new position.

        Parameters
        ----------
        position_seconds:
            Desired transport time in seconds. Values outside the 100-second
            period are wrapped with modular arithmetic.

        Returns
        -------
        None
            The method updates the internal transport state. If playback is
            active, the browser queue is flushed and refilled from the new
            position.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.seek(12.5)
        >>> round(player.position, 2)
        12.5

        Seeking past the loop wraps back into the fixed period:

        >>> player.seek(112.5)
        >>> round(player.position, 2)
        12.5
        """
        self._ensure_not_closed()

        normalized = float(position_seconds % self._configuration.period_duration)

        with self._state_lock:
            self.last_error = ""
            self._position_unwrapped = normalized
            self._generated_until_unwrapped = normalized
            self._pending_transition = None
            self._request_auto_normalization_hard_reset_locked()
            if self._is_playing:
                self._play_anchor_unwrapped = normalized
                self._play_started_monotonic = self._time.monotonic()
            self._update_status_locked(normalized)

        self._send_control_message("reset-queue", reason="seek")
        self._wake_event.set()

    def set_function(
        self,
        function: SignalCallable,
        *,
        function_name: str | None = None,
        phase_match: bool = True,
    ) -> PhaseMatchResult:
        """Install or replace the signal callable used for playback.

        Parameters
        ----------
        function:
            Numeric callable that accepts one time in seconds and returns one
            sample in ``[-1, 1]``.
        function_name:
            Optional human-readable display name shown by the widget.
        phase_match:
            When ``True`` and a previous user function exists, run the phase
            matcher so the replacement starts with a compatible phase offset.
            When ``False``, the incoming callable starts with zero phase offset.

        Returns
        -------
        PhaseMatchResult
            Result describing the phase-matching decision. The result still
            contains useful explanatory text when phase matching was skipped.

        Notes
        -----
        While playback is active, the change does not affect already-rendered
        audio.  It becomes audible after at most roughly the configured
        lookahead duration, which is intentionally small.

        Examples
        --------
        >>> import math
        >>> player = FunctionAudioPlayer()
        >>> result = player.set_function(
        ...     lambda t: 0.3 * math.sin(2 * math.pi * 220.0 * t),
        ...     function_name="220 Hz sine",
        ... )
        >>> isinstance(result, PhaseMatchResult)
        True
        >>> player.current_function_name
        '220 Hz sine'
        """
        self._ensure_not_closed()

        if not callable(function):
            raise TypeError("function must be callable.")

        name = _normalize_function_name(function, function_name)

        with self._state_lock:
            self.last_error = ""
            transition_unwrapped = (
                self._generated_until_unwrapped if self._is_playing else self._position_unwrapped
            )

            if not self._user_function_installed:
                result = PhaseMatchResult.no_match(
                    anchor_transport_time=transition_unwrapped,
                    notes="initial function installed",
                    phase_offset=0.0,
                )
                phase_offset = 0.0
            elif not phase_match:
                result = PhaseMatchResult.no_match(
                    anchor_transport_time=transition_unwrapped,
                    notes="phase matching disabled",
                    phase_offset=0.0,
                )
                phase_offset = 0.0
            else:
                result = phase_match_functions(
                    current_function=self._active_signal.function,
                    next_function=function,
                    current_phase_offset=self._active_signal.phase_offset,
                    anchor_transport_time=transition_unwrapped,
                    period=self._configuration.period_duration,
                    sample_rate=self._configuration.sample_rate,
                    coarse_candidates=self._configuration.phase_search_candidates,
                    top_candidates=self._configuration.phase_top_candidates,
                    shape_window=self._configuration.phase_shape_window,
                    shape_samples=self._configuration.phase_shape_samples,
                    comparison_mode=(
                        "centered_unit_peak"
                        if self._configuration.auto_normalize
                        else "clipped"
                    ),
                )
                phase_offset = result.phase_offset

            next_signal = _SignalState(function=function, phase_offset=phase_offset, name=name)

            if self._is_playing:
                self._pending_transition = _PendingTransition(
                    signal=next_signal,
                    transition_unwrapped=transition_unwrapped,
                    phase_result=result,
                )
            else:
                self._active_signal = next_signal
                self._pending_transition = None
                self._request_auto_normalization_hard_reset_locked()

            self._user_function_installed = True
            self._last_phase_match_result = result
            self.current_function_name = name
            self.last_phase_summary = result.summary()
            self._update_status_locked()

        self._wake_event.set()
        return result

    def snapshot_state(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of player state.

        Parameters
        ----------
        None

        Returns
        -------
        dict
            Dictionary containing transport, buffering, widget, and last phase
            matching information.

        Notes
        -----
        Browser-side widget startup is asynchronous. If this method is called in
        the same notebook cell that first displays the widget, fields such as
        ``frontend_ready`` may still be ``False`` even though the front end is
        working normally and will report ready moments later.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> snapshot = player.snapshot_state()
        >>> snapshot["playback_state"]
        'stopped'
        """
        with self._state_lock:
            phase_data = (
                asdict(self._last_phase_match_result)
                if self._last_phase_match_result is not None
                else None
            )
            diagnostics = self._last_auto_normalization_diagnostics
            return {
                "sample_rate": self.sample_rate,
                "period_duration": self.period_duration,
                "position_seconds": float(self.position_seconds),
                "buffered_seconds": float(self.buffered_seconds),
                "playback_state": self.playback_state,
                "frontend_state": self.frontend_state,
                "current_function_name": self.current_function_name,
                "last_phase_summary": self.last_phase_summary,
                "last_error": self.last_error,
                "frontend_ready": bool(self.frontend_ready),
                "audio_enabled": bool(self.audio_enabled),
                "is_playing": bool(self._is_playing),
                "auto_normalize": bool(self._configuration.auto_normalize),
                "current_normalization_factor": float(
                    self._auto_normalization_state.normalization_factor
                    if self._configuration.auto_normalize
                    else 1.0
                ),
                "current_dc_estimate": float(
                    self._auto_normalization_state.dc_estimate
                    if self._configuration.auto_normalize
                    else 0.0
                ),
                "normalization_state_initialized": bool(
                    self._auto_normalization_state.initialized
                    if self._configuration.auto_normalize
                    else False
                ),
                "last_normalization_output_peak": float(diagnostics.output_peak) if diagnostics else 0.0,
                "last_normalization_clip_hits": int(diagnostics.clip_hit_count) if diagnostics else 0,
                "last_phase_match_result": phase_data,
            }

    def close(self) -> None:
        """Stop the transport thread and close the widget comm.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method is idempotent and may be called multiple times safely.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player.close()
        >>> player.snapshot_state()["playback_state"] in {"stopped", "error"}
        True
        """
        if self._closed_flag:
            return

        self._closed_flag = True
        with self._state_lock:
            self._is_playing = False
            self._pending_transition = None
            self._shutdown_event.set()
            self._update_status_locked()

        self._send_control_message("stop")
        self._wake_event.set()

        if self._threading.current_thread() is not self._pump_thread:
            self._pump_thread.join(timeout=1.0)

        try:
            super().close()
        except Exception:
            # Widget shutdown is best-effort. The transport thread has already
            # been stopped, which is the most important cleanup action.
            pass

    def _current_position_unwrapped_locked(self) -> float:
        """Return the current unwrapped position while holding the state lock.

        Parameters
        ----------
        None

        Returns
        -------
        float
            Unwrapped transport time in seconds. The value may exceed the loop
            period while playback is active.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> round(player._current_position_unwrapped_locked(), 6)
        0.0
        """
        if not self._is_playing:
            return float(self._position_unwrapped)
        elapsed = max(0.0, self._time.monotonic() - self._play_started_monotonic)
        return float(self._play_anchor_unwrapped + elapsed)

    def _request_auto_normalization_hard_reset_locked(self) -> None:
        """Reset streaming autonormalization state before a discontinuous restart.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The next normalized chunk will reseed its local DC estimate from
            the newly rendered analysis block instead of from stale history.
        """
        self._auto_normalization_state = AutoNormalizationState()
        self._auto_normalization_hard_reset_pending = True
        self._last_auto_normalization_diagnostics = None

    def _update_status_locked(self, current_unwrapped: float | None = None) -> None:
        """Refresh synchronized status traitlets while holding the state lock.

        Parameters
        ----------
        current_unwrapped:
            Optional already-computed current unwrapped position. Supplying the
            value avoids recomputing it.

        Returns
        -------
        None
            Traitlets used by the browser view are updated in place.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player._update_status_locked()
        >>> player.playback_state
        'stopped'
        """
        if current_unwrapped is None:
            current_unwrapped = self._current_position_unwrapped_locked()

        wrapped_position = float(current_unwrapped % self._configuration.period_duration)
        buffered = max(0.0, self._generated_until_unwrapped - current_unwrapped)

        self.position_seconds = wrapped_position
        self.buffered_seconds = float(buffered)

        if self.last_error:
            self.playback_state = "error"
        elif self._is_playing and not self._frontend_ready_flag:
            self.playback_state = "waiting-for-display"
        elif self._is_playing and not self._audio_enabled_flag:
            self.playback_state = "waiting-for-browser-gesture"
        elif self._is_playing:
            self.playback_state = "playing"
        else:
            self.playback_state = "stopped"

    def _handle_frontend_detached_locked(self) -> None:
        """Mark the browser helper as temporarily detached while preserving play intent.

        Parameters
        ----------
        None

        Returns
        -------
        None
            Front-end readiness flags are cleared and buffered audio is discarded,
            but transport intent remains unchanged so a later redisplay may resync.
        """
        current_unwrapped = self._current_position_unwrapped_locked()
        self._position_unwrapped = current_unwrapped
        self._generated_until_unwrapped = current_unwrapped
        self._frontend_ready_flag = False
        self.frontend_ready = False
        self._audio_enabled_flag = False
        self.audio_enabled = False
        self.frontend_state = "detached"
        self._request_auto_normalization_hard_reset_locked()
        self._update_status_locked(current_unwrapped)

    def _handle_transport_disconnect_locked(self) -> None:
        """Mark the browser helper as permanently disconnected after a transport send failure.

        Parameters
        ----------
        None

        Returns
        -------
        None
            Playback is stopped without surfacing a synthesis error because the
            underlying issue is widget transport teardown rather than audio logic.
        """
        current_unwrapped = self._current_position_unwrapped_locked()
        self._position_unwrapped = current_unwrapped
        self._generated_until_unwrapped = current_unwrapped
        self._pending_transition = None
        self._is_playing = False
        self._frontend_ready_flag = False
        self.frontend_ready = False
        self._audio_enabled_flag = False
        self.audio_enabled = False
        self.frontend_state = "frontend-disconnected"
        self._request_auto_normalization_hard_reset_locked()
        self._update_status_locked(current_unwrapped)

    def _handle_frontend_message(
        self,
        _widget: Any,
        content: dict[str, Any],
        buffers: list[memoryview],
    ) -> None:
        """Handle custom messages arriving from the browser widget.

        Parameters
        ----------
        _widget:
            Widget instance supplied by the ipywidgets callback interface. The
            player does not need to inspect it.
        content:
            JSON-like message dictionary sent by the browser.
        buffers:
            Optional binary buffers attached to the message. The current
            implementation does not expect binary data from the browser.

        Returns
        -------
        None
            Internal flags and synchronized traitlets are updated as needed.

        Examples
        --------
        The method is usually triggered by the browser, but it can be called
        directly for tests:

        >>> player = FunctionAudioPlayer()
        >>> player._handle_frontend_message(player, {"type": "frontend-ready"}, [])
        >>> player.frontend_ready
        True
        """
        _ = buffers
        message_type = str(content.get("type", ""))

        should_resync_transport = False

        with self._state_lock:
            if message_type == "frontend-ready":
                self._frontend_ready_flag = True
                self.frontend_ready = True
                self.frontend_state = "ready"
                should_resync_transport = self._is_playing

            elif message_type == "audio-unlocked":
                self._audio_enabled_flag = True
                self.audio_enabled = True
                self.frontend_state = "audio-enabled"
                should_resync_transport = self._is_playing

            elif message_type == "frontend-stats":
                queued_seconds = max(0.0, float(content.get("queuedSeconds", 0.0)))
                context_state = str(content.get("contextState", "unknown"))
                if self._audio_enabled_flag:
                    self.frontend_state = f"audio-enabled | context={context_state}"
                else:
                    self.frontend_state = f"waiting-for-browser-gesture | context={context_state}"
                self.buffered_seconds = queued_seconds

            elif message_type == "frontend-detached":
                self._handle_frontend_detached_locked()

            elif message_type == "frontend-error":
                self.last_error = str(content.get("message", "unknown frontend error"))
                self.frontend_state = "frontend-error"
                current_unwrapped = self._current_position_unwrapped_locked()
                self._position_unwrapped = current_unwrapped
                self._generated_until_unwrapped = current_unwrapped
                self._is_playing = False

            elif message_type == "frontend-info":
                self.frontend_state = str(content.get("message", self.frontend_state))

            self._update_status_locked()

        if should_resync_transport:
            self._send_control_message("reset-queue", reason=message_type)
            self._send_control_message("play")
            self._wake_event.set()

    def _send_control_message(self, message_type: str, **payload: Any) -> None:
        """Send a small JSON control message to the browser widget.

        Parameters
        ----------
        message_type:
            String identifying the control action, for example ``"play"`` or
            ``"reset-queue"``.
        **payload:
            Additional JSON-serializable fields included with the message.

        Returns
        -------
        None
            The method is a no-op when the front end has not been displayed yet.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player._send_control_message("play")
        """
        if not self._frontend_ready_flag or self._closed_flag:
            return
        try:
            self.send({"type": message_type, **payload})
        except Exception:
            with self._state_lock:
                self._handle_transport_disconnect_locked()

    def _send_audio_chunk(self, start_unwrapped: float, samples: np.ndarray) -> None:
        """Send one binary float32 PCM chunk to the browser widget.

        Parameters
        ----------
        start_unwrapped:
            Unwrapped transport time, in seconds, of the chunk's first sample.
        samples:
            One-dimensional float32 PCM chunk.

        Returns
        -------
        None
            The method transmits the chunk via a custom widget message with one
            attached binary buffer.

        Examples
        --------
        >>> import numpy as np
        >>> player = FunctionAudioPlayer()
        >>> player._send_audio_chunk(0.0, np.zeros(4, dtype=np.float32))
        """
        if not self._frontend_ready_flag or self._closed_flag:
            return

        chunk = np.ascontiguousarray(samples, dtype=np.float32)
        payload = {
            "type": "audio-chunk",
            "chunkId": int(self._chunk_counter),
            "sampleRate": int(self._configuration.sample_rate),
            "frameCount": int(chunk.shape[0]),
            "transportStart": float(start_unwrapped),
            "duration": float(chunk.shape[0] / self._configuration.sample_rate),
        }
        self._chunk_counter += 1
        try:
            self.send(payload, buffers=[memoryview(chunk)])
        except Exception:
            with self._state_lock:
                self._handle_transport_disconnect_locked()

    def _render_next_chunk_locked(self) -> tuple[float, np.ndarray]:
        """Render the next chunk while holding the state lock.

        Parameters
        ----------
        None

        Returns
        -------
        tuple[float, numpy.ndarray]
            Pair containing the chunk start time in unwrapped seconds and the
            rendered float32 PCM chunk.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> start, chunk = player._render_next_chunk_locked()
        >>> start
        0.0
        >>> chunk.shape[0] == player.configuration.chunk_samples
        True
        """
        start_unwrapped = float(self._generated_until_unwrapped)
        frame_count = self._configuration.chunk_samples
        actual_duration = self._configuration.actual_chunk_duration

        transition_due = (
            self._pending_transition is not None
            and start_unwrapped >= (self._pending_transition.transition_unwrapped - 1e-12)
        )

        if not self._configuration.auto_normalize:
            if transition_due:
                assert self._pending_transition is not None
                outgoing = generate_chunk(
                    self._active_signal.function,
                    start_time=start_unwrapped,
                    frame_count=frame_count,
                    sample_rate=self._configuration.sample_rate,
                    period=self._configuration.period_duration,
                    phase_offset=self._active_signal.phase_offset,
                )
                incoming = generate_chunk(
                    self._pending_transition.signal.function,
                    start_time=start_unwrapped,
                    frame_count=frame_count,
                    sample_rate=self._configuration.sample_rate,
                    period=self._configuration.period_duration,
                    phase_offset=self._pending_transition.signal.phase_offset,
                )
                chunk = crossfade_chunks(
                    outgoing,
                    incoming,
                    self._configuration.crossfade_samples,
                )
                self._active_signal = self._pending_transition.signal
                self._pending_transition = None
            else:
                chunk = generate_chunk(
                    self._active_signal.function,
                    start_time=start_unwrapped,
                    frame_count=frame_count,
                    sample_rate=self._configuration.sample_rate,
                    period=self._configuration.period_duration,
                    phase_offset=self._active_signal.phase_offset,
                )

            self._generated_until_unwrapped = start_unwrapped + actual_duration
            return start_unwrapped, chunk

        if transition_due:
            assert self._pending_transition is not None
            outgoing_raw = generate_raw_chunk(
                self._active_signal.function,
                start_time=start_unwrapped,
                frame_count=frame_count,
                sample_rate=self._configuration.sample_rate,
                period=self._configuration.period_duration,
                phase_offset=self._active_signal.phase_offset,
            )
            incoming_raw = generate_raw_chunk(
                self._pending_transition.signal.function,
                start_time=start_unwrapped,
                frame_count=frame_count,
                sample_rate=self._configuration.sample_rate,
                period=self._configuration.period_duration,
                phase_offset=self._pending_transition.signal.phase_offset,
            )
            raw_chunk = crossfade_chunks_raw(
                outgoing_raw,
                incoming_raw,
                self._configuration.crossfade_samples,
            )
            post_chunk_signal = self._pending_transition.signal
            self._active_signal = self._pending_transition.signal
            self._pending_transition = None
        else:
            raw_chunk = generate_raw_chunk(
                self._active_signal.function,
                start_time=start_unwrapped,
                frame_count=frame_count,
                sample_rate=self._configuration.sample_rate,
                period=self._configuration.period_duration,
                phase_offset=self._active_signal.phase_offset,
            )
            post_chunk_signal = self._active_signal

        raw_future = generate_raw_chunk(
            post_chunk_signal.function,
            start_time=start_unwrapped + actual_duration,
            frame_count=self._configuration.normalization_attack_lookahead_samples,
            sample_rate=self._configuration.sample_rate,
            period=self._configuration.period_duration,
            phase_offset=post_chunk_signal.phase_offset,
        )
        chunk, diagnostics = apply_autonormalization(
            raw_chunk,
            raw_future,
            sample_rate=self._configuration.sample_rate,
            dc_time_constant=self._configuration.normalization_dc_time_constant,
            attack_lookahead_duration=self._configuration.normalization_attack_lookahead_duration,
            release_time_constant=self._configuration.normalization_release_time_constant,
            state=self._auto_normalization_state,
            hard_reset=self._auto_normalization_hard_reset_pending,
        )
        self._last_auto_normalization_diagnostics = diagnostics
        self._auto_normalization_hard_reset_pending = False
        self._generated_until_unwrapped = start_unwrapped + actual_duration
        return start_unwrapped, chunk

    def _handle_pump_error(self, exc: Exception) -> None:
        """Stop playback and surface an exception raised by the pump thread.

        Parameters
        ----------
        exc:
            Exception raised while rendering or sending a chunk.

        Returns
        -------
        None
            Player state is updated to reflect the failure.

        Examples
        --------
        >>> player = FunctionAudioPlayer()
        >>> player._handle_pump_error(RuntimeError("boom"))
        >>> player.playback_state
        'error'
        """
        with self._state_lock:
            current_unwrapped = self._current_position_unwrapped_locked()
            self._position_unwrapped = current_unwrapped
            self._generated_until_unwrapped = current_unwrapped
            self._pending_transition = None
            self._is_playing = False
            self._request_auto_normalization_hard_reset_locked()
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            self._update_status_locked(current_unwrapped)

        self._send_control_message("stop")

    def _pump_loop(self) -> None:
        """Background loop that keeps the browser audio queue filled.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The loop runs until the player is closed.

        Notes
        -----
        The method is intentionally conservative: it only renders while the
        front end is ready, audio permission has been granted, and the lookahead
        budget is not yet full.

        Examples
        --------
        The method is started automatically by :meth:`__init__`.
        """
        while not self._shutdown_event.is_set():
            self._wake_event.wait(timeout=self._configuration.pump_interval)
            self._wake_event.clear()

            while not self._shutdown_event.is_set():
                with self._state_lock:
                    current_unwrapped = self._current_position_unwrapped_locked()
                    target_horizon = current_unwrapped + self._configuration.lookahead_duration

                    if not self._is_playing:
                        self._update_status_locked(current_unwrapped)
                        break
                    if not self._frontend_ready_flag:
                        self._update_status_locked(current_unwrapped)
                        break
                    if not self._audio_enabled_flag:
                        self._update_status_locked(current_unwrapped)
                        break
                    if self._generated_until_unwrapped >= target_horizon - 1e-12:
                        self._update_status_locked(current_unwrapped)
                        break

                    try:
                        chunk_start, chunk = self._render_next_chunk_locked()
                        self._update_status_locked(current_unwrapped)
                    except Exception as exc:
                        self._handle_pump_error(exc)
                        break

                try:
                    self._send_audio_chunk(chunk_start, chunk)
                except Exception as exc:
                    self._handle_pump_error(exc)
                    break
