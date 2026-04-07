"""Public entry point for the audited MathLive rebuild surface.

This package now exposes two notebook-facing widget classes:

- :class:`gu_toolkit.math_input.widget.MathInput` for generic raw-LaTeX input.
- :class:`gu_toolkit.math_input.identifier_widget.IdentifierInput` for a
  separate, visibly constrained plain-identifier field with explicit context
  policy.

The frontend implementations use MathLive behind AnyWidget bridges, but that
backend detail stays private to this subpackage so the user-facing Python APIs
remain small and auditable.

Examples
--------
Generic expression field::

    from gu_toolkit.math_input import MathInput
    field = MathInput(value=r"x^2 + 1")
    field

Separate identifier field::

    from gu_toolkit.math_input import IdentifierInput
    name = IdentifierInput(
        value="mass",
        context_names=["mass", "time", "speed"],
        context_policy="context_only",
    )
    name

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
- Guide: ``docs/guides/math-input.md``.
- Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
- Contract tests: ``tests/test_math_input_widget.py`` and ``tests/test_identifier_input_widget.py``.
"""

from .identifier_widget import IdentifierInput
from .widget import MathInput

__all__ = ["MathInput", "IdentifierInput"]
