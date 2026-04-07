"""Symbolic convenience helpers used throughout the notebook-facing API.

The :mod:`gu_toolkit.Symbolic` module provides lightweight wrappers around
core SymPy constructs to make interactive expression authoring concise and
readable:

* :class:`SymbolFamily` creates a *family* of symbols that can be indexed via
  ``[]`` while preserving SymPy assumptions.
* :class:`FunctionFamily` creates indexed SymPy undefined functions and also
  behaves like a callable base function.
* :func:`symbols` creates one or more symbol/function families from a
  space-separated string, mirroring :func:`sympy.symbols` ergonomics.
* :class:`Infix` and the predefined operator instances (:data:`eq`,
  :data:`lt`, :data:`le`, :data:`gt`, :data:`ge`) provide pipe-based infix
  syntax such as ``a |eq| b`` for relational construction.

Names are normalized into LaTeX-oriented SymPy names by default. This means
Greek identifiers such as ``"alpha"`` become ``"\\alpha"``, indexed symbols
use explicit braces (for example ``x_{1}``), and multi-letter function names
are wrapped in ``\\operatorname{...}`` unless the user already supplied an
explicit LaTeX form.
"""

from __future__ import annotations

from numbers import Integral
from typing import Any

import sympy as sp

from .identifiers import (
    function_head_to_latex,
    function_latex_method,
    identifier_to_latex,
    semantic_function,
    symbol,
    validate_identifier,
)


def _create_family(factory, source, **kwargs):
    """Create family objects while preserving SymPy's output shape."""

    if isinstance(source, sp.Symbol):
        return factory(source.name, **kwargs)
    if isinstance(source, (tuple, list, set)):
        mapped = (_create_family(factory, item, **kwargs) for item in source)
        return type(source)(mapped)
    return factory(str(source), **kwargs)


def _canonicalize_index_component(value: Any) -> str:
    """Return one canonical identifier atom for an indexed family lookup."""

    if isinstance(value, sp.Integer):
        return str(int(value))
    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, str):
        text = str(value).strip()
        if not text:
            raise ValueError("Index components may not be empty.")
        if text.isdigit():
            return text
        if not text.replace("_", "").isalnum():
            raise ValueError(
                f"String index components may only contain letters, digits, and underscores, got {text!r}."
            )
        return text
    if isinstance(value, sp.Symbol):
        return str(value.name)
    if isinstance(value, sp.Basic):
        return str(sp.sstr(value))
    return str(value)


def _build_indexed_name(base_name: str, indices: tuple[Any, ...]) -> str:
    """Combine one canonical base name with canonical subscript atoms."""

    pieces = [base_name]
    for item in indices:
        atom = _canonicalize_index_component(item)
        pieces.append(atom.replace("_", "__"))
    return "_".join(pieces)

def _make_semantic_function(name: str, **kwargs: Any) -> type[sp.Function]:
    """Create one undefined SymPy function class with semantic LaTeX metadata."""

    canonical = validate_identifier(str(name), role="function")
    return sp.Function(
        canonical,
        __dict__={
            "__gu_name__": canonical,
            "__gu_latex__": function_head_to_latex(canonical),
            "_latex": function_latex_method,
        },
        **kwargs,
    )


def symbols(names, *, cls=sp.Symbol, **args) -> Any:
    """Create one or more symbolic families with SymPy-compatible signature.
    
    Full API
    --------
    ``symbols(names, *, cls=sp.Symbol, **args) -> Any``
    
    Parameters
    ----------
    names : Any
        Value for ``names`` in this API. Required.
    
    cls : Any, optional
        Value for ``cls`` in this API. Defaults to ``sp.Symbol``.
    
    **args : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``cls=sp.Symbol``: Value for ``cls`` in this API.
    - ``**args``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.Symbolic``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.Symbolic import symbols
        result = symbols(...)
    
    Discovery-oriented use::
    
        help(symbols)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(symbols)`` and inspect sibling APIs in the same module.
    """

    if cls in (sp.Symbol, SymbolFamily):
        family_cls = SymbolFamily
    elif cls in (sp.Function, FunctionFamily):
        family_cls = FunctionFamily
    else:
        return sp.symbols(names, cls=cls, **args)

    parser_args = {}
    if "seq" in args:
        parser_args["seq"] = args["seq"]
    parsed = sp.symbols(names, cls=sp.Symbol, **parser_args)
    return _create_family(family_cls, parsed, **args)


class SymbolFamily(sp.Symbol):
    """A SymPy symbol that lazily creates indexed child symbols.
    
    Full API
    --------
    ``SymbolFamily()``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    SymbolFamily
        New ``SymbolFamily`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``SymbolFamily`` lives in ``gu_toolkit.Symbolic``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.Symbolic import SymbolFamily
        obj = SymbolFamily(...)
    
    Discovery-oriented use::
    
        help(SymbolFamily)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(SymbolFamily)`` and ``dir(SymbolFamily)`` to inspect adjacent members.
    """

    def __new__(cls, name, **kwargs):
        """Create the family root symbol and initialize child caches."""

        canonical_name = validate_identifier(str(name), role="symbol")
        obj = super().__new__(cls, canonical_name, **kwargs)
        obj._family_cache = {}
        obj._family_kwargs = kwargs
        return obj

    def __getitem__(self, k):
        """Return an indexed child symbol from this family.

        Parameters
        ----------
        k:
            A single index value or a tuple of index values.

        Returns
        -------
        sympy.Symbol
            Cached or newly-created child symbol named with ``self.name`` and
            the provided indices.
        """

        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._family_cache:
            child_name = _build_indexed_name(self.name, k)
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
        return self._family_cache[k]


class FunctionFamily:
    """A family of SymPy undefined functions supporting indexed lookup.
    
    Full API
    --------
    ``FunctionFamily(name, **kwargs)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    name : Any
        Human-readable or canonical name for the target object. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    FunctionFamily
        New ``FunctionFamily`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``FunctionFamily`` lives in ``gu_toolkit.Symbolic``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.Symbolic import FunctionFamily
        obj = FunctionFamily(...)
    
    Discovery-oriented use::
    
        help(FunctionFamily)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(FunctionFamily)`` and ``dir(FunctionFamily)`` to inspect adjacent members.
    """

    def __init__(self, name, **kwargs):
        """Initialize the base function and index cache."""

        self.name = validate_identifier(str(name), role="function")
        self._kwargs = kwargs
        self._base = _make_semantic_function(self.name, **kwargs)
        self._cache = {}

    def __getitem__(self, k):
        """Return an indexed function symbol for ``k``.

        Parameters
        ----------
        k:
            A single index value or a tuple of index values.

        Returns
        -------
        sympy.FunctionClass
            Cached or newly-created undefined function class.
        """

        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            indexed_name = _build_indexed_name(self.name, k)
            self._cache[k] = _make_semantic_function(indexed_name, **self._kwargs)
        return self._cache[k]

    def __call__(self, *args):
        """Call the base undefined function with positional arguments."""

        return self._base(*args)

    def _sympy_(self):
        """Return the wrapped SymPy object for SymPy protocol interop."""

        return self._base

    def __str__(self):
        """Return the string representation of the base function."""

        return str(self._base)

    def __repr__(self):
        """Return the repr of the base function."""

        return repr(self._base)


class Infix:
    """Pipe-based infix operator adapter.
    
    Full API
    --------
    ``Infix(func)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    Returns
    -------
    Infix
        New ``Infix`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``Infix`` lives in ``gu_toolkit.Symbolic``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.Symbolic import Infix
        obj = Infix(...)
    
    Discovery-oriented use::
    
        help(Infix)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(Infix)`` and ``dir(Infix)`` to inspect adjacent members.
    """

    __slots__ = ("func",)

    def __init__(self, func):
        """Store the callable used to evaluate infix expressions."""

        self.func = func

    def __ror__(self, left):
        """Capture the left operand and return a partial infix object."""

        return _InfixPartial(self.func, left)


class _InfixPartial:
    """Internal helper that stores the left-hand operand for :class:`Infix`."""

    __slots__ = ("func", "left")

    def __init__(self, func, left):
        self.func = func
        self.left = left

    def __or__(self, right):
        """Apply the wrapped binary callable to ``(left, right)``."""

        return self.func(self.left, right)


#: Infix wrapper for :func:`sympy.Eq`.
eq = Infix(sp.Eq)
#: Infix wrapper for :func:`sympy.Lt`.
lt = Infix(sp.Lt)
#: Infix wrapper for :func:`sympy.Le`.
le = Infix(sp.Le)
#: Infix wrapper for :func:`sympy.Gt`.
gt = Infix(sp.Gt)
#: Infix wrapper for :func:`sympy.Ge`.
ge = Infix(sp.Ge)


__all__ = [
    "symbol",
    "symbols",
    "SymbolFamily",
    "FunctionFamily",
    "Infix",
    "eq",
    "lt",
    "le",
    "gt",
    "ge",
]
