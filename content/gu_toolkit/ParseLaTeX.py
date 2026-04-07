"""LaTeX parsing helpers with backend fallback for notebook ergonomics.

The default behavior prefers SymPy's ``lark`` backend and falls back to
``antlr`` when necessary. This keeps parsing resilient in interactive notebook
sessions where parser availability can vary.
"""

from __future__ import annotations

from typing import Any

from sympy import Basic
from sympy.parsing.latex import parse_latex as _sympy_parse_latex

__all__ = ["LatexParseError", "parse_latex"]


class LatexParseError(RuntimeError):
    """Raised when both configured SymPy LaTeX backends fail to parse input.
    
    Full API
    --------
    ``LatexParseError()``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    LatexParseError
        New ``LatexParseError`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``LatexParseError`` lives in ``gu_toolkit.ParseLaTeX``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.ParseLaTeX import LatexParseError
        obj = LatexParseError(...)
    
    Discovery-oriented use::
    
        help(LatexParseError)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(LatexParseError)`` and ``dir(LatexParseError)`` to inspect adjacent members.
    """


def parse_latex(tex: str, *args: Any, **kwargs: Any):
    """Parse a LaTeX string into a SymPy expression with backend fallback.
    
    Full API
    --------
    ``parse_latex(tex: str, *args: Any, **kwargs: Any)``
    
    Parameters
    ----------
    tex : str
        Value for ``tex`` in this API. Required.
    
    *args : Any, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ParseLaTeX``. These helpers bridge symbolic authoring with numeric execution so notebook expressions can stay concise without giving up compiled evaluation.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ParseLaTeX import parse_latex
        result = parse_latex(...)
    
    Discovery-oriented use::
    
        help(parse_latex)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Regression/spec tests: ``tests/test_numeric_callable_api.py``.
    - Runtime discovery tip: compare symbolic authoring helpers with the numeric-callable tests/examples to see how symbolic inputs become numeric callables.
    - In a notebook or REPL, run ``help(parse_latex)`` and inspect sibling APIs in the same module.
    """
    backend = kwargs.get("backend")

    if backend is not None:
        return _sympy_parse_latex(tex, *args, **kwargs)

    lark_err = None
    try:
        lark_result = _sympy_parse_latex(tex, *args, backend="lark", **kwargs)
        if isinstance(lark_result, Basic):
            return lark_result
        raise TypeError(
            f"lark backend returned non-SymPy result ({type(lark_result).__name__})"
        )
    except Exception as e:
        lark_err = e

    try:
        return _sympy_parse_latex(tex, *args, backend="antlr", **kwargs)
    except Exception as antlr_err:
        raise LatexParseError(
            "Failed to parse LaTeX with both backends.\n"
            f"Input: {tex!r}\n"
            f"Lark error: {type(lark_err).__name__}: {lark_err}\n"
            f"ANTLR error: {type(antlr_err).__name__}: {antlr_err}"
        ) from antlr_err
