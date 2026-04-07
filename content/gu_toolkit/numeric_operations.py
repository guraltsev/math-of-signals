"""Common numeric operations for symbolic expressions.

Includes numeric integration, real Fourier coefficients, and simple audio playback.
"""

from __future__ import annotations

import base64
import inspect
import io
import wave

import numpy as np
import sympy as sp
from IPython.display import HTML

try:
    from .numpify import NumericFunction, numpify_cached
except ImportError:  # pragma: no cover
    from numpify import NumericFunction, numpify_cached

_NUMERIC_CALLABLE_TYPES = (NumericFunction,)


def _to_quad_limit(v):
    if v == sp.oo:
        return np.inf
    if v == -sp.oo:
        return -np.inf
    return float(sp.N(v))


def _resolve_numeric_callable(expr, x, freeze, freeze_kwargs):
    if isinstance(expr, _NUMERIC_CALLABLE_TYPES):
        compiled = expr
    elif isinstance(expr, sp.Lambda):
        variables = tuple(expr.variables)
        if not variables:
            const_val = float(sp.N(expr.expr))
            return lambda t: np.full_like(
                np.asarray(t, dtype=float), const_val, dtype=float
            )
        compiled = numpify_cached(expr.expr, vars=variables)
    elif isinstance(expr, (sp.Basic, int, float, complex, np.number)):
        symbolic_expr = sp.sympify(expr)
        if not isinstance(x, sp.Symbol):
            raise TypeError(
                f"NIntegrate expects x to be a sympy Symbol for symbolic expressions, got {type(x)}"
            )
        required_symbols = tuple(
            sorted((symbolic_expr.free_symbols - {x}), key=lambda s: s.name)
        )
        compiled = numpify_cached(symbolic_expr, vars=(x, *required_symbols))
    elif callable(expr):
        signature = inspect.signature(expr)
        positional = [
            param
            for param in signature.parameters.values()
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        required = [param for param in positional if param.default is inspect._empty]
        if len(required) > 1:
            raise TypeError(
                "Generic callables with parameters are not supported yet; "
                "pass a NumericFunction and use freeze=..."
            )
        if freeze is not None or freeze_kwargs:
            raise TypeError(
                "freeze= is only supported for symbolic/NumericFunction inputs"
            )
        return expr
    else:
        raise TypeError(f"Unsupported expr type for NIntegrate: {type(expr)}")

    if not compiled.vars:
        raise TypeError("NIntegrate requires an x argument for NumericFunction inputs")
    if len(compiled.vars) == 1:
        return (
            compiled.freeze(freeze, **freeze_kwargs)
            if (freeze is not None or freeze_kwargs)
            else compiled
        )
    return (
        compiled.freeze(freeze, **freeze_kwargs)
        if (freeze is not None or freeze_kwargs)
        else compiled
    )


def NIntegrate(expr, var_and_limits, freeze=None, **freeze_kwargs):
    """Numerically integrate a symbolic expression over a one-dimensional interval.
    
    Full API
    --------
    ``NIntegrate(expr, var_and_limits, freeze=None, **freeze_kwargs)``
    
    Parameters
    ----------
    expr : Any
        Symbolic expression payload. Required.
    
    var_and_limits : Any
        Tuple containing the variable and its numeric limits. Required.
    
    freeze : Any, optional
        Boolean flag controlling whether dynamic parameters are frozen during evaluation. Defaults to ``None``.
    
    **freeze_kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``freeze=None``: Boolean flag controlling whether dynamic parameters are frozen during evaluation.
    - ``**freeze_kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.numeric_operations``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.numeric_operations import NIntegrate
        result = NIntegrate(...)
    
    Discovery-oriented use::
    
        help(NIntegrate)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(NIntegrate)`` and inspect sibling APIs in the same module.
    """

    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover
        raise TypeError("NIntegrate expects limits as a tuple: (x, a, b)") from exc

    from scipy.integrate import quad

    f = _resolve_numeric_callable(expr, x, freeze, freeze_kwargs)

    def _integrand(t):
        return float(np.asarray(f(t)))

    value, _error = quad(_integrand, _to_quad_limit(a), _to_quad_limit(b))
    return value


def NReal_Fourier_Series(
    expr, var_and_limits, samples=4000, freeze=None, **freeze_kwargs
):
    """Compute real Fourier-series coefficients for a symbolic expression on an interval.
    
    Full API
    --------
    ``NReal_Fourier_Series(expr, var_and_limits, samples=4000, freeze=None, **freeze_kwargs)``
    
    Parameters
    ----------
    expr : Any
        Symbolic expression payload. Required.
    
    var_and_limits : Any
        Tuple containing the variable and its numeric limits. Required.
    
    samples : Any, optional
        Sampling density used when evaluating a curve or field. Defaults to ``4000``.
    
    freeze : Any, optional
        Boolean flag controlling whether dynamic parameters are frozen during evaluation. Defaults to ``None``.
    
    **freeze_kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``samples=4000``: Sampling density used when evaluating a curve or field.
    - ``freeze=None``: Boolean flag controlling whether dynamic parameters are frozen during evaluation.
    - ``**freeze_kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.numeric_operations``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.numeric_operations import NReal_Fourier_Series
        result = NReal_Fourier_Series(...)
    
    Discovery-oriented use::
    
        help(NReal_Fourier_Series)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(NReal_Fourier_Series)`` and inspect sibling APIs in the same module.
    """

    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover
        raise TypeError(
            "NReal_Fourier_Series expects limits as a tuple: (x, a, b)"
        ) from exc

    if int(samples) < 2:
        raise ValueError("samples must be >= 2")
    sample_count = int(samples)

    from scipy.fft import rfft

    start = float(sp.N(a))
    stop = float(sp.N(b))
    length = stop - start
    if length <= 0:
        raise ValueError("NReal_Fourier_Series expects b > a")

    f = _resolve_numeric_callable(expr, x, freeze, freeze_kwargs)

    grid = start + length * np.arange(sample_count, dtype=float) / sample_count
    values = np.asarray(f(grid), dtype=float)
    if values.ndim == 0:
        values = np.full(sample_count, float(values), dtype=float)
    else:
        values = np.ravel(values)
    if values.shape[0] != sample_count:
        raise ValueError("expr must evaluate to one value per sample point")

    spectrum = rfft(values)
    dx = length / sample_count
    mode_index = np.arange(spectrum.shape[0], dtype=float)
    phase = np.exp(-1j * (2.0 * np.pi * mode_index * start / length))
    c = (dx / np.sqrt(length)) * phase * spectrum

    cos_coeffs = np.sqrt(2.0) * np.real(c)
    sin_coeffs = -np.sqrt(2.0) * np.imag(c)
    cos_coeffs[0] = np.real(c[0])
    sin_coeffs[0] = 0.0

    return cos_coeffs, sin_coeffs


def play(expr, var_and_limits, loop=False, autoplay=False):
    """Render a symbolic expression as an inline HTML audio player.
    
    Full API
    --------
    ``play(expr, var_and_limits, loop=False, autoplay=False)``
    
    Parameters
    ----------
    expr : Any
        Symbolic expression payload. Required.
    
    var_and_limits : Any
        Tuple containing the variable and its numeric limits. Required.
    
    loop : Any, optional
        Boolean flag controlling whether audio playback should loop. Defaults to ``False``.
    
    autoplay : Any, optional
        Boolean flag controlling whether audio playback should start automatically. Defaults to ``False``.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``loop=False``: Boolean flag controlling whether audio playback should loop.
    - ``autoplay=False``: Boolean flag controlling whether audio playback should start automatically.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.numeric_operations``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.numeric_operations import play
        result = play(...)
    
    Discovery-oriented use::
    
        help(play)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(play)`` and inspect sibling APIs in the same module.
    """

    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover
        raise TypeError("play expects limits as a tuple: (x, a, b)") from exc

    if not isinstance(expr, sp.Basic):
        raise TypeError(f"play expects a SymPy expression, got {type(expr)}")
    if not isinstance(x, sp.Symbol):
        raise TypeError(f"play expects x to be a sympy Symbol, got {type(x)}")

    sample_rate = 44100
    start = float(sp.N(a))
    stop = float(sp.N(b))
    duration = stop - start
    if duration <= 0:
        raise ValueError("play expects b > a so the duration is positive")

    sample_count = max(2, int(np.ceil(duration * sample_rate)))
    t = np.linspace(start, stop, sample_count, endpoint=False, dtype=float)

    fn = numpify_cached(expr, vars=x)
    y = np.asarray(fn(t), dtype=float)
    if y.ndim == 0:
        y = np.full_like(t, float(y))
    else:
        y = np.ravel(y)
        if y.shape[0] != sample_count:
            raise ValueError(
                "Expression must evaluate to one audio sample per time point"
            )

    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 0:
        y = 0.99 * y / peak

    pcm = (np.clip(y, -1.0, 1.0) * 32767).astype(np.int16)

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm.tobytes())
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    loop_attr = " loop" if loop else ""
    autoplay_attr = " autoplay" if autoplay else ""
    return HTML(
        f"<audio controls{autoplay_attr}{loop_attr} "
        f'src="data:audio/wav;base64,{encoded}"></audio>'
    )


__all__ = ["NIntegrate", "NReal_Fourier_Series", "play"]
