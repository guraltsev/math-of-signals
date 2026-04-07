"""Immutable snapshot of a single plot's reproducible state.

A :class:`PlotSnapshot` captures everything needed to emit a plotting call that
reconstructs one curve on a :class:`gu_toolkit.Figure.Figure`. Cartesian plots
round-trip through ``fig.plot(...)`` and parametric plots round-trip through
``fig.parametric_plot(...)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sympy.core.expr import Expr
from sympy.core.symbol import Symbol


@dataclass(frozen=True)
class PlotSnapshot:
    """Immutable record of one plot's state.
    
    Full API
    --------
    ``PlotSnapshot(id: str, var: Symbol, func: Expr, parameters: tuple[Symbol, Ellipsis], label: str, visible: bool, x_domain: tuple[float, float] | None, sampling_points: int | None, color: str | None, thickness: float | None, dash: str | None, opacity: float | None, autonormalization: bool=False, views: tuple[str, Ellipsis]=(), kind: str='cartesian', x_func: Expr | None=None, parameter_domain: tuple[float, float] | None=None)``
    
    Public members exposed from this class: ``samples``, ``is_parametric``, ``y_func``
    
    Parameters
    ----------
    id : str
        Stable identifier used to create, update, or look up the target object. Required.
    
    var : Symbol
        Primary symbolic variable used for evaluation. Required.
    
    func : Expr
        Symbolic expression or callable to evaluate. Required.
    
    parameters : tuple[Symbol, Ellipsis]
        Parameter symbols/keys that should stay bound to this operation. Required.
    
    label : str
        Human-readable label used in UI or plotting output. Required.
    
    visible : bool
        Visibility flag for a plot, field, panel, or UI element. Required.
    
    x_domain : tuple[float, float] | None
        Numeric x-domain used for evaluation or rendering. Required.
    
    sampling_points : int | None
        Sampling density used when evaluating a curve or field. Required.
    
    color : str | None
        Explicit color value. Required.
    
    thickness : float | None
        Value for ``thickness`` in this API. Required.
    
    dash : str | None
        Dash pattern used for contour or curve rendering. Required.
    
    opacity : float | None
        Opacity value applied to the rendered output. Required.
    
    autonormalization : bool, optional
        Value for ``autonormalization`` in this API. Defaults to ``False``.
    
    views : tuple[str, Ellipsis], optional
        Collection of view identifiers associated with this object or update. Defaults to ``()``.
    
    kind : str, optional
        Value for ``kind`` in this API. Defaults to ``'cartesian'``.
    
    x_func : Expr | None, optional
        Expression or callable that supplies x-values. Defaults to ``None``.
    
    parameter_domain : tuple[float, float] | None, optional
        Numeric domain used for a parametric sweep variable. Defaults to ``None``.
    
    Returns
    -------
    PlotSnapshot
        New ``PlotSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``autonormalization=False``: Value for ``autonormalization`` in this API.
    - ``views=()``: Collection of view identifiers associated with this object or update.
    - ``kind='cartesian'``: Value for ``kind`` in this API.
    - ``x_func=None``: Expression or callable that supplies x-values.
    - ``parameter_domain=None``: Numeric domain used for a parametric sweep variable.
    
    Architecture note
    -----------------
    ``PlotSnapshot`` lives in ``gu_toolkit.PlotSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.PlotSnapshot import PlotSnapshot
        obj = PlotSnapshot(...)
    
    Discovery-oriented use::
    
        help(PlotSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/render-batching-and-snapshots.md``.
    - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
    - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
    - In a notebook or REPL, run ``help(PlotSnapshot)`` and ``dir(PlotSnapshot)`` to inspect adjacent members.
    """

    id: str
    var: Symbol
    func: Expr
    parameters: tuple[Symbol, ...]
    label: str
    visible: bool
    x_domain: tuple[float, float] | None
    sampling_points: int | None
    color: str | None
    thickness: float | None
    dash: str | None
    opacity: float | None
    autonormalization: bool = False
    views: tuple[str, ...] = ()
    kind: str = "cartesian"
    x_func: Expr | None = None
    parameter_domain: tuple[float, float] | None = None

    @property
    def samples(self) -> int | None:
        """Compatibility alias for :attr:`sampling_points`.
        
        Full API
        --------
        ``obj.samples -> int | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        int | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``PlotSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotSnapshot(...)
            current = obj.samples
        
        Discovery-oriented use::
        
            help(PlotSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/render-batching-and-snapshots.md``.
        - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
        - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
        - In a notebook or REPL, run ``help(PlotSnapshot)`` and ``dir(PlotSnapshot)`` to inspect adjacent members.
        """
        return self.sampling_points

    @property
    def is_parametric(self) -> bool:
        """Return whether this snapshot represents a parametric curve.
        
        Full API
        --------
        ``obj.is_parametric -> bool``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``PlotSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotSnapshot(...)
            current = obj.is_parametric
        
        Discovery-oriented use::
        
            help(PlotSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/render-batching-and-snapshots.md``.
        - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
        - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
        - In a notebook or REPL, run ``help(PlotSnapshot)`` and ``dir(PlotSnapshot)`` to inspect adjacent members.
        """
        return self.kind == "parametric"

    @property
    def y_func(self) -> Expr:
        """Return the primary stored symbolic expression.
        
        Full API
        --------
        ``obj.y_func -> Expr``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Expr
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``PlotSnapshot``. Snapshots define the stable boundary between live notebook state and reproducible export/code-generation workflows. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotSnapshot(...)
            current = obj.y_func
        
        Discovery-oriented use::
        
            help(PlotSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/render-batching-and-snapshots.md``.
        - Regression/spec tests: ``tests/test_figure_snapshot_codegen.py``.
        - Runtime discovery tip: create a snapshot in a notebook and inspect ``help(FigureSnapshot)`` or the generated code helpers side by side.
        - In a notebook or REPL, run ``help(PlotSnapshot)`` and ``dir(PlotSnapshot)`` to inspect adjacent members.
        """
        return self.func

    def __repr__(self) -> str:
        return (
            f"PlotSnapshot(id={self.id!r}, kind={self.kind!r}, "
            f"var={self.var!r}, func={self.func!r}, label={self.label!r})"
        )
