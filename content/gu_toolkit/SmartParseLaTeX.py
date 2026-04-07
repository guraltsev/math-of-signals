"""LaTeX parsing helpers with backend fallback for notebook ergonomics.

The default behavior prefers SymPy's ``lark`` backend and falls back to
``antlr`` when necessary. This keeps parsing resilient in interactive notebook
sessions where parser availability can vary.
"""

from __future__ import annotations

from typing import Any

from sympy.parsing.latex import parse_latex as _sympy_parse_latex

__all__ = ["LatexParseError", "parse_latex"]


class LatexParseError(RuntimeError):
    """Raised when both configured SymPy LaTeX backends fail to parse input."""


def parse_latex(tex: str, *args: Any, **kwargs: Any):
    """Parse a LaTeX string into a SymPy expression with backend fallback.

    Parameters
    ----------
    tex : str
        LaTeX input expression.
    *args : Any
        Positional arguments forwarded to SymPy's parser.
    **kwargs : Any
        Keyword arguments forwarded to SymPy's parser. If ``backend`` is
        supplied explicitly, the fallback flow is bypassed.

    Returns
    -------
    sympy.Basic
        Parsed symbolic expression.

    Raises
    ------
    LatexParseError
        If fallback mode is active and both ``lark`` and ``antlr`` fail.

    Examples
    --------
    >>> parse_latex(r"x^2 + 1")  # doctest: +SKIP
    x**2 + 1
    >>> parse_latex(r"\\frac{1}{x}", backend="antlr")  # doctest: +SKIP
    1/x

    See Also
    --------
    sympy.parsing.latex.parse_latex
        Underlying SymPy parser wrapped by this helper.
    """
    backend = kwargs.get("backend", None)

    if backend is not None:
        return _sympy_parse_latex(tex, *args, **kwargs)

    lark_err = None
    try:
        return _sympy_parse_latex(tex, *args, backend="lark", **kwargs)
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
