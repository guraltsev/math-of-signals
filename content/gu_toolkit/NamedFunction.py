"""
NamedFunction: Create SymPy ``Function`` classes from Python callables
=====================================================================

Purpose
-------
Provide a small decorator, :func:`NamedFunction`, that turns either:

1) a regular Python function, or
2) a small "spec class" with ``symbolic`` and ``numeric`` methods

into a concrete SymPy ``Function`` subclass.

This is useful when you want to write expressions such as ``G(x)`` in SymPy while also
attaching:

- a symbolic definition (for rewriting/expansion),
- and/or a NumPy-ready numerical implementation (for compilation).

Non-goals
---------
- This module does **not** aim to support arbitrary Python callables (keyword-only args,
  varargs, defaults, etc.). SymPy ``Function`` calls are positional; we intentionally
  keep the interface strict to avoid surprising runtime behavior.
- This module does **not** implement a full compilation pipeline; it only stores a
  NumPy-friendly callable (``f_numpy``) when provided.

Design overview
---------------
SymPy's ``Function`` uses a metaclass with a read-only ``__signature__``.  To preserve
nice interactive help (``inspect.signature``) we generate the function class using a
custom metaclass that exposes an overridden signature via a private attribute.

The generated SymPy Function class implements:

- ``_eval_rewrite_as_expand_definition``:
  Used by ``expr.rewrite("expand_definition")`` to expand the symbolic definition when
  one is available.
- ``_eval_evalf``:
  Numeric fallback via rewriting, when possible.
- ``f_numpy`` (optional):
  A NumPy-friendly callable for numerical evaluation in compilation pipelines.

Key invariants / assumptions
----------------------------
- The decorated callable's arguments are *positional*, required, and fixed in number.
- A symbolic definition may return ``None`` to keep the function opaque.
- When a symbolic definition returns a non-SymPy object (e.g. a string), we attempt to
  ``sympify`` it for documentation and rewriting. If that fails, the function is kept
  opaque for rewriting and the docstring falls back to a safe representation.

Supported Python versions
-------------------------
- Python >= 3.10

Dependencies
------------
- SymPy (required)

Public entrypoints
------------------
- :func:`NamedFunction`

Testing pointer
---------------
- See ``test_namedfunction.py`` for a minimal, assertion-based verification script.

Examples
--------
Function decorator:

>>> import sympy as sp
>>> from NamedFunction import NamedFunction
>>> x = sp.Symbol("x")
>>> @NamedFunction
... def F(x):
...     return x + 1
>>> sp.simplify(F(x).rewrite("expand_definition") - (x + 1))
0

Class decorator with an *opaque* symbolic definition (returns None):

>>> @NamedFunction
... class G:
...     def symbolic(self, x):
...         return None
...     def numeric(self, x):
...         return x
>>> expr = G(x)
>>> expr.rewrite("expand_definition") == expr
True
>>> callable(getattr(G, "f_numpy", None))
True
"""

from __future__ import annotations

import inspect
import textwrap
from typing import Callable, Optional, Protocol, Tuple, Type, Union, cast

import sympy as sp


__all__ = [
    # Public API
    "NamedFunction",
]


# === SECTION: Types & protocols [id: types]===
#
# Keep public signatures free of `Any` while still documenting intent.
# === END SECTION: Types & protocols ===


_SymbolicReturn = Union[sp.Basic, int, float, complex, str, None]
_SymbolicCallable = Callable[..., _SymbolicReturn]


class _NamedFunctionSpec(Protocol):
    """Protocol for @NamedFunction class-decoration.

    A spec class is never instantiated; its methods are called with ``self=None``.
    """

    def symbolic(self, *args: sp.Basic) -> _SymbolicReturn:
        """Return the symbolic expansion/definition for the function call."""
        ...

    def numeric(self, *args: object) -> object:
        """Return a numeric implementation used by ``numpify`` bindings."""
        ...


# === SECTION: Signature support [id: signature]===
#
# SymPy's Function metaclass makes __signature__ read-only. We override it at the
# metaclass level to preserve `inspect.signature(...)` for generated classes.
# === END SECTION: Signature support ===


class _SignedFunctionMeta(type(sp.Function)):
    """Metaclass that allows overriding ``__signature__`` on generated classes."""

    @property
    def __signature__(cls) -> Optional[inspect.Signature]:  # noqa: D401
        """Expose generated call signatures for ``inspect.signature``."""
        # Invariant: we only set `_custom_signature` on classes created by this module.
        return cast(Optional[inspect.Signature], getattr(cls, "_custom_signature", None))


# === SECTION: LaTeX helpers [id: latex]===
#
# We use custom LaTeX symbol names for nicer documentation output.
# === END SECTION: LaTeX helpers ===


_GREEK_LETTERS: set[str] = {
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "omicron",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "chi",
    "psi",
    "omega",
    "Gamma",
    "Delta",
    "Theta",
    "Lambda",
    "Xi",
    "Pi",
    "Sigma",
    "Upsilon",
    "Phi",
    "Psi",
    "Omega",
}


def _get_smart_latex_symbol(name: str) -> sp.Symbol:
    """Return a Symbol with a helpful LaTeX name.

    Rules
    -----
    - Greek letter names are rendered as Greek in LaTeX (``alpha`` -> ``\\alpha``).
    - Multi-letter words are wrapped in ``\\mathrm{...}``.
    - Underscores are interpreted as subscripts (``x_val`` -> ``x_{val}``).

    Notes
    -----
    This affects LaTeX rendering only. The symbol's *SymPy name* remains unchanged.

    Examples
    --------
    >>> import sympy as sp
    >>> from NamedFunction import _get_smart_latex_symbol  # internal helper
    >>> s = _get_smart_latex_symbol("x_val")
    >>> sp.latex(s)
    'x_{val}'
    """
    if not name:
        return sp.Symbol(name)

    if "_" in name:
        head, sub = name.split("_", 1)
    else:
        head, sub = name, None

    if len(head) > 1 and head not in _GREEK_LETTERS:
        tex_head = f"\\mathrm{{{head}}}"
    else:
        tex_head = f"\\{head}" if head in _GREEK_LETTERS else head

    tex = f"{tex_head}_{{{sub}}}" if sub else tex_head
    return sp.Symbol(name, latex_name=tex)


def _latex_function_name(name: str) -> str:
    """Return a LaTeX string for a function name."""
    if len(name) > 1 and name not in _GREEK_LETTERS:
        return f"\\mathrm{{{name}}}"
    if name in _GREEK_LETTERS:
        return f"\\{name}"
    return name


# === SECTION: Sympify & documentation helpers [id: docs]===
#
# We want docstrings that render math expressions, not code strings. If a symbolic
# definition returns a string (or another sympifiable object), we try to sympify it.
# === END SECTION: Sympify & documentation helpers ===


def _validate_fixed_positional_signature(sig: inspect.Signature, *, what: str) -> int:
    """Validate that a callable has a fixed number of required positional arguments.

    Parameters
    ----------
    sig:
        Signature of the callable to validate.
    what:
        Human-readable label used in error messages (e.g. "function F" or "C.symbolic").

    Returns
    -------
    int
        Number of positional arguments (including ``self`` if present).

    Raises
    ------
    ValueError
        If the signature contains varargs, varkw, keyword-only parameters, or defaults.
    """
    supported_kinds = {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }
    params = list(sig.parameters.values())

    for p in params:
        if p.kind not in supported_kinds:
            raise ValueError(
                f"{what} must use only positional parameters (no *args, **kwargs, or keyword-only). "
                f"Got parameter {p.name!r} with kind={p.kind}."
            )
        if p.default is not inspect._empty:
            raise ValueError(
                f"{what} must not define default values. SymPy Function calls are positional and "
                "always provide all arguments."
            )

    return len(params)


def _sympify_for_docs(value: _SymbolicReturn, *, locals_map: dict[str, sp.Symbol]) -> Optional[sp.Basic]:
    """Try to coerce *value* into a SymPy expression (for docs and rewriting).

    Returns
    -------
    sympy.Basic | None
        A SymPy expression if conversion succeeds; otherwise None.
    """
    if value is None:
        return None
    if isinstance(value, sp.Basic):
        return value

    # Try sympify directly; this handles Python ints/floats/complex, etc.
    try:
        coerced = sp.sympify(value, locals=locals_map)
    except Exception:
        coerced = None

    if isinstance(coerced, sp.Basic):
        return coerced

    # If the value is a string-like object, try to sympify its string form.
    # This is the key fix for docstrings that would otherwise render as
    #   \mathtt{\text{x**2 + 1}}
    try:
        coerced2 = sp.sympify(str(value), locals=locals_map)
    except Exception:
        return None

    return coerced2 if isinstance(coerced2, sp.Basic) else None


def _generate_enhanced_docstring(
    *,
    original_doc: Optional[str],
    definition_code: str,
    definition_latex: str
) -> str:
    """Create a consistent docstring for the generated SymPy Function class."""
    doc: list[str] = []

    if original_doc:
        doc.append(textwrap.dedent(original_doc).strip())
        doc.append("")

    doc.append("NamedFunction-generated SymPy Function.")
    doc.append("")
    doc.append("Definition")
    doc.append("----------")
    doc.append(definition_code)

    if definition_latex:
        doc.append("")
        doc.append("LaTeX")
        doc.append("----")
        doc.append(f"$ {definition_latex} $")


    return "\n".join(doc).strip()


def _doc_placeholders_from_signature(
    sig: inspect.Signature,
    *,
    nargs: int,
    skip_first: bool,
) -> Tuple[sp.Symbol, ...]:
    """Create placeholder symbols for doc generation, using parameter names if possible."""
    params = list(sig.parameters.values())
    start = 1 if skip_first else 0
    names = [p.name for p in params[start:]]

    # If anything looks inconsistent, fall back to x_0, x_1, ...
    if len(names) != nargs:
        return tuple(_get_smart_latex_symbol(f"x_{i}") for i in range(nargs))

    return tuple(_get_smart_latex_symbol(nm) for nm in names)


def _build_definition_strings(
    *,
    func_name: str,
    sig: inspect.Signature,
    nargs: int,
    call_symbolic: Callable[..., _SymbolicReturn],
    skip_first_arg: bool,
) -> Tuple[str, str]:
    """Compute the code and LaTeX definition strings for documentation.

    This function is best-effort: failures must not prevent decoration.
    """
    syms = _doc_placeholders_from_signature(sig, nargs=nargs, skip_first=skip_first_arg)
    locals_map = {s.name: s for s in syms}

    try:
        raw_value = call_symbolic(*syms) if not skip_first_arg else call_symbolic(None, *syms)
    except Exception as e:
        return f"Could not expand definition automatically.\nError: {e}", ""

    if raw_value is None:
        return "`None` (Opaque function)", ""

    expr = _sympify_for_docs(raw_value, locals_map=locals_map)
    args_code = ", ".join(str(s) for s in syms)
    lhs_code = f"{func_name}({args_code})"

    if expr is None:
        # Fall back: still show something useful, but avoid pretending we have valid math.
        return f"`{lhs_code} = {raw_value!r}`", ""

    # Code-style definition: readable and copy-pastable.
    rhs_code = sp.sstr(expr)
    code_def = f"`{lhs_code} = {rhs_code}`"

    # LaTeX-style definition.
    args_latex = ", ".join(sp.latex(s) for s in syms)
    rhs_latex = sp.latex(expr)
    latex_def = f"{_latex_function_name(func_name)}({args_latex}) = {rhs_latex}"
    return code_def, latex_def


# === SECTION: Public decorator [id: public]===
#
# Single entrypoint that dispatches based on whether it is decorating a function or class.
# === END SECTION: Public decorator ===


def NamedFunction(obj: Union[_SymbolicCallable, Type[_NamedFunctionSpec]]) -> Type[sp.Function]:
    """Decorate a Python callable or spec class to produce a SymPy Function class.

    Two modes are supported.

    Mode 1: function decorator
        The decorated function must accept ``n`` positional arguments and return:
        - a SymPy expression (or any sympifiable value) for symbolic expansion, or
        - ``None`` to indicate an opaque/undefined symbolic expansion.

        You may also attach a NumPy implementation by setting ``func.f_numpy = callable``
        *before* decorating.

    Mode 2: class decorator
        The decorated class must define exactly two methods:

        - ``symbolic(self, *args)``: returns a SymPy expression (or sympifiable value) or ``None``.
        - ``numeric(self, *args)``: returns a NumPy-compatible value.

        The resulting SymPy Function class exposes ``f_numpy(*args)`` that calls the class's
        ``numeric`` method (without instantiating the class).

    Parameters
    ----------
    obj:
        A function or a class meeting the requirements above.

    Returns
    -------
    Type[sympy.Function]
        A SymPy Function subclass with name equal to the original object name.

    Raises
    ------
    TypeError
        If ``obj`` is neither a function nor a class.
    ValueError
        If the decorated object does not meet the required signature constraints.
    """
    if inspect.isclass(obj):
        return _handle_class_decoration(cast(Type[_NamedFunctionSpec], obj))
    if callable(obj):
        return _handle_function_decoration(cast(_SymbolicCallable, obj))
    raise TypeError(f"@NamedFunction must decorate a function or a class, not {type(obj)}")


# === SECTION: Decoration implementations [id: impl]===
#
# Helpers that build SymPy Function subclasses.
# === END SECTION: Decoration implementations ===


def _handle_function_decoration(func: _SymbolicCallable) -> Type[sp.Function]:
    """Create a SymPy Function class from a plain function."""
    sig = inspect.signature(func)
    nargs = _validate_fixed_positional_signature(sig, what=f"function {getattr(func, '__name__', '<callable>')}")

    has_numpy = callable(getattr(func, "f_numpy", None))

    definition_code, definition_latex = _build_definition_strings(
        func_name=func.__name__,
        sig=sig,
        nargs=nargs,
        call_symbolic=func,
        skip_first_arg=False,
    )

    new_doc = _generate_enhanced_docstring(
        original_doc=func.__doc__,
        definition_code=definition_code,
        definition_latex=definition_latex
    )

    def _eval_rewrite_as_expand_definition(self: sp.Function, *args: object, **_kwargs: object) -> sp.Basic:
        raw = func(*args)
        if raw is None or raw == self:
            return self

        # Best-effort coercion; if we can't make a SymPy object, keep opaque.
        locals_map = {f"x_{i}": _get_smart_latex_symbol(f"x_{i}") for i in range(len(args))}
        expr = _sympify_for_docs(cast(_SymbolicReturn, raw), locals_map=locals_map)
        return self if expr is None else cast(sp.Basic, expr)

    def _eval_evalf(self: sp.Function, prec: int) -> sp.Basic:
        rewritten = self.rewrite("expand_definition")
        if rewritten == self:
            return self
        return cast(sp.Basic, rewritten.evalf(prec))

    class_dict: dict[str, object] = {
        "nargs": nargs,
        "_eval_rewrite_as_expand_definition": _eval_rewrite_as_expand_definition,
        "_eval_evalf": _eval_evalf,
        "__module__": func.__module__,
        "__doc__": new_doc,
        "_original_func": staticmethod(func),
        "f_numpy": getattr(func, "f_numpy", None),
    }

    NewClass = _SignedFunctionMeta(func.__name__, (sp.Function,), class_dict)
    NewClass._custom_signature = sig
    return cast(Type[sp.Function], NewClass)


def _handle_class_decoration(cls: Type[_NamedFunctionSpec]) -> Type[sp.Function]:
    """Create a SymPy Function class from a spec class (symbolic + numeric)."""
    if not hasattr(cls, "symbolic") or not hasattr(cls, "numeric"):
        raise ValueError(
            f"Class {cls.__name__} decorated with @NamedFunction must define both "
            "'symbolic' and 'numeric' methods."
        )

    symbolic_func = getattr(cls, "symbolic")
    numeric_func = getattr(cls, "numeric")

    sig_sym = inspect.signature(symbolic_func)
    sig_num = inspect.signature(numeric_func)

    nparams_sym = _validate_fixed_positional_signature(sig_sym, what=f"{cls.__name__}.symbolic")
    nparams_num = _validate_fixed_positional_signature(sig_num, what=f"{cls.__name__}.numeric")

    if nparams_sym != nparams_num:
        raise ValueError(
            f"Signature mismatch in {cls.__name__}: 'symbolic' takes {nparams_sym} parameters "
            f"but 'numeric' takes {nparams_num} parameters."
        )

    nargs = nparams_sym - 1
    if nargs < 0:
        raise ValueError(f"{cls.__name__}.symbolic must accept at least 'self'.")

    definition_code, definition_latex = _build_definition_strings(
        func_name=cls.__name__,
        sig=sig_sym,
        nargs=nargs,
        call_symbolic=symbolic_func,
        skip_first_arg=True,
    )

    new_doc = _generate_enhanced_docstring(
        original_doc=cls.__doc__,
        definition_code=definition_code,
        definition_latex=definition_latex
    )

    def _eval_rewrite_as_expand_definition(self: sp.Function, *args: object, **_kwargs: object) -> sp.Basic:
        raw = symbolic_func(None, *args)
        if raw is None or raw == self:
            return self

        locals_map = {f"x_{i}": _get_smart_latex_symbol(f"x_{i}") for i in range(len(args))}
        expr = _sympify_for_docs(cast(_SymbolicReturn, raw), locals_map=locals_map)
        return self if expr is None else cast(sp.Basic, expr)

    def _eval_evalf(self: sp.Function, prec: int) -> sp.Basic:
        rewritten = self.rewrite("expand_definition")
        if rewritten == self:
            return self
        return cast(sp.Basic, rewritten.evalf(prec))

    @staticmethod
    def f_numpy(*args: object) -> object:
        return numeric_func(None, *args)

    # Store a signature matching SymPy usage (no 'self').
    params = list(sig_sym.parameters.values())[1:]
    public_sig = inspect.Signature(params)

    class_dict: dict[str, object] = {
        "nargs": nargs,
        "_eval_rewrite_as_expand_definition": _eval_rewrite_as_expand_definition,
        "_eval_evalf": _eval_evalf,
        "__module__": cls.__module__,
        "__doc__": new_doc,
        "f_numpy": f_numpy,
        "_original_class": cls,
    }

    NewClass = _SignedFunctionMeta(cls.__name__, (sp.Function,), class_dict)
    NewClass._custom_signature = public_sig
    return cast(Type[sp.Function], NewClass)
