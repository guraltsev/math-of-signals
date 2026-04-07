"""jlab_function_audio.normalization
===================================

Streaming autonormalization for callable audio.

Architecture
------------
The module implements the optional Python-side autonormalization path used by
:class:`jlab_function_audio.player.FunctionAudioPlayer` when
``auto_normalize=True``. The browser stays a passive scheduler: all waveform
analysis, local DC removal, attenuation tracking, and final safety clipping
happen before the chunk is sent to JavaScript.

Non-negotiable invariants
-------------------------
The implementation is intentionally built around the following rules:

- ``auto_normalize=False`` must leave the legacy clipped render path untouched.
- The normalizer may only subtract local DC and/or attenuate. It never applies
  gain above unity to the centered signal.
- The attenuation factor ``M`` always satisfies ``M >= 1``.
- Future loudness can influence the current sample only through the bounded
  attack-lookahead window supplied to :func:`apply_autonormalization`.
- Past loudness influences the current sample only through the bounded release
  memory and local DC state stored in :class:`AutoNormalizationState`.
- The final clip to ``[-1, 1]`` remains only a safety net.

Functionality
-------------
The public entry point is :func:`apply_autonormalization`. It performs four
steps on the raw waveform that will actually be heard:

1. seed or continue a one-pole local DC estimate,
2. subtract that local DC continuously sample by sample,
3. compute a bounded forward running peak over the DC-centered signal,
4. apply one-sided attenuation with immediate attack and exponential release.

The function accepts a chunk to emit and a short chunk of future raw samples
used only for bounded lookahead analysis. The stored state is advanced through
**the emitted chunk only** so streaming results remain consistent and local.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import exp

import numpy as np

from .sampling import clip_audio_chunk


@dataclass(slots=True)
class AutoNormalizationState:
    """Mutable streaming state for the autonormalizer.

    Parameters
    ----------
    dc_estimate:
        Current one-pole estimate of local DC in the raw waveform.
    normalization_factor:
        Current attenuation factor ``M``. The value is always clamped to be at
        least ``1.0``.
    initialized:
        Flag indicating whether the state has been seeded from a real analysis
        block yet.
    """

    dc_estimate: float = 0.0
    normalization_factor: float = 1.0
    initialized: bool = False


@dataclass(frozen=True, slots=True)
class AutoNormalizationDiagnostics:
    """Lightweight diagnostics captured for one emitted chunk.

    Parameters
    ----------
    output_peak:
        Maximum absolute value of the final emitted chunk after safety clipping.
    clip_hit_count:
        Number of samples whose pre-clip value exceeded ``[-1, 1]``.
    removed_dc_estimate:
        Ending local DC estimate after the emitted chunk.
    ending_normalization_factor:
        Ending attenuation factor ``M`` after the emitted chunk.
    minimum_normalization_factor:
        Minimum ``M`` seen while processing the emitted chunk.
    maximum_normalization_factor:
        Maximum ``M`` seen while processing the emitted chunk.
    centered_input_peak:
        Maximum absolute value of the DC-centered emitted chunk before
        attenuation.
    """

    output_peak: float
    clip_hit_count: int
    removed_dc_estimate: float
    ending_normalization_factor: float
    minimum_normalization_factor: float
    maximum_normalization_factor: float
    centered_input_peak: float


def _validate_positive_parameter(name: str, value: float) -> float:
    """Return a positive floating-point parameter or raise ``ValueError``."""
    numeric = float(value)
    if numeric <= 0.0:
        raise ValueError(f"{name} must be strictly positive.")
    return numeric


def _seed_state(
    analysis_source: np.ndarray,
    *,
    sample_rate: int,
    dc_time_constant: float,
    state: AutoNormalizationState,
) -> None:
    """Seed a hard-reset state from the local mean of available raw audio."""
    seed_span = max(1, int(round(float(sample_rate) * float(dc_time_constant))))
    seed_count = min(seed_span, int(analysis_source.shape[0]))
    if seed_count > 0:
        dc_estimate = float(np.mean(analysis_source[:seed_count], dtype=np.float64))
    else:
        dc_estimate = 0.0
    state.dc_estimate = dc_estimate
    state.normalization_factor = 1.0
    state.initialized = True


def _center_analysis_with_one_pole(
    analysis_source: np.ndarray,
    *,
    alpha_dc: float,
    initial_dc_estimate: float,
    emitted_count: int,
) -> tuple[np.ndarray, float]:
    """Center a current+future analysis block with a one-pole DC estimate.

    Returns
    -------
    tuple[numpy.ndarray, float]
        The centered analysis signal for the full current+future block, and the
        DC estimate after processing only the emitted portion of the block.
    """
    centered = np.empty_like(analysis_source, dtype=np.float64)
    dc_estimate = float(initial_dc_estimate)
    dc_after_emitted = dc_estimate
    blend = 1.0 - float(alpha_dc)

    for index, sample in enumerate(analysis_source):
        dc_estimate = float(alpha_dc * dc_estimate + blend * float(sample))
        centered[index] = float(sample) - dc_estimate
        if index + 1 == emitted_count:
            dc_after_emitted = dc_estimate

    if emitted_count == 0:
        dc_after_emitted = float(initial_dc_estimate)

    return centered, float(dc_after_emitted)


def _forward_window_max_abs(values: np.ndarray, window_length: int, output_length: int) -> np.ndarray:
    """Return forward running absolute maxima for a bounded lookahead window."""
    output_length = int(output_length)
    if output_length <= 0:
        return np.zeros(0, dtype=np.float64)

    magnitudes = np.abs(np.asarray(values, dtype=np.float64))
    total = int(magnitudes.shape[0])
    window = max(1, int(window_length))
    initial_end = min(total, window)

    indices: deque[int] = deque()
    for index in range(initial_end):
        while indices and magnitudes[index] >= magnitudes[indices[-1]]:
            indices.pop()
        indices.append(index)

    result = np.empty(output_length, dtype=np.float64)
    for start in range(output_length):
        while indices and indices[0] < start:
            indices.popleft()
        result[start] = float(magnitudes[indices[0]]) if indices else 0.0

        next_index = start + window
        if next_index < total:
            while indices and magnitudes[next_index] >= magnitudes[indices[-1]]:
                indices.pop()
            indices.append(next_index)

    return result


def apply_autonormalization(
    raw_chunk: np.ndarray,
    raw_future: np.ndarray,
    *,
    sample_rate: int,
    dc_time_constant: float,
    attack_lookahead_duration: float,
    release_time_constant: float,
    state: AutoNormalizationState,
    hard_reset: bool = False,
) -> tuple[np.ndarray, AutoNormalizationDiagnostics]:
    """Normalize one raw chunk with bounded lookahead and release memory.

    Parameters
    ----------
    raw_chunk:
        One-dimensional array containing the raw unclipped chunk to emit.
    raw_future:
        One-dimensional array containing a bounded amount of future raw audio.
        The values influence only the emitted chunk's local peak targets. They
        do **not** advance the stored state beyond the emitted chunk.
    sample_rate:
        Output sample rate in hertz.
    dc_time_constant:
        Positive time constant, in seconds, of the one-pole local DC estimate.
    attack_lookahead_duration:
        Positive bounded lookahead duration, in seconds, used by the forward
        local-peak analysis window.
    release_time_constant:
        Positive time constant, in seconds, of the attenuation release memory.
    state:
        Mutable streaming state reused across successive calls.
    hard_reset:
        When ``True``, seed the local DC estimate from the current analysis
        block and reset ``M`` to ``1.0`` before processing.

    Returns
    -------
    tuple[numpy.ndarray, AutoNormalizationDiagnostics]
        Final float32 chunk after safety clipping, together with lightweight
        diagnostics describing the emitted chunk.

    Notes
    -----
    The procedure never applies gain above unity to the DC-centered signal.
    Future audio influences the present only through the bounded lookahead
    window, while past audio influences the present only through the bounded DC
    and release-memory states.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be strictly positive.")
    dc_time_constant = _validate_positive_parameter("dc_time_constant", dc_time_constant)
    attack_lookahead_duration = _validate_positive_parameter(
        "attack_lookahead_duration",
        attack_lookahead_duration,
    )
    release_time_constant = _validate_positive_parameter(
        "release_time_constant",
        release_time_constant,
    )

    current = np.asarray(raw_chunk, dtype=np.float64).reshape(-1)
    future = np.asarray(raw_future, dtype=np.float64).reshape(-1)

    analysis_source = np.concatenate((current, future), dtype=np.float64)
    if hard_reset or not state.initialized:
        _seed_state(
            analysis_source,
            sample_rate=sample_rate,
            dc_time_constant=dc_time_constant,
            state=state,
        )
    else:
        state.normalization_factor = max(1.0, float(state.normalization_factor))
        state.dc_estimate = float(state.dc_estimate)

    alpha_dc = exp(-1.0 / (float(sample_rate) * dc_time_constant))
    release_decay = exp(-1.0 / (float(sample_rate) * release_time_constant))
    lookahead_samples = max(1, int(round(float(sample_rate) * attack_lookahead_duration)))

    centered_analysis, dc_after_emitted = _center_analysis_with_one_pole(
        analysis_source,
        alpha_dc=alpha_dc,
        initial_dc_estimate=state.dc_estimate,
        emitted_count=int(current.shape[0]),
    )
    centered_current = centered_analysis[: current.shape[0]]
    local_peak = _forward_window_max_abs(
        centered_analysis,
        window_length=lookahead_samples,
        output_length=int(current.shape[0]),
    )

    emitted = np.empty_like(centered_current, dtype=np.float64)
    normalization_factor = max(1.0, float(state.normalization_factor))
    min_factor = normalization_factor
    max_factor = normalization_factor

    for index, sample in enumerate(centered_current):
        target_factor = max(1.0, float(local_peak[index]))
        if target_factor >= normalization_factor:
            normalization_factor = target_factor
        else:
            normalization_factor = max(
                target_factor,
                1.0 + (normalization_factor - 1.0) * release_decay,
            )
        normalization_factor = max(1.0, float(normalization_factor))
        emitted[index] = float(sample) / normalization_factor
        min_factor = min(min_factor, normalization_factor)
        max_factor = max(max_factor, normalization_factor)

    preclip_peak = float(np.max(np.abs(emitted))) if emitted.size else 0.0
    clip_hit_count = int(np.count_nonzero(np.abs(emitted) > 1.0 + 1e-12))
    output = clip_audio_chunk(emitted)

    state.dc_estimate = float(dc_after_emitted)
    state.normalization_factor = float(max(1.0, normalization_factor))
    state.initialized = True

    diagnostics = AutoNormalizationDiagnostics(
        output_peak=float(np.max(np.abs(output))) if output.size else 0.0,
        clip_hit_count=clip_hit_count,
        removed_dc_estimate=float(state.dc_estimate),
        ending_normalization_factor=float(state.normalization_factor),
        minimum_normalization_factor=float(min_factor),
        maximum_normalization_factor=float(max_factor),
        centered_input_peak=float(np.max(np.abs(centered_current))) if centered_current.size else preclip_peak,
    )
    return output, diagnostics
