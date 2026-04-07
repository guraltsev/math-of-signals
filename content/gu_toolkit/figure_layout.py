"""Figure widget layout primitives.

`FigureLayout` owns widget composition only. It builds the notebook widget tree,
manages the view selector plus persistent per-view page hosts, and exposes the
sidebar and output regions used by :class:`gu_toolkit.Figure.Figure`.

It does not own plot data, render policy, or pane reflow callbacks.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ._widget_stubs import widgets
from .ui_system import build_layout, build_section_panel, load_ui_css, shared_style_widget
from IPython.display import clear_output, display

from .layout_logging import layout_value_snapshot


class OneShotOutput(widgets.Output):
    """An ``Output`` widget that raises when displayed more than once.
    
    Full API
    --------
    ``OneShotOutput()``
    
    Public members exposed from this class: ``has_been_displayed``, ``reset_display_state``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    OneShotOutput
        New ``OneShotOutput`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``OneShotOutput`` lives in ``gu_toolkit.figure_layout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_layout import OneShotOutput
        obj = OneShotOutput(...)
    
    Discovery-oriented use::
    
        help(OneShotOutput)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(OneShotOutput)`` and ``dir(OneShotOutput)`` to inspect adjacent members.
    """

    __slots__ = ("_displayed",)

    def __init__(self) -> None:
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(
        self, include: Any = None, exclude: Any = None, **kwargs: Any
    ) -> Any:
        if self._displayed:
            raise RuntimeError(
                "OneShotOutput has already been displayed. "
                "This widget supports only one-time display."
            )
        self._displayed = True
        return super()._repr_mimebundle_(include=include, exclude=exclude, **kwargs)

    @property
    def has_been_displayed(self) -> bool:
        """Return whether been displayed.
        
        Full API
        --------
        ``obj.has_been_displayed -> bool``
        
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
        This member belongs to ``OneShotOutput``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = OneShotOutput(...)
            current = obj.has_been_displayed
        
        Discovery-oriented use::
        
            help(OneShotOutput)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(OneShotOutput)`` and ``dir(OneShotOutput)`` to inspect adjacent members.
        """

        return self._displayed

    def reset_display_state(self) -> None:
        """Work with reset display state on ``OneShotOutput``.
        
        Full API
        --------
        ``obj.reset_display_state() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``OneShotOutput``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = OneShotOutput(...)
            obj.reset_display_state(...)
        
        Discovery-oriented use::
        
            help(OneShotOutput)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(OneShotOutput)`` and ``dir(OneShotOutput)`` to inspect adjacent members.
        """

        self._displayed = False


@dataclass
class _ViewPage:
    """Internal widget record for one persistent view host."""

    view_id: str
    title: str
    host_box: widgets.Box
    widget: widgets.Widget | None = None


class FigureLayout:
    """Own the widget tree used by a figure instance.
    
    Full API
    --------
    ``FigureLayout(title: str='')``
    
    Public members exposed from this class: ``bind_layout_debug``, ``bind_reflow_request``, ``output_widget``, ``layout_snapshot``,
        ``set_title``, ``get_title``, ``update_sidebar_visibility``, ``ensure_view_page``,
        ``attach_view_widget``, ``remove_view_page``, ``set_view_order``,
        ``set_active_view``, ``set_view_title``, ``observe_view_selection``,
        ``observe_full_width_change``, ``bind_view_reflow``, ``content_layout_mode``,
        ``set_plot_widget``, ``set_view_plot_widget``, ``set_view_tabs``,
        ``trigger_reflow_for_view``, ``observe_tab_selection``
    
    Parameters
    ----------
    title : str, optional
        Human-readable title text shown in the UI or stored in snapshots. Defaults to ``''``.
    
    Returns
    -------
    FigureLayout
        New ``FigureLayout`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``title=''``: Human-readable title text shown in the UI or stored in snapshots.
    
    Architecture note
    -----------------
    ``FigureLayout`` lives in ``gu_toolkit.figure_layout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_layout import FigureLayout
        obj = FigureLayout(...)
    
    Discovery-oriented use::
    
        help(FigureLayout)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
    """

    _STYLE_CSS = load_ui_css("figure_layout.css")

    def __init__(self, title: str = "") -> None:
        self._view_pages: dict[str, _ViewPage] = {}
        self._layout_event_emitter: Callable[..., Any] | None = None
        self._layout_event_base: dict[str, Any] = {}
        self._ordered_view_ids: tuple[str, ...] = ()
        self._active_view_id: str | None = None
        self._suspend_view_selector_events = False
        self._reflow_callback: Callable[[str, str], Any] | None = None
        self._content_layout_mode = "wrapped"

        # 1. Title bar
        self.title_html = widgets.HTMLMath(
            value=title, layout=build_layout(margin="0px")
        )
        self.title_html.add_class("gu-figure-title")
        self.full_width_checkbox = widgets.Checkbox(
            value=False,
            description="Full width plot",
            indent=False,
            layout=build_layout(width="160px", margin="0px"),
        )
        self._titlebar = widgets.HBox(
            [self.title_html, self.full_width_checkbox],
            layout=build_layout(
                width="100%",
                align_items="center",
                justify_content="space-between",
                margin="0 0 6px 0",
            ),
        )
        self._titlebar.add_class("gu-figure-titlebar")

        # 2. Persistent view selector + stage
        self.view_selector = widgets.ToggleButtons(
            options=(),
            value=None,
            layout=build_layout(display="none", width="100%", margin="0 0 6px 0"),
        )
        self.view_stage = widgets.Box(
            children=(),
            layout=build_layout(
                width="100%",
                height="60vh",
                min_width="0",
                min_height="260px",
                margin="0px",
                padding="0px",
                flex="1 1 560px",
                display="flex",
                flex_flow="column",
                overflow="hidden",
            ),
        )
        self.view_stage.add_class("gu-figure-view-stage")
        self.view_stage.add_class("gu-figure-context-governed")

        # 3. Controls sidebar
        self.legend_panel = build_section_panel(
            "Legend",
            variant="toolbar",
            display="none",
            extra_classes=("gu-figure-sidebar-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-panel-body", "gu-figure-legend-area"),
        )
        self.legend_header = self.legend_panel.title
        self.legend_header_toolbar = self.legend_panel.toolbar
        self.legend_box = self.legend_panel.body

        self.params_panel = build_section_panel(
            "Parameters",
            variant="minimal",
            display="none",
            extra_classes=("gu-figure-sidebar-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-panel-body",),
        )
        self.params_header = self.params_panel.title
        self.params_box = self.params_panel.body

        self.info_panel = build_section_panel(
            "Info",
            variant="minimal",
            display="none",
            extra_classes=("gu-figure-sidebar-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-panel-body", "gu-figure-info-output"),
        )
        self.info_header = self.info_panel.title
        self.info_box = self.info_panel.body

        self.sidebar_container = widgets.VBox(
            [
                self.legend_panel.panel,
                self.params_panel.panel,
                self.info_panel.panel,
            ],
            layout=build_layout(
                margin="0px",
                padding="0px 0px 0px 10px",
                flex="0 1 380px",
                min_width="260px",
                max_width="400px",
                display="none",
                overflow_x="hidden",
                overflow_y="auto",
                box_sizing="border-box",
            ),
        )
        self.sidebar_container.add_class("gu-figure-sidebar")
        self.sidebar_container.add_class("gu-figure-context-governed")

        # 4. Main content wrapper
        self.left_panel = widgets.VBox(
            [self.view_selector, self.view_stage],
            layout=build_layout(
                width="100%",
                min_width="0",
                flex="1 1 560px",
                margin="0px",
                padding="0px",
            ),
        )
        self.left_panel.add_class("gu-figure-left-panel")

        self.content_wrapper = widgets.Box(
            [self.left_panel, self.sidebar_container],
            layout=build_layout(
                display="flex",
                flex_flow="row wrap",
                align_items="stretch",
                width="100%",
                min_width="0",
                min_height="0",
                gap="8px",
            ),
        )
        self.content_wrapper.add_class("gu-figure-content")

        # 5. Output area below the figure
        self.print_output = widgets.Output(
            layout=build_layout(
                width="100%",
                min_width="0",
                min_height="32px",
                margin="0px",
                padding="0px",
            )
        )
        self.print_output.add_class("gu-figure-output-widget")
        self.output_panel = build_section_panel(
            "Output",
            variant="minimal",
            display="flex",
            extra_classes=("gu-figure-output-panel", "gu-figure-panel-box"),
            body_extra_classes=("gu-figure-output-body",),
        )
        self.print_header = self.output_panel.title
        self.print_panel = self.output_panel.panel
        self.output_panel.body.children = (self.print_output,)
        self.output_panel.body.layout.overflow_y = "auto"
        self.print_area = widgets.VBox(
            [self.print_panel],
            layout=build_layout(width="100%", margin="6px 0 0 0"),
        )
        self.print_area.add_class("gu-figure-context-governed")

        self._style_widget = shared_style_widget(self._STYLE_CSS)

        self.root_widget = widgets.VBox(
            [self._style_widget, self._titlebar, self.content_wrapper, self.print_area],
            layout=build_layout(width="100%", min_width="0", position="relative"),
        )
        self.root_widget.add_class("gu-figure-root")
        self.root_widget.add_class("gu-theme-root")

        self.full_width_checkbox.observe(self._on_full_width_change, names="value")
        self._apply_content_layout_mode(is_full=self.full_width_checkbox.value)
        self._emit_layout_event(
            "layout_initialized",
            phase="completed",
            title=title,
            sidebar_display=self.sidebar_container.layout.display,
            view_stage=layout_value_snapshot(self.view_stage.layout, ("width", "height", "min_height", "display", "overflow")),
        )

    def bind_layout_debug(self, emitter: Callable[..., Any], **base_fields: Any) -> None:
        """Bind layout debug.
        
        Full API
        --------
        ``obj.bind_layout_debug(emitter: Callable[..., Any], **base_fields: Any) -> None``
        
        Parameters
        ----------
        emitter : Callable[Ellipsis, Any]
            Value for ``emitter`` in this API. Required.
        
        **base_fields : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``**base_fields``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.bind_layout_debug(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self._layout_event_emitter = emitter
        self._layout_event_base = dict(base_fields)

    def _emit_layout_event(self, event: str, *, phase: str, **fields: Any) -> None:
        if self._layout_event_emitter is None:
            return
        payload = dict(self._layout_event_base)
        payload.update(fields)
        self._layout_event_emitter(event=event, source="FigureLayout", phase=phase, **payload)

    def bind_reflow_request(self, callback: Callable[[str, str], Any] | None) -> None:
        """Backward-compatible alias for :meth:`bind_view_reflow`.
        
        Full API
        --------
        ``obj.bind_reflow_request(callback: Callable[[str, str], Any] | None) -> None``
        
        Parameters
        ----------
        callback : Callable[[str, str], Any] | None
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.bind_reflow_request(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        self._reflow_callback = callback

    @property
    def output_widget(self) -> OneShotOutput:
        """Work with output widget on ``FigureLayout``.
        
        Full API
        --------
        ``obj.output_widget -> OneShotOutput``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        OneShotOutput
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            current = obj.output_widget
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        out = OneShotOutput()
        with out:
            display(self.root_widget)
        return out

    def layout_snapshot(self) -> dict[str, Any]:
        """Return a structural snapshot of the figure layout widget tree.
        
        Full API
        --------
        ``obj.layout_snapshot() -> dict[str, Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            result = obj.layout_snapshot(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        pages = {
            view_id: {
                "title": page.title,
                "display": page.host_box.layout.display,
                "has_widget": page.widget is not None,
            }
            for view_id, page in self._view_pages.items()
        }
        return {
            "title": self.title_html.value,
            "full_width": bool(self.full_width_checkbox.value),
            "content_layout_mode": self._content_layout_mode,
            "ordered_view_ids": list(self._ordered_view_ids),
            "active_view_id": self._active_view_id,
            "view_selector_display": self.view_selector.layout.display,
            "content_wrapper": layout_value_snapshot(
                self.content_wrapper.layout,
                ("display", "flex_flow", "gap", "width", "min_width", "min_height"),
            ),
            "left_panel": layout_value_snapshot(
                self.left_panel.layout,
                ("width", "min_width", "flex"),
            ),
            "view_stage": layout_value_snapshot(
                self.view_stage.layout,
                ("width", "height", "min_width", "min_height", "display", "flex", "overflow"),
            ),
            "sidebar": layout_value_snapshot(
                self.sidebar_container.layout,
                ("display", "flex", "min_width", "max_width", "width", "padding", "overflow"),
            ),
            "print_area": layout_value_snapshot(
                self.print_area.layout,
                ("width", "margin"),
            ),
            "pages": pages,
        }

    def set_title(self, text: str) -> None:
        """Set title.
        
        Full API
        --------
        ``obj.set_title(text: str) -> None``
        
        Parameters
        ----------
        text : str
            Human-readable text payload or label content. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_title(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self.title_html.value = text

    def get_title(self) -> str:
        """Return title.
        
        Full API
        --------
        ``obj.get_title() -> str``
        
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
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            result = obj.get_title(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        return self.title_html.value

    def update_sidebar_visibility(
        self, has_params: bool, has_info: bool, has_legend: bool
    ) -> bool:
        """Apply sidebar section visibility and report geometry changes.
        
        Full API
        --------
        ``obj.update_sidebar_visibility(has_params: bool, has_info: bool, has_legend: bool) -> bool``
        
        Parameters
        ----------
        has_params : bool
            Boolean flag or query related to availability of params. Required.
        
        has_info : bool
            Boolean flag or query related to availability of info. Required.
        
        has_legend : bool
            Boolean flag or query related to availability of legend. Required.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            result = obj.update_sidebar_visibility(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        old_state = (
            self.params_header.layout.display,
            self.params_panel.panel.layout.display,
            self.info_header.layout.display,
            self.info_panel.panel.layout.display,
            self.legend_panel.panel.layout.display,
            self.sidebar_container.layout.display,
        )

        self.params_header.layout.display = "block" if has_params else "none"
        self.params_panel.panel.layout.display = "flex" if has_params else "none"

        self.info_header.layout.display = "block" if has_info else "none"
        self.info_panel.panel.layout.display = "flex" if has_info else "none"

        self.legend_panel.panel.layout.display = "flex" if has_legend else "none"

        show_sidebar = has_params or has_info or has_legend
        self.sidebar_container.layout.display = "flex" if show_sidebar else "none"

        new_state = (
            self.params_header.layout.display,
            self.params_panel.panel.layout.display,
            self.info_header.layout.display,
            self.info_panel.panel.layout.display,
            self.legend_panel.panel.layout.display,
            self.sidebar_container.layout.display,
        )
        changed = new_state != old_state
        self._emit_layout_event(
            "sidebar_visibility_changed" if changed else "sidebar_visibility_unchanged",
            phase="completed",
            has_params=has_params,
            has_info=has_info,
            has_legend=has_legend,
            sidebar_display=self.sidebar_container.layout.display,
        )
        return changed

    def ensure_view_page(self, view_id: str, title: str) -> None:
        """Ensure a persistent host page exists for ``view_id``.
        
        Full API
        --------
        ``obj.ensure_view_page(view_id: str, title: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        title : str
            Human-readable title text shown in the UI or stored in snapshots. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.ensure_view_page(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        previous_order = self._ordered_view_ids
        page = self._view_pages.get(key)
        created = False
        if page is None:
            host_box = widgets.Box(
                children=(),
                layout=build_layout(
                    width="100%",
                    height="100%",
                    min_width="0",
                    min_height="0",
                    display="none",
                    flex="1 1 auto",
                    overflow="hidden",
                ),
            )
            host_box.add_class("gu-figure-view-page")
            page = _ViewPage(
                view_id=key,
                title=str(title),
                host_box=host_box,
                widget=None,
            )
            self._view_pages[key] = page
            if key not in self._ordered_view_ids:
                self._ordered_view_ids = (*self._ordered_view_ids, key)
            created = True
        else:
            page.title = str(title)

        self._rebuild_view_stage()
        self._refresh_view_selector()
        if self._ordered_view_ids != previous_order:
            self._emit_layout_event(
                "view_order_changed",
                phase="completed",
                ordered_view_ids=list(self._ordered_view_ids),
            )
        self._emit_layout_event(
            "view_page_created" if created else "view_page_updated",
            phase="completed",
            view_id=view_id,
            title=title,
            host_box=layout_value_snapshot(
                page.host_box.layout,
                ("width", "height", "display", "overflow"),
            ),
        )
        self._apply_active_page_visibility()

    def attach_view_widget(self, view_id: str, widget: widgets.Widget) -> None:
        """Attach ``widget`` to the persistent page for ``view_id``.
        
        Full API
        --------
        ``obj.attach_view_widget(view_id: str, widget: widgets.Widget) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        widget : widgets.Widget
            Widget/control instance associated with this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.attach_view_widget(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        if key in self._view_pages:
            title = self._view_pages[key].title
        else:
            title = key
        self.ensure_view_page(key, title=title)
        page = self._view_pages[key]
        attached_widget: widgets.Widget
        if isinstance(widget, widgets.Widget):
            attached_widget = widget
        else:
            fallback = widgets.Output(
                layout=build_layout(
                    width="100%",
                    height="100%",
                    min_width="0",
                    min_height="0",
                    overflow="hidden",
                )
            )
            add_class = getattr(fallback, "add_class", None)
            if callable(add_class):
                add_class("gu-figure-view-fallback-output")
            try:
                with fallback:
                    clear_output(wait=True)
                    display(widget)
            except Exception:
                pass
            attached_widget = fallback
        page.widget = attached_widget
        page.host_box.children = (attached_widget,)
        self._emit_layout_event("view_widget_attached", phase="completed", view_id=view_id, widget_type=type(widget).__name__)

    def remove_view_page(self, view_id: str) -> None:
        """Remove page bookkeeping for ``view_id`` if present.
        
        Full API
        --------
        ``obj.remove_view_page(view_id: str) -> None``
        
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
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.remove_view_page(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        previous_order = self._ordered_view_ids
        page = self._view_pages.pop(key, None)
        if page is None:
            return
        page.host_box.children = ()
        self._ordered_view_ids = tuple(v for v in self._ordered_view_ids if v != key)
        if self._active_view_id == key:
            self._active_view_id = (
                self._ordered_view_ids[0] if self._ordered_view_ids else None
            )
        self._rebuild_view_stage()
        self._refresh_view_selector()
        if self._ordered_view_ids != previous_order:
            self._emit_layout_event(
                "view_order_changed",
                phase="completed",
                ordered_view_ids=list(self._ordered_view_ids),
            )
        self._emit_layout_event("view_page_removed", phase="completed", view_id=view_id)
        self._apply_active_page_visibility()

    def set_view_order(self, view_ids: Sequence[str]) -> None:
        """Set the visual order of registered view pages.
        
        Full API
        --------
        ``obj.set_view_order(view_ids: Sequence[str]) -> None``
        
        Parameters
        ----------
        view_ids : Sequence[str]
            Collection of view identifiers associated with this object or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_order(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        ordered = tuple(str(view_id) for view_id in view_ids if str(view_id) in self._view_pages)
        if ordered == self._ordered_view_ids:
            self._refresh_view_selector()
            self._apply_active_page_visibility()
            return
        self._ordered_view_ids = ordered
        if self._active_view_id not in self._ordered_view_ids:
            self._active_view_id = self._ordered_view_ids[0] if self._ordered_view_ids else None
        self._rebuild_view_stage()
        self._refresh_view_selector()
        self._apply_active_page_visibility()

    def set_active_view(self, view_id: str) -> None:
        """Show only the active view page and sync selector selection.
        
        Full API
        --------
        ``obj.set_active_view(view_id: str) -> None``
        
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
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_active_view(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        key = str(view_id)
        if key not in self._view_pages:
            raise KeyError(f"Unknown view page: {key}")
        self._active_view_id = key
        self._apply_active_page_visibility()
        self._refresh_view_selector()

    def set_view_title(self, view_id: str, title: str) -> None:
        """Update the selector title for ``view_id``.
        
        Full API
        --------
        ``obj.set_view_title(view_id: str, title: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        title : str
            Human-readable title text shown in the UI or stored in snapshots. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_title(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        page = self._view_pages.get(str(view_id))
        if page is None:
            return
        page.title = str(title)
        self._refresh_view_selector()

    def observe_view_selection(self, callback: Callable[[str], None]) -> None:
        """Call ``callback`` whenever the selector chooses a new view.
        
        Full API
        --------
        ``obj.observe_view_selection(callback: Callable[[str], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[str], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.observe_view_selection(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        def _on_selection(change: dict[str, Any]) -> None:
            if self._suspend_view_selector_events:
                return
            new_value = change.get("new")
            if new_value is None:
                return
            callback(str(new_value))

        self.view_selector.observe(_on_selection, names="value")

    def observe_full_width_change(self, callback: Callable[[bool], None]) -> None:
        """Observe full-width layout toggle changes.
        
        Full API
        --------
        ``obj.observe_full_width_change(callback: Callable[[bool], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[bool], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.observe_full_width_change(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        def _on_full_width(change: dict[str, Any]) -> None:
            callback(bool(change.get("new")))

        self.full_width_checkbox.observe(_on_full_width, names="value")

    def bind_view_reflow(self, callback: Callable[[str, str], Any]) -> None:
        """Register a callback used by compatibility reflow wrappers.
        
        Full API
        --------
        ``obj.bind_view_reflow(callback: Callable[[str, str], Any]) -> None``
        
        Parameters
        ----------
        callback : Callable[[str, str], Any]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.bind_view_reflow(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        self._reflow_callback = callback

    @property
    def content_layout_mode(self) -> str:
        """Return the current high-level content layout mode.
        
        Full API
        --------
        ``obj.content_layout_mode -> str``
        
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
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            current = obj.content_layout_mode
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """
        return self._content_layout_mode

    # ------------------------------------------------------------------
    # Compatibility wrappers kept for one refactor cycle.
    # ------------------------------------------------------------------

    def set_plot_widget(
        self,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        """Set plot widget.
        
        Full API
        --------
        ``obj.set_plot_widget(widget: widgets.Widget, *, reflow_callback: Callable[[], None] | None=None) -> None``
        
        Parameters
        ----------
        widget : widgets.Widget
            Widget/control instance associated with this API. Required.
        
        reflow_callback : Callable[[], None] | None, optional
            Value for ``reflow_callback`` in this API. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``reflow_callback=None``: Value for ``reflow_callback`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_plot_widget(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        if reflow_callback is not None:
            self.bind_view_reflow(lambda _view_id, _reason: reflow_callback())
        self.ensure_view_page("main", "main")
        self.attach_view_widget("main", widget)
        self.set_view_order(("main",))
        self.set_active_view("main")

    def set_view_plot_widget(
        self,
        view_id: str,
        widget: widgets.Widget,
        *,
        reflow_callback: Callable[[], None] | None = None,
    ) -> None:
        """Set view plot widget.
        
        Full API
        --------
        ``obj.set_view_plot_widget(view_id: str, widget: widgets.Widget, *, reflow_callback: Callable[[], None] | None=None) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        widget : widgets.Widget
            Widget/control instance associated with this API. Required.
        
        reflow_callback : Callable[[], None] | None, optional
            Value for ``reflow_callback`` in this API. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``reflow_callback=None``: Value for ``reflow_callback`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_plot_widget(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        if reflow_callback is not None:
            self.bind_view_reflow(lambda _view_id, _reason: reflow_callback())
        self.ensure_view_page(str(view_id), str(view_id))
        self.attach_view_widget(str(view_id), widget)

    def set_view_tabs(self, view_ids: Sequence[str], *, active_view_id: str) -> None:
        """Set view tabs.
        
        Full API
        --------
        ``obj.set_view_tabs(view_ids: Sequence[str], *, active_view_id: str) -> None``
        
        Parameters
        ----------
        view_ids : Sequence[str]
            Collection of view identifiers associated with this object or update. Required.
        
        active_view_id : str
            Identifier for the currently selected view. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.set_view_tabs(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self.set_view_order(view_ids)
        self.set_active_view(active_view_id)

    def trigger_reflow_for_view(self, view_id: str) -> None:
        """Work with trigger reflow for view on ``FigureLayout``.
        
        Full API
        --------
        ``obj.trigger_reflow_for_view(view_id: str) -> None``
        
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
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.trigger_reflow_for_view(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        key = str(view_id)
        if self._reflow_callback is None:
            self._emit_layout_event(
                "reflow_callback_missing",
                phase="skipped",
                view_id=key,
                reason="compatibility_reflow",
            )
            return None
        self._emit_layout_event(
            "reflow_callback_invoked",
            phase="requested",
            view_id=key,
            reason="compatibility_reflow",
        )
        self._reflow_callback(key, "compatibility_reflow")
        return None

    def observe_tab_selection(self, callback: Callable[[str], None]) -> None:
        """Observe tab selection.
        
        Full API
        --------
        ``obj.observe_tab_selection(callback: Callable[[str], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[str], None]
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FigureLayout``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FigureLayout(...)
            obj.observe_tab_selection(...)
        
        Discovery-oriented use::
        
            help(FigureLayout)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(FigureLayout)`` and ``dir(FigureLayout)`` to inspect adjacent members.
        """

        self.observe_view_selection(callback)

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------

    def _rebuild_view_stage(self) -> None:
        self.view_stage.children = tuple(
            self._view_pages[view_id].host_box
            for view_id in self._ordered_view_ids
            if view_id in self._view_pages
        )

    def _apply_active_page_visibility(self) -> None:
        for view_id, page in self._view_pages.items():
            display = "flex" if view_id == self._active_view_id else "none"
            page.host_box.layout.display = display
            self._emit_layout_event("view_page_visibility_changed", phase="completed", view_id=view_id, display_state=display, is_active=(view_id == self._active_view_id))

    def _refresh_view_selector(self) -> None:
        options = [
            (self._view_pages[view_id].title, view_id)
            for view_id in self._ordered_view_ids
            if view_id in self._view_pages
        ]
        show_selector = len(options) > 1
        desired_value = None
        if self._active_view_id is not None and any(val == self._active_view_id for _, val in options):
            desired_value = self._active_view_id
        elif options:
            desired_value = options[0][1]
            self._active_view_id = desired_value

        self._suspend_view_selector_events = True
        try:
            self.view_selector.options = tuple(options)
            self.view_selector.layout.display = "flex" if show_selector else "none"
            if desired_value is None:
                self.view_selector.value = None
            elif self.view_selector.value != desired_value:
                self.view_selector.value = desired_value
        finally:
            self._suspend_view_selector_events = False
        self._emit_layout_event("view_selector_refreshed", phase="completed", options=[val for _, val in options], selector_display=self.view_selector.layout.display, active_view_id=self._active_view_id)

    def _apply_content_layout_mode(self, *, is_full: bool) -> None:
        layout = self.content_wrapper.layout
        plot_layout = self.left_panel.layout
        sidebar_layout = self.sidebar_container.layout

        if is_full:
            self._content_layout_mode = "stacked"
            layout.flex_flow = "column"
            plot_layout.flex = "0 0 auto"
            sidebar_layout.flex = "0 0 auto"
            sidebar_layout.max_width = ""
            sidebar_layout.width = "100%"
            sidebar_layout.padding = "0px"
        else:
            self._content_layout_mode = "wrapped"
            layout.flex_flow = "row wrap"
            plot_layout.flex = "1 1 560px"
            sidebar_layout.flex = "0 1 380px"
            sidebar_layout.max_width = "400px"
            sidebar_layout.width = "auto"
            sidebar_layout.padding = "0px 0px 0px 10px"

    def _on_full_width_change(self, change: dict[str, Any]) -> None:
        is_full = bool(change["new"])
        self._apply_content_layout_mode(is_full=is_full)
        layout = self.content_wrapper.layout
        plot_layout = self.left_panel.layout
        sidebar_layout = self.sidebar_container.layout
        self._emit_layout_event(
            "full_width_layout_changed",
            phase="completed",
            is_full=is_full,
            layout_mode=self._content_layout_mode,
            content_wrapper=layout_value_snapshot(layout, ("display", "flex_flow", "gap")),
            left_panel=layout_value_snapshot(plot_layout, ("width", "min_width", "flex")),
            sidebar=layout_value_snapshot(sidebar_layout, ("display", "flex", "max_width", "width", "padding")),
        )
