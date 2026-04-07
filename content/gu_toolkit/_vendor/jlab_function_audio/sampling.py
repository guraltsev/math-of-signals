"""jlab_function_audio.sampling
================================

Sampling helpers for periodic callable audio.

Architecture
------------
This module contains the low-level numeric helpers shared by the player and the
phase matcher.  The functions here deliberately work on plain Python callables
and NumPy arrays so the rest of the package can focus on transport logic and
Jupyter integration.

Functionality
-------------
The helpers in this module are responsible for:

- wrapping transport times into the requested fixed period,
- evaluating a user-provided numeric callable on a scalar or sample grid,
- clipping samples into the safe range required by the request,
- producing mono float32 chunks for browser playback,
- blending old and new chunks with a short crossfade.

Main implementation notes
-------------------------
The implementation intentionally evaluates the user callable one scalar at a
time.  That choice favors predictable behavior for ordinary Python functions
written with :mod:`math` over maximum vectorized throughput.  Chunk sizes are
small, so the scalar approach is still fast enough for the intended notebook
workflow.

Examples
--------
Wrap unbounded transport time into a 100-second loop:

>>> wrap_periodic_time([99.5, 100.25, 201.0], 100.0).tolist()
[99.5, 0.25, 1.0]

Render a short sine chunk:

>>> import math
>>> signal = lambda t: math.sin(2 * math.pi * 2 * t)
>>> chunk = generate_chunk(signal, start_time=0.0, frame_count=8, sample_rate=8, period=100.0)
>>> np.round(chunk, 6).tolist()
[0.0, 1.0, 0.0, -1.0, -0.0, 1.0, 0.0, -1.0]
"""
from __future__ import annotations

from typing import Callable, Iterable

import numpy as np

SignalCallable = Callable[[float], float]


def wrap_periodic_time(time_seconds: float | Iterable[float] | np.ndarray, period: float) -> np.ndarray:
    """Wrap one or more times into the half-open interval ``[0, period)``.

    Parameters
    ----------
    time_seconds:
        Scalar or array-like transport times in seconds. The values may be
        unbounded or negative.
    period:
        Positive loop period in seconds.

    Returns
    -------
    numpy.ndarray
        Wrapped floating-point times with the same broadcasted shape as the
        input.

    Raises
    ------
    ValueError
        Raised when `period` is not strictly positive.

    Examples
    --------
    >>> wrap_periodic_time([-0.25, 0.0, 100.25], 100.0).tolist()
    [99.75, 0.0, 0.25]

    >>> wrap_periodic_time([12.5], 100.0).tolist()
    [12.5]
    """
    if period <= 0:
        raise ValueError("period must be strictly positive.")
    values = np.asarray(time_seconds, dtype=np.float64)
    return np.mod(values, period)


def _coerce_sample_value(value: float) -> float:
    """Convert a user-returned sample to a safe finite float in ``[-1, 1]``.

    Parameters
    ----------
    value:
        Value returned by the user-supplied callable for a single sample time.

    Returns
    -------
    float
        Finite clipped sample suitable for audio output.

    Examples
    --------
    >>> _coerce_sample_value(1.25)
    1.0
    >>> _coerce_sample_value(float("nan"))
    0.0
    """
    numeric = float(value)
    if not np.isfinite(numeric):
        return 0.0
    return float(max(-1.0, min(1.0, numeric)))


def _coerce_raw_sample_value(value: float) -> float:
    """Convert a user-returned sample to a safe finite float without clipping.

    Parameters
    ----------
    value:
        Value returned by the user-supplied callable for a single sample time.

    Returns
    -------
    float
        Finite sample value suitable for the raw autonormalization path. Any
        non-finite value is coerced to ``0.0``.
    """
    numeric = float(value)
    if not np.isfinite(numeric):
        return 0.0
    return numeric


def evaluate_signal(function: SignalCallable, sample_times: Iterable[float] | np.ndarray) -> np.ndarray:
    """Evaluate a numeric callable on a sample grid and clip the result.

    Parameters
    ----------
    function:
        Numeric callable accepting a single time in seconds and returning one
        numeric sample. The callable is expected to produce values in
        ``[-1, 1]``, but the function defensively clips the result.
    sample_times:
        Iterable of sample times in seconds.

    Returns
    -------
    numpy.ndarray
        One-dimensional float32 array of clipped samples.

    Notes
    -----
    The implementation deliberately evaluates the callable one scalar at a time.
    That makes ordinary Python callables built with :mod:`math` behave exactly
    as expected.

    Examples
    --------
    >>> import math
    >>> samples = evaluate_signal(lambda t: math.sin(2 * math.pi * t), [0.0, 0.25, 0.5])
    >>> np.round(samples, 6).tolist()
    [0.0, 1.0, 0.0]

    Out-of-range values are clipped:

    >>> evaluate_signal(lambda t: 4.0, [0.0, 1.0]).tolist()
    [1.0, 1.0]
    """
    times = np.asarray(list(sample_times), dtype=np.float64)
    values = np.empty(times.shape[0], dtype=np.float32)
    for index, time_value in enumerate(times):
        values[index] = _coerce_sample_value(function(float(time_value)))
    return values


def evaluate_signal_raw(function: SignalCallable, sample_times: Iterable[float] | np.ndarray) -> np.ndarray:
    """Evaluate a numeric callable on a sample grid without clipping finite values.

    Parameters
    ----------
    function:
        Numeric callable accepting a single time in seconds and returning one
        numeric sample.
    sample_times:
        Iterable of sample times in seconds.

    Returns
    -------
    numpy.ndarray
        One-dimensional float64 array of finite samples. Non-finite callable
        results are replaced with ``0.0``.
    """
    times = np.asarray(list(sample_times), dtype=np.float64)
    values = np.empty(times.shape[0], dtype=np.float64)
    for index, time_value in enumerate(times):
        values[index] = _coerce_raw_sample_value(function(float(time_value)))
    return values


def generate_chunk(
    function: SignalCallable,
    *,
    start_time: float,
    frame_count: int,
    sample_rate: int,
    period: float,
    phase_offset: float = 0.0,
) -> np.ndarray:
    """Render one periodic mono chunk from a user callable.

    Parameters
    ----------
    function:
        Numeric callable that maps one time in seconds to one sample in
        ``[-1, 1]``.
    start_time:
        Unwrapped transport time, in seconds, for the first sample of the
        rendered chunk.
    frame_count:
        Number of samples to render.
    sample_rate:
        Chunk sample rate in hertz.
    period:
        Fixed loop period in seconds. Transport time is wrapped into this
        period before the callable is evaluated.
    phase_offset:
        Phase offset, in seconds, added to the transport time before the
        periodic wrap. This is how the phase matcher aligns a replacement
        callable with the currently playing signal.

    Returns
    -------
    numpy.ndarray
        Float32 mono PCM chunk with shape ``(frame_count,)``.

    Raises
    ------
    ValueError
        Raised when `frame_count` is negative or when `sample_rate` is not
        strictly positive.

    Examples
    --------
    >>> import math
    >>> chunk = generate_chunk(
    ...     lambda t: math.sin(2 * math.pi * t),
    ...     start_time=0.0,
    ...     frame_count=4,
    ...     sample_rate=4,
    ...     period=100.0,
    ... )
    >>> np.round(chunk, 6).tolist()
    [0.0, 1.0, 0.0, -1.0]

    Applying a phase offset samples from a different point in the periodic
    function:

    >>> shifted = generate_chunk(
    ...     lambda t: t / 100.0,
    ...     start_time=0.0,
    ...     frame_count=2,
    ...     sample_rate=2,
    ...     period=100.0,
    ...     phase_offset=10.0,
    ... )
    >>> shifted.tolist()
    [0.1, 0.105]
    """
    if frame_count < 0:
        raise ValueError("frame_count must be greater than or equal to zero.")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be strictly positive.")
    if frame_count == 0:
        return np.zeros(0, dtype=np.float32)

    offsets = np.arange(frame_count, dtype=np.float64) / float(sample_rate)
    wrapped_times = wrap_periodic_time(start_time + phase_offset + offsets, period)
    return evaluate_signal(function, wrapped_times)


def generate_raw_chunk(
    function: SignalCallable,
    *,
    start_time: float,
    frame_count: int,
    sample_rate: int,
    period: float,
    phase_offset: float = 0.0,
) -> np.ndarray:
    """Render one periodic mono raw chunk without clipping finite values.

    Parameters
    ----------
    function:
        Numeric callable that maps one time in seconds to one sample.
    start_time:
        Unwrapped transport time, in seconds, for the first sample.
    frame_count:
        Number of samples to render.
    sample_rate:
        Chunk sample rate in hertz.
    period:
        Fixed loop period in seconds.
    phase_offset:
        Phase offset, in seconds, added before periodic wrapping.

    Returns
    -------
    numpy.ndarray
        Float64 mono chunk with shape ``(frame_count,)`` containing unclipped
        finite samples.
    """
    if frame_count < 0:
        raise ValueError("frame_count must be greater than or equal to zero.")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be strictly positive.")
    if frame_count == 0:
        return np.zeros(0, dtype=np.float64)

    offsets = np.arange(frame_count, dtype=np.float64) / float(sample_rate)
    wrapped_times = wrap_periodic_time(start_time + phase_offset + offsets, period)
    return evaluate_signal_raw(function, wrapped_times)


def clip_audio_chunk(samples: np.ndarray) -> np.ndarray:
    """Safety-clip a chunk into ``[-1, 1]`` and return float32 PCM.

    Parameters
    ----------
    samples:
        Array-like mono audio chunk.

    Returns
    -------
    numpy.ndarray
        Float32 chunk clipped into the browser-safe output range.
    """
    return np.clip(np.asarray(samples, dtype=np.float64), -1.0, 1.0).astype(np.float32, copy=False)


def _crossfade_chunks_impl(
    outgoing: np.ndarray,
    incoming: np.ndarray,
    crossfade_samples: int,
    *,
    dtype: np.dtype,
) -> np.ndarray:
    """Blend two equal-length chunks with a linear crossfade in a chosen dtype."""
    outgoing_array = np.asarray(outgoing, dtype=dtype)
    incoming_array = np.asarray(incoming, dtype=dtype)

    if outgoing_array.shape != incoming_array.shape:
        raise ValueError("outgoing and incoming must have the same shape.")

    total_samples = outgoing_array.shape[0]
    fade = int(max(0, min(crossfade_samples, total_samples)))
    if fade == 0:
        return incoming_array.copy()

    result = incoming_array.copy()
    if fade == 1:
        result[0] = incoming_array[0]
        return result

    ramp = np.linspace(0.0, 1.0, fade, endpoint=True, dtype=dtype)
    result[:fade] = (1.0 - ramp) * outgoing_array[:fade] + ramp * incoming_array[:fade]
    return result


def crossfade_chunks_raw(
    outgoing: np.ndarray,
    incoming: np.ndarray,
    crossfade_samples: int,
) -> np.ndarray:
    """Blend two equal-length raw chunks while preserving float64 precision."""
    return _crossfade_chunks_impl(
        outgoing,
        incoming,
        crossfade_samples,
        dtype=np.float64,
    )


def crossfade_chunks(
    outgoing: np.ndarray,
    incoming: np.ndarray,
    crossfade_samples: int,
) -> np.ndarray:
    """Blend two equal-length chunks with a linear crossfade.

    Parameters
    ----------
    outgoing:
        Chunk that is currently being replaced.
    incoming:
        Chunk that should take over after the crossfade.
    crossfade_samples:
        Number of initial samples over which a linear blend is applied. Samples
        after that point are taken directly from `incoming`.

    Returns
    -------
    numpy.ndarray
        New float32 chunk representing the blended transition.

    Raises
    ------
    ValueError
        Raised when the chunks do not have the same shape.

    Examples
    --------
    >>> import numpy as np
    >>> a = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    >>> b = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
    >>> crossfade_chunks(a, b, 2).tolist()
    [0.0, 1.0, 1.0, 1.0]

    A zero-length crossfade simply returns the incoming chunk:

    >>> crossfade_chunks(a, b, 0).tolist()
    [1.0, 1.0, 1.0, 1.0]
    """
    return _crossfade_chunks_impl(
        outgoing,
        incoming,
        crossfade_samples,
        dtype=np.float32,
    )


def approximate_derivative(
    function: SignalCallable,
    *,
    time_seconds: float,
    period: float,
    delta: float,
) -> float:
    """Estimate the derivative of a periodic callable with a central difference.

    Parameters
    ----------
    function:
        Numeric callable being differentiated.
    time_seconds:
        Point, in seconds, at which the derivative should be estimated.
    period:
        Loop period used to wrap `time_seconds - delta` and
        `time_seconds + delta`.
    delta:
        Small positive finite difference step in seconds.

    Returns
    -------
    float
        Estimated first derivative in units of amplitude per second.

    Raises
    ------
    ValueError
        Raised when `delta` is not strictly positive.

    Examples
    --------
    >>> import math
    >>> round(
    ...     approximate_derivative(
    ...         lambda t: math.sin(2 * math.pi * t),
    ...         time_seconds=0.0,
    ...         period=100.0,
    ...         delta=1e-6,
    ...     ),
    ...     3,
    ... )
    6.283
    """
    if delta <= 0:
        raise ValueError("delta must be strictly positive.")

    t_minus = float(wrap_periodic_time([time_seconds - delta], period)[0])
    t_plus = float(wrap_periodic_time([time_seconds + delta], period)[0])
    value_minus = float(evaluate_signal(function, [t_minus])[0])
    value_plus = float(evaluate_signal(function, [t_plus])[0])
    return (value_plus - value_minus) / (2.0 * delta)
