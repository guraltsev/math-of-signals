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
from collections.abc import Callable
from typing import Protocol, cast

import sympy as sp

__all__ = [
    # Public API
    "NamedFunction",
]


# === SECTION: Types & protocols [id: types]===
#
# Keep public signatures free of `Any` while still documenting intent.
# === END SECTION: Types & protocols ===


_SymbolicReturn = sp.Basic | int | float | complex | str | None
_SymbolicCallable = Callable[..., _SymbolicReturn]


class _NamedFunctionSpec(Protocol):
    """Protocol for @NamedFunction class-decoration.

    A spec class is never instantiated; its methods are called with ``self=None``.
    """

    def symbolic(self, *args: sp.Basic) -> _SymbolicReturn:
        """Return the symbolic expansion/definition for the function call.
        
        Full API
        --------
        ``obj.symbolic(*args: sp.Basic) -> _SymbolicReturn``
        
        Parameters
        ----------
        *args : sp.Basic, optional
            Additional positional arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        _SymbolicReturn
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
        
        Architecture note
        -----------------
        This member belongs to ``_NamedFunctionSpec``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _NamedFunctionSpec(...)
            result = obj.symbolic(...)
        
        Discovery-oriented use::
        
            help(_NamedFunctionSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(_NamedFunctionSpec)`` and ``dir(_NamedFunctionSpec)`` to inspect adjacent members.
        """
        ...

    def numeric(self, *args: object) -> object:
        """Return a numeric implementation used by ``numpify`` bindings.
        
        Full API
        --------
        ``obj.numeric(*args: object) -> object``
        
        Parameters
        ----------
        *args : object, optional
            Additional positional arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        object
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
        
        Architecture note
        -----------------
        This member belongs to ``_NamedFunctionSpec``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _NamedFunctionSpec(...)
            result = obj.numeric(...)
        
        Discovery-oriented use::
        
            help(_NamedFunctionSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
        - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
        - In a notebook or REPL, run ``help(_NamedFunctionSpec)`` and ``dir(_NamedFunctionSpec)`` to inspect adjacent members.
        """
        ...


# === SECTION: Signature support [id: signature]===
#
# SymPy's Function metaclass makes __signature__ read-only. We override it at the
# metaclass level to preserve `inspect.signature(...)` for generated classes.
# === END SECTION: Signature support ===


class _SignedFunctionMeta(type(sp.Function)):
    """Metaclass that allows overriding ``__signature__`` on generated classes."""

    @property
    def __signature__(cls) -> inspect.Signature | None:  # noqa: D401
        """Expose generated call signatures for ``inspect.signature``."""
        # Invariant: we only set `_custom_signature` on classes created by this module.
        return cast(inspect.Signature | None, getattr(cls, "_custom_signature", None))


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


def _sympify_for_docs(
    value: _SymbolicReturn, *, locals_map: dict[str, sp.Symbol]
) -> sp.Basic | None:
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
    *, original_doc: str | None, definition_code: str, definition_latex: str
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
) -> tuple[sp.Symbol, ...]:
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
) -> tuple[str, str]:
    """Compute the code and LaTeX definition strings for documentation.

    This function is best-effort: failures must not prevent decoration.
    """
    syms = _doc_placeholders_from_signature(sig, nargs=nargs, skip_first=skip_first_arg)
    locals_map = {s.name: s for s in syms}

    try:
        raw_value = (
            call_symbolic(*syms) if not skip_first_arg else call_symbolic(None, *syms)
        )
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


def NamedFunction(
    obj: _SymbolicCallable | type[_NamedFunctionSpec],
) -> type[sp.Function]:
    """Decorate a Python callable or spec class to produce a SymPy Function class.
    
    Full API
    --------
    ``NamedFunction(obj: _SymbolicCallable | type[_NamedFunctionSpec]) -> type[sp.Function]``
    
    Parameters
    ----------
    obj : _SymbolicCallable | type[_NamedFunctionSpec]
        Value for ``obj`` in this API. Required.
    
    Returns
    -------
    type[sp.Function]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.NamedFunction``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.NamedFunction import NamedFunction
        result = NamedFunction(...)
    
    Discovery-oriented use::
    
        help(NamedFunction)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(NamedFunction)`` and inspect sibling APIs in the same module.
    """
    if inspect.isclass(obj):
        return _handle_class_decoration(cast(type[_NamedFunctionSpec], obj))
    if callable(obj):
        return _handle_function_decoration(cast(_SymbolicCallable, obj))
    raise TypeError(
        f"@NamedFunction must decorate a function or a class, not {type(obj)}"
    )


# === SECTION: Decoration implementations [id: impl]===
#
# Helpers that build SymPy Function subclasses.
# === END SECTION: Decoration implementations ===


def _handle_function_decoration(func: _SymbolicCallable) -> type[sp.Function]:
    """Create a SymPy Function class from a plain function."""
    sig = inspect.signature(func)
    nargs = _validate_fixed_positional_signature(
        sig, what=f"function {getattr(func, '__name__', '<callable>')}"
    )

    callable(getattr(func, "f_numpy", None))

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
        definition_latex=definition_latex,
    )

    def _eval_rewrite_as_expand_definition(
        self: sp.Function, *args: object, **_kwargs: object
    ) -> sp.Basic:
        raw = func(*args)
        if raw is None or raw == self:
            return self

        # Best-effort coercion; if we can't make a SymPy object, keep opaque.
        locals_map = {
            f"x_{i}": _get_smart_latex_symbol(f"x_{i}") for i in range(len(args))
        }
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
    return cast(type[sp.Function], NewClass)


def _handle_class_decoration(cls: type[_NamedFunctionSpec]) -> type[sp.Function]:
    """Create a SymPy Function class from a spec class (symbolic + numeric)."""
    if not hasattr(cls, "symbolic") or not hasattr(cls, "numeric"):
        raise ValueError(
            f"Class {cls.__name__} decorated with @NamedFunction must define both "
            "'symbolic' and 'numeric' methods."
        )

    symbolic_func = cls.symbolic
    numeric_func = cls.numeric

    sig_sym = inspect.signature(symbolic_func)
    sig_num = inspect.signature(numeric_func)

    nparams_sym = _validate_fixed_positional_signature(
        sig_sym, what=f"{cls.__name__}.symbolic"
    )
    nparams_num = _validate_fixed_positional_signature(
        sig_num, what=f"{cls.__name__}.numeric"
    )

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
        definition_latex=definition_latex,
    )

    def _eval_rewrite_as_expand_definition(
        self: sp.Function, *args: object, **_kwargs: object
    ) -> sp.Basic:
        raw = symbolic_func(None, *args)
        if raw is None or raw == self:
            return self

        locals_map = {
            f"x_{i}": _get_smart_latex_symbol(f"x_{i}") for i in range(len(args))
        }
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
    return cast(type[sp.Function], NewClass)
