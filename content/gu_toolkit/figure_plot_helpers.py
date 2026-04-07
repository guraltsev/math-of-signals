"""Shared helpers for plot creation/update workflows.

These helpers keep light, coordination-oriented logic out of ``Figure.py`` so
feature additions can grow in focused modules without inflating the coordinator
module beyond the decomposition budget enforced by the test suite.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def resolve_plot_id(existing_plots: Mapping[str, Any], requested_id: str | None) -> str:
    """Return a stable plot id, auto-generating one when needed.
    
    Full API
    --------
    ``resolve_plot_id(existing_plots: Mapping[str, Any], requested_id: str | None) -> str``
    
    Parameters
    ----------
    existing_plots : Mapping[str, Any]
        Value for ``existing_plots`` in this API. Required.
    
    requested_id : str | None
        Value for ``requested_id`` in this API. Required.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_helpers``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_helpers import resolve_plot_id
        result = resolve_plot_id(...)
    
    Discovery-oriented use::
    
        help(resolve_plot_id)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(resolve_plot_id)`` and inspect sibling APIs in the same module.
    """
    if requested_id is not None:
        return requested_id
    for i in range(100):
        candidate = f"f_{i}"
        if candidate not in existing_plots:
            return candidate
    raise ValueError("Too many auto-generated IDs")



def normalize_view_ids(
    view: str | Sequence[str] | None,
    *,
    default_view_id: str,
) -> tuple[str, ...]:
    """Normalize a public ``view=`` argument into a tuple of view ids.
    
    Full API
    --------
    ``normalize_view_ids(view: str | Sequence[str] | None, *, default_view_id: str) -> tuple[str, ...]``
    
    Parameters
    ----------
    view : str | Sequence[str] | None
        View identifier or view-scoped target. When omitted, the active view is used. Required.
    
    default_view_id : str
        Identifier for the default view or fallback view. Required.
    
    Returns
    -------
    tuple[str, Ellipsis]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_helpers``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_helpers import normalize_view_ids
        result = normalize_view_ids(...)
    
    Discovery-oriented use::
    
        help(normalize_view_ids)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(normalize_view_ids)`` and inspect sibling APIs in the same module.
    """
    if isinstance(view, str):
        return (view,)
    if view is None:
        return (default_view_id,)
    return tuple(view)



def remove_plot_from_figure(figure: Any, plot_id: str) -> None:
    """Detach a plot's traces, remove it from the registry, and update UI.
    
    Full API
    --------
    ``remove_plot_from_figure(figure: Any, plot_id: str) -> None``
    
    Parameters
    ----------
    figure : Any
        Figure instance that owns the relevant state. Required.
    
    plot_id : str
        Stable plot identifier used for lookup or update. Required.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_helpers``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_helpers import remove_plot_from_figure
        remove_plot_from_figure(...)
    
    Discovery-oriented use::
    
        help(remove_plot_from_figure)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(remove_plot_from_figure)`` and inspect sibling APIs in the same module.
    """
    plot = figure.plots.pop(plot_id, None)
    if plot is None:
        return
    for view_id in tuple(plot.views):
        plot.remove_from_view(view_id)
    figure._legend.on_plot_removed(plot_id)
