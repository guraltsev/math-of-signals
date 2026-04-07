"""jlab_function_audio
=======================

Background callable audio for JupyterLab.

Architecture
------------
The package is intentionally split into small layers:

- :mod:`jlab_function_audio.config` defines validated immutable configuration.
- :mod:`jlab_function_audio.sampling` renders periodic mono float32 chunks from
  ordinary Python callables.
- :mod:`jlab_function_audio.matching` chooses phase offsets for live callable
  replacement.
- :mod:`jlab_function_audio.player` combines those pieces with an AnyWidget
  front end so JupyterLab can schedule sound in the browser through a hidden helper.

Functionality
-------------
The public API centers on :class:`FunctionAudioPlayer` and the phase-matching
utilities used by that player.  Together they implement the requested feature
set:

- set the signal callable after construction,
- play, stop, restart, and seek through a fixed 100-second period,
- buffer only small chunks ahead of playback,
- swap callables while running with phase matching and click suppression.

Main implementation notes
-------------------------
The player itself depends on :mod:`anywidget` and :mod:`ipywidgets`.  The module
keeps the rest of the package importable even when those optional runtime
dependencies are missing, so notebook-independent helpers such as
:func:`phase_match_functions` can still be imported and documented.

Examples
--------
Use the player in a notebook:

>>> import math
>>> from jlab_function_audio import FunctionAudioPlayer
>>> player = FunctionAudioPlayer()
>>> _ = player.set_function(lambda t: 0.25 * math.sin(2 * math.pi * 220.0 * t))
>>> isinstance(player.configuration.sample_rate, int)
True
"""
from __future__ import annotations

from .config import PlayerConfiguration, STANDARD_SAMPLE_RATES, validate_sample_rate
from .matching import PhaseMatchResult, phase_match_functions
from .normalization import (
    AutoNormalizationDiagnostics,
    AutoNormalizationState,
    apply_autonormalization,
)
from .sampling import (
    SignalCallable,
    approximate_derivative,
    clip_audio_chunk,
    crossfade_chunks,
    crossfade_chunks_raw,
    evaluate_signal,
    evaluate_signal_raw,
    generate_chunk,
    generate_raw_chunk,
    wrap_periodic_time,
)

__version__ = "0.1.5"


try:
    from .player import FunctionAudioPlayer
except ModuleNotFoundError as exc:  # pragma: no cover - only used without widget deps.
    if exc.name not in {"anywidget", "ipywidgets"}:
        raise

    _widget_dependency_import_error = exc

    class FunctionAudioPlayer:  # type: ignore[override]
        """Fallback placeholder shown when widget dependencies are missing.

        Parameters
        ----------
        *args, **kwargs:
            Ignored. The constructor always raises a :class:`ModuleNotFoundError`
            explaining which extra packages are required.

        Returns
        -------
        FunctionAudioPlayer
            This class never returns an instance; it raises immediately.

        Examples
        --------
        >>> try:
        ...     FunctionAudioPlayer()
        ... except ModuleNotFoundError as exc:
        ...     "anywidget" in str(exc)
        True
        """

        def __init__(self, *args, **kwargs) -> None:
            """Raise an informative dependency error.

            Parameters
            ----------
            *args, **kwargs:
                Ignored. They are accepted so the fallback mirrors the real
                constructor signature loosely enough for error reporting.

            Returns
            -------
            None
                The method never returns because it raises immediately.

            Examples
            --------
            >>> try:
            ...     FunctionAudioPlayer()
            ... except ModuleNotFoundError as exc:
            ...     "anywidget" in str(exc)
            True
            """
            raise ModuleNotFoundError(
                "FunctionAudioPlayer requires the optional widget dependencies "
                "`anywidget>=0.9.0` and `ipywidgets>=8.1.0`. Install the package "
                "with `pip install jlab-function-audio` or install those "
                "dependencies explicitly."
            ) from _widget_dependency_import_error


__all__ = [
    "AutoNormalizationDiagnostics",
    "AutoNormalizationState",
    "FunctionAudioPlayer",
    "PhaseMatchResult",
    "PlayerConfiguration",
    "STANDARD_SAMPLE_RATES",
    "SignalCallable",
    "__version__",
    "apply_autonormalization",
    "approximate_derivative",
    "clip_audio_chunk",
    "crossfade_chunks",
    "crossfade_chunks_raw",
    "evaluate_signal",
    "evaluate_signal_raw",
    "generate_chunk",
    "generate_raw_chunk",
    "phase_match_functions",
    "validate_sample_rate",
    "wrap_periodic_time",
]
