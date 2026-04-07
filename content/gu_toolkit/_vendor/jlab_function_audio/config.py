"""jlab_function_audio.config
=================================

Validated public configuration for the JupyterLab callable-audio engine.

Architecture
------------
The package separates configuration from playback logic so that the transport
engine, phase matcher, and browser widget can share one immutable source of
truth.  `PlayerConfiguration` stores all timing, buffering, gain, and
phase-matching parameters in plain Python data structures.  The
`FunctionAudioPlayer` constructor accepts either this dataclass directly or the
same values as keyword arguments and then mirrors the validated values into
traitlets for the browser-facing widget.

Functionality
-------------
The module provides:

- a curated tuple of standard sample rates,
- a validator that enforces the "use standard sampling rates" requirement,
- an immutable dataclass describing the player's timing and phase-matching
  behavior.

Main implementation notes
-------------------------
The configuration is intentionally conservative:

- 48 kHz is the default sample rate,
- chunks are short enough to allow low-latency updates,
- lookahead stays small to keep function swaps responsive,
- attack and release remain short but non-zero to suppress clicks,
- crossfade and phase-search parameters are exposed so advanced users can tune
  trade-offs between latency and robustness.

Examples
--------
Create a custom configuration and pass it to the player:

>>> from jlab_function_audio.config import PlayerConfiguration
>>> cfg = PlayerConfiguration(sample_rate=48000, chunk_duration=0.025)
>>> cfg.chunk_samples
1200
>>> round(cfg.actual_chunk_duration, 6)
0.025

Attempting to use a non-standard sample rate raises an informative error:

>>> PlayerConfiguration(sample_rate=47000)
Traceback (most recent call last):
...
ValueError: sample_rate must be one of
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp

STANDARD_SAMPLE_RATES: tuple[int, ...] = (
    8000,
    11025,
    16000,
    22050,
    32000,
    44100,
    48000,
    88200,
    96000,
)


def validate_sample_rate(sample_rate: int) -> int:
    """Validate that a requested sample rate is a commonly used standard rate.

    Parameters
    ----------
    sample_rate:
        Integer sample rate in hertz requested by the caller.

    Returns
    -------
    int
        The validated sample rate. The function returns the input unchanged when
        it is one of the supported standard rates.

    Raises
    ------
    ValueError
        Raised when `sample_rate` is not one of the curated standard rates.

    Examples
    --------
    Accept a standard rate:

    >>> validate_sample_rate(48000)
    48000

    Reject a non-standard rate:

    >>> validate_sample_rate(47000)
    Traceback (most recent call last):
    ...
    ValueError: sample_rate must be one of
    """
    if int(sample_rate) not in STANDARD_SAMPLE_RATES:
        raise ValueError(
            "sample_rate must be one of "
            f"{STANDARD_SAMPLE_RATES}, received {sample_rate!r}."
        )
    return int(sample_rate)


@dataclass(frozen=True, slots=True)
class PlayerConfiguration:
    """Immutable configuration for :class:`jlab_function_audio.FunctionAudioPlayer`.

    Parameters
    ----------
    sample_rate:
        Output sample rate in hertz. The value must be one of
        :data:`STANDARD_SAMPLE_RATES`.
    chunk_duration:
        Length of one rendered audio chunk in seconds. Shorter chunks reduce the
        audible latency of `set_function(...)` updates but increase messaging
        overhead.
    lookahead_duration:
        Amount of audio, in seconds, that the Python pump tries to keep queued
        in the browser. This is the primary latency budget for live function
        swaps.
    attack_duration:
        Small fade-in used when playback starts or when a seek flushes the
        browser queue.
    release_duration:
        Small fade-out used when playback stops.
    crossfade_duration:
        Duration of the crossfade applied to the first chunk rendered after a
        live function replacement.
    period_duration:
        Visible period of the transport in seconds. The request requires a
        100-second loop, so the default and typical value is `100.0`.
    gain:
        Master output gain applied in the browser. The signal callable itself
        should still return values in ``[-1, 1]``.
    pump_interval:
        Sleep interval for the Python background pump thread. Smaller values
        improve responsiveness but wake the thread more often.
    phase_search_candidates:
        Number of coarse candidate function times considered by the phase
        matcher when a new callable is installed.
    phase_top_candidates:
        Number of the best coarse candidates refined with the more expensive
        local objective.
    phase_shape_window:
        Forward comparison window, in seconds, used by the phase matcher.
    phase_shape_samples:
        Number of samples taken inside the forward comparison window.

    Returns
    -------
    PlayerConfiguration
        An immutable configuration object with validated timing and sample-rate
        values. Convenience properties such as :attr:`chunk_samples` and
        :attr:`actual_chunk_duration` are derived from these values.

    Notes
    -----
    The dataclass is frozen so it can be safely shared across threads without
    accidental mutation.

    Examples
    --------
    A low-latency configuration:

    >>> cfg = PlayerConfiguration(
    ...     sample_rate=48000,
    ...     chunk_duration=0.02,
    ...     lookahead_duration=0.06,
    ... )
    >>> cfg.chunk_samples
    960
    >>> round(cfg.actual_chunk_duration, 6)
    0.02

    Tune phase matching for heavier live updates:

    >>> cfg = PlayerConfiguration(phase_search_candidates=1024, phase_top_candidates=8)
    >>> cfg.phase_search_candidates
    1024
    """

    sample_rate: int = 48000
    chunk_duration: float = 0.025
    lookahead_duration: float = 0.075
    attack_duration: float = 0.01
    release_duration: float = 0.02
    crossfade_duration: float = 0.012
    period_duration: float = 100.0
    gain: float = 0.18
    auto_normalize: bool = False
    normalization_dc_time_constant: float = 0.05
    normalization_attack_lookahead_duration: float = 0.025
    normalization_release_time_constant: float = 0.35
    pump_interval: float = 0.01
    phase_search_candidates: int = 2048
    phase_top_candidates: int = 12
    phase_shape_window: float = 0.03
    phase_shape_samples: int = 32

    def __post_init__(self) -> None:
        """Validate the configuration after dataclass construction.

        Parameters
        ----------
        None

        Returns
        -------
        None
            The method mutates nothing because the dataclass is frozen. It
            raises when validation fails.

        Examples
        --------
        The method runs automatically when the dataclass is instantiated:

        >>> cfg = PlayerConfiguration()
        >>> cfg.sample_rate
        48000
        """
        sample_rate = validate_sample_rate(self.sample_rate)

        if self.chunk_duration <= 0:
            raise ValueError("chunk_duration must be strictly positive.")
        if self.lookahead_duration <= 0:
            raise ValueError("lookahead_duration must be strictly positive.")
        if self.lookahead_duration < self.chunk_duration:
            raise ValueError(
                "lookahead_duration must be greater than or equal to chunk_duration."
            )
        if self.attack_duration < 0:
            raise ValueError("attack_duration must be non-negative.")
        if self.release_duration < 0:
            raise ValueError("release_duration must be non-negative.")
        if self.crossfade_duration < 0:
            raise ValueError("crossfade_duration must be non-negative.")
        if self.crossfade_duration > self.chunk_duration:
            raise ValueError(
                "crossfade_duration must be less than or equal to chunk_duration."
            )
        if self.period_duration <= 0:
            raise ValueError("period_duration must be strictly positive.")
        if self.gain < 0:
            raise ValueError("gain must be non-negative.")
        if self.normalization_dc_time_constant <= 0:
            raise ValueError("normalization_dc_time_constant must be strictly positive.")
        if self.normalization_attack_lookahead_duration <= 0:
            raise ValueError(
                "normalization_attack_lookahead_duration must be strictly positive."
            )
        if self.normalization_release_time_constant <= 0:
            raise ValueError(
                "normalization_release_time_constant must be strictly positive."
            )
        if self.pump_interval <= 0:
            raise ValueError("pump_interval must be strictly positive.")
        if self.phase_search_candidates <= 0:
            raise ValueError("phase_search_candidates must be strictly positive.")
        if self.phase_top_candidates <= 0:
            raise ValueError("phase_top_candidates must be strictly positive.")
        if self.phase_top_candidates > self.phase_search_candidates:
            raise ValueError(
                "phase_top_candidates must be less than or equal to "
                "phase_search_candidates."
            )
        if self.phase_shape_window <= 0:
            raise ValueError("phase_shape_window must be strictly positive.")
        if self.phase_shape_samples <= 1:
            raise ValueError("phase_shape_samples must be greater than one.")

        object.__setattr__(self, "sample_rate", sample_rate)

    @property
    def chunk_samples(self) -> int:
        """Return the integer number of samples rendered in one audio chunk.

        Parameters
        ----------
        None

        Returns
        -------
        int
            The rounded integer number of samples produced in one chunk at the
            configured sample rate.

        Examples
        --------
        >>> PlayerConfiguration(sample_rate=48000, chunk_duration=0.025).chunk_samples
        1200
        """
        return int(round(self.sample_rate * self.chunk_duration))

    @property
    def actual_chunk_duration(self) -> float:
        """Return the exact chunk duration implied by :attr:`chunk_samples`.

        Parameters
        ----------
        None

        Returns
        -------
        float
            The exact chunk duration after converting the requested duration to
            an integer number of samples.

        Examples
        --------
        >>> cfg = PlayerConfiguration(sample_rate=44100, chunk_duration=0.01)
        >>> round(cfg.actual_chunk_duration, 8)
        0.01
        """
        return self.chunk_samples / float(self.sample_rate)

    @property
    def crossfade_samples(self) -> int:
        """Return the number of samples used by the function-swap crossfade.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Number of samples included in the first-chunk crossfade after a live
            `set_function(...)` update.

        Examples
        --------
        >>> PlayerConfiguration(sample_rate=48000, crossfade_duration=0.012).crossfade_samples
        576
        """
        return int(round(self.sample_rate * self.crossfade_duration))


    @property
    def normalization_attack_lookahead_samples(self) -> int:
        """Return the bounded autonormalization lookahead in samples.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Positive integer number of samples used by the forward local-peak
            analysis window. The current sample is always included, so the
            value is never smaller than one.
        """
        return max(1, int(round(self.sample_rate * self.normalization_attack_lookahead_duration)))

    @property
    def normalization_release_decay_per_sample(self) -> float:
        """Return the per-sample exponential decay used by release memory.

        Parameters
        ----------
        None

        Returns
        -------
        float
            Multiplicative decay in ``(0, 1)`` applied to the attenuation
            memory on samples where the local target is falling.
        """
        return float(
            exp(-1.0 / (float(self.sample_rate) * float(self.normalization_release_time_constant)))
        )

    @property
    def normalization_dc_alpha(self) -> float:
        """Return the one-pole coefficient used by the local DC estimator.

        Parameters
        ----------
        None

        Returns
        -------
        float
            Exponential smoothing factor in ``(0, 1)`` used by the local DC
            estimate in the autonormalized render path.
        """
        return float(exp(-1.0 / (float(self.sample_rate) * float(self.normalization_dc_time_constant))))
