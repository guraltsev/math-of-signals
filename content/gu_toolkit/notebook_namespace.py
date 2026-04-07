"""Backward-compatible alias for the notebook convenience namespace.

This module keeps legacy imports working:

>>> from gu_toolkit.notebook_namespace import sp  # doctest: +SKIP

The canonical module is :mod:`gu_toolkit.Notebook`, which exposes the same
notebook-friendly symbols for interactive workflows.
"""

from .Notebook import *  # noqa: F403
