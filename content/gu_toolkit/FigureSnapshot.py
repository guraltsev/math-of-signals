"""Immutable snapshot of an entire Figure's reproducible state.

A ``FigureSnapshot`` aggregates parameter metadata, plot snapshots, and
info-card content into a single frozen object that can be inspected
programmatically or fed to :func:`codegen.figure_to_code` to emit a
self-contained Python script.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field

from .ParameterSnapshot import ParameterSnapshot
from .FieldPlotSnapshot import FieldPlotSnapshot
from .PlotSnapshot import PlotSnapshot


@dataclass(frozen=True)
class InfoCardSnapshot:
    """Immutable record of a simple info card.
    
    Full API
    --------
    ``InfoCardSnapshot(id: Hashable, segments: tuple[str, Ellipsis], view_id: str | None=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    id : Hashable
        Stable identifier used to create, update, or look up the target object. Required.
    
    segments : tuple[str, Ellipsis]
        Value for ``segments`` in this API. Required.
    
    view_id : str | None, optional
        Identifier for the relevant view inside a figure. Defaults to ``None``.
    
    Returns
    -------
    InfoCardSnapshot
        New ``InfoCardSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``view_id=None``: Identifier for the relevant view inside a figure.
    
    Architecture note
    -----------------
    ``InfoCardSnapshot`` lives in ``gu_toolkit.FigureSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.FigureSnapshot import InfoCardSnapshot
        obj = InfoCardSnapshot(...)
    
    Discovery-oriented use::
    
        help(InfoCardSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(InfoCardSnapshot)`` and ``dir(InfoCardSnapshot)`` to inspect adjacent members.
    """

    id: Hashable
    segments: tuple[str, ...]
    view_id: str | None = None


@dataclass(frozen=True)
class ViewSnapshot:
    """Immutable record of one workspace view.
    
    Full API
    --------
    ``ViewSnapshot(id: str, title: str, x_label: str, y_label: str, x_range: tuple[float, float], y_range: tuple[float, float], viewport_x_range: tuple[float, float] | None=None, viewport_y_range: tuple[float, float] | None=None)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    id : str
        Stable identifier used to create, update, or look up the target object. Required.
    
    title : str
        Human-readable title text shown in the UI or stored in snapshots. Required.
    
    x_label : str
        Horizontal-axis label text. Required.
    
    y_label : str
        Vertical-axis label text. Required.
    
    x_range : tuple[float, float]
        Range specification for the x-axis. Required.
    
    y_range : tuple[float, float]
        Range specification for the y-axis. Required.
    
    viewport_x_range : tuple[float, float] | None, optional
        Remembered x-axis viewport range for a view. Defaults to ``None``.
    
    viewport_y_range : tuple[float, float] | None, optional
        Remembered y-axis viewport range for a view. Defaults to ``None``.
    
    Returns
    -------
    ViewSnapshot
        New ``ViewSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``viewport_x_range=None``: Remembered x-axis viewport range for a view.
    - ``viewport_y_range=None``: Remembered y-axis viewport range for a view.
    
    Architecture note
    -----------------
    ``ViewSnapshot`` lives in ``gu_toolkit.FigureSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.FigureSnapshot import ViewSnapshot
        obj = ViewSnapshot(...)
    
    Discovery-oriented use::
    
        help(ViewSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(ViewSnapshot)`` and ``dir(ViewSnapshot)`` to inspect adjacent members.
    """

    id: str
    title: str
    x_label: str
    y_label: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    viewport_x_range: tuple[float, float] | None = None
    viewport_y_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class FigureSnapshot:
    """Immutable record of a full figure's state.
    
    Full API
    --------
    ``FigureSnapshot(x_range: tuple[float, float], y_range: tuple[float, float], sampling_points: int, title: str, parameters: ParameterSnapshot, plots: dict[str, PlotSnapshot | FieldPlotSnapshot], info_cards: tuple[InfoCardSnapshot, Ellipsis], views: tuple[ViewSnapshot, Ellipsis]=field(default_factory=tuple), active_view_id: str='main', default_x_range: tuple[float, float] | None=None, default_y_range: tuple[float, float] | None=None, default_samples: int | None=None)``
    
    Public members exposed from this class: ``samples``
    
    Parameters
    ----------
    x_range : tuple[float, float]
        Range specification for the x-axis. Required.
    
    y_range : tuple[float, float]
        Range specification for the y-axis. Required.
    
    sampling_points : int
        Sampling density used when evaluating a curve or field. Required.
    
    title : str
        Human-readable title text shown in the UI or stored in snapshots. Required.
    
    parameters : ParameterSnapshot
        Parameter symbols/keys that should stay bound to this operation. Required.
    
    plots : dict[str, PlotSnapshot | FieldPlotSnapshot]
        Value for ``plots`` in this API. Required.
    
    info_cards : tuple[InfoCardSnapshot, Ellipsis]
        Value for ``info_cards`` in this API. Required.
    
    views : tuple[ViewSnapshot, Ellipsis], optional
        Collection of view identifiers associated with this object or update. Defaults to ``field(default_factory=tuple)``.
    
    active_view_id : str, optional
        Identifier for the currently selected view. Defaults to ``'main'``.
    
    default_x_range : tuple[float, float] | None, optional
        Default x-axis range used when a view is created or reset. Defaults to ``None``.
    
    default_y_range : tuple[float, float] | None, optional
        Default y-axis range used when a view is created or reset. Defaults to ``None``.
    
    default_samples : int | None, optional
        Value for ``default_samples`` in this API. Defaults to ``None``.
    
    Returns
    -------
    FigureSnapshot
        New ``FigureSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``views=field(default_factory=tuple)``: Collection of view identifiers associated with this object or update.
    - ``active_view_id='main'``: Identifier for the currently selected view.
    - ``default_x_range=None``: Default x-axis range used when a view is created or reset.
    - ``default_y_range=None``: Default y-axis range used when a view is created or reset.
    - ``default_samples=None``: Value for ``default_samples`` in this API.
    
    Architecture note
    -----------------
    ``FigureSnapshot`` lives in ``gu_toolkit.FigureSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.FigureSnapshot import FigureSnapshot
        obj = FigureSnapshot(...)
    
    Discovery-oriented use::
    
        help(FigureSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(FigureSnapshot)`` and ``dir(FigureSnapshot)`` to inspect adjacent members.
    """

    x_range: tuple[float, float]
    y_range: tuple[float, float]
    sampling_points: int
    title: str
    parameters: ParameterSnapshot
    plots: dict[str, PlotSnapshot | FieldPlotSnapshot]
    info_cards: tuple[InfoCardSnapshot, ...]
    views: tuple[ViewSnapshot, ...] = field(default_factory=tuple)
    active_view_id: str = "main"
    default_x_range: tuple[float, float] | None = None
    default_y_range: tuple[float, float] | None = None
    default_samples: int | None = None

    def __post_init__(self) -> None:
        if self.default_x_range is None:
            object.__setattr__(self, "default_x_range", self.x_range)
        if self.default_y_range is None:
            object.__setattr__(self, "default_y_range", self.y_range)
        if self.default_samples is None:
            object.__setattr__(self, "default_samples", self.sampling_points)

    @property
    def samples(self) -> int:
        """Compatibility alias for :attr:`sampling_points`.
        
        Full API
        --------
        ``obj.samples -> int``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        int
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureSnapshot(...)
            current = obj.samples
        
        Discovery-oriented use::
        
            help(FigureSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/render-batching-and-snapshots.md``.
        - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
        - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
        - In a notebook or REPL, run ``help(FigureSnapshot)`` and ``dir(FigureSnapshot)`` to inspect adjacent members.
        """
        return self.sampling_points

    def __repr__(self) -> str:
        return (
            f"FigureSnapshot(title={self.title!r}, "
            f"plots={len(self.plots)}, "
            f"parameters={len(self.parameters)})"
        )
