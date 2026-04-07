"""Canonical identifier rules, rendering helpers, and reversible parsing.

This module centralizes the toolkit's identifier semantics so symbolic identity
stays separate from presentation. Canonical identifiers are plain validated
strings (for example ``velocity``, ``a_1_2`` or ``theta__x``); display LaTeX is
always derived from those names rather than stored in ``Symbol.name``.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from typing import Any, Iterable

import sympy as sp

__all__ = [
    "CANONICAL_IDENTIFIER_RE",
    "ExpressionRenderContext",
    "IdentifierError",
    "build_symbol_names",
    "encode_identifier_atoms",
    "function_head_to_latex",
    "function_latex_method",
    "identifier_to_latex",
    "parse_identifier",
    "register_symbol_latex",
    "render_latex",
    "rewrite_wrapped_identifier_calls",
    "semantic_function",
    "split_identifier_atoms",
    "strip_math_delimiters",
    "symbol",
    "symbol_latex_override",
    "validate_identifier",
]


CANONICAL_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_ATOM_TEXT_RE = re.compile(r"^[A-Za-z0-9_]+$")
_ALPHA_ATOM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_DIGIT_ATOM_RE = re.compile(r"^[0-9]+$")


_GREEK_NAME_TO_LATEX: dict[str, str] = {
    "alpha": r"\alpha",
    "beta": r"\beta",
    "gamma": r"\gamma",
    "delta": r"\delta",
    "epsilon": r"\epsilon",
    "varepsilon": r"\varepsilon",
    "zeta": r"\zeta",
    "eta": r"\eta",
    "theta": r"\theta",
    "vartheta": r"\vartheta",
    "iota": r"\iota",
    "kappa": r"\kappa",
    "lambda": r"\lambda",
    "mu": r"\mu",
    "nu": r"\nu",
    "xi": r"\xi",
    "omicron": r"o",
    "pi": r"\pi",
    "rho": r"\rho",
    "sigma": r"\sigma",
    "tau": r"\tau",
    "upsilon": r"\upsilon",
    "phi": r"\phi",
    "varphi": r"\varphi",
    "chi": r"\chi",
    "psi": r"\psi",
    "omega": r"\omega",
    "Gamma": r"\Gamma",
    "Delta": r"\Delta",
    "Theta": r"\Theta",
    "Lambda": r"\Lambda",
    "Xi": r"\Xi",
    "Pi": r"\Pi",
    "Sigma": r"\Sigma",
    "Upsilon": r"\Upsilon",
    "Phi": r"\Phi",
    "Psi": r"\Psi",
    "Omega": r"\Omega",
}

_GREEK_LATEX_TO_NAME = {value: key for key, value in _GREEK_NAME_TO_LATEX.items()}
_IDENTIFIER_LATEX_COMMANDS: dict[str, str] = {
    **{name: name for name in _GREEK_NAME_TO_LATEX},
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "cot": "cot",
    "sec": "sec",
    "csc": "csc",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
    "log": "log",
    "ln": "ln",
    "exp": "exp",
}

_EXPLICIT_MACRO_IDENTIFIERS = {"lambda", "Lambda"}
_SYMBOL_LATEX_OVERRIDES: dict[str, str] = {}
_SEMANTIC_FUNCTION_CACHE: dict[str, type[sp.Function]] = {}


class IdentifierError(ValueError):
    """Exception raised when an identifier cannot be validated or parsed under the toolkit's canonical naming rules.
    
    Full API
    --------
    ``IdentifierError(*args: object)``
    
    Parameters
    ----------
    *args : object
        Positional message fragments forwarded to ``ValueError``.
    
    Returns
    -------
    IdentifierError
        Exception instance raised by the identifier layer and reused by higher-level semantic-math helpers.
    
    Optional arguments
    ------------------
    This exception type does not define toolkit-specific optional arguments; any ``*args`` are forwarded to ``ValueError``.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import IdentifierError, validate_identifier
    
        try:
            validate_identifier(r"\\theta")
        except IdentifierError:
            pass
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """


@dataclass(frozen=True)
class IdentifierScanResult:
    """Structured result for scanning one identifier-sized segment out of a larger text buffer.
    
    Full API
    --------
    ``IdentifierScanResult(canonical: 'str', end: 'int', explicit: 'bool') -> None``
    
    Parameters
    ----------
    canonical : str
        Canonical identifier spelling that was scanned from the source text.
    
    end : int
        Index just past the scanned identifier segment.
    
    explicit : bool
        Whether the scanned spelling was explicit enough to stand on its own (for example a wrapped or subscripted form) rather than context-dependent.
    
    Returns
    -------
    IdentifierScanResult
        Immutable record containing the canonical name, the scan end offset, and whether the matched spelling was explicit rather than context-dependent.
    
    Optional arguments
    ------------------
    This record has no optional fields; all three constructor arguments are required because a scan result is only meaningful when it has a canonical name, end offset, and explicitness flag.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import scan_identifier_segment
    
        scan_identifier_segment(r"\\theta + x", 0)
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    canonical: str
    end: int
    explicit: bool


@dataclass(frozen=True)
class ExpressionRenderContext:
    """Immutable record carrying explicit SymPy symbol-to-LaTeX overrides for semantic rendering.
    
    Full API
    --------
    ``ExpressionRenderContext(symbol_names: 'dict[sp.Symbol, str]') -> None``
    
    Parameters
    ----------
    symbol_names : dict[sp.Symbol, str]
        Explicit mapping from SymPy symbols to the LaTeX strings that should represent them during rendering.
    
    Returns
    -------
    ExpressionRenderContext
        Immutable record whose ``symbol_names`` mapping can be handed to SymPy's LaTeX printer or to ``render_latex()``.
    
    Optional arguments
    ------------------
    This record has no optional fields. Pass an explicit ``symbol_names`` mapping whenever you need rendering to use a specific display form.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import symbol
        from gu_toolkit.identifiers.policy import ExpressionRenderContext
    
        ExpressionRenderContext(symbol_names={symbol("theta__x"): r"\\mathrm{theta\\_x}"})
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    symbol_names: dict[sp.Symbol, str]


def strip_math_delimiters(text: str) -> str:
    """Remove outer ``$...$``, ``\\(...\\)``, or ``\\[...\\]`` delimiters from a math fragment.
    
    Full API
    --------
    ``strip_math_delimiters(text: 'str') -> 'str'``
    
    Parameters
    ----------
    text : str
        User-supplied identifier or expression text. The text may already be canonical or may use one of the supported display-LaTeX spellings.
    
    Returns
    -------
    str
        The input text without an outer inline/display math wrapper. Inner content is left unchanged apart from surrounding whitespace trimming.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import strip_math_delimiters
    
        strip_math_delimiters(r"$\\theta$")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    stripped = str(text or "").strip()
    if len(stripped) >= 2 and stripped[0] == "$" and stripped[-1] == "$":
        return stripped[1:-1].strip()
    if stripped.startswith(r"\(") and stripped.endswith(r"\)"):
        return stripped[2:-2].strip()
    if stripped.startswith(r"\[") and stripped.endswith(r"\]"):
        return stripped[2:-2].strip()
    return stripped


def validate_identifier(name: str, *, role: str = "identifier") -> str:
    """Validate that a name already uses the toolkit's canonical identifier grammar.
    
    Full API
    --------
    ``validate_identifier(name: 'str', *, role: 'str' = 'identifier') -> 'str'``
    
    Parameters
    ----------
    name : str
        Canonical identifier or function name. Canonical names are plain validated strings such as ``theta__x`` or ``a_1_2`` rather than raw display LaTeX.
    
    role : str, optional
        Human-readable noun used in error messages when validation or parsing fails.
    
    Returns
    -------
    str
        The validated canonical identifier. The returned string is suitable for storage, ``sympy.Symbol`` names, and context registration.
    
    Optional arguments
    ------------------
    - ``role='identifier'``: Human-readable noun used in error messages when validation or parsing fails.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import validate_identifier
    
        validate_identifier("theta__x")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    text = str(name or "").strip()
    if not CANONICAL_IDENTIFIER_RE.match(text):
        raise IdentifierError(
            f"{role.capitalize()} must match {CANONICAL_IDENTIFIER_RE.pattern!r}, got {text!r}."
        )
    split_identifier_atoms(text, _validated=True)
    return text


def split_identifier_atoms(name: str, *, _validated: bool = False) -> tuple[str, ...]:
    """Decode a canonical identifier into the atoms that define its base name and subscript parts.
    
    Full API
    --------
    ``split_identifier_atoms(name: 'str', *, _validated: 'bool' = False) -> 'tuple[str, ...]'``
    
    Parameters
    ----------
    name : str
        Canonical identifier or function name. Canonical names are plain validated strings such as ``theta__x`` or ``a_1_2`` rather than raw display LaTeX.
    
    _validated : bool, optional
        Value for ``_validated`` in this API.
    
    Returns
    -------
    tuple[str, ...]
        Canonical atoms such as ``("a", "1", "2")`` for ``"a_1_2"`` or ``("theta_x",)`` for ``"theta__x"``.
    
    Optional arguments
    ------------------
    - ``_validated=False``: Value for ``_validated`` in this API.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import split_identifier_atoms
    
        split_identifier_atoms("a_1_2")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    text = str(name or "").strip()
    if not _validated:
        validate_identifier(text)

    atoms: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "_":
            current.append(char)
            index += 1
            continue

        if index + 1 < len(text) and text[index + 1] == "_":
            current.append("_")
            index += 2
            continue

        if not current:
            raise IdentifierError(f"Invalid identifier {text!r}: empty atom before '_' .")
        atoms.append("".join(current))
        current = []
        index += 1

    if not current:
        raise IdentifierError(f"Invalid identifier {text!r}: trailing '_' is not allowed.")
    atoms.append("".join(current))
    return tuple(atoms)


def encode_identifier_atoms(atoms: Iterable[str], *, role: str = "identifier") -> str:
    """Encode identifier atoms back into the canonical storage spelling used by the toolkit.
    
    Full API
    --------
    ``encode_identifier_atoms(atoms: 'Iterable[str]', *, role: 'str' = 'identifier') -> 'str'``
    
    Parameters
    ----------
    atoms : Iterable[str]
        Display atoms that should be encoded into one canonical identifier. Literal underscores stay inside an atom; subscript boundaries become separate atoms.
    
    role : str, optional
        Human-readable noun used in error messages when validation or parsing fails.
    
    Returns
    -------
    str
        Canonical identifier spelling that round-trips through ``split_identifier_atoms()`` and keeps literal underscores encoded with doubled underscores.
    
    Optional arguments
    ------------------
    - ``role='identifier'``: Human-readable noun used in error messages when validation or parsing fails.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import encode_identifier_atoms
    
        encode_identifier_atoms(["theta_x"])
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    pieces = [str(atom).strip() for atom in atoms]
    if not pieces or not pieces[0]:
        raise IdentifierError(f"{role.capitalize()} must contain at least one atom.")

    encoded = []
    for index, atom in enumerate(pieces):
        if not atom:
            raise IdentifierError(f"{role.capitalize()} cannot contain empty atoms.")
        if not _ATOM_TEXT_RE.match(atom):
            raise IdentifierError(
                f"{role.capitalize()} atom {atom!r} may only contain letters, digits, and underscores."
            )
        if index == 0 and atom[0].isdigit():
            raise IdentifierError(f"{role.capitalize()} must start with a letter, got {atom!r}.")
        encoded.append(atom.replace("_", "__"))

    return validate_identifier("_".join(encoded), role=role)


def _escape_math_text_atom(atom: str) -> str:
    return atom.replace("_", r"\_")


def _render_atom(atom: str, *, text_command: str = "mathrm") -> str:
    if "_" in atom:
        return rf"\{text_command}{{{_escape_math_text_atom(atom)}}}"
    if atom in _GREEK_NAME_TO_LATEX:
        return _GREEK_NAME_TO_LATEX[atom]
    if atom.isdigit():
        return atom
    if len(atom) == 1:
        return atom
    return rf"\{text_command}{{{atom}}}"


def _render_identifier(name: str, *, text_command: str, role: str) -> str:
    atoms = split_identifier_atoms(validate_identifier(name, role=role))
    base = _render_atom(atoms[0], text_command=text_command)
    if len(atoms) == 1:
        return base
    subscript = ",".join(_render_atom(atom, text_command=text_command) for atom in atoms[1:])
    return f"{base}_{{{subscript}}}"


def identifier_to_latex(name: str, *, latex_expr: str | None = None) -> str:
    """Render a canonical identifier name as display LaTeX.
    
    Full API
    --------
    ``identifier_to_latex(name: 'str', *, latex_expr: 'str | None' = None) -> 'str'``
    
    Parameters
    ----------
    name : str
        Canonical identifier or function name. Canonical names are plain validated strings such as ``theta__x`` or ``a_1_2`` rather than raw display LaTeX.
    
    latex_expr : str | None, optional
        Display-LaTeX override for a symbol. When omitted or empty, the display form is derived automatically from the canonical name.
    
    Returns
    -------
    str
        Display LaTeX for the identifier. Single-letter and Greek names stay compact; multi-letter atoms fall back to readable ``\\mathrm{...}`` forms unless an override is supplied.
    
    Optional arguments
    ------------------
    - ``latex_expr=None``: Display-LaTeX override for a symbol. When omitted or empty, the display form is derived automatically from the canonical name.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import identifier_to_latex
    
        identifier_to_latex("theta__x")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    if latex_expr is not None:
        text = str(latex_expr).strip()
        if text:
            return text
    return _render_identifier(name, text_command="mathrm", role="identifier")


def symbol(name: str, *, latex_expr: str | None = None, **kwargs: Any) -> sp.Symbol:
    """Create one toolkit-aware SymPy symbol by validating a canonical identifier before calling ``sympy.Symbol``.
    
    Full API
    --------
    ``symbol(name: 'str', *, latex_expr: 'str | None' = None, **kwargs: 'Any') -> 'sp.Symbol'``
    
    Parameters
    ----------
    name : str
        Canonical identifier name. Canonical names are validated plain strings such as ``theta__x`` or ``a_1_2`` rather than raw display LaTeX.
    
    latex_expr : str | None, optional
        Optional display-LaTeX override stored for later rendering. When omitted or empty, the display form is derived automatically from the canonical name.
    
    **kwargs : Any
        Keyword arguments forwarded directly to ``sympy.Symbol``. Use them for normal SymPy assumptions such as ``real=True`` or ``positive=True``.
    
    Returns
    -------
    sp.Symbol
        Regular ``sympy.Symbol`` instance whose ``.name`` is the validated canonical identifier. If ``latex_expr`` is supplied, the helper also records that override for later use by ``build_symbol_names()`` and ``render_latex()``.
    
    Optional arguments
    ------------------
    - ``latex_expr=None``: Optional display-LaTeX override stored for later rendering.
    - ``**kwargs``: Keyword arguments forwarded directly to ``sympy.Symbol``.
    
    Architecture note
    -----------------
    This helper intentionally wraps ``sympy.Symbol`` rather than replacing SymPy's symbol model. Use ``symbol()`` when you want one symbol that participates in the toolkit's canonical-identifier validation and optional LaTeX metadata. Use ``sympy.Symbol(...)`` for raw SymPy construction without toolkit validation/metadata. Use ``sympy.symbols(...)`` when you want to create many plain SymPy symbols at once; if each name should be toolkit-validated, call ``symbol()`` for each one.
    
    Examples
    --------
    Basic use::
    
        import sympy as sp
        from gu_toolkit.identifiers import symbol
    
        theta_x = symbol("theta__x", latex_expr=r"\\vartheta_x", real=True)
        assert isinstance(theta_x, sp.Symbol)
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    canonical = validate_identifier(name, role="symbol")
    if latex_expr is not None:
        register_symbol_latex(canonical, latex_expr)
    return sp.Symbol(canonical, **kwargs)


def register_symbol_latex(symbol_or_name: str | sp.Symbol, latex_expr: str) -> None:
    """Register or clear a display-LaTeX override for a canonical symbol name.
    
    Full API
    --------
    ``register_symbol_latex(symbol_or_name: 'str | sp.Symbol', latex_expr: 'str') -> 'None'``
    
    Parameters
    ----------
    symbol_or_name : str | sp.Symbol
        Canonical symbol name or a ``sympy.Symbol`` whose ``.name`` should be used.
    
    latex_expr : str
        Display-LaTeX override for a symbol. When omitted or empty, the display form is derived automatically from the canonical name.
    
    Returns
    -------
    None
        ``None``. The call updates module-level display metadata used by ``symbol_latex_override()``, ``build_symbol_names()``, and ``render_latex()``.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import register_symbol_latex, symbol
    
        theta_x = symbol("theta__x")
        register_symbol_latex(theta_x, r"\\vartheta_x")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    if isinstance(symbol_or_name, sp.Symbol):
        name = symbol_or_name.name
    else:
        name = str(symbol_or_name)
    canonical = validate_identifier(name, role="symbol")
    text = str(latex_expr or "").strip()
    if not text:
        _SYMBOL_LATEX_OVERRIDES.pop(canonical, None)
        return
    _SYMBOL_LATEX_OVERRIDES[canonical] = text


def symbol_latex_override(symbol_or_name: str | sp.Symbol) -> str | None:
    """Look up the stored display-LaTeX override for a canonical symbol, if one has been registered.
    
    Full API
    --------
    ``symbol_latex_override(symbol_or_name: 'str | sp.Symbol') -> 'str | None'``
    
    Parameters
    ----------
    symbol_or_name : str | sp.Symbol
        Canonical symbol name or a ``sympy.Symbol`` whose ``.name`` should be used.
    
    Returns
    -------
    str | None
        Registered display-LaTeX override for the symbol name, or ``None`` when the symbol should render from canonical spelling alone.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import symbol
        from gu_toolkit.identifiers.policy import symbol_latex_override
    
        theta_x = symbol("theta__x", latex_expr=r"\\vartheta_x")
        symbol_latex_override(theta_x)
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    if isinstance(symbol_or_name, sp.Symbol):
        name = symbol_or_name.name
    else:
        name = str(symbol_or_name)
    return _SYMBOL_LATEX_OVERRIDES.get(name)


def build_symbol_names(
    expr: Any,
    *,
    explicit: dict[sp.Symbol, str] | None = None,
) -> dict[sp.Symbol, str]:
    """Build the ``symbol_names`` mapping consumed by SymPy's LaTeX printer for semantic rendering.
    
    Full API
    --------
    ``build_symbol_names(expr: 'Any', *, explicit: 'dict[sp.Symbol, str] | None' = None) -> 'dict[sp.Symbol, str]'``
    
    Parameters
    ----------
    expr : Any
        Expression, symbol, or SymPy-compatible value to inspect, render, or parse against.
    
    explicit : dict[sp.Symbol, str] | None, optional
        Explicit ``sympy.Symbol -> latex`` overrides that should win over automatically derived display names.
    
    Returns
    -------
    dict[sp.Symbol, str]
        Mapping from SymPy symbols to the display-LaTeX strings that should override SymPy's default rendering for the given expression.
    
    Optional arguments
    ------------------
    - ``explicit=None``: Explicit ``sympy.Symbol -> latex`` overrides that should win over automatically derived display names.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import symbol
        from gu_toolkit.identifiers.policy import build_symbol_names
    
        expr = symbol("theta__x") + symbol("velocity")
        build_symbol_names(expr)
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    mapping: dict[sp.Symbol, str] = {}
    if explicit:
        mapping.update(explicit)

    free_symbols = set(getattr(expr, "free_symbols", set()))
    if isinstance(expr, sp.Symbol):
        free_symbols.add(expr)

    for sym in free_symbols:
        if not isinstance(sym, sp.Symbol):
            continue
        if sym in mapping:
            continue
        override = symbol_latex_override(sym)
        if override is not None:
            mapping[sym] = override
            continue
        try:
            mapping[sym] = identifier_to_latex(sym.name)
        except IdentifierError:
            continue
    return mapping


def render_latex(
    expr: Any,
    *,
    symbol_names: dict[sp.Symbol, str] | None = None,
) -> str:
    """Render a SymPy expression using canonical identifier display rules and stored symbol overrides.
    
    Full API
    --------
    ``render_latex(expr: 'Any', *, symbol_names: 'dict[sp.Symbol, str] | None' = None) -> 'str'``
    
    Parameters
    ----------
    expr : Any
        Expression, symbol, or SymPy-compatible value to inspect, render, or parse against.
    
    symbol_names : dict[sp.Symbol, str] | None, optional
        Explicit ``sympy.Symbol -> latex`` overrides passed to the renderer. These are merged with any stored semantic symbol metadata.
    
    Returns
    -------
    str
        LaTeX string produced from the expression after semantic symbol-name overrides have been merged into SymPy's printer.
    
    Optional arguments
    ------------------
    - ``symbol_names=None``: Explicit ``sympy.Symbol -> latex`` overrides passed to the renderer. These are merged with any stored semantic symbol metadata.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import render_latex, symbol
    
        expr = symbol("theta__x") + symbol("velocity")
        render_latex(expr)
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    if isinstance(expr, str):
        return expr
    try:
        sym_expr = sp.sympify(expr)
    except Exception:
        return str(expr)
    mapping = build_symbol_names(sym_expr, explicit=symbol_names)
    if mapping:
        return sp.latex(sym_expr, symbol_names=mapping)
    return sp.latex(sym_expr)


def function_head_to_latex(name: str, *, latex_head: str | None = None) -> str:
    """Render a canonical function name as the LaTeX head used in a call expression.
    
    Full API
    --------
    ``function_head_to_latex(name: 'str', *, latex_head: 'str | None' = None) -> 'str'``
    
    Parameters
    ----------
    name : str
        Canonical identifier or function name. Canonical names are plain validated strings such as ``theta__x`` or ``a_1_2`` rather than raw display LaTeX.
    
    latex_head : str | None, optional
        Display-LaTeX override for a function head. When omitted, the head is derived automatically from the canonical function name.
    
    Returns
    -------
    str
        Display LaTeX for a semantic function head, typically a single letter, a Greek macro, or an ``\\operatorname{...}`` form with optional subscript atoms.
    
    Optional arguments
    ------------------
    - ``latex_head=None``: Display-LaTeX override for a function head. When omitted, the head is derived automatically from the canonical function name.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import function_head_to_latex
    
        function_head_to_latex("Force_t")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    if latex_head is not None:
        text = str(latex_head).strip()
        if text:
            return text
    return _render_identifier(name, text_command="operatorname", role="function")


def function_latex_method(self: sp.Function, printer: Any) -> str:
    """SymPy ``_latex`` hook installed on semantic function classes created by ``semantic_function()``.
    
    Full API
    --------
    ``function_latex_method(printer: 'Any') -> 'str'``
    
    Parameters
    ----------
    printer : Any
        SymPy LaTeX printer instance calling the installed ``_latex`` hook.
    
    Returns
    -------
    str
        LaTeX string for the current function application. This hook is installed on semantic function classes so ``sp.latex(...)`` renders their heads semantically.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This hook lives in ``gu_toolkit.identifiers.policy`` but is not meant to be the primary entry point. ``semantic_function()`` installs it on generated SymPy function classes so ``sp.latex(...)`` prints semantic call heads consistently.
    
    Examples
    --------
    Basic use::
    
        import sympy as sp
        from gu_toolkit.identifiers.policy import semantic_function
    
        Force_t = semantic_function("Force_t")
        sp.latex(Force_t(sp.Symbol("x")))
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    func = self.func
    name = getattr(func, "__gu_name__", getattr(func, "__name__", str(func)))
    latex_head = getattr(func, "__gu_latex__", None)
    head = function_head_to_latex(str(name), latex_head=latex_head)
    args = ", ".join(printer._print(arg) for arg in self.args)
    return f"{head}({args})"


def semantic_function(name: str, *, latex_head: str | None = None) -> type[sp.Function]:
    """Create or reuse a SymPy function class that preserves canonical name and display-head metadata.
    
    Full API
    --------
    ``semantic_function(name: 'str', *, latex_head: 'str | None' = None) -> 'type[sp.Function]'``
    
    Parameters
    ----------
    name : str
        Canonical identifier or function name. Canonical names are plain validated strings such as ``theta__x`` or ``a_1_2`` rather than raw display LaTeX.
    
    latex_head : str | None, optional
        Display-LaTeX override for a function head. When omitted, the head is derived automatically from the canonical function name.
    
    Returns
    -------
    type[sp.Function]
        Cached SymPy function class whose canonical name lives in ``__gu_name__`` and whose display head lives in ``__gu_latex__``.
    
    Optional arguments
    ------------------
    - ``latex_head=None``: Display-LaTeX override for a function head. When omitted, the head is derived automatically from the canonical function name.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import semantic_function
    
        Force_t = semantic_function("Force_t")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    canonical = validate_identifier(name, role="function")
    cached = _SEMANTIC_FUNCTION_CACHE.get(canonical)
    if cached is not None:
        if latex_head is not None:
            cached.__gu_latex__ = function_head_to_latex(canonical, latex_head=latex_head)
        return cached

    cls = sp.Function(
        canonical,
        __dict__={
            "__gu_name__": canonical,
            "__gu_latex__": function_head_to_latex(canonical, latex_head=latex_head),
            "_latex": function_latex_method,
        },
    )
    _SEMANTIC_FUNCTION_CACHE[canonical] = cls
    return cls


def _skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _extract_braced_group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise IdentifierError("Expected '{' while parsing LaTeX input.")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise IdentifierError("Unbalanced braces in LaTeX input.")


def _decode_mathrm_atom(text: str) -> str:
    decoded = text.replace(r"\_", "_").strip()
    if not decoded or not _ATOM_TEXT_RE.match(decoded):
        raise IdentifierError(f"Unsupported \\mathrm atom: {text!r}.")
    return decoded


def _parse_display_atom(text: str, start: int) -> tuple[str, int]:
    index = _skip_spaces(text, start)
    if index >= len(text):
        raise IdentifierError("Expected identifier atom.")

    if text.startswith(r"\mathrm", index) or text.startswith(r"\operatorname", index):
        command = r"\mathrm" if text.startswith(r"\mathrm", index) else r"\operatorname"
        index += len(command)
        index = _skip_spaces(text, index)
        group, index = _extract_braced_group(text, index)
        return _decode_mathrm_atom(group), index

    if text[index] == "\\":
        command_match = re.match(r"\\([A-Za-z]+)", text[index:])
        if command_match is None:
            raise IdentifierError(f"Unsupported LaTeX command near {text[index:index + 12]!r}.")
        command = command_match.group(1)
        if command not in _IDENTIFIER_LATEX_COMMANDS:
            raise IdentifierError(f"Unsupported identifier command \\{command}.")
        return _IDENTIFIER_LATEX_COMMANDS[command], index + len(command_match.group(0))

    digit_match = re.match(r"[0-9]+", text[index:])
    if digit_match is not None:
        return digit_match.group(0), index + len(digit_match.group(0))

    word_match = re.match(r"[A-Za-z][A-Za-z0-9]*", text[index:])
    if word_match is not None:
        return word_match.group(0), index + len(word_match.group(0))

    raise IdentifierError(f"Could not parse identifier atom near {text[index:index + 12]!r}.")


def _parse_display_subscript_atoms(text: str) -> tuple[str, ...]:
    index = 0
    atoms: list[str] = []
    while True:
        index = _skip_spaces(text, index)
        atom, index = _parse_display_atom(text, index)
        atoms.append(atom)
        index = _skip_spaces(text, index)
        if index >= len(text):
            break
        if text[index] != ",":
            raise IdentifierError(f"Expected ',' in identifier subscript list, got {text[index]!r}.")
        index += 1
    return tuple(atoms)


def _parse_display_identifier(text: str, start: int) -> tuple[tuple[str, ...], int]:
    index = _skip_spaces(text, start)
    base, index = _parse_display_atom(text, index)
    atoms = [base]
    index = _skip_spaces(text, index)

    if index < len(text) and text[index] == "_":
        index += 1
        index = _skip_spaces(text, index)
        if index < len(text) and text[index] == "{":
            group, index = _extract_braced_group(text, index)
            atoms.extend(_parse_display_subscript_atoms(group))
        else:
            atom, index = _parse_display_atom(text, index)
            atoms.append(atom)
    return tuple(atoms), index


def _looks_like_call_remainder(text: str) -> bool:
    remainder = text.lstrip()
    return remainder.startswith(("(", "[", r"\left"))


def _split_mathrm_atom_prefix(text: str) -> tuple[str, str] | None:
    index = 0
    while index < len(text):
        if text.startswith(r"\_", index):
            index += 2
            continue
        if text[index].isalnum():
            index += 1
            continue
        break

    if index == 0:
        return None

    prefix = text[:index]
    try:
        canonical = encode_identifier_atoms((_decode_mathrm_atom(prefix),))
    except IdentifierError:
        return None
    return canonical, text[index:]


def _rewrite_wrapped_text_group(group: str) -> str | None:
    try:
        _decode_mathrm_atom(group)
    except IdentifierError:
        pass
    else:
        return None

    try:
        atoms, end = _parse_display_identifier(group, 0)
        canonical = encode_identifier_atoms(atoms)
    except IdentifierError:
        canonical = None
        end = 0
    else:
        remainder = group[end:]
        if _looks_like_call_remainder(remainder):
            return f"{function_head_to_latex(canonical)}{remainder}"

    atom_prefix = _split_mathrm_atom_prefix(group)
    if atom_prefix is not None:
        canonical, remainder = atom_prefix
        if _looks_like_call_remainder(remainder):
            return f"{function_head_to_latex(canonical)}{remainder}"

    return None


def rewrite_wrapped_identifier_calls(text: str) -> str:
    """Rewrite wrapped identifier/function call heads that MathLive emits inside ``\\mathrm{...}`` or ``\\operatorname{...}`` groups.
    
    Full API
    --------
    ``rewrite_wrapped_identifier_calls(text: 'str') -> 'str'``
    
    Parameters
    ----------
    text : str
        User-supplied identifier or expression text. The text may already be canonical or may use one of the supported display-LaTeX spellings.
    
    Returns
    -------
    str
        Rewritten text where wrapped function-call heads such as ``\\mathrm{Force\\left(x\\right)}`` become explicit semantic call heads that the parser can understand.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import rewrite_wrapped_identifier_calls
    
        rewrite_wrapped_identifier_calls(r"\\mathrm{Force\\left(x\\right)}")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    source = str(text or "")
    if not source:
        return source

    result: list[str] = []
    index = 0
    while index < len(source):
        if source.startswith(r"\mathrm", index):
            command = r"\mathrm"
        elif source.startswith(r"\operatorname", index):
            command = r"\operatorname"
        else:
            result.append(source[index])
            index += 1
            continue

        cursor = _skip_spaces(source, index + len(command))
        if cursor >= len(source) or source[cursor] != "{":
            result.append(source[index])
            index += 1
            continue

        try:
            group, end = _extract_braced_group(source, cursor)
        except IdentifierError:
            result.append(source[index])
            index += 1
            continue

        rewritten_group = rewrite_wrapped_identifier_calls(group)
        replacement = _rewrite_wrapped_text_group(rewritten_group)
        if replacement is None:
            result.append(command)
            result.append("{")
            result.append(rewritten_group)
            result.append("}")
        else:
            result.append(replacement)
        index = end

    return "".join(result)


def parse_identifier(text: str) -> str:
    """Parse canonical text or supported display LaTeX back into a canonical identifier name.
    
    Full API
    --------
    ``parse_identifier(text: 'str') -> 'str'``
    
    Parameters
    ----------
    text : str
        User-supplied identifier or expression text. The text may already be canonical or may use one of the supported display-LaTeX spellings.
    
    Returns
    -------
    str
        Canonical identifier spelling recovered from the supplied text. Unsupported or ambiguous input raises ``IdentifierError``.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers import parse_identifier
    
        parse_identifier(r"\\mathrm{theta\\_x}")
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    source = strip_math_delimiters(str(text or "")).strip()
    if not source:
        raise IdentifierError("Identifier is required.")

    try:
        return validate_identifier(source)
    except IdentifierError:
        pass

    atoms, index = _parse_display_identifier(source, 0)
    index = _skip_spaces(source, index)
    if index != len(source):
        raise IdentifierError(f"Unexpected trailing text in identifier: {source[index:]!r}.")
    return encode_identifier_atoms(atoms)


def _scan_command_identifier(text: str, start: int) -> IdentifierScanResult | None:
    if text[start] != "\\":
        return None

    if text.startswith(r"\mathrm", start) or text.startswith(r"\operatorname", start):
        atoms, end = _parse_display_identifier(text, start)
        canonical = encode_identifier_atoms(atoms)
        return IdentifierScanResult(canonical=canonical, end=end, explicit=True)

    command_match = re.match(r"\\([A-Za-z]+)", text[start:])
    if command_match is None:
        return None
    command = command_match.group(1)
    if command not in _IDENTIFIER_LATEX_COMMANDS:
        return None

    base = _IDENTIFIER_LATEX_COMMANDS[command]
    end = start + len(command_match.group(0))
    explicit = command in _EXPLICIT_MACRO_IDENTIFIERS
    end = _skip_spaces(text, end)
    if end < len(text) and text[end] == "_":
        atoms, end = _parse_display_identifier(text, start)
        return IdentifierScanResult(
            canonical=encode_identifier_atoms(atoms),
            end=end,
            explicit=True,
        )
    return IdentifierScanResult(canonical=base, end=end, explicit=explicit)


def _scan_word_identifier(text: str, start: int) -> IdentifierScanResult | None:
    if not text[start].isalpha():
        return None

    raw_match = re.match(r"[A-Za-z][A-Za-z0-9_]*", text[start:])
    if raw_match is None:
        return None
    raw = raw_match.group(0)
    end = start + len(raw)

    if "_" in raw:
        try:
            canonical = validate_identifier(raw)
        except IdentifierError:
            canonical = ""
        else:
            return IdentifierScanResult(canonical=canonical, end=end, explicit=True)

    base_match = re.match(r"[A-Za-z][A-Za-z0-9]*", text[start:])
    if base_match is None:
        return None
    base = base_match.group(0)
    base_end = start + len(base)
    probe = _skip_spaces(text, base_end)
    if probe < len(text) and text[probe] == "_":
        atoms, end = _parse_display_identifier(text, start)
        return IdentifierScanResult(
            canonical=encode_identifier_atoms(atoms),
            end=end,
            explicit=True,
        )
    return IdentifierScanResult(canonical=base, end=base_end, explicit=False)


def scan_identifier_segment(text: str, start: int) -> IdentifierScanResult | None:
    """Scan one identifier-like segment from a larger text buffer without parsing the whole string.
    
    Full API
    --------
    ``scan_identifier_segment(text: 'str', start: 'int') -> 'IdentifierScanResult | None'``
    
    Parameters
    ----------
    text : str
        User-supplied identifier or expression text. The text may already be canonical or may use one of the supported display-LaTeX spellings.
    
    start : int
        Zero-based offset where scanning should begin inside ``text``.
    
    Returns
    -------
    IdentifierScanResult | None
        Scan record for the identifier that starts at ``start``, or ``None`` if the text at that offset cannot begin an identifier.
    
    Optional arguments
    ------------------
    This API has no optional parameters.
    
    Architecture note
    -----------------
    This API lives in ``gu_toolkit.identifiers.policy``, the source-of-truth layer for canonical identifier semantics. Higher-level helpers should call into this layer rather than inventing their own naming rules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.identifiers.policy import scan_identifier_segment
    
        scan_identifier_segment(r"\\theta + x", 0)
    
    Discovery-oriented use::
    
        help(symbol)
        help(parse_identifier)
    
    Learn more / explore
    --------------------
    - Start with the semantic-math row in ``docs/guides/api-discovery.md``.
    - Guide: ``docs/guides/semantic-math-refactoring-philosophy.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Secondary notebook: ``examples/Robust_identifier_system_showcase.ipynb``.
    - Focused tests: ``tests/semantic_math/test_identifier_policy.py`` and ``tests/semantic_math/test_symbolic_identifier_families.py``.
    """

    if start >= len(text):
        return None
    if text[start] == "\\":
        return _scan_command_identifier(text, start)
    if text[start].isalpha():
        return _scan_word_identifier(text, start)
    return None
