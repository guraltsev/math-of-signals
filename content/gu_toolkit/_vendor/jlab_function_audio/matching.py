"""jlab_function_audio.matching
================================

Phase matching for live callable replacement.

Architecture
------------
When the user calls :meth:`jlab_function_audio.FunctionAudioPlayer.set_function`
during playback, the new callable cannot simply begin at time zero.  Doing so
would usually create a discontinuity at the chunk boundary, which is heard as a
click.  This module implements the matching layer that chooses a phase offset
for the incoming callable before the player renders the first replacement chunk.

Functionality
-------------
The public entry point is :func:`phase_match_functions`.  It searches the
incoming callable over the fixed 100-second period and selects the function time
that best matches the signal already in flight.  The score combines three
components:

1. boundary value error,
2. boundary slope error,
3. short forward-window shape error.

The player then uses the returned phase offset for future chunks and applies a
short crossfade on the first replacement chunk to guarantee click suppression.

Main implementation notes
-------------------------
The matcher intentionally separates coarse and refined search:

- a coarse sweep is cheap and explores the whole 100-second period,
- only the best coarse candidates are refined with the more expensive
  short-window objective.

This structure keeps the algorithm fast enough for notebook interaction while
still finding musically sensible alignments for common signals such as sines,
FM tones, and additive spectra.

Examples
--------
Match a replacement sine to the currently playing sine:

>>> import math
>>> old = lambda t: math.sin(2 * math.pi * 220.0 * t)
>>> new = lambda t: 0.7 * math.sin(2 * math.pi * 220.0 * t) + 0.2 * math.sin(2 * math.pi * 440.0 * t)
>>> result = phase_match_functions(
...     current_function=old,
...     next_function=new,
...     current_phase_offset=0.0,
...     anchor_transport_time=12.5,
...     period=100.0,
...     sample_rate=48000,
... )
>>> 0.0 <= result.phase_offset < 100.0
True
>>> result.used_phase_matching
True
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .sampling import (
    SignalCallable,
    approximate_derivative,
    evaluate_signal,
    evaluate_signal_raw,
    wrap_periodic_time,
)


@dataclass(frozen=True, slots=True)
class PhaseMatchResult:
    """Description of one phase-matching decision.

    Parameters
    ----------
    phase_offset:
        Phase offset, in seconds, that should be added to future transport times
        before the incoming callable is sampled.
    matched_function_time:
        Point inside the incoming callable's period that best matches the
        outgoing signal at the transition anchor.
    anchor_transport_time:
        Unwrapped transport time at which the transition begins.
    coarse_score:
        Score of the best candidate from the coarse global search.
    refined_score:
        Score of the final refined candidate after local search.
    value_error:
        Squared boundary value mismatch used by the final objective.
    slope_error:
        Normalized squared boundary slope mismatch used by the final objective.
    shape_error:
        Mean squared error over the short forward comparison window.
    used_phase_matching:
        Flag indicating whether an actual match was computed. Initial function
        installation and explicit opt-out can return a result with this set to
        ``False``.
    candidates_evaluated:
        Number of coarse candidates considered by the search.
    notes:
        Short human-readable explanation of the decision.

    Returns
    -------
    PhaseMatchResult
        Immutable result object suitable for logging, notebook display, or
        post-hoc diagnostics.

    Examples
    --------
    Build a placeholder result when phase matching is not needed:

    >>> result = PhaseMatchResult.no_match(anchor_transport_time=0.0, notes="initial function")
    >>> result.used_phase_matching
    False
    >>> result.phase_offset
    0.0
    """

    phase_offset: float
    matched_function_time: float
    anchor_transport_time: float
    coarse_score: float
    refined_score: float
    value_error: float
    slope_error: float
    shape_error: float
    used_phase_matching: bool
    candidates_evaluated: int
    notes: str = ""

    @classmethod
    def no_match(
        cls,
        *,
        anchor_transport_time: float,
        notes: str,
        phase_offset: float = 0.0,
    ) -> "PhaseMatchResult":
        """Create a placeholder result for cases without active phase matching.

        Parameters
        ----------
        anchor_transport_time:
            Transport time, in seconds, at which the new callable becomes
            current.
        notes:
            Human-readable explanation, for example ``"initial function"`` or
            ``"phase matching disabled"``.
        phase_offset:
            Phase offset that should still be used. The default of ``0.0`` is
            appropriate for most non-matched updates.

        Returns
        -------
        PhaseMatchResult
            Result object with all error fields set to zero and
            :attr:`used_phase_matching` set to ``False``.

        Examples
        --------
        >>> result = PhaseMatchResult.no_match(
        ...     anchor_transport_time=5.0,
        ...     notes="phase matching disabled",
        ... )
        >>> result.used_phase_matching
        False
        >>> result.notes
        'phase matching disabled'
        """
        return cls(
            phase_offset=float(phase_offset),
            matched_function_time=float(phase_offset),
            anchor_transport_time=float(anchor_transport_time),
            coarse_score=0.0,
            refined_score=0.0,
            value_error=0.0,
            slope_error=0.0,
            shape_error=0.0,
            used_phase_matching=False,
            candidates_evaluated=0,
            notes=notes,
        )

    def summary(self) -> str:
        """Return a compact human-readable summary of the match.

        Parameters
        ----------
        None

        Returns
        -------
        str
            One-line textual description suitable for notebook output or widget
            status text.

        Examples
        --------
        >>> result = PhaseMatchResult.no_match(anchor_transport_time=0.0, notes="initial function")
        >>> result.summary()
        'initial function'
        """
        if not self.used_phase_matching:
            return self.notes or "phase matching was not used"

        return (
            "phase offset="
            f"{self.phase_offset:.6f}s | value error={self.value_error:.6e} | "
            f"slope error={self.slope_error:.6e} | shape error={self.shape_error:.6e}"
        )


_VALID_COMPARISON_MODES = {"clipped", "centered_unit_peak"}


@dataclass(frozen=True, slots=True)
class _CenteredUnitPeakFeatures:
    """Local DC- and scale-insensitive comparison features for phase matching."""

    boundary_value: float
    slope: float
    window: np.ndarray


def _validate_comparison_mode(comparison_mode: str) -> str:
    """Return a supported comparison mode or raise ``ValueError``."""
    normalized = str(comparison_mode)
    if normalized not in _VALID_COMPARISON_MODES:
        raise ValueError(
            "comparison_mode must be one of "
            f"{tuple(sorted(_VALID_COMPARISON_MODES))}, received {comparison_mode!r}."
        )
    return normalized


def _approximate_derivative_raw(
    function: SignalCallable,
    *,
    time_seconds: float,
    period: float,
    delta: float,
) -> float:
    """Estimate a derivative from the unclipped callable domain."""
    if delta <= 0:
        raise ValueError("delta must be strictly positive.")

    t_minus = float(wrap_periodic_time([time_seconds - delta], period)[0])
    t_plus = float(wrap_periodic_time([time_seconds + delta], period)[0])
    value_minus = float(evaluate_signal_raw(function, [t_minus])[0])
    value_plus = float(evaluate_signal_raw(function, [t_plus])[0])
    return (value_plus - value_minus) / (2.0 * delta)


def _center_and_unit_peak_scale(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Subtract the local mean and scale a window to unit peak for comparison."""
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return np.zeros(0, dtype=np.float64), 0.0, 1.0

    local_mean = float(np.mean(array, dtype=np.float64))
    centered = array - local_mean
    local_peak = float(np.max(np.abs(centered)))
    scale = local_peak if local_peak > 1e-12 else 1.0
    return centered / scale, local_mean, scale


def _extract_centered_unit_peak_features(
    function: SignalCallable,
    *,
    anchor_time: float,
    period: float,
    derivative_delta: float,
    shape_window: float,
    shape_samples: int,
) -> _CenteredUnitPeakFeatures:
    """Extract local comparison features after centering and unit-peak scaling."""
    window_offsets = np.linspace(
        0.0,
        shape_window,
        int(shape_samples),
        endpoint=False,
        dtype=np.float64,
    )
    window_times = wrap_periodic_time(anchor_time + window_offsets, period)
    raw_window = evaluate_signal_raw(function, window_times)
    normalized_window, local_mean, local_scale = _center_and_unit_peak_scale(raw_window)
    raw_boundary_value = float(raw_window[0]) if raw_window.size else 0.0
    raw_slope = _approximate_derivative_raw(
        function,
        time_seconds=anchor_time,
        period=period,
        delta=derivative_delta,
    )
    boundary_value = (raw_boundary_value - local_mean) / local_scale
    slope = raw_slope / local_scale
    return _CenteredUnitPeakFeatures(
        boundary_value=float(boundary_value),
        slope=float(slope),
        window=normalized_window,
    )


def _score_candidate_centered_unit_peak(
    *,
    current_features: _CenteredUnitPeakFeatures,
    next_function: SignalCallable,
    candidate_function_time: float,
    period: float,
    derivative_delta: float,
    slope_scale: float,
    shape_window: float,
    shape_samples: int,
    slope_weight: float,
    shape_weight: float,
) -> tuple[float, float, float, float]:
    """Score one candidate with local DC- and scale-insensitive comparison."""
    next_features = _extract_centered_unit_peak_features(
        next_function,
        anchor_time=candidate_function_time,
        period=period,
        derivative_delta=derivative_delta,
        shape_window=shape_window,
        shape_samples=shape_samples,
    )
    value_error = (next_features.boundary_value - current_features.boundary_value) ** 2
    slope_error = ((next_features.slope - current_features.slope) / slope_scale) ** 2
    shape_error = float(np.mean((next_features.window - current_features.window) ** 2))
    total = float(value_error + slope_weight * slope_error + shape_weight * shape_error)
    return total, float(value_error), float(slope_error), float(shape_error)


def _score_candidate(
    *,
    current_function: SignalCallable,
    next_function: SignalCallable,
    current_anchor_time: float,
    candidate_function_time: float,
    period: float,
    derivative_delta: float,
    slope_scale: float,
    shape_window: float,
    shape_samples: int,
    slope_weight: float,
    shape_weight: float,
) -> tuple[float, float, float, float]:
    """Compute the full objective for one refined candidate.

    Parameters
    ----------
    current_function:
        Callable currently represented in the already-scheduled audio.
    next_function:
        Replacement callable being matched.
    current_anchor_time:
        Wrapped function time inside `current_function` at the transition anchor.
    candidate_function_time:
        Wrapped function time inside `next_function` being tested.
    period:
        Period used to wrap times for both callables.
    derivative_delta:
        Central-difference step in seconds.
    slope_scale:
        Positive scale factor used to normalize slope mismatch.
    shape_window:
        Forward time window, in seconds, used for shape comparison.
    shape_samples:
        Number of samples taken inside the forward comparison window.
    slope_weight:
        Weight applied to the normalized slope error.
    shape_weight:
        Weight applied to the forward-window mean squared error.

    Returns
    -------
    tuple[float, float, float, float]
        Four floats: total score, boundary value error, normalized slope error,
        and shape error.

    Examples
    --------
    The helper is primarily internal, but it returns a fully expanded objective:

    >>> import math
    >>> old = lambda t: math.sin(2 * math.pi * t)
    >>> new = lambda t: math.sin(2 * math.pi * t)
    >>> score, value_error, slope_error, shape_error = _score_candidate(
    ...     current_function=old,
    ...     next_function=new,
    ...     current_anchor_time=0.0,
    ...     candidate_function_time=0.0,
    ...     period=100.0,
    ...     derivative_delta=1e-6,
    ...     slope_scale=1.0,
    ...     shape_window=0.01,
    ...     shape_samples=8,
    ...     slope_weight=0.01,
    ...     shape_weight=0.5,
    ... )
    >>> round(score, 8)
    0.0
    """
    current_value = float(evaluate_signal(current_function, [current_anchor_time])[0])
    next_value = float(evaluate_signal(next_function, [candidate_function_time])[0])
    value_error = (next_value - current_value) ** 2

    current_slope = approximate_derivative(
        current_function,
        time_seconds=current_anchor_time,
        period=period,
        delta=derivative_delta,
    )
    next_slope = approximate_derivative(
        next_function,
        time_seconds=candidate_function_time,
        period=period,
        delta=derivative_delta,
    )
    slope_error = ((next_slope - current_slope) / slope_scale) ** 2

    window_offsets = np.linspace(
        0.0,
        shape_window,
        int(shape_samples),
        endpoint=False,
        dtype=np.float64,
    )
    current_window_times = wrap_periodic_time(current_anchor_time + window_offsets, period)
    next_window_times = wrap_periodic_time(candidate_function_time + window_offsets, period)
    current_window = evaluate_signal(current_function, current_window_times)
    next_window = evaluate_signal(next_function, next_window_times)
    shape_error = float(np.mean((next_window - current_window) ** 2))

    total = float(value_error + slope_weight * slope_error + shape_weight * shape_error)
    return total, float(value_error), float(slope_error), float(shape_error)


def _refine_candidates(
    *,
    coarse_candidates: Iterable[float],
    step: float,
    current_function: SignalCallable,
    next_function: SignalCallable,
    current_anchor_time: float,
    period: float,
    derivative_delta: float,
    slope_scale: float,
    shape_window: float,
    shape_samples: int,
    slope_weight: float,
    shape_weight: float,
    refinement_rounds: int = 4,
    local_points: int = 17,
    comparison_mode: str = "clipped",
    current_centered_features: _CenteredUnitPeakFeatures | None = None,
) -> tuple[float, float, float, float, float]:
    """Refine a shortlist of coarse candidates with a local search.

    Parameters
    ----------
    coarse_candidates:
        Iterable of wrapped function times selected by the coarse global sweep.
    step:
        Spacing, in seconds, between neighboring coarse candidates. The local
        search starts with this width and shrinks it on each refinement round.
    current_function:
        Outgoing callable.
    next_function:
        Incoming callable.
    current_anchor_time:
        Wrapped current-function time at the transition anchor.
    period:
        Loop period in seconds.
    derivative_delta:
        Central-difference step in seconds.
    slope_scale:
        Positive scale factor used to normalize slope mismatch.
    shape_window:
        Forward comparison window in seconds.
    shape_samples:
        Number of samples used inside the comparison window.
    slope_weight:
        Weight applied to slope mismatch.
    shape_weight:
        Weight applied to forward-window mismatch.
    refinement_rounds:
        Number of local shrinking-grid rounds.
    local_points:
        Number of points evaluated in each local grid.

    Returns
    -------
    tuple[float, float, float, float, float]
        Total score, matched function time, value error, slope error, and shape
        error for the best refined candidate.

    Examples
    --------
    The helper is internal; the public API normally calls it for you:

    >>> import math
    >>> old = lambda t: math.sin(2 * math.pi * t)
    >>> new = lambda t: math.sin(2 * math.pi * t)
    >>> score, matched_time, value_error, slope_error, shape_error = _refine_candidates(
    ...     coarse_candidates=[0.0],
    ...     step=0.1,
    ...     current_function=old,
    ...     next_function=new,
    ...     current_anchor_time=0.0,
    ...     period=100.0,
    ...     derivative_delta=1e-6,
    ...     slope_scale=1.0,
    ...     shape_window=0.01,
    ...     shape_samples=8,
    ...     slope_weight=0.01,
    ...     shape_weight=0.5,
    ... )
    >>> round(score, 8)
    0.0
    >>> round(matched_time, 8)
    0.0
    """
    best_score = float("inf")
    best_time = 0.0
    best_value_error = 0.0
    best_slope_error = 0.0
    best_shape_error = 0.0

    for coarse_time in coarse_candidates:
        center = float(coarse_time)
        span = float(step)

        for _ in range(int(refinement_rounds)):
            local_times = np.linspace(center - span, center + span, int(local_points))
            local_times = wrap_periodic_time(local_times, period)

            local_best = None
            for candidate_time in local_times:
                if comparison_mode == "clipped":
                    candidate_score = _score_candidate(
                        current_function=current_function,
                        next_function=next_function,
                        current_anchor_time=current_anchor_time,
                        candidate_function_time=float(candidate_time),
                        period=period,
                        derivative_delta=derivative_delta,
                        slope_scale=slope_scale,
                        shape_window=shape_window,
                        shape_samples=shape_samples,
                        slope_weight=slope_weight,
                        shape_weight=shape_weight,
                    )
                else:
                    assert current_centered_features is not None
                    candidate_score = _score_candidate_centered_unit_peak(
                        current_features=current_centered_features,
                        next_function=next_function,
                        candidate_function_time=float(candidate_time),
                        period=period,
                        derivative_delta=derivative_delta,
                        slope_scale=slope_scale,
                        shape_window=shape_window,
                        shape_samples=shape_samples,
                        slope_weight=slope_weight,
                        shape_weight=shape_weight,
                    )
                if local_best is None or candidate_score[0] < local_best[0]:
                    local_best = (candidate_score[0], float(candidate_time), *candidate_score[1:])

            assert local_best is not None
            _, center, value_error, slope_error, shape_error = local_best
            span /= 4.0

        if local_best is not None and local_best[0] < best_score:
            best_score, best_time, best_value_error, best_slope_error, best_shape_error = local_best

    return (
        float(best_score),
        float(best_time),
        float(best_value_error),
        float(best_slope_error),
        float(best_shape_error),
    )


def phase_match_functions(
    *,
    current_function: SignalCallable,
    next_function: SignalCallable,
    current_phase_offset: float,
    anchor_transport_time: float,
    period: float,
    sample_rate: int,
    coarse_candidates: int = 2048,
    top_candidates: int = 12,
    shape_window: float = 0.03,
    shape_samples: int = 32,
    slope_weight: float = 0.01,
    shape_weight: float = 0.5,
    derivative_delta: float | None = None,
    comparison_mode: str = "clipped",
) -> PhaseMatchResult:
    """Choose a phase offset for a replacement callable.

    Parameters
    ----------
    current_function:
        Callable currently represented in the already-scheduled audio.
    next_function:
        Callable that should replace `current_function`.
    current_phase_offset:
        Phase offset currently applied to `current_function`.
    anchor_transport_time:
        Unwrapped transport time, in seconds, at which the replacement should
        begin.
    period:
        Period of the callable domain in seconds. The request uses a fixed value
        of 100 seconds.
    sample_rate:
        Sample rate used by the player. This sets the default
        central-difference step when `derivative_delta` is not supplied.
    coarse_candidates:
        Number of function times from the incoming callable considered in the
        initial global sweep.
    top_candidates:
        Number of best coarse candidates refined by the local search.
    shape_window:
        Forward comparison window in seconds. Larger windows favor continuity of
        short waveform shape, while smaller windows focus more strongly on the
        exact boundary.
    shape_samples:
        Number of samples taken within `shape_window`.
    slope_weight:
        Weight applied to the normalized squared slope mismatch.
    shape_weight:
        Weight applied to the forward-window mean squared error.
    derivative_delta:
        Optional custom central-difference step. When omitted, the function uses
        one audio sample interval.
    comparison_mode:
        Comparison domain used by the matcher. The default ``"clipped"`` keeps
        legacy behavior. ``"centered_unit_peak"`` compares local windows after
        subtracting their mean and scaling them to unit peak so DC and gross
        scale differences do not dominate phase selection.

    Returns
    -------
    PhaseMatchResult
        Immutable description of the chosen phase offset and the associated
        objective terms.

    Raises
    ------
    ValueError
        Raised when the candidate counts or timing arguments are invalid.

    Notes
    -----
    The returned phase offset is intended to be applied as:

    ``incoming_callable((transport_time + phase_offset) % period)``

    Examples
    --------
    Match two related waveforms:

    >>> import math
    >>> old = lambda t: math.sin(2 * math.pi * 220.0 * t)
    >>> new = lambda t: 0.8 * math.sin(2 * math.pi * 220.0 * t) + 0.1 * math.sin(2 * math.pi * 440.0 * t)
    >>> result = phase_match_functions(
    ...     current_function=old,
    ...     next_function=new,
    ...     current_phase_offset=0.0,
    ...     anchor_transport_time=12.5,
    ...     period=100.0,
    ...     sample_rate=48000,
    ... )
    >>> 0.0 <= result.phase_offset < 100.0
    True
    >>> result.used_phase_matching
    True
    """
    if period <= 0:
        raise ValueError("period must be strictly positive.")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be strictly positive.")
    if coarse_candidates <= 0:
        raise ValueError("coarse_candidates must be strictly positive.")
    if top_candidates <= 0:
        raise ValueError("top_candidates must be strictly positive.")
    if top_candidates > coarse_candidates:
        raise ValueError("top_candidates must be less than or equal to coarse_candidates.")
    if shape_window <= 0:
        raise ValueError("shape_window must be strictly positive.")
    if shape_samples <= 1:
        raise ValueError("shape_samples must be greater than one.")

    derivative_delta = float(derivative_delta or (1.0 / float(sample_rate)))
    comparison_mode = _validate_comparison_mode(comparison_mode)
    current_anchor_time = float(
        wrap_periodic_time([anchor_transport_time + current_phase_offset], period)[0]
    )

    if comparison_mode == "centered_unit_peak":
        current_features = _extract_centered_unit_peak_features(
            current_function,
            anchor_time=current_anchor_time,
            period=period,
            derivative_delta=derivative_delta,
            shape_window=shape_window,
            shape_samples=shape_samples,
        )
        slope_scale = max(1.0, abs(current_features.slope))
        coarse_times = np.linspace(
            0.0,
            period,
            int(coarse_candidates),
            endpoint=False,
            dtype=np.float64,
        )
        coarse_scores = np.empty(coarse_times.shape[0], dtype=np.float64)
        for index, candidate_time in enumerate(coarse_times):
            coarse_scores[index] = _score_candidate_centered_unit_peak(
                current_features=current_features,
                next_function=next_function,
                candidate_function_time=float(candidate_time),
                period=period,
                derivative_delta=derivative_delta,
                slope_scale=slope_scale,
                shape_window=shape_window,
                shape_samples=shape_samples,
                slope_weight=slope_weight,
                shape_weight=shape_weight,
            )[0]

        shortlist_count = min(int(top_candidates), coarse_scores.shape[0])
        shortlist_indices = np.argpartition(coarse_scores, shortlist_count - 1)[:shortlist_count]
        shortlist_indices = shortlist_indices[np.argsort(coarse_scores[shortlist_indices])]
        shortlist_times = coarse_times[shortlist_indices]

        refined_score, matched_time, value_error, refined_slope_error, shape_error = _refine_candidates(
            coarse_candidates=shortlist_times,
            step=period / float(coarse_candidates),
            current_function=current_function,
            next_function=next_function,
            current_anchor_time=current_anchor_time,
            period=period,
            derivative_delta=derivative_delta,
            slope_scale=slope_scale,
            shape_window=shape_window,
            shape_samples=shape_samples,
            slope_weight=slope_weight,
            shape_weight=shape_weight,
            comparison_mode=comparison_mode,
            current_centered_features=current_features,
        )

        phase_offset = float((matched_time - (anchor_transport_time % period)) % period)
        best_coarse_score = float(coarse_scores[shortlist_indices[0]])

        return PhaseMatchResult(
            phase_offset=phase_offset,
            matched_function_time=float(matched_time),
            anchor_transport_time=float(anchor_transport_time),
            coarse_score=best_coarse_score,
            refined_score=float(refined_score),
            value_error=float(value_error),
            slope_error=float(refined_slope_error),
            shape_error=float(shape_error),
            used_phase_matching=True,
            candidates_evaluated=int(coarse_candidates),
            notes="phase matching completed",
        )

    current_value = float(evaluate_signal(current_function, [current_anchor_time])[0])
    current_slope = approximate_derivative(
        current_function,
        time_seconds=current_anchor_time,
        period=period,
        delta=derivative_delta,
    )
    slope_scale = max(1.0, abs(current_slope))

    coarse_times = np.linspace(0.0, period, int(coarse_candidates), endpoint=False, dtype=np.float64)
    next_values = evaluate_signal(next_function, coarse_times)

    derivative_plus = np.empty_like(next_values, dtype=np.float64)
    derivative_minus = np.empty_like(next_values, dtype=np.float64)
    for index, candidate_time in enumerate(coarse_times):
        derivative_plus[index] = float(
            evaluate_signal(next_function, [float((candidate_time + derivative_delta) % period)])[0]
        )
        derivative_minus[index] = float(
            evaluate_signal(next_function, [float((candidate_time - derivative_delta) % period)])[0]
        )

    next_slopes = (derivative_plus - derivative_minus) / (2.0 * derivative_delta)
    boundary_error = (next_values - current_value) ** 2
    slope_error = ((next_slopes - current_slope) / slope_scale) ** 2
    coarse_scores = boundary_error + slope_weight * slope_error

    shortlist_count = min(int(top_candidates), coarse_scores.shape[0])
    shortlist_indices = np.argpartition(coarse_scores, shortlist_count - 1)[:shortlist_count]
    shortlist_indices = shortlist_indices[np.argsort(coarse_scores[shortlist_indices])]
    shortlist_times = coarse_times[shortlist_indices]

    refined_score, matched_time, value_error, refined_slope_error, shape_error = _refine_candidates(
        coarse_candidates=shortlist_times,
        step=period / float(coarse_candidates),
        current_function=current_function,
        next_function=next_function,
        current_anchor_time=current_anchor_time,
        period=period,
        derivative_delta=derivative_delta,
        slope_scale=slope_scale,
        shape_window=shape_window,
        shape_samples=shape_samples,
        slope_weight=slope_weight,
        shape_weight=shape_weight,
        comparison_mode=comparison_mode,
    )

    phase_offset = float((matched_time - (anchor_transport_time % period)) % period)
    best_coarse_score = float(coarse_scores[shortlist_indices[0]])

    return PhaseMatchResult(
        phase_offset=phase_offset,
        matched_function_time=float(matched_time),
        anchor_transport_time=float(anchor_transport_time),
        coarse_score=best_coarse_score,
        refined_score=float(refined_score),
        value_error=float(value_error),
        slope_error=float(refined_slope_error),
        shape_error=float(shape_error),
        used_phase_matching=True,
        candidates_evaluated=int(coarse_candidates),
        notes="phase matching completed",
    )
