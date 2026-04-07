"""Sound playback and sound-generation integration for interactive figures.

Public entry points
-------------------
``FigureSoundManager``

Architecture note
-----------------
Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering.

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for the package-level task map.
- Example notebook: ``examples/Fourier-Sounds.ipynb``.
- Regression/spec tests: ``tests/test_figure_sound.py``.
- Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
"""

from __future__ import annotations

"""Figure-level streaming sound playback.

This module owns the figure's optional sound-generation subsystem:

- figure-scoped enable/disable state,
- single-active-plot playback policy,
- incremental chunk rendering from plot numeric expressions,
- a thin browser bridge that queues PCM chunks in Web Audio.

The Python side renders one second of mono PCM at a time. The browser side
requests chunks on demand and schedules them into a small playback queue.
"""

import base64
import uuid
import warnings
from typing import TYPE_CHECKING, Any

import numpy as np
import traitlets

from ._widget_stubs import anywidget, widgets

if TYPE_CHECKING:
    from .Figure import Figure
    from .figure_legend import LegendPanelManager
    from .figure_plot import Plot


class _SoundStreamBridge(anywidget.AnyWidget):
    """Hidden frontend bridge that turns PCM chunks into browser audio."""

    root_class = traitlets.Unicode("").tag(sync=True)

    _esm = r"""
    function safeNumber(value, fallback) {
      const num = Number(value);
      return Number.isFinite(num) ? num : fallback;
    }

    function clamp(value, minValue, maxValue) {
      return Math.min(maxValue, Math.max(minValue, value));
    }

    function decodePcm16Base64(payload) {
      const text = String(payload || "");
      const binary = atob(text);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i) & 0xff;
      }
      return new Int16Array(bytes.buffer.slice(0));
    }

    function modulo(value, period) {
      if (!(period > 0)) return 0;
      const out = value % period;
      return out < 0 ? out + period : out;
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        const state = {
          audioContext: null,
          isPlaying: false,
          activeToken: null,
          activePlotId: "",
          sourceEntries: [],
          nextStartTime: 0,
          requestInFlight: 0,
          maxBufferedSeconds: 2.0,
          loopSeconds: 60.0,
        };

        function rootEl() {
          const rootClass = model.get("root_class") || "";
          return rootClass ? document.querySelector(`.${rootClass}`) : null;
        }

        function ensureAudioContext() {
          if (state.audioContext) return state.audioContext;
          const Ctor = window.AudioContext || window.webkitAudioContext;
          if (!Ctor) return null;
          try {
            state.audioContext = new Ctor();
          } catch (e) {
            state.audioContext = null;
          }
          return state.audioContext;
        }

        function primeAudioContext() {
          const ctx = ensureAudioContext();
          if (!ctx) return;
          if (ctx.state === "suspended") {
            try {
              ctx.resume();
            } catch (e) {}
          }
        }

        function clearEndedEntries() {
          const ctx = state.audioContext;
          if (!ctx) {
            state.sourceEntries = [];
            return;
          }
          const now = ctx.currentTime - 0.02;
          state.sourceEntries = state.sourceEntries.filter((entry) => entry.endAt > now);
        }

        function bufferedSeconds() {
          const ctx = state.audioContext;
          if (!ctx) return 0;
          clearEndedEntries();
          if (!state.sourceEntries.length) return 0;
          const tail = state.sourceEntries.reduce((best, entry) => (
            entry.endAt > best.endAt ? entry : best
          ));
          return Math.max(0, tail.endAt - ctx.currentTime);
        }

        function currentPlaybackCursor() {
          const ctx = state.audioContext;
          if (!ctx) return 0;
          clearEndedEntries();
          const now = ctx.currentTime;
          for (const entry of state.sourceEntries) {
            if (now >= entry.startAt && now < entry.endAt) {
              return modulo(entry.chunkStartSeconds + (now - entry.startAt), state.loopSeconds);
            }
          }
          if (state.sourceEntries.length) {
            const first = state.sourceEntries.reduce((best, entry) => (
              entry.startAt < best.startAt ? entry : best
            ));
            return modulo(first.chunkStartSeconds, state.loopSeconds);
          }
          return 0;
        }

        function stopAllSources() {
          for (const entry of state.sourceEntries) {
            try {
              entry.source.onended = null;
            } catch (e) {}
            try {
              entry.source.stop();
            } catch (e) {}
            try {
              entry.source.disconnect();
            } catch (e) {}
          }
          state.sourceEntries = [];
          state.nextStartTime = 0;
          state.requestInFlight = 0;
          state.isPlaying = false;
          state.activePlotId = "";
        }

        function requestChunk(cursorSeconds) {
          if (!state.isPlaying || state.activeToken === null || state.activeToken === undefined) {
            return;
          }
          if (state.requestInFlight > 0) return;
          state.requestInFlight += 1;
          const payload = {
            type: "sound_stream_request",
            action: "request_chunk",
            token: state.activeToken,
          };
          if (Number.isFinite(cursorSeconds)) {
            payload.cursor_seconds = cursorSeconds;
          }
          try {
            model.send(payload);
          } catch (e) {
            state.requestInFlight = Math.max(0, state.requestInFlight - 1);
          }
        }

        function maybeRequestChunk() {
          if (!state.isPlaying) return;
          if (bufferedSeconds() >= state.maxBufferedSeconds) return;
          requestChunk(undefined);
        }

        function scheduleChunk(message) {
          const ctx = ensureAudioContext();
          state.requestInFlight = Math.max(0, state.requestInFlight - 1);
          if (!ctx || !state.isPlaying) return;
          if (message.token !== state.activeToken) return;

          const sampleRate = Math.max(1, Math.trunc(safeNumber(message.sample_rate, 44100)));
          const frameCount = Math.max(0, Math.trunc(safeNumber(message.frame_count, 0)));
          const chunkStartSeconds = modulo(
            safeNumber(message.chunk_start_seconds, 0),
            state.loopSeconds,
          );
          const pcm = decodePcm16Base64(message.pcm_base64 || "");
          const buffer = ctx.createBuffer(1, frameCount || pcm.length, sampleRate);
          const channel = buffer.getChannelData(0);
          const usable = Math.min(channel.length, pcm.length);
          for (let i = 0; i < usable; i += 1) {
            channel[i] = clamp(pcm[i] / 32767.0, -1.0, 1.0);
          }
          for (let i = usable; i < channel.length; i += 1) {
            channel[i] = 0.0;
          }

          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(ctx.destination);

          const now = ctx.currentTime + 0.03;
          const startAt = Math.max(now, state.nextStartTime || now);
          const duration = buffer.duration || (frameCount / sampleRate);
          const entry = {
            source,
            startAt,
            endAt: startAt + duration,
            chunkStartSeconds,
          };

          source.onended = () => {
            state.sourceEntries = state.sourceEntries.filter((candidate) => candidate !== entry);
            maybeRequestChunk();
          };

          state.sourceEntries.push(entry);
          state.sourceEntries.sort((left, right) => left.startAt - right.startAt);
          state.nextStartTime = entry.endAt;

          try {
            source.start(startAt);
          } catch (e) {
            state.sourceEntries = state.sourceEntries.filter((candidate) => candidate !== entry);
            try { source.disconnect(); } catch (err) {}
            return;
          }

          maybeRequestChunk();
        }

        function handleStart(message) {
          primeAudioContext();
          stopAllSources();
          state.isPlaying = true;
          state.activeToken = message.token;
          state.activePlotId = String(message.plot_id || "");
          requestChunk(safeNumber(message.cursor_seconds, 0));
        }

        function handleStop(message) {
          state.activeToken = message.token;
          stopAllSources();
        }

        function handleRefresh(message) {
          primeAudioContext();
          const cursorSeconds = currentPlaybackCursor();
          stopAllSources();
          state.isPlaying = true;
          state.activeToken = message.token;
          state.activePlotId = String(message.plot_id || "");
          requestChunk(cursorSeconds);
        }

        function onCustomMessage(message) {
          if (!message || message.type !== "sound_stream") return;
          const action = message.action;
          if (action === "start") {
            handleStart(message);
            return;
          }
          if (action === "stop") {
            handleStop(message);
            return;
          }
          if (action === "refresh") {
            handleRefresh(message);
            return;
          }
          if (action === "chunk") {
            scheduleChunk(message);
            return;
          }
          if (action === "error") {
            handleStop(message);
          }
        }

        function onPointerIntent(event) {
          const target = event && event.target;
          const root = rootEl();
          if (!(target instanceof HTMLElement) || !(root instanceof HTMLElement)) return;
          if (!root.contains(target)) return;
          primeAudioContext();
        }

        function onKeydownIntent(event) {
          const root = rootEl();
          const active = document.activeElement;
          if (!(root instanceof HTMLElement) || !(active instanceof HTMLElement)) return;
          if (!root.contains(active)) return;
          primeAudioContext();
        }

        model.on("msg:custom", onCustomMessage);
        document.addEventListener("pointerdown", onPointerIntent, true);
        document.addEventListener("keydown", onKeydownIntent, true);

        return () => {
          try { model.off("msg:custom", onCustomMessage); } catch (e) {}
          try { document.removeEventListener("pointerdown", onPointerIntent, true); } catch (e) {}
          try { document.removeEventListener("keydown", onKeydownIntent, true); } catch (e) {}
          stopAllSources();
          const ctx = state.audioContext;
          if (ctx && typeof ctx.close === "function") {
            try { ctx.close(); } catch (e) {}
          }
          state.audioContext = null;
        };
      },
    };
    """


class FigureSoundManager:
    """Own the figure's single-active streaming playback state.
    
    Full API
    --------
    ``FigureSoundManager(figure: Figure, legend: LegendPanelManager, root_widget: widgets.Box | None=None)``
    
    Public members exposed from this class: ``enabled``, ``active_plot_id``, ``sound_generation_enabled``, ``sound``,
        ``on_parameter_change``
    
    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    
    legend : LegendPanelManager
        Value for ``legend`` in this API. Required.
    
    root_widget : widgets.Box | None, optional
        Value for ``root_widget`` in this API. Defaults to ``None``.
    
    Returns
    -------
    FigureSoundManager
        New ``FigureSoundManager`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``root_widget=None``: Value for ``root_widget`` in this API.
    
    Architecture note
    -----------------
    ``FigureSoundManager`` lives in ``gu_toolkit.figure_sound``. Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_sound import FigureSoundManager
        obj = FigureSoundManager(...)
    
    Discovery-oriented use::
    
        help(FigureSoundManager)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Fourier-Sounds.ipynb``.
    - Regression/spec tests: ``tests/test_figure_sound.py``.
    - Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
    - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(FigureSoundManager)`` to inspect adjacent members.
    """

    sample_rate = 44100
    chunk_seconds = 1.0
    loop_seconds = 60.0
    _value_tolerance = 1.0e-9

    def __init__(
        self,
        figure: Figure,
        legend: LegendPanelManager,
        *,
        root_widget: widgets.Box | None = None,
    ) -> None:
        self._figure = figure
        self._legend = legend
        self._root_widget = root_widget
        self._enabled = True
        self._active_plot_id: str | None = None
        self._generation_token = 0
        self._cursor_seconds = 0.0
        self._primed_chunk: tuple[int, float, str, int] | None = None

        self._root_css_class = f"gu-figure-sound-root-{uuid.uuid4().hex[:8]}"
        if self._root_widget is not None:
            add_class = getattr(self._root_widget, "add_class", None)
            if callable(add_class):
                add_class(self._root_css_class)

        self._bridge = _SoundStreamBridge(
            root_class=self._root_css_class,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._bridge.on_msg(self._handle_bridge_message)
        if self._root_widget is not None and self._bridge not in self._root_widget.children:
            self._root_widget.children += (self._bridge,)

        bind_handler = getattr(self._legend, "bind_sound_enabled_handler", None)
        if callable(bind_handler):
            bind_handler(self.sound_generation_enabled)
        self._legend.set_sound_generation_enabled(self._enabled)
        self._legend.set_sound_playing_plot(None)

    @property
    def enabled(self) -> bool:
        """Return whether sound controls are enabled for the figure.
        
        Full API
        --------
        ``obj.enabled -> bool``
        
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
        This member belongs to ``FigureSoundManager``. Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureSoundManager(...)
            current = obj.enabled
        
        Discovery-oriented use::
        
            help(FigureSoundManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
        - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(FigureSoundManager)`` to inspect adjacent members.
        """
        return self._enabled

    @property
    def active_plot_id(self) -> str | None:
        """Return the currently playing plot id, if any.
        
        Full API
        --------
        ``obj.active_plot_id -> str | None``
        
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
        This member belongs to ``FigureSoundManager``. Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureSoundManager(...)
            current = obj.active_plot_id
        
        Discovery-oriented use::
        
            help(FigureSoundManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
        - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(FigureSoundManager)`` to inspect adjacent members.
        """
        return self._active_plot_id

    def sound_generation_enabled(self, enabled: bool | None = None) -> bool:
        """Query or set the figure-level sound-generation toggle.
        
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
        This member belongs to ``FigureSoundManager``. Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureSoundManager(...)
            result = obj.sound_generation_enabled(...)
        
        Discovery-oriented use::
        
            help(FigureSoundManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
        - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(FigureSoundManager)`` to inspect adjacent members.
        """
        if enabled is None:
            return self._enabled

        next_enabled = bool(enabled)
        if next_enabled == self._enabled:
            self._legend.set_sound_generation_enabled(self._enabled)
            return self._enabled

        self._enabled = next_enabled
        if not self._enabled:
            self._stop_playback()
        self._legend.set_sound_generation_enabled(self._enabled)
        return self._enabled

    def sound(self, plot_id: str, *, run: bool = True) -> None:
        """Start, stop, or restart playback for ``plot_id``.
        
        Full API
        --------
        ``obj.sound(plot_id: str, *, run: bool=True) -> None``
        
        Parameters
        ----------
        plot_id : str
            Stable plot identifier used for lookup or update. Required.
        
        run : bool, optional
            Value for ``run`` in this API. Defaults to ``True``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``run=True``: Value for ``run`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureSoundManager(...)
            obj.sound(...)
        
        Discovery-oriented use::
        
            help(FigureSoundManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
        - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(FigureSoundManager)`` to inspect adjacent members.
        """
        normalized_plot_id = str(plot_id)
        if not run:
            if self._active_plot_id == normalized_plot_id:
                self._stop_playback()
            return

        if not self._enabled:
            raise RuntimeError(
                "Sound generation is disabled. Enable it with sound_generation_enabled(True)."
            )

        plot = self._figure.plots.get(normalized_plot_id)
        if plot is None:
            raise KeyError(f"Unknown plot id: {normalized_plot_id!r}")

        previous_token = self._generation_token
        previous_plot_id = self._active_plot_id
        previous_cursor = self._cursor_seconds
        previous_primed = self._primed_chunk
        next_token = previous_token + 1

        try:
            primed_chunk = self._build_chunk(
                plot,
                start_seconds=0.0,
                token=next_token,
            )
        except Exception:
            self._generation_token = previous_token
            self._active_plot_id = previous_plot_id
            self._cursor_seconds = previous_cursor
            self._primed_chunk = previous_primed
            self._legend.set_sound_playing_plot(previous_plot_id)
            raise

        self._generation_token = next_token
        self._active_plot_id = normalized_plot_id
        self._cursor_seconds = 0.0
        self._primed_chunk = primed_chunk
        self._legend.set_sound_playing_plot(normalized_plot_id)
        self._send_message(
            {
                "type": "sound_stream",
                "action": "start",
                "plot_id": normalized_plot_id,
                "token": self._generation_token,
                "cursor_seconds": 0.0,
            }
        )

    def on_parameter_change(self, _event: Any) -> None:
        """Refresh queued audio so future chunks use the latest parameter values.
        
        Full API
        --------
        ``obj.on_parameter_change(_event: Any) -> None``
        
        Parameters
        ----------
        _event : Any
            Value for ``_event`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. Sound features are layered on top of the figure/plot model so audio generation reacts to the same selection and parameter state as visual rendering. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureSoundManager(...)
            obj.on_parameter_change(...)
        
        Discovery-oriented use::
        
            help(FigureSoundManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - Runtime discovery tip: pair this API with ``Figure.sound(...)`` and the Fourier sound notebooks to see the full audio workflow.
        - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(FigureSoundManager)`` to inspect adjacent members.
        """
        if not self._enabled or self._active_plot_id is None:
            return
        plot = self._figure.plots.get(self._active_plot_id)
        if plot is None:
            self._stop_playback()
            return
        self._generation_token += 1
        self._primed_chunk = None
        self._send_message(
            {
                "type": "sound_stream",
                "action": "refresh",
                "plot_id": self._active_plot_id,
                "token": self._generation_token,
            }
        )

    def _stop_playback(self) -> None:
        self._generation_token += 1
        token = self._generation_token
        self._active_plot_id = None
        self._cursor_seconds = 0.0
        self._primed_chunk = None
        self._legend.set_sound_playing_plot(None)
        self._send_message(
            {
                "type": "sound_stream",
                "action": "stop",
                "token": token,
            }
        )

    def _handle_bridge_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "sound_stream_request":
            return
        if content.get("action") != "request_chunk":
            return

        token = self._safe_int(content.get("token"), default=-1)
        if token != self._generation_token:
            return
        if not self._enabled or self._active_plot_id is None:
            return

        plot = self._figure.plots.get(self._active_plot_id)
        if plot is None:
            self._stop_playback()
            return

        cursor_override = content.get("cursor_seconds")
        if cursor_override is not None:
            self._cursor_seconds = self._normalize_cursor(
                self._safe_float(cursor_override, default=self._cursor_seconds)
            )
            self._primed_chunk = None

        try:
            payload = self._next_chunk_payload(plot)
        except Exception as exc:
            self._fail_playback(plot_id=self._active_plot_id, error=exc, raise_error=False)
            return

        self._send_message(payload)

    def _next_chunk_payload(self, plot: Plot) -> dict[str, Any]:
        primed = self._primed_chunk
        if (
            primed is not None
            and primed[0] == self._generation_token
            and abs(primed[1] - self._cursor_seconds) <= self._value_tolerance
        ):
            token, chunk_start_seconds, pcm_base64, frame_count = primed
            self._primed_chunk = None
        else:
            token, chunk_start_seconds, pcm_base64, frame_count = self._build_chunk(
                plot,
                start_seconds=self._cursor_seconds,
                token=self._generation_token,
            )

        payload = {
            "type": "sound_stream",
            "action": "chunk",
            "plot_id": self._active_plot_id or "",
            "token": token,
            "sample_rate": self.sample_rate,
            "frame_count": frame_count,
            "chunk_start_seconds": chunk_start_seconds,
            "pcm_base64": pcm_base64,
        }
        self._cursor_seconds = self._normalize_cursor(chunk_start_seconds + self.chunk_seconds)
        return payload

    def _build_chunk(
        self,
        plot: Plot,
        *,
        start_seconds: float,
        token: int,
    ) -> tuple[int, float, str, int]:
        chunk_start = self._normalize_cursor(start_seconds)
        frame_count = max(1, int(round(self.sample_rate * self.chunk_seconds)))
        offsets = np.arange(frame_count, dtype=float) / float(self.sample_rate)
        x_values = np.mod(chunk_start + offsets, self.loop_seconds)

        try:
            raw_values = plot.numeric_expression(x_values)
            y_values = np.asarray(raw_values, dtype=float)
        except Exception as exc:
            raise ValueError(
                f"Failed to evaluate sound for plot {plot.id!r}: {exc}"
            ) from exc

        if y_values.ndim == 0:
            y_values = np.full(frame_count, float(y_values), dtype=float)
        else:
            y_values = np.ravel(y_values)
            if y_values.shape[0] != frame_count:
                raise ValueError(
                    "Sound expression must evaluate to exactly one sample per time point."
                )

        if not np.all(np.isfinite(y_values)):
            raise ValueError("Sound expression must be finite and stay within [-1, 1].")

        peak = float(np.max(np.abs(y_values))) if y_values.size else 0.0
        if peak > 1.0 + self._value_tolerance:
            autonormalization_handler = getattr(plot, "autonormalization", None)
            autonormalization_enabled = False
            if callable(autonormalization_handler):
                try:
                    autonormalization_enabled = bool(autonormalization_handler())
                except Exception:
                    autonormalization_enabled = False
            if autonormalization_enabled and peak > self._value_tolerance:
                y_values = y_values / peak
            else:
                raise ValueError(
                    "Sound expression must stay within [-1, 1]; enable autonormalization to scale louder chunks automatically."
                )

        pcm = (np.clip(y_values, -1.0, 1.0) * 32767.0).astype(np.int16)
        pcm_base64 = base64.b64encode(pcm.tobytes()).decode("ascii")
        return token, chunk_start, pcm_base64, frame_count

    def _fail_playback(
        self,
        *,
        plot_id: str | None,
        error: Exception,
        raise_error: bool = True,
    ) -> None:
        self._generation_token += 1
        token = self._generation_token
        self._active_plot_id = None
        self._cursor_seconds = 0.0
        self._primed_chunk = None
        self._legend.set_sound_playing_plot(None)
        self._send_message(
            {
                "type": "sound_stream",
                "action": "error",
                "plot_id": plot_id or "",
                "token": token,
                "message": str(error),
            }
        )
        if raise_error:
            raise error
        warnings.warn(f"Sound playback stopped: {error}", stacklevel=2)

    def _send_message(self, payload: dict[str, Any]) -> None:
        try:
            self._bridge.send(payload)
        except TypeError:
            self._bridge.send(payload, None)

    def _normalize_cursor(self, value: float) -> float:
        return float(value) % self.loop_seconds

    @staticmethod
    def _safe_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _safe_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)
