"""Notebook-friendly symbolic-math prelude and convenience exports.

Provides SymPy/NumPy/Pandas shortcuts, indexed symbol and function families,
and infix relation operators tuned for discoverable notebook use.
"""

from __future__ import annotations

__all__=[]
# --- The deliberate classroom prelude ---
import sympy as sp
__all__+=["sp"]
from sympy import *
__all__+= list(getattr(sp, "__all__", []))

import numpy as np
__all__+=["np"]



import pandas as pd
__all__+=["pd"]

# print("__all__ (from prelude):",__all__)
import sympy as sp

class SymbolFamily(sp.Symbol):
    """
    A SymPy Symbol that creates indexed children via [].
    Inherits from sp.Symbol, so all math (x**2, diff, etc.) works natively.
    """
    def __new__(cls, name, **kwargs):
        """Create a family root symbol with cached indexed children support."""
        # Create the actual SymPy Symbol
        obj = super().__new__(cls, name, **kwargs)
        
        # Attach our family-specific attributes to the new instance
        # We use distinct names (e.g., _family_cache) to avoid colliding with SymPy internals
        obj._family_cache = {}
        obj._family_kwargs = kwargs
        return obj

    def __getitem__(self, k):
        """Return a cached indexed child symbol, creating it on first access."""
        if not isinstance(k, tuple):
            k = (k,)
            
        if k not in self._family_cache:
            sub = ",".join(map(str, k))
            child_name = f"{self.name}_{sub}"
            # Create a standard Symbol for the child
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
            
        return self._family_cache[k]

class FunctionFamily:
    """
    A wrapper for SymPy Functions (e.g., f(x)).
    SymPy Functions are complex to subclass directly, so this proxy 
    is the standard way to handle them.
    """
    def __init__(self, name, **kwargs):
        """Initialize a function-family wrapper around a base SymPy Function."""
        self.name = name
        self._kwargs = kwargs
        # Create the base function (e.g. f)
        self._base = sp.Function(name, **kwargs)
        self._cache = {}

    def __getitem__(self, k):
        """Return an indexed child function (for example ``f[1]`` -> ``f_1``)."""
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            sub = ",".join(map(str, k))
            # Create a new Function for the child (e.g. f_1)
            self._cache[k] = sp.Function(f"{self.name}_{sub}", **self._kwargs)
        return self._cache[k]

    def __call__(self, *args):
        """Call the base symbolic function with positional arguments."""
        # Allows f(x) to work
        return self._base(*args)
    
    def _sympy_(self):
        """Return the underlying SymPy function for SymPy coercion."""
        # Allows SymPy to recognize this object
        return self._base
    
    def __str__(self):
        """Return the string form of the wrapped base function."""
        return str(self._base)
    
    def __repr__(self):
        """Return a representation matching the wrapped SymPy function."""
        return repr(self._base)

__all__ += ["SymbolFamily", "FunctionFamily"]

# -----------------------
# Roman (lowercase)
# -----------------------
for _ch in "abcdefghijklmnopqrstuvwxyz":
    globals()[_ch] = SymbolFamily(_ch)

# conventional function letters
for _ch in "fgh":
    globals()[_ch] = FunctionFamily(_ch)

# conventional integer indices (as in your original snippet)
for _ch in "klmnij":
    globals()[_ch] = SymbolFamily(_ch, integer=True)

__all__ += list("abcdefghijklmnopqrstuvwxyz")

# -----------------------
# Roman (uppercase)
# -----------------------
for _ch in "ABCDEFGHIJKLOPQRSTUVWXYZ":
    globals()[_ch] = SymbolFamily(_ch)

for _ch in "MN":
    globals()[_ch] = SymbolFamily(_ch, integer=True)

# conventional function letters
for _ch in "FGH":
    globals()[_ch] = FunctionFamily(_ch)

__all__ += list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

# -----------------------
# Greek (lowercase): SymPy canonical names (not LaTeX macros)
# -----------------------
alpha = SymbolFamily("alpha")
beta = SymbolFamily("beta")
gamma = SymbolFamily("gamma")
delta = SymbolFamily("delta")

epsilon = SymbolFamily("epsilon")
varepsilon = SymbolFamily("varepsilon")

zeta = SymbolFamily("zeta")
eta = SymbolFamily("eta")

theta = SymbolFamily("theta")
vartheta = SymbolFamily("vartheta")

kappa = SymbolFamily("kappa")
lam = SymbolFamily("lambda")  # "lambda" is a Python keyword
mu = SymbolFamily("mu")
nu = SymbolFamily("nu")
xi = SymbolFamily("xi")

rho = SymbolFamily("rho")

sigma = SymbolFamily("sigma")
varsigma = SymbolFamily("varsigma")
tau = SymbolFamily("tau")

phi = SymbolFamily("phi")
varphi = SymbolFamily("varphi")

chi = SymbolFamily("chi")
psi = SymbolFamily("psi")
omega = SymbolFamily("omega")

__all__ += [
    "alpha","beta","gamma","delta",
    "epsilon","varepsilon",
    "zeta","eta",
    "theta","vartheta",
    "kappa","lam","mu","nu","xi","rho",
    "sigma","varsigma","tau",
    "phi","varphi",
    "chi","psi","omega",
]

del _ch





class Infix:
    """Generic infix operator used as: a |OP| b."""
    __slots__ = ("func",)

    def __init__(self, func):
        """Store the binary callable implementing the infix operation."""
        self.func = func

    def __ror__(self, left):
        """Capture the left operand during ``a |op`` parsing."""
        return _InfixPartial(self.func, left)


class _InfixPartial:
    """Intermediate state object used to complete ``a |op| b`` expressions."""
    __slots__ = ("func", "left")

    def __init__(self, func, left):
        """Persist partial infix state until the right operand arrives."""
        self.func = func
        self.left = left

    def __or__(self, right):
        """Apply the infix callable to the captured operands."""
        return self.func(self.left, right)

eq = Infix(sp.Eq)
lt = Infix(sp.Lt)
le = Infix(sp.Le)
gt = Infix(sp.Gt)
ge = Infix(sp.Ge)
__all__+=["Infix", "eq", "lt", "le", "gt", "ge"]

## Demo:
# x, y = sp.symbols("x y")
# expr1 = x + 1
# expr2 = 2*y

# print(expr1 | eq | expr2)      # Eq(x + 1, 2*y)
# print((x**2) | eq | (y**2))    # Eq(x**2, y**2)


from IPython.display import HTML, Latex, display
__all__+=["HTML", "Latex", "display"]

from pprint import pprint
__all__+=["pprint"]


def _to_quad_limit(v):
    """Convert symbolic bounds (including infinities) to SciPy-compatible floats."""
    if v == sp.oo:
        return np.inf
    if v == -sp.oo:
        return -np.inf
    return float(sp.N(v))


def _resolve_parameter_values(required_symbols, binding, current_figure_getter):
    """Resolve values for required symbols from explicit binding or figure context."""
    if not required_symbols:
        return {}

    if binding is None:
        fig = current_figure_getter(required=True)
        return {sym: fig.parameters[sym].value for sym in required_symbols}

    if isinstance(binding, dict):
        missing = [sym for sym in required_symbols if sym not in binding and sym.name not in binding]
        if missing:
            names = ", ".join(sym.name for sym in missing)
            raise ValueError(f"binding is missing values for: {names}")
        return {
            sym: (binding[sym] if sym in binding else binding[sym.name])
            for sym in required_symbols
        }

    provider = None
    if hasattr(binding, "params"):
        provider = binding.params
    elif hasattr(binding, "parameters"):
        provider = binding.parameters

    if provider is None:
        raise TypeError(
            "binding must be dict[Symbol|name, value], SmartFigure-like provider, or None"
        )

    missing = [sym for sym in required_symbols if sym not in provider]
    if missing:
        names = ", ".join(sym.name for sym in missing)
        raise ValueError(f"binding provider is missing values for: {names}")
    return {sym: provider[sym].value for sym in required_symbols}


def _resolve_numeric_callable(expr, x, binding, _NumpifiedFunction, _BoundNumpifiedFunction, _numpify_cached, _current_figure):
    """Build a numeric callable of one variable from supported symbolic/numeric inputs."""
    if isinstance(expr, _BoundNumpifiedFunction):
        return expr

    if isinstance(expr, _NumpifiedFunction):
        if not expr.args:
            raise TypeError("NIntegrate requires an x argument for numpified functions")
        if len(expr.args) == 1:
            return expr
        if binding is None:
            return expr.bind(_current_figure(required=True))
        return expr.bind(binding)

    if isinstance(expr, sp.Lambda):
        variables = tuple(expr.variables)
        if not variables:
            const_val = float(sp.N(expr.expr))
            return lambda t: np.full_like(np.asarray(t, dtype=float), const_val, dtype=float)
        lead_symbol = variables[0]
        extra_symbols = variables[1:]
        if extra_symbols:
            value_map = _resolve_parameter_values(extra_symbols, binding, _current_figure)
            compiled = _numpify_cached(expr.expr, args=variables)
            return compiled.bind(value_map)
        return _numpify_cached(expr.expr, args=lead_symbol)

    if isinstance(expr, sp.Basic):
        if not isinstance(x, sp.Symbol):
            raise TypeError(f"NIntegrate expects x to be a sympy Symbol for symbolic expressions, got {type(x)}")
        required_symbols = tuple(sorted((sp.sympify(expr).free_symbols - {x}), key=lambda s: s.name))
        if not required_symbols:
            return _numpify_cached(expr, args=x)
        value_map = _resolve_parameter_values(required_symbols, binding, _current_figure)
        compiled = _numpify_cached(expr, args=(x, *required_symbols))
        return compiled.bind(value_map)

    if callable(expr):
        import inspect

        signature = inspect.signature(expr)
        positional = [
            param for param in signature.parameters.values()
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        required = [param for param in positional if param.default is inspect._empty]

        if len(required) <= 1:
            return expr

        value_list = []
        parameter_symbols = tuple(sp.Symbol(param.name) for param in required[1:])
        value_map = _resolve_parameter_values(parameter_symbols, binding, _current_figure)
        for sym in parameter_symbols:
            value_list.append(value_map[sym])

        def f(t):
            return expr(t, *value_list)

        return f

    raise TypeError(f"Unsupported expr type for NIntegrate: {type(expr)}")


def NIntegrate(expr, var_and_limits, binding=None):
    """Numerically integrate a symbolic or numeric 1D function.

    Parameters
    ----------
    expr:
        One of:

        - a SymPy expression,
        - a :class:`numpify.NumpifiedFunction`,
        - a :class:`numpify.BoundNumpifiedFunction`,
        - or a plain numeric callable ``f(x)``.
    var_and_limits:
        Tuple ``(x, a, b)`` where ``a``/``b`` are scalar bounds (including
        ``sympy.oo``/``-sympy.oo``). For plain numeric callables, ``x`` is
        ignored and only ``(a, b)`` are used.
    binding:
        Optional parameter source when ``expr`` needs extra arguments:

        - ``dict[Symbol, value]`` for explicit bindings,
        - ``SmartFigure`` for live figure-backed bindings,
        - ``None`` to use the current figure context when needed.

    Returns
    -------
    float
        Numeric integral value computed with ``scipy.integrate.quad``.
    """
    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover - defensive shape validation
        raise TypeError("NIntegrate expects limits as a tuple: (x, a, b)") from exc

    try:
        from .numpify import (
            BoundNumpifiedFunction as _BoundNumpifiedFunction,
            NumpifiedFunction as _NumpifiedFunction,
            numpify_cached as _numpify_cached,
        )
        from .SmartFigure import current_figure as _current_figure
    except ImportError:
        from numpify import (
            BoundNumpifiedFunction as _BoundNumpifiedFunction,
            NumpifiedFunction as _NumpifiedFunction,
            numpify_cached as _numpify_cached,
        )
        from SmartFigure import current_figure as _current_figure

    from scipy.integrate import quad

    f = _resolve_numeric_callable(
        expr,
        x,
        binding,
        _NumpifiedFunction,
        _BoundNumpifiedFunction,
        _numpify_cached,
        _current_figure,
    )

    def _integrand(t):
        return float(np.asarray(f(t)))

    value, _error = quad(_integrand, _to_quad_limit(a), _to_quad_limit(b))
    return value


__all__ += ["NIntegrate"]


def NReal_Fourier_Series(expr, var_and_limits, samples=4000, binding=None):
    """Return L2-normalized real Fourier coefficients on a finite interval.

    Parameters
    ----------
    expr:
        Any expression/callable accepted by :func:`NIntegrate`.
    var_and_limits:
        Tuple ``(x, a, b)``. For plain callables the symbol entry is ignored.
    samples:
        Number of uniform samples used to estimate coefficients.
    binding:
        Optional parameter source used for expressions that require extra args.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        ``(cos_coeffs, sin_coeffs)`` with L2-normalized basis on ``(a, b)``:
        ``phi_0 = 1/sqrt(L)``,
        ``phi_n^c = sqrt(2/L) cos(2*pi*n*x/L)``,
        ``phi_n^s = sqrt(2/L) sin(2*pi*n*x/L)`` for ``n>=1``.
    """
    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover - defensive shape validation
        raise TypeError("NReal_Fourier_Series expects limits as a tuple: (x, a, b)") from exc

    if int(samples) < 2:
        raise ValueError("samples must be >= 2")
    sample_count = int(samples)

    try:
        from .numpify import (
            BoundNumpifiedFunction as _BoundNumpifiedFunction,
            NumpifiedFunction as _NumpifiedFunction,
            numpify_cached as _numpify_cached,
        )
        from .SmartFigure import current_figure as _current_figure
    except ImportError:
        from numpify import (
            BoundNumpifiedFunction as _BoundNumpifiedFunction,
            NumpifiedFunction as _NumpifiedFunction,
            numpify_cached as _numpify_cached,
        )
        from SmartFigure import current_figure as _current_figure

    from scipy.fft import rfft

    start = float(sp.N(a))
    stop = float(sp.N(b))
    length = stop - start
    if length <= 0:
        raise ValueError("NReal_Fourier_Series expects b > a")

    f = _resolve_numeric_callable(
        expr,
        x,
        binding,
        _NumpifiedFunction,
        _BoundNumpifiedFunction,
        _numpify_cached,
        _current_figure,
    )

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


__all__ += ["NReal_Fourier_Series"]


def play(expr, var_and_limits, loop=True):
    """Play a 1D SymPy expression as audio over a time interval.

    Parameters
    ----------
    expr:
        SymPy expression in one variable.
    var_and_limits:
        Tuple ``(x, a, b)`` where ``x`` is the time symbol and ``a``/``b``
        are start/end times in seconds.
    loop:
        If ``True`` (default), playback restarts automatically when finished.

    Returns
    -------
    IPython.display.HTML
        Display object for an autoplaying audio element.
    """
    try:
        x, a, b = var_and_limits
    except Exception as exc:  # pragma: no cover - defensive shape validation
        raise TypeError("play expects limits as a tuple: (x, a, b)") from exc

    if not isinstance(expr, sp.Basic):
        raise TypeError(f"play expects a SymPy expression, got {type(expr)}")
    if not isinstance(x, sp.Symbol):
        raise TypeError(f"play expects x to be a sympy Symbol, got {type(x)}")

    try:
        from .numpify import numpify_cached as _numpify_cached
    except ImportError:
        from numpify import numpify_cached as _numpify_cached

    import base64
    import io
    import wave

    sample_rate = 44100
    start = float(sp.N(a))
    stop = float(sp.N(b))
    duration = stop - start
    if duration <= 0:
        raise ValueError("play expects b > a so the duration is positive")

    sample_count = max(2, int(np.ceil(duration * sample_rate)))
    t = np.linspace(start, stop, sample_count, endpoint=False, dtype=float)

    fn = _numpify_cached(expr, args=x)
    y = np.asarray(fn(t), dtype=float)
    if y.ndim == 0:
        y = np.full_like(t, float(y))
    else:
        y = np.ravel(y)
        if y.shape[0] != sample_count:
            raise ValueError("Expression must evaluate to one audio sample per time point")

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
    widget = HTML(
        f'<audio controls autoplay{loop_attr} '
        f'src="data:audio/wav;base64,{encoded}"></audio>'
    )
    display(widget)
    return widget


__all__ += ["play"]
