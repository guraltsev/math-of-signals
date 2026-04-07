"""Immutable snapshot of one scalar-field plot's reproducible state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sympy.core.expr import Expr
from sympy.core.symbol import Symbol


@dataclass(frozen=True)
class FieldPlotSnapshot:
    """Immutable record of one contour/heatmap scalar-field plot.
    
    Full API
    --------
    ``FieldPlotSnapshot(id: str, render_mode: Literal['contour', 'heatmap'], preset: str | None, x_var: Symbol, y_var: Symbol, func: Expr, parameters: tuple[Symbol, Ellipsis], label: str, visible: bool, x_domain: tuple[float, float] | None, y_domain: tuple[float, float] | None, grid: tuple[int, int] | None, colorscale: Any | None, z_range: tuple[float, float] | None, z_step: float | None, under_color: str | None, over_color: str | None, show_colorbar: bool | None, opacity: float | None, reversescale: bool | None, colorbar: dict[str, Any] | None, trace: dict[str, Any] | None, views: tuple[str, Ellipsis]=(), levels: int | None=None, level_step: float | None=None, level_start: float | None=None, level_end: float | None=None, filled: bool | None=None, show_labels: bool | None=None, line_color: str | None=None, line_width: float | None=None, line_dash: str | None=None, smoothing: str | bool | None=None, connectgaps: bool | None=None, kind: str='field')``
    
    Public members exposed from this class: ``is_field``, ``is_contour``, ``is_heatmap``
    
    Parameters
    ----------
    id : str
        Stable identifier used to create, update, or look up the target object. Required.
    
    render_mode : Literal['contour', 'heatmap']
        Rendering mode or plot kind to create. Required.
    
    preset : str | None
        Named preset that chooses a particular rendering style. Required.
    
    x_var : Symbol
        Symbol used as the horizontal variable. Required.
    
    y_var : Symbol
        Symbol used as the vertical variable. Required.
    
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
    
    y_domain : tuple[float, float] | None
        Numeric y-domain used for evaluation or rendering. Required.
    
    grid : tuple[int, int] | None
        Grid resolution or grid specification used for field sampling. Required.
    
    colorscale : Any | None
        Colorscale specification passed to the renderer. Required.
    
    z_range : tuple[float, float] | None
        Numeric value range used for scalar-field color mapping. Required.
    
    z_step : float | None
        Numeric spacing between scalar-field contour or color levels. Required.
    
    under_color : str | None
        Color used below the represented scalar range. Required.
    
    over_color : str | None
        Color used above the represented scalar range. Required.
    
    show_colorbar : bool | None
        Boolean flag controlling whether a colorbar is shown. Required.
    
    opacity : float | None
        Opacity value applied to the rendered output. Required.
    
    reversescale : bool | None
        Boolean flag controlling whether the colorscale is reversed. Required.
    
    colorbar : dict[str, Any] | None
        Renderer-specific colorbar configuration mapping. Required.
    
    trace : dict[str, Any] | None
        Renderer-specific trace configuration mapping. Required.
    
    views : tuple[str, Ellipsis], optional
        Collection of view identifiers associated with this object or update. Defaults to ``()``.
    
    levels : int | None, optional
        Number of contour or scalar levels to generate. Defaults to ``None``.
    
    level_step : float | None, optional
        Spacing between contour or scalar levels. Defaults to ``None``.
    
    level_start : float | None, optional
        First contour/scalar level to include. Defaults to ``None``.
    
    level_end : float | None, optional
        Last contour/scalar level to include. Defaults to ``None``.
    
    filled : bool | None, optional
        Boolean flag controlling whether contour regions are filled. Defaults to ``None``.
    
    show_labels : bool | None, optional
        Boolean flag controlling whether labels are drawn on contour lines. Defaults to ``None``.
    
    line_color : str | None, optional
        Explicit line color for contour or curve rendering. Defaults to ``None``.
    
    line_width : float | None, optional
        Line width used for contour or curve rendering. Defaults to ``None``.
    
    line_dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    smoothing : str | bool | None, optional
        Smoothing option passed to the renderer or interpolation layer. Defaults to ``None``.
    
    connectgaps : bool | None, optional
        Boolean flag controlling whether missing samples are connected. Defaults to ``None``.
    
    kind : str, optional
        Value for ``kind`` in this API. Defaults to ``'field'``.
    
    Returns
    -------
    FieldPlotSnapshot
        New ``FieldPlotSnapshot`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``views=()``: Collection of view identifiers associated with this object or update.
    - ``levels=None``: Number of contour or scalar levels to generate.
    - ``level_step=None``: Spacing between contour or scalar levels.
    - ``level_start=None``: First contour/scalar level to include.
    - ``level_end=None``: Last contour/scalar level to include.
    - ``filled=None``: Boolean flag controlling whether contour regions are filled.
    - ``show_labels=None``: Boolean flag controlling whether labels are drawn on contour lines.
    - ``line_color=None``: Explicit line color for contour or curve rendering.
    - ``line_width=None``: Line width used for contour or curve rendering.
    - ``line_dash=None``: Dash pattern used for contour or curve rendering.
    - ``smoothing=None``: Smoothing option passed to the renderer or interpolation layer.
    - ``connectgaps=None``: Boolean flag controlling whether missing samples are connected.
    - ``kind='field'``: Value for ``kind`` in this API.
    
    Architecture note
    -----------------
    ``FieldPlotSnapshot`` lives in ``gu_toolkit.FieldPlotSnapshot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.FieldPlotSnapshot import FieldPlotSnapshot
        obj = FieldPlotSnapshot(...)
    
    Discovery-oriented use::
    
        help(FieldPlotSnapshot)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(FieldPlotSnapshot)`` and ``dir(FieldPlotSnapshot)`` to inspect adjacent members.
    """

    id: str
    render_mode: Literal["contour", "heatmap"]
    preset: str | None
    x_var: Symbol
    y_var: Symbol
    func: Expr
    parameters: tuple[Symbol, ...]
    label: str
    visible: bool
    x_domain: tuple[float, float] | None
    y_domain: tuple[float, float] | None
    grid: tuple[int, int] | None
    colorscale: Any | None
    z_range: tuple[float, float] | None
    z_step: float | None
    under_color: str | None
    over_color: str | None
    show_colorbar: bool | None
    opacity: float | None
    reversescale: bool | None
    colorbar: dict[str, Any] | None
    trace: dict[str, Any] | None
    views: tuple[str, ...] = ()
    levels: int | None = None
    level_step: float | None = None
    level_start: float | None = None
    level_end: float | None = None
    filled: bool | None = None
    show_labels: bool | None = None
    line_color: str | None = None
    line_width: float | None = None
    line_dash: str | None = None
    smoothing: str | bool | None = None
    connectgaps: bool | None = None
    kind: str = "field"

    @property
    def is_field(self) -> bool:
        """Return whether this snapshot represents a scalar-field trace.
        
        Full API
        --------
        ``obj.is_field -> bool``
        
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
        This member belongs to ``FieldPlotSnapshot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldPlotSnapshot(...)
            current = obj.is_field
        
        Discovery-oriented use::
        
            help(FieldPlotSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldPlotSnapshot)`` and ``dir(FieldPlotSnapshot)`` to inspect adjacent members.
        """
        return True

    @property
    def is_contour(self) -> bool:
        """Return whether the snapshot renders as a contour trace.
        
        Full API
        --------
        ``obj.is_contour -> bool``
        
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
        This member belongs to ``FieldPlotSnapshot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldPlotSnapshot(...)
            current = obj.is_contour
        
        Discovery-oriented use::
        
            help(FieldPlotSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldPlotSnapshot)`` and ``dir(FieldPlotSnapshot)`` to inspect adjacent members.
        """
        return self.render_mode == "contour"

    @property
    def is_heatmap(self) -> bool:
        """Return whether the snapshot renders as a heatmap trace.
        
        Full API
        --------
        ``obj.is_heatmap -> bool``
        
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
        This member belongs to ``FieldPlotSnapshot``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldPlotSnapshot(...)
            current = obj.is_heatmap
        
        Discovery-oriented use::
        
            help(FieldPlotSnapshot)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldPlotSnapshot)`` and ``dir(FieldPlotSnapshot)`` to inspect adjacent members.
        """
        return self.render_mode == "heatmap"

    def __repr__(self) -> str:
        return (
            f"FieldPlotSnapshot(id={self.id!r}, render_mode={self.render_mode!r}, "
            f"x_var={self.x_var!r}, y_var={self.y_var!r}, func={self.func!r})"
        )
