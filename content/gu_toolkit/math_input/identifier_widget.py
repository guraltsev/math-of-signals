"""Minimal audited identifier-input widget for the MathLive rebuild.

Phase 3 keeps ``IdentifierInput`` as a separate widget and extends only one
visible capability on top of the Phase 2 baseline: ``context_or_new`` now uses
canonical identifier rules from ``gu_toolkit.identifiers`` instead of a local
regular expression. In practical terms, this means the widget can now accept
canonical names such as ``alpha``, ``theta_x`` and ``a_1_2`` on the Python
side, while the frontend can visibly work with their supported display forms
such as ``\alpha`` and ``x_{1}``.

The public contract in this phase is:

- Python-side ``value`` and ``context_names`` remain canonical identifier
  strings, not raw LaTeX.
- Canonical validation comes from ``gu_toolkit.identifiers.validate_identifier``.
- ``context_or_new`` allows new canonical identifiers that round-trip through
  the toolkit identifier layer, including Greek names and subscripted names.
- ``IdentifierInput`` bakes in a default forbidden-symbol list for common
  function-style names such as ``sin``, ``cos``, and ``log``.
- The forbidden-symbol list can be replaced at construction time.
- Forbidden names are rejected immediately when provided through Python traits
  or through ``context_names``.
- Invalid frontend drafts may remain visible for correction, but they do not
  overwrite the last accepted Python value.

Examples
--------
Create an identifier field that only accepts names from a provided context::

    from gu_toolkit import IdentifierInput
    field = IdentifierInput(
        value="mass",
        context_names=["mass", "theta_x", "alpha"],
        context_policy="context_only",
    )
    field

Create an identifier field that allows a new canonical name while forbidding the
built-in function-like defaults::

    field = IdentifierInput(
        context_names=["mass", "theta_x", "alpha"],
        context_policy="context_or_new",
    )

Create an identifier field with a custom forbidden list::

    field = IdentifierInput(
        context_policy="context_or_new",
        forbidden_symbols=["alpha", "beta"],
    )

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
- Guide: ``docs/guides/math-input.md``.
- Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
- Contract tests: ``tests/test_math_input_widget.py`` and ``tests/test_identifier_input_widget.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import traitlets
from traitlets import TraitError

from ..identifiers import IdentifierError, validate_identifier
from .widget import MathInput

DEFAULT_FORBIDDEN_SYMBOLS = (
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "sinh",
    "cosh",
    "tanh",
    "log",
    "ln",
    "exp",
)
_CONTEXT_POLICIES = ("context_only", "context_or_new")
MODULE_DIR = Path(__file__).resolve().parent
IDENTIFIER_INPUT_ESM_PATH = MODULE_DIR / "_identifier_input_widget.js"
IDENTIFIER_INPUT_CSS_PATH = MODULE_DIR / "_identifier_input_widget.css"


def _normalize_canonical_identifier(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TraitError(f"{field_name} must be a string.")
    text = value.strip()
    if text == "":
        raise TraitError(f"{field_name} must not be empty.")
    try:
        return validate_identifier(text)
    except IdentifierError as exc:
        raise TraitError(
            f"{field_name} must be a canonical identifier accepted by gu_toolkit.identifiers; "
            f"got {value!r}."
        ) from exc



def _normalize_forbidden_symbols(value: Iterable[str]) -> list[str]:
    names = list(value)
    normalized: list[str] = []
    seen: set[str] = set()
    for name in names:
        canonical = _normalize_canonical_identifier(name, field_name="forbidden_symbols entry")
        if canonical in seen:
            raise TraitError(
                "forbidden_symbols must not contain duplicates; "
                f"repeated entry {canonical!r} found."
            )
        seen.add(canonical)
        normalized.append(canonical)
    return normalized



def _normalize_context_names(
    value: Iterable[str],
    *,
    forbidden_symbols: Iterable[str],
) -> list[str]:
    names = list(value)
    normalized: list[str] = []
    seen: set[str] = set()
    forbidden = set(forbidden_symbols)
    for name in names:
        canonical = _normalize_canonical_identifier(name, field_name="context_names entry")
        if canonical in seen:
            raise TraitError(
                "context_names must not contain duplicates; "
                f"repeated entry {canonical!r} found."
            )
        if canonical in forbidden:
            raise TraitError(
                "context_names must not contain forbidden symbols; "
                f"found forbidden entry {canonical!r}."
            )
        seen.add(canonical)
        normalized.append(canonical)
    return normalized



def _validate_identifier_value(
    value: str,
    *,
    field_name: str,
    forbidden_symbols: Iterable[str],
) -> str:
    if not isinstance(value, str):
        raise TraitError(f"{field_name} must be a string.")
    text = value.strip()
    if text == "":
        return ""
    try:
        canonical = validate_identifier(text)
    except IdentifierError as exc:
        raise TraitError(
            f"{field_name} must be empty or a canonical identifier accepted by "
            f"gu_toolkit.identifiers; got {value!r}."
        ) from exc
    forbidden = set(forbidden_symbols)
    if canonical in forbidden:
        raise TraitError(f"{field_name} {canonical!r} is forbidden in IdentifierInput.")
    return canonical



def _validate_value_against_policy(
    value: str,
    *,
    context_names: list[str],
    context_policy: str,
    forbidden_symbols: list[str],
    field_name: str,
) -> str:
    canonical = _validate_identifier_value(
        value,
        field_name=field_name,
        forbidden_symbols=forbidden_symbols,
    )
    if canonical == "":
        return canonical
    if context_policy == "context_only" and canonical not in context_names:
        raise TraitError(
            f"{field_name} {canonical!r} is not present in context_names under context_only policy."
        )
    return canonical


class IdentifierInput(MathInput):
    """Render a visibly constrained notebook identifier field with explicit context policy.

    Full API
    --------
    ``IdentifierInput(value: str = "", context_names: Iterable[str] = (), context_policy: str = "context_only", forbidden_symbols: Iterable[str] | None = None, **kwargs: Any)``

    Public members exposed from this class: ``value``, ``context_names``, ``context_policy``, ``forbidden_symbols``

    Parameters
    ----------
    value : str, optional
        Canonical identifier string synchronized between Python and the frontend
        when the current frontend content is accepted. The empty string is
        allowed. Any non-empty value must satisfy
        ``gu_toolkit.identifiers.validate_identifier()`` and must not appear in
        ``forbidden_symbols``. Defaults to ``""``.

    context_names : Iterable[str], optional
        Allowed or menu-suggested canonical identifier names, depending on
        ``context_policy``. Every entry must satisfy the canonical identifier
        rules from ``gu_toolkit.identifiers`` and must not appear in
        ``forbidden_symbols``. Defaults to ``()``.

    context_policy : str, optional
        Explicit identifier policy. Use ``"context_only"`` to accept only names
        listed in ``context_names``. Use ``"context_or_new"`` to suggest names
        from ``context_names`` through the identifier menu while still allowing
        a new canonical identifier validated by ``gu_toolkit.identifiers``.
        Defaults to ``"context_only"``.

    forbidden_symbols : Iterable[str] | None, optional
        Canonical identifier names that this widget must reject. When omitted or
        ``None``, the widget uses ``DEFAULT_FORBIDDEN_SYMBOLS``. This is meant
        for function-style names such as ``sin`` or ``log`` that should stay
        unavailable inside ``IdentifierInput`` even though they are valid
        canonical identifiers elsewhere in the toolkit.

    **kwargs : Any, optional
        Additional widget keyword arguments forwarded to the underlying widget
        base class, such as ``layout``. Optional variadic input.

    Returns
    -------
    IdentifierInput
        Widget instance whose ``value``, ``context_names``, ``context_policy``,
        and ``forbidden_symbols`` traits are synchronized with the rendered
        identifier field.

    Optional arguments
    ------------------
    - ``value=""``: Canonical identifier string mirrored between Python and the frontend when accepted.
    - ``context_names=()``: Context identifiers exposed through the identifier menu.
    - ``context_policy="context_only"``: Explicit identifier admission policy.
    - ``forbidden_symbols=None``: Replacement forbidden-symbol list. When omitted, ``DEFAULT_FORBIDDEN_SYMBOLS`` is used.
    - ``**kwargs``: Forwarded widget keywords. When omitted, the widget uses a simple full-width layout.

    Architecture note
    -----------------
    ``IdentifierInput`` remains a separate subclass rather than a role flag
    layered onto ``MathInput``. In this phase it keeps the narrow audited widget
    surface from Phase 2, but delegates Python-side name validation to
    ``gu_toolkit.identifiers`` so the canonical symbolic rules are no longer
    duplicated in Python. The frontend still uses a small explicit bridge to
    keep invalid drafts visible, expose a restricted context menu, and show a
    constrained identifier-only virtual keyboard in ``context_or_new`` mode.
    Forbidden names are rejected early in Python for trusted state, while the
    frontend leaves forbidden drafts visible and invalid so the user can correct
    them manually.

    Examples
    --------
    Context-only identifier field::

        from gu_toolkit import IdentifierInput
        field = IdentifierInput(
            value="mass",
            context_names=["mass", "theta_x", "alpha"],
            context_policy="context_only",
        )
        field

    Suggest-or-new identifier field with Greek and subscript support::

        field = IdentifierInput(
            context_names=["mass", "theta_x", "alpha"],
            context_policy="context_or_new",
        )
        field.value = "theta_x"

    Suggest-or-new identifier field with a custom forbidden list::

        field = IdentifierInput(
            context_policy="context_or_new",
            forbidden_symbols=["alpha", "beta"],
        )

    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map.
    - Guide: ``docs/guides/math-input.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Contract tests: ``tests/test_math_input_widget.py`` and ``tests/test_identifier_input_widget.py``.
    """

    # Keep asset source paths explicit and module-local.
    # Real anywidget may replace MathInput._esm/_css with wrapped asset objects
    # during class creation, so deriving identifier assets from those runtime
    # attributes is not import-safe.
    _esm = IDENTIFIER_INPUT_ESM_PATH
    _css = IDENTIFIER_INPUT_CSS_PATH

    context_names = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)
    context_policy = traitlets.Enum(_CONTEXT_POLICIES, default_value="context_only").tag(sync=True)
    forbidden_symbols = traitlets.List(
        trait=traitlets.Unicode(),
        default_value=list(DEFAULT_FORBIDDEN_SYMBOLS),
    ).tag(sync=True)

    def __init__(
        self,
        value: str = "",
        context_names: Iterable[str] = (),
        context_policy: str = "context_only",
        forbidden_symbols: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> None:
        normalized_forbidden_symbols = _normalize_forbidden_symbols(
            DEFAULT_FORBIDDEN_SYMBOLS if forbidden_symbols is None else forbidden_symbols
        )
        normalized_context_names = _normalize_context_names(
            context_names,
            forbidden_symbols=normalized_forbidden_symbols,
        )
        if context_policy not in _CONTEXT_POLICIES:
            raise TraitError(
                "context_policy must be one of "
                f"{_CONTEXT_POLICIES!r}; got {context_policy!r}."
            )
        _validate_value_against_policy(
            value,
            context_names=normalized_context_names,
            context_policy=context_policy,
            forbidden_symbols=normalized_forbidden_symbols,
            field_name="value",
        )

        super().__init__(value="", **kwargs)
        self.forbidden_symbols = normalized_forbidden_symbols
        self.context_names = normalized_context_names
        self.context_policy = context_policy
        if value != "":
            self.value = value

    @traitlets.validate("value")
    def _validate_value_trait(self, proposal: dict[str, Any]) -> str:
        value = proposal["value"]
        return _validate_value_against_policy(
            value,
            context_names=list(self.context_names),
            context_policy=str(self.context_policy),
            forbidden_symbols=list(self.forbidden_symbols),
            field_name="value",
        )

    @traitlets.validate("context_names")
    def _validate_context_names_trait(self, proposal: dict[str, Any]) -> list[str]:
        normalized = _normalize_context_names(
            proposal["value"],
            forbidden_symbols=list(self.forbidden_symbols),
        )
        _validate_value_against_policy(
            str(self.value),
            context_names=normalized,
            context_policy=str(self.context_policy),
            forbidden_symbols=list(self.forbidden_symbols),
            field_name="value",
        )
        return normalized

    @traitlets.validate("context_policy")
    def _validate_context_policy_trait(self, proposal: dict[str, Any]) -> str:
        policy = proposal["value"]
        if policy not in _CONTEXT_POLICIES:
            raise TraitError(
                "context_policy must be one of "
                f"{_CONTEXT_POLICIES!r}; got {policy!r}."
            )
        _validate_value_against_policy(
            str(self.value),
            context_names=list(self.context_names),
            context_policy=str(policy),
            forbidden_symbols=list(self.forbidden_symbols),
            field_name="value",
        )
        return str(policy)

    @traitlets.validate("forbidden_symbols")
    def _validate_forbidden_symbols_trait(self, proposal: dict[str, Any]) -> list[str]:
        normalized = _normalize_forbidden_symbols(proposal["value"])
        normalized_context_names = _normalize_context_names(
            list(self.context_names),
            forbidden_symbols=normalized,
        )
        _validate_value_against_policy(
            str(self.value),
            context_names=normalized_context_names,
            context_policy=str(self.context_policy),
            forbidden_symbols=normalized,
            field_name="value",
        )
        return normalized
