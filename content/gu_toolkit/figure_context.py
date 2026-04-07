"""Figure context stack and defaults."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .Figure import Figure

from .figure_plot_style import PLOT_STYLE_OPTIONS
from .figure_types import NumberLike, NumberLikeOrStr, RangeLike, VisibleSpec

_FIGURE_STACK_LOCAL = threading.local()


def _figure_stack() -> list[Figure]:
    """Return a thread-local figure stack."""
    stack = getattr(_FIGURE_STACK_LOCAL, "stack", None)
    if stack is None:
        stack = []
        _FIGURE_STACK_LOCAL.stack = stack
    return stack


class _FigureDefaultSentinel:
    """Sentinel value meaning "inherit from figure defaults"."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return the stable debug token for the figure-default sentinel."""
        return "FIGURE_DEFAULT"


FIGURE_DEFAULT = _FigureDefaultSentinel()


def _is_figure_default(value: Any) -> bool:
    """Return True when *value* requests figure-default behavior."""
    return value is FIGURE_DEFAULT or (
        isinstance(value, str) and value.lower() == "figure_default"
    )


def _current_figure() -> Figure | None:
    """Return the most recently pushed Figure, if any.

    Returns
    -------
    Figure or None
        The current figure on the stack, or ``None`` if no figure is active.
    """
    stack = _figure_stack()
    if not stack:
        return None
    return stack[-1]


def _require_current_figure() -> Figure:
    """Return the current Figure, or raise if none is active.

    Returns
    -------
    Figure
        The active Figure on the stack.

    Raises
    ------
    RuntimeError
        If no Figure is active.
    """
    fig = _current_figure()
    if fig is None:
        raise RuntimeError("No current Figure. Use `with fig:` first.")
    return fig


def current_figure(*, required: bool = True) -> Figure | None:
    """Return the active Figure from the context stack.
    
    Full API
    --------
    ``current_figure(*, required: bool=True) -> Figure | None``
    
    Parameters
    ----------
    required : bool, optional
        Value for ``required`` in this API. Defaults to ``True``.
    
    Returns
    -------
    Figure | None
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``required=True``: Value for ``required`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_context``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_context import current_figure
        result = current_figure(...)
    
    Discovery-oriented use::
    
        help(current_figure)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(current_figure)`` and inspect sibling APIs in the same module.
    """
    fig = _current_figure()
    if fig is None and required:
        raise RuntimeError(
            "No active Figure. Use `with fig:` to set one, "
            "or pass an explicit figure as parameter_context."
        )
    return fig


def _push_current_figure(fig: Figure) -> None:
    """Push a Figure onto the global stack.

    Parameters
    ----------
    fig : Figure
        The figure to mark as current.

    Returns
    -------
    None
    """
    _figure_stack().append(fig)


def _pop_current_figure(fig: Figure) -> None:
    """Remove a specific Figure from the global stack if present.

    Parameters
    ----------
    fig : Figure
        The figure to remove.

    Returns
    -------
    None
    """
    stack = _figure_stack()
    if not stack:
        return
    if stack[-1] is fig:
        stack.pop()
        return
    for i in range(len(stack) - 1, -1, -1):
        if stack[i] is fig:
            del stack[i]
            break


@contextmanager
def _use_figure(fig: Figure) -> Iterator[Figure]:
    """Context manager that temporarily sets a Figure as current.

    Parameters
    ----------
    fig : Figure
        The figure to make current within the context.

    Yields
    ------
    Figure
        The same figure passed in.
    """
    _push_current_figure(fig)
    try:
        yield fig
    finally:
        _pop_current_figure(fig)


# NOTE: Type aliases and plot-style contracts are defined in dedicated modules
# (``figure_types`` and ``figure_plot_style``). We re-export them here for
# backwards compatibility with early internal imports.
