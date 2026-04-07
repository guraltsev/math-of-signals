"""Public view objects and the figure-level view facade.

A :class:`View` is the public per-workspace object returned by
``fig.views[view_id]``. It owns one stable Plotly widget runtime together with
per-view axis defaults, remembered viewport state, and selector metadata.

``FigureViews`` is the small mapping-like facade exposed on :class:`Figure`.
It provides ``current`` / ``current_id`` helpers plus creation and removal
delegation without exposing :class:`ViewManager` internals.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

import plotly.graph_objects as go

from .InputConvert import InputConvert
from .PlotlyPane import PlotlyPane
from .figure_types import RangeLike

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .Figure import Figure


class View:
    """Public object representing one plotting workspace in a figure.
    
    Full API
    --------
    ``View(figure: Figure, id: str, title: str, x_label: str, y_label: str, default_x_range: RangeLike, default_y_range: RangeLike, figure_widget: go.FigureWidget, pane: PlotlyPane, is_active: bool=False, is_stale: bool=False)``
    
    Public members exposed from this class: ``figure``, ``figure_widget``, ``pane``, ``plotly_layout``, ``title``, ``x_label``,
        ``y_label``, ``x_range``, ``default_x_range``, ``y_range``, ``default_y_range``,
        ``current_x_range``, ``current_y_range``, ``activate``
    
    Parameters
    ----------
    figure : Figure
        Figure instance that owns the relevant state. Required.
    
    id : str
        Stable identifier used to create, update, or look up the target object. Required.
    
    title : str
        Human-readable title text shown in the UI or stored in snapshots. Required.
    
    x_label : str
        Horizontal-axis label text. Required.
    
    y_label : str
        Vertical-axis label text. Required.
    
    default_x_range : RangeLike
        Default x-axis range used when a view is created or reset. Required.
    
    default_y_range : RangeLike
        Default y-axis range used when a view is created or reset. Required.
    
    figure_widget : go.FigureWidget
        Value for ``figure_widget`` in this API. Required.
    
    pane : PlotlyPane
        Plot/display pane that owns the rendered widget. Required.
    
    is_active : bool, optional
        Boolean flag or query related to active. Defaults to ``False``.
    
    is_stale : bool, optional
        Boolean flag or query related to stale. Defaults to ``False``.
    
    Returns
    -------
    View
        New ``View`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``is_active=False``: Boolean flag or query related to active.
    - ``is_stale=False``: Boolean flag or query related to stale.
    
    Architecture note
    -----------------
    ``View`` lives in ``gu_toolkit.figure_view``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_view import View
        obj = View(...)
    
    Discovery-oriented use::
    
        help(View)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
    """

    __slots__ = (
        "_figure",
        "id",
        "_title",
        "_x_label",
        "_y_label",
        "_default_x_range",
        "_default_y_range",
        "viewport_x_range",
        "viewport_y_range",
        "is_active",
        "is_stale",
        "_figure_widget",
        "_pane",
        "_context_previous_ids",
    )

    def __init__(
        self,
        *,
        figure: Figure,
        id: str,
        title: str,
        x_label: str,
        y_label: str,
        default_x_range: RangeLike,
        default_y_range: RangeLike,
        figure_widget: go.FigureWidget,
        pane: PlotlyPane,
        is_active: bool = False,
        is_stale: bool = False,
    ) -> None:
        self._figure = figure
        self.id = str(id)
        self._title = str(title)
        self._x_label = str(x_label)
        self._y_label = str(y_label)
        self._default_x_range = self._coerce_range(default_x_range)
        self._default_y_range = self._coerce_range(default_y_range)
        self.viewport_x_range: tuple[float, float] | None = None
        self.viewport_y_range: tuple[float, float] | None = None
        self.is_active = bool(is_active)
        self.is_stale = bool(is_stale)
        self._figure_widget = figure_widget
        self._pane = pane
        self._context_previous_ids: list[str | None] = []
        self._apply_axis_titles()
        self._apply_default_ranges()

    @staticmethod
    def _coerce_range(value: RangeLike) -> tuple[float, float]:
        return (
            float(InputConvert(value[0], float)),
            float(InputConvert(value[1], float)),
        )

    def _apply_axis_titles(self) -> None:
        self._figure_widget.update_xaxes(title_text=(self._x_label or None))
        self._figure_widget.update_yaxes(title_text=(self._y_label or None))

    def _apply_default_ranges(self) -> None:
        self._figure_widget.update_xaxes(range=self._default_x_range)
        self._figure_widget.update_yaxes(range=self._default_y_range)

    @property
    def figure(self) -> Figure:
        """Return the parent figure that owns this view.
        
        Full API
        --------
        ``obj.figure -> Figure``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Figure
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.figure
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._figure

    @property
    def figure_widget(self) -> go.FigureWidget:
        """Return the stable Plotly widget owned by this view.
        
        Full API
        --------
        ``obj.figure_widget -> go.FigureWidget``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        go.FigureWidget
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.figure_widget
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._figure_widget

    @property
    def pane(self) -> PlotlyPane:
        """Return the stable :class:`PlotlyPane` owned by this view.
        
        Full API
        --------
        ``obj.pane -> PlotlyPane``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        PlotlyPane
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.pane
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._pane

    @property
    def plotly_layout(self) -> Any:
        """Return the Plotly layout object for this view's widget.
        
        Full API
        --------
        ``obj.plotly_layout -> Any``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.plotly_layout
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._figure_widget.layout

    @property
    def title(self) -> str:
        """Return the selector title shown for this view.
        
        Full API
        --------
        ``obj.title -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.title
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Work with title on ``View``.
        
        Full API
        --------
        ``obj.title = value``
        
        Parameters
        ----------
        value : str
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.title = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        self._title = str(value)
        self._figure._layout.set_view_title(self.id, self._title)

    @property
    def x_label(self) -> str:
        """Return the stored x-axis label for this view.
        
        Full API
        --------
        ``obj.x_label -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.x_label
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._x_label

    @x_label.setter
    def x_label(self, value: str) -> None:
        """Work with x label on ``View``.
        
        Full API
        --------
        ``obj.x_label = value``
        
        Parameters
        ----------
        value : str
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.x_label = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        self._x_label = str(value)
        self._apply_axis_titles()

    @property
    def y_label(self) -> str:
        """Return the stored y-axis label for this view.
        
        Full API
        --------
        ``obj.y_label -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.y_label
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._y_label

    @y_label.setter
    def y_label(self, value: str) -> None:
        """Work with y label on ``View``.
        
        Full API
        --------
        ``obj.y_label = value``
        
        Parameters
        ----------
        value : str
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.y_label = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        self._y_label = str(value)
        self._apply_axis_titles()

    @property
    def x_range(self) -> tuple[float, float]:
        """Return the default x-range for this view.
        
        Full API
        --------
        ``obj.x_range -> tuple[float, float]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.x_range
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._default_x_range

    @x_range.setter
    def x_range(self, value: RangeLike) -> None:
        """Work with x range on ``View``.
        
        Full API
        --------
        ``obj.x_range = value``
        
        Parameters
        ----------
        value : RangeLike
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.x_range = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        rng = self._coerce_range(value)
        self._default_x_range = rng
        self.viewport_x_range = rng
        self._figure_widget.update_xaxes(range=rng)

    @property
    def default_x_range(self) -> tuple[float, float]:
        """Compatibility alias for :attr:`x_range`.
        
        Full API
        --------
        ``obj.default_x_range -> tuple[float, float]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.default_x_range
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self.x_range

    @default_x_range.setter
    def default_x_range(self, value: RangeLike) -> None:
        """Work with default x range on ``View``.
        
        Full API
        --------
        ``obj.default_x_range = value``
        
        Parameters
        ----------
        value : RangeLike
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.default_x_range = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        self.x_range = value

    @property
    def y_range(self) -> tuple[float, float]:
        """Return the default y-range for this view.
        
        Full API
        --------
        ``obj.y_range -> tuple[float, float]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.y_range
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self._default_y_range

    @y_range.setter
    def y_range(self, value: RangeLike) -> None:
        """Work with y range on ``View``.
        
        Full API
        --------
        ``obj.y_range = value``
        
        Parameters
        ----------
        value : RangeLike
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.y_range = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        rng = self._coerce_range(value)
        self._default_y_range = rng
        self.viewport_y_range = rng
        self._figure_widget.update_yaxes(range=rng)

    @property
    def default_y_range(self) -> tuple[float, float]:
        """Compatibility alias for :attr:`y_range`.
        
        Full API
        --------
        ``obj.default_y_range -> tuple[float, float]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.default_y_range
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        return self.y_range

    @default_y_range.setter
    def default_y_range(self, value: RangeLike) -> None:
        """Work with default y range on ``View``.
        
        Full API
        --------
        ``obj.default_y_range = value``
        
        Parameters
        ----------
        value : RangeLike
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.default_y_range = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        self.y_range = value

    @property
    def current_x_range(self) -> tuple[float, float] | None:
        """Return the live viewport x-range when available.
        
        Full API
        --------
        ``obj.current_x_range -> tuple[float, float] | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float] | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.current_x_range
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        rng = self._figure_widget.layout.xaxis.range
        if rng is None:
            return self.viewport_x_range
        result = (float(rng[0]), float(rng[1]))
        self.viewport_x_range = result
        return result

    @current_x_range.setter
    def current_x_range(self, value: RangeLike | None) -> None:
        """Work with current x range on ``View``.
        
        Full API
        --------
        ``obj.current_x_range = value``
        
        Parameters
        ----------
        value : RangeLike | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.current_x_range = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        if value is None:
            rng = self._default_x_range
        else:
            rng = self._coerce_range(value)
        self.viewport_x_range = rng
        self._figure_widget.update_xaxes(range=rng)

    @property
    def current_y_range(self) -> tuple[float, float] | None:
        """Return the live viewport y-range when available.
        
        Full API
        --------
        ``obj.current_y_range -> tuple[float, float] | None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[float, float] | None
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            current = obj.current_y_range
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        rng = self._figure_widget.layout.yaxis.range
        if rng is None:
            return self.viewport_y_range
        result = (float(rng[0]), float(rng[1]))
        self.viewport_y_range = result
        return result

    @current_y_range.setter
    def current_y_range(self, value: RangeLike | None) -> None:
        """Work with current y range on ``View``.
        
        Full API
        --------
        ``obj.current_y_range = value``
        
        Parameters
        ----------
        value : RangeLike | None
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            obj.current_y_range = value
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """

        if value is None:
            rng = self._default_y_range
        else:
            rng = self._coerce_range(value)
        self.viewport_y_range = rng
        self._figure_widget.update_yaxes(range=rng)

    def activate(self) -> View:
        """Activate this view on its parent figure and return ``self``.
        
        Full API
        --------
        ``obj.activate() -> View``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``View``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = View(...)
            result = obj.activate(...)
        
        Discovery-oriented use::
        
            help(View)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(View)`` and ``dir(View)`` to inspect adjacent members.
        """
        self._figure.set_active_view(self.id)
        return self

    def __enter__(self) -> View:
        previous: str | None = None
        try:
            previous = self._figure.views.current_id
        except Exception:  # pragma: no cover - defensive
            previous = None
        self._context_previous_ids.append(previous)
        self._figure.__enter__()
        try:
            self.activate()
        except Exception as exc:  # pragma: no cover - defensive cleanup
            self._context_previous_ids.pop()
            self._figure.__exit__(type(exc), exc, exc.__traceback__)
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        previous = self._context_previous_ids.pop() if self._context_previous_ids else None
        try:
            if previous is not None and previous in self._figure.views and previous != self.id:
                self._figure.set_active_view(previous)
        finally:
            self._figure.__exit__(exc_type, exc, tb)


class FigureViews(Mapping[str, View]):
    """Mapping-like facade that exposes a figure's registered views.
    
    Full API
    --------
    ``FigureViews(fig: Figure)``
    
    Public members exposed from this class: ``current_id``, ``current``, ``add``, ``remove``, ``select``
    
    Parameters
    ----------
    fig : Figure
        Figure instance that owns the relevant state. Required.
    
    Returns
    -------
    FigureViews
        New ``FigureViews`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``FigureViews`` lives in ``gu_toolkit.figure_view``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_view import FigureViews
        obj = FigureViews(...)
    
    Discovery-oriented use::
    
        help(FigureViews)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
    """

    __slots__ = ("_fig",)

    def __init__(self, fig: Figure) -> None:
        self._fig = fig

    def __getitem__(self, key: str) -> View:
        return self._fig._view_manager.require_view(str(key))

    def __iter__(self) -> Iterator[str]:
        return iter(self._fig._view_manager.views)

    def __len__(self) -> int:
        return len(self._fig._view_manager.views)

    @property
    def current_id(self) -> str:
        """Return the current active view id.
        
        Full API
        --------
        ``obj.current_id -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureViews``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureViews(...)
            current = obj.current_id
        
        Discovery-oriented use::
        
            help(FigureViews)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
        """
        return self._fig._view_manager.active_view_id

    @current_id.setter
    def current_id(self, value: str) -> None:
        """Work with current id on ``FigureViews``.
        
        Full API
        --------
        ``obj.current_id = value``
        
        Parameters
        ----------
        value : str
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureViews``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureViews(...)
            obj.current_id = value
        
        Discovery-oriented use::
        
            help(FigureViews)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
        """

        self._fig.set_active_view(str(value))

    @property
    def current(self) -> View:
        """Return the current active public view object.
        
        Full API
        --------
        ``obj.current -> View``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureViews``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureViews(...)
            current = obj.current
        
        Discovery-oriented use::
        
            help(FigureViews)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
        """
        return self._fig._view_manager.active_view()

    def add(
        self,
        view_id: str,
        *,
        title: str | None = None,
        x_range: RangeLike | None = None,
        y_range: RangeLike | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        activate: bool = False,
    ) -> View:
        """Create a new view by delegating to :meth:`Figure.add_view`.
        
        Full API
        --------
        ``obj.add(view_id: str, *, title: str | None=None, x_range: RangeLike | None=None, y_range: RangeLike | None=None, x_label: str | None=None, y_label: str | None=None, activate: bool=False) -> View``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        title : str | None, optional
            Human-readable title text shown in the UI or stored in snapshots. Defaults to ``None``.
        
        x_range : RangeLike | None, optional
            Range specification for the x-axis. Defaults to ``None``.
        
        y_range : RangeLike | None, optional
            Range specification for the y-axis. Defaults to ``None``.
        
        x_label : str | None, optional
            Horizontal-axis label text. Defaults to ``None``.
        
        y_label : str | None, optional
            Vertical-axis label text. Defaults to ``None``.
        
        activate : bool, optional
            Boolean flag that requests the newly created/updated object become active. Defaults to ``False``.
        
        Returns
        -------
        View
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``title=None``: Human-readable title text shown in the UI or stored in snapshots.
        - ``x_range=None``: Range specification for the x-axis.
        - ``y_range=None``: Range specification for the y-axis.
        - ``x_label=None``: Horizontal-axis label text.
        - ``y_label=None``: Vertical-axis label text.
        - ``activate=False``: Boolean flag that requests the newly created/updated object become active.
        
        Architecture note
        -----------------
        This member belongs to ``FigureViews``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureViews(...)
            result = obj.add(...)
        
        Discovery-oriented use::
        
            help(FigureViews)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
        """
        return self._fig.add_view(
            view_id,
            title=title,
            x_range=x_range,
            y_range=y_range,
            x_label=x_label,
            y_label=y_label,
            activate=activate,
        )

    def remove(self, view_id: str) -> None:
        """Remove a view by delegating to :meth:`Figure.remove_view`.
        
        Full API
        --------
        ``obj.remove(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureViews``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureViews(...)
            obj.remove(...)
        
        Discovery-oriented use::
        
            help(FigureViews)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
        """
        self._fig.remove_view(view_id)

    def select(self, view_id: str) -> None:
        """Select a view by setting :attr:`current_id`.
        
        Full API
        --------
        ``obj.select(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureViews``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureViews(...)
            obj.select(...)
        
        Discovery-oriented use::
        
            help(FigureViews)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureViews)`` and ``dir(FigureViews)`` to inspect adjacent members.
        """
        self.current_id = view_id


__all__ = ["FigureViews", "View"]
