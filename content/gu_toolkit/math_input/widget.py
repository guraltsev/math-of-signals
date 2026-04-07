"""Minimal audited generic math-input widget for the MathLive rebuild.

``MathInput`` remains the small generic baseline in Phase 2. Its public Python
contract is still a single ``value`` trait containing the raw LaTeX string
owned by the widget model. Frontend rendering and synchronization are delegated
to a small AnyWidget bridge that imports MathLive as an implementation detail,
not as part of the public API.

The design goal is auditability rather than completeness:

- no identifier rules,
- no context-sensitive suggestions,
- no menu customization,
- no role switching,
- no semantic post-processing.

The frontend bootstrap now also configures explicit MathLive asset paths instead
of relying on broken implicit CDN-relative font or sound URLs.

Examples
--------
Create and display a field in a notebook::

    from gu_toolkit import MathInput
    field = MathInput(value=r"\\frac{x+1}{x-1}")
    field

Read and set the raw value from Python::

    field.value
    field.value = r"\\int_0^1 x^2\\,dx"

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
- Guide: ``docs/guides/math-input.md``.
- Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
- Contract test: ``tests/test_math_input_widget.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import traitlets

from .._widget_stubs import anywidget, widgets

MODULE_DIR = Path(__file__).resolve().parent
MATH_INPUT_ESM_PATH = MODULE_DIR / "_math_input_widget.js"
MATH_INPUT_CSS_PATH = MODULE_DIR / "_math_input_widget.css"


class MathInput(anywidget.AnyWidget):
    """Render a generic notebook math-input field that synchronizes raw LaTeX with Python.

    Full API
    --------
    ``MathInput(value: str = "", **kwargs: Any)``

    Public members exposed from this class: ``value``

    Parameters
    ----------
    value : str, optional
        Raw LaTeX string used to initialize the field. This is the only
        synchronized generic widget value and is mirrored directly to and from
        the frontend math field. Defaults to ``""``.

    **kwargs : Any, optional
        Additional widget keyword arguments forwarded to the underlying widget
        base class, such as ``layout``. Optional variadic input.

    Returns
    -------
    MathInput
        Widget instance whose ``value`` trait is synchronized with the rendered
        field.

    Optional arguments
    ------------------
    - ``value=""``: Raw LaTeX string used to initialize the field and mirrored
      directly between Python and the frontend.
    - ``**kwargs``: Forwarded widget keywords. When omitted, the widget uses a
      simple full-width layout.

    Architecture note
    -----------------
    ``MathInput`` remains the complete generic math-input surface in Phase 2. It owns a
    single explicit contract—``value`` as a raw LaTeX string—and keeps the
    MathLive dependency behind the private frontend bridge inside
    ``gu_toolkit.math_input``. The frontend bridge also sets explicit MathLive
    font and sound configuration so notebook rendering does not depend on
    broken implicit asset paths. Later phases should add new behavior in small,
    visibly verifiable layers instead of mutating this class into a policy-heavy
    abstraction.

    Examples
    --------
    Basic use::

        from gu_toolkit import MathInput
        field = MathInput(value=r"\\frac{x+1}{x-1}")
        field

    Discovery-oriented use::

        help(MathInput)
        field = MathInput()
        field.value

    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map.
    - Guide: ``docs/guides/math-input.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Contract test: ``tests/test_math_input_widget.py``.
    """

    _esm = MATH_INPUT_ESM_PATH
    _css = MATH_INPUT_CSS_PATH

    value = traitlets.Unicode("").tag(sync=True)

    def __init__(self, value: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("layout", widgets.Layout(width="100%"))
        super().__init__(value=value, **kwargs)
