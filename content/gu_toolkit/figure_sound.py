"""Figure-level streaming sound playback.

Public entry points
-------------------
``FigureSoundManager``

Architecture note
-----------------
This module keeps GU-specific playback policy in a small adapter layer while the
vendored ``jlab_function_audio`` runtime owns buffering, browser transport,
frontend lifecycle, and bounded streaming auto-normalization.

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for the package-level task map.
- Example notebook: ``examples/Fourier-Sounds.ipynb``.
- Regression/spec tests: ``tests/test_figure_sound.py``.
- Runtime discovery tip: pair this API with ``Plot.sound(...)`` and the Fourier
  sound notebooks to see the full audio workflow.
"""

from __future__ import annotations

import importlib
import weakref
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import numpy as np

from ._widget_stubs import install_widget_stubs, widgets

if TYPE_CHECKING:
    from .Figure import Figure
    from .figure_legend import LegendPanelManager
    from .figure_plot import Plot


_PLAYER_CLASS: type[Any] | None = None
_PLAYER_CONFIG_CLASS: type[Any] | None = None


def _load_player_runtime() -> tuple[type[Any], type[Any]]:
    global _PLAYER_CLASS, _PLAYER_CONFIG_CLASS

    if _PLAYER_CLASS is None or _PLAYER_CONFIG_CLASS is None:
        install_widget_stubs()
        player_module = importlib.import_module(
            "gu_toolkit._vendor.jlab_function_audio.player"
        )
        config_module = importlib.import_module(
            "gu_toolkit._vendor.jlab_function_audio.config"
        )
        _PLAYER_CLASS = player_module.FunctionAudioPlayer
        _PLAYER_CONFIG_CLASS = config_module.PlayerConfiguration
    return _PLAYER_CLASS, _PLAYER_CONFIG_CLASS


class _PlotSignalAdapter:
    """Batched GU-to-callable adapter used by the vendored player."""

    _index_tolerance = 1.0e-6

    def __init__(
        self,
        plot: Plot,
        *,
        sample_rate: int,
        period: float,
        batch_samples: int,
        value_tolerance: float,
    ) -> None:
        self._plot = plot
        self._sample_rate = int(sample_rate)
        self._period = float(period)
        self._batch_samples = max(1, int(batch_samples))
        self._value_tolerance = float(value_tolerance)
        self._cache_start_time: float | None = None
        self._cache_values = np.zeros(0, dtype=np.float64)

    def __call__(self, time_seconds: float) -> float:
        sample_time = float(time_seconds)
        cache_start = self._cache_start_time
        if cache_start is not None and self._cache_values.size:
            offset_samples = (sample_time - cache_start) * float(self._sample_rate)
            local_index = int(round(offset_samples))
            if (
                0 <= local_index < self._cache_values.shape[0]
                and abs(offset_samples - local_index) <= self._index_tolerance
            ):
                return float(self._cache_values[local_index])

        offsets = np.arange(self._batch_samples, dtype=np.float64) / float(self._sample_rate)
        values = self._evaluate_times(sample_time + offsets)
        self._cache_start_time = sample_time
        self._cache_values = values
        return float(values[0])

    def _preflight(self, *, start_seconds: float, duration_seconds: float) -> None:
        frame_count = max(1, int(round(float(duration_seconds) * float(self._sample_rate))))
        offsets = np.arange(frame_count, dtype=np.float64) / float(self._sample_rate)
        _ = self._evaluate_times(float(start_seconds) + offsets)

    def _allow_over_range_enabled(self) -> bool:
        handler = getattr(self._plot, "autonormalization", None)
        if callable(handler):
            try:
                return bool(handler())
            except Exception:
                return False
        return bool(getattr(self._plot, "_sound_autonormalization", False))

    def _evaluate_times(self, times: np.ndarray) -> np.ndarray:
        wrapped_times = np.mod(np.asarray(times, dtype=np.float64), self._period)

        try:
            raw_values = self._plot.numeric_expression(wrapped_times)
            values = np.asarray(raw_values, dtype=np.float64)
        except Exception as exc:  # pragma: no cover - exercised via public API tests.
            raise ValueError(
                f"Failed to evaluate sound for plot {self._plot.id!r}: {exc}"
            ) from exc

        frame_count = int(wrapped_times.shape[0])
        if values.ndim == 0:
            values = np.full(frame_count, float(values), dtype=np.float64)
        else:
            values = np.ravel(values)
            if values.shape[0] != frame_count:
                raise ValueError(
                    "Sound expression must evaluate to exactly one sample per time point."
                )

        allow_over_range = self._allow_over_range_enabled()

        if not np.all(np.isfinite(values)):
            if allow_over_range:
                raise ValueError("Sound expression must stay finite during playback.")
            raise ValueError("Sound expression must be finite and stay within [-1, 1].")

        if not allow_over_range:
            peak = float(np.max(np.abs(values))) if values.size else 0.0
            if peak > 1.0 + self._value_tolerance:
                raise ValueError(
                    "Sound expression must stay within [-1, 1]; enable "
                    "autonormalization to attenuate louder audio automatically."
                )

        return values.astype(np.float64, copy=False)


class FigureSoundManager:
    """Own the figure's single-active streaming playback state.

    Full API
    --------
    ``FigureSoundManager(figure: Figure, legend: LegendPanelManager, root_widget: widgets.Box | None=None)``

    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    legend : LegendPanelManager
        Legend manager used to keep the speaker-button UI in sync with playback.
        Required.
    root_widget : widgets.Box | None, optional
        Hidden widget container used when the vendored player should live inside
        the figure widget tree. Defaults to ``None``.

    Returns
    -------
    FigureSoundManager
        New ``FigureSoundManager`` instance configured according to the
        constructor arguments.

    Optional arguments
    ------------------
    - ``root_widget=None``: Hidden widget container used for embedded playback.

    Architecture note
    -----------------
    ``FigureSoundManager`` lives in ``gu_toolkit.figure_sound``. GU keeps the
    public figure/plot sound contract here, while the vendored
    ``jlab_function_audio`` player owns browser transport, buffering, queue
    flushing, and bounded streaming auto-normalization.

    Examples
    --------
    Construction::

        from gu_toolkit.figure_sound import FigureSoundManager
        manager = FigureSoundManager(...)

    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the
      package.
    - Example notebook: ``examples/Fourier-Sounds.ipynb``.
    - Regression/spec tests: ``tests/test_figure_sound.py``.
    - In a notebook or REPL, run ``help(FigureSoundManager)`` and ``dir(...)``
      to inspect adjacent members.
    """

    sample_rate = 44100
    loop_seconds = 60.0
    start_validation_seconds = 1.0
    value_tolerance = 1.0e-9

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
        self._player: Any | None = None
        self._player_embedded = False
        self._player_state_observer_guard = 0
        self._active_signal_adapter: _PlotSignalAdapter | None = None
        self._finalizer = weakref.finalize(
            self,
            type(self)._finalize_manager,
            weakref.ref(self),
        )

        bind_handler = getattr(self._legend, "bind_sound_enabled_handler", None)
        if callable(bind_handler):
            bind_handler(self.sound_generation_enabled)
        self._legend.set_sound_generation_enabled(self._enabled)
        self._legend.set_sound_playing_plot(None)

    @staticmethod
    def _finalize_manager(manager_ref: weakref.ReferenceType[FigureSoundManager]) -> None:
        manager = manager_ref()
        if manager is None:
            return
        try:
            manager.close()
        except Exception:
            return

    @property
    def enabled(self) -> bool:
        """Return whether sound controls are enabled for the figure.

        Full API
        --------
        ``obj.enabled -> bool``

        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond
        implicit object context.

        Returns
        -------
        bool
            ``True`` when figure-linked sound controls are enabled.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. The adapter keeps figure
        policy in GU while delegating runtime playback to the vendored engine.

        Examples
        --------
        Basic use::

            current = manager.enabled

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.enabled)``.
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
        None. This API does not declare user-supplied parameters beyond
        implicit object context.

        Returns
        -------
        str | None
            Active plot id when playback is running, otherwise ``None``.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. GU owns the one-active-
        plot policy even though the vendored player itself only knows about one
        callable at a time.

        Examples
        --------
        Basic use::

            current_plot = manager.active_plot_id

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.active_plot_id)``.
        """
        return self._active_plot_id

    def sound_generation_enabled(self, enabled: bool | None = None) -> bool:
        """Query or set the figure-wide sound-generation toggle.

        Full API
        --------
        ``obj.sound_generation_enabled(enabled: bool | None=None) -> bool``

        Parameters
        ----------
        enabled : bool | None, optional
            Boolean flag that turns figure-linked sound controls on or off.
            Defaults to ``None``.

        Returns
        -------
        bool
            The resulting enabled state.

        Optional arguments
        ------------------
        - ``enabled=None``: Query the current state without mutating it.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. The method updates GU's
        public enable/disable state and keeps the legend speaker buttons aligned
        with that state.

        Examples
        --------
        Basic use::

            manager.sound_generation_enabled(False)
            manager.sound_generation_enabled(True)

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.sound_generation_enabled)``.
        """
        if enabled is None:
            return self._enabled

        next_enabled = bool(enabled)
        if next_enabled == self._enabled:
            self._legend.set_sound_generation_enabled(self._enabled)
            return self._enabled

        self._enabled = next_enabled
        if not self._enabled:
            self._stop_player()
        self._legend.set_sound_generation_enabled(self._enabled)
        return self._enabled

    def sound(self, plot_id: str, *, run: bool = True) -> None:
        """Start, stop, or restart playback for one plot.

        Full API
        --------
        ``obj.sound(plot_id: str, *, run: bool=True) -> None``

        Parameters
        ----------
        plot_id : str
            Stable plot identifier used for lookup or update. Required.
        run : bool, optional
            When ``True``, start or restart the requested plot. When ``False``,
            stop it if it is the active plot. Defaults to ``True``.

        Returns
        -------
        None
            This call is used for side effects and does not return a value.

        Optional arguments
        ------------------
        - ``run=True``: Start or restart the requested plot.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. GU preserves restart-from-
        zero behavior, strict synchronous preflight validation, and legend state
        while the vendored player handles buffered runtime playback.

        Examples
        --------
        Basic use::

            manager.sound("tone", run=True)
            manager.sound("tone", run=False)

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.sound)``.
        """
        normalized_plot_id = str(plot_id)
        if not run:
            if self._active_plot_id == normalized_plot_id:
                self._stop_player()
            return

        if not self._enabled:
            raise RuntimeError(
                "Sound generation is disabled. Enable it with sound_generation_enabled(True)."
            )

        plot = self._figure.plots.get(normalized_plot_id)
        if plot is None:
            raise KeyError(f"Unknown plot id: {normalized_plot_id!r}")

        allow_over_range = bool(plot.autonormalization())
        adapter = self._build_signal_adapter(plot)
        adapter._preflight(
            start_seconds=0.0,
            duration_seconds=self.start_validation_seconds,
        )

        player = self._ensure_player()
        if bool(player.configuration.auto_normalize) != allow_over_range:
            player.set_auto_normalize(allow_over_range)
        player.set_function(
            adapter,
            function_name=str(getattr(plot, "label", None) or plot.id),
            phase_match=False,
        )
        player.seek(0.0)
        player.play()

        self._active_signal_adapter = adapter
        self._active_plot_id = normalized_plot_id
        self._legend.set_sound_playing_plot(normalized_plot_id)

    def on_parameter_change(self, _event: Any) -> None:
        """Refresh queued audio so future chunks use the latest parameter values.

        Full API
        --------
        ``obj.on_parameter_change(_event: Any) -> None``

        Parameters
        ----------
        _event : Any
            Change payload forwarded from figure render hooks. Required.

        Returns
        -------
        None
            This call is used for side effects and does not return a value.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. The active adapter reads
        plot state dynamically, so refreshing parameters only needs to flush the
        vendored player queue from the current cursor.

        Examples
        --------
        Basic use::

            manager.on_parameter_change({"reason": "slider"})

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.on_parameter_change)``.
        """
        if not self._enabled or self._active_plot_id is None:
            return

        plot = self._figure.plots.get(self._active_plot_id)
        if plot is None:
            self._stop_player()
            return

        player = self._player
        if player is None:
            return

        target_mode = bool(plot.autonormalization())
        if bool(player.configuration.auto_normalize) != target_mode:
            player.set_auto_normalize(target_mode)
            return

        player.seek(float(player.position))

    def on_plot_removed(self, plot_id: str) -> None:
        """Stop playback if the removed plot is the active sound source.

        Full API
        --------
        ``obj.on_plot_removed(plot_id: str) -> None``

        Parameters
        ----------
        plot_id : str
            Stable identifier of the plot being removed from the figure.
            Required.

        Returns
        -------
        None
            This call is used for side effects and does not return a value.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. Plot removal is figure-
        specific coordination logic, so GU stops the vendored runtime when the
        active plot disappears from the figure model.

        Examples
        --------
        Basic use::

            manager.on_plot_removed("tone")

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.on_plot_removed)``.
        """
        if self._active_plot_id == str(plot_id):
            self._stop_player()

    def close(self) -> None:
        """Release the vendored player and detach it from the figure widget tree.

        Full API
        --------
        ``obj.close() -> None``

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method is idempotent and may be called multiple times safely.

        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.

        Architecture note
        -----------------
        This member belongs to ``FigureSoundManager``. The manager owns the
        lifecycle of the lazily-created vendored player and therefore performs
        best-effort observer teardown, widget detachment, and runtime cleanup.

        Examples
        --------
        Basic use::

            manager.close()

        Learn more / explore
        --------------------
        - Example notebook: ``examples/Fourier-Sounds.ipynb``.
        - Regression/spec tests: ``tests/test_figure_sound.py``.
        - In a notebook or REPL, run ``help(FigureSoundManager.close)``.
        """
        player = self._player
        if player is None:
            if self._finalizer.alive:
                self._finalizer.detach()
            return

        with self._suppress_player_observers():
            try:
                player.unobserve(self._handle_player_trait_change, names=["playback_state", "last_error"])
            except Exception:
                pass
            try:
                player.stop()
            except Exception:
                pass

        self._detach_player_widget(player)

        try:
            player.close()
        except Exception:
            pass

        self._player = None
        self._player_embedded = False
        self._active_signal_adapter = None
        self._active_plot_id = None
        self._legend.set_sound_playing_plot(None)
        if self._finalizer.alive:
            self._finalizer.detach()

    def _build_signal_adapter(
        self,
        plot: Plot,
    ) -> _PlotSignalAdapter:
        configuration = self._player_config()
        batch_samples = int(getattr(configuration, "chunk_samples", 1024))
        return _PlotSignalAdapter(
            plot,
            sample_rate=self.sample_rate,
            period=self.loop_seconds,
            batch_samples=batch_samples,
            value_tolerance=self.value_tolerance,
        )

    def _player_config(self) -> Any:
        _, player_config_class = _load_player_runtime()
        return player_config_class(
            sample_rate=self.sample_rate,
            period_duration=self.loop_seconds,
            gain=1.0,
            auto_normalize=False,
        )

    def _ensure_player(self) -> Any:
        if self._player is not None:
            if self._root_widget is not None and not self._player_embedded:
                self._embed_player_widget(self._player)
            return self._player

        player_class, _ = _load_player_runtime()
        player = player_class(
            configuration=self._player_config(),
            auto_display=False,
        )
        self._player = player
        player.observe(self._handle_player_trait_change, names=["playback_state", "last_error"])
        if self._root_widget is not None:
            self._embed_player_widget(player)
        return player

    def _embed_player_widget(self, player: Any) -> None:
        if self._root_widget is None:
            return
        try:
            children = tuple(getattr(self._root_widget, "children", ()) or ())
            if player not in children:
                self._root_widget.children = children + (player,)
        except Exception:
            return
        mark_embedded = getattr(player, "mark_embedded", None)
        if callable(mark_embedded):
            mark_embedded()
        self._player_embedded = True

    def _detach_player_widget(self, player: Any) -> None:
        if self._root_widget is None:
            return
        try:
            children = tuple(getattr(self._root_widget, "children", ()) or ())
            filtered = tuple(child for child in children if child is not player)
            if filtered != children:
                self._root_widget.children = filtered
        except Exception:
            return
        self._player_embedded = False

    @contextmanager
    def _suppress_player_observers(self):
        self._player_state_observer_guard += 1
        try:
            yield
        finally:
            self._player_state_observer_guard = max(0, self._player_state_observer_guard - 1)

    def _handle_player_trait_change(self, _change: Any) -> None:
        if self._player_state_observer_guard > 0 or self._active_plot_id is None:
            return
        player = self._player
        if player is None:
            return

        playback_state = str(getattr(player, "playback_state", ""))
        last_error = str(getattr(player, "last_error", "") or "")
        if last_error or playback_state in {"error", "stopped"}:
            self._active_plot_id = None
            self._active_signal_adapter = None
            self._legend.set_sound_playing_plot(None)

    def _stop_player(self) -> None:
        player = self._player
        self._active_plot_id = None
        self._active_signal_adapter = None
        self._legend.set_sound_playing_plot(None)
        if player is None:
            return
        with self._suppress_player_observers():
            player.stop()


__all__ = ["FigureSoundManager"]
