"""Info section manager for figure sidebars.

The *Info section* is the optional sidebar region used for explanatory text,
small computed summaries, and arbitrary notebook output associated with a
figure. Two lanes are supported:

- raw :class:`ipywidgets.Output` widgets created via :meth:`get_output`, and
- simple *info cards* created via :meth:`set_simple_card`.

An *info card* is a small rich-text block composed of static string segments,
dynamic callable segments, or a mixture of both. Cards may be global or scoped
to a specific view. A view-scoped card is shown only while that view is the
active one.
"""

from __future__ import annotations

import html
import re
import time
import traceback
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ._widget_stubs import widgets
from IPython.display import display

from .debouncing import QueuedDebouncer
from .FigureSnapshot import InfoCardSnapshot
from .ui_system import build_layout

# SECTION: InfoPanelManager (The Model for Info) [id: InfoPanelManager]
# =============================================================================


class InfoPanelManager:
    """Own the figure sidebar's Info section.
    
    Full API
    --------
    ``InfoPanelManager(layout_box: widgets.Box)``
    
    Public members exposed from this class: ``bind_layout_change_callback``, ``get_output``, ``add_component``, ``get_component``,
        ``has_info``, ``outputs``, ``set_simple_card``, ``set_active_view``,
        ``schedule_info_update``, ``bind_figure``, ``snapshot``
    
    Parameters
    ----------
    layout_box : widgets.Box
        Value for ``layout_box`` in this API. Required.
    
    Returns
    -------
    InfoPanelManager
        New ``InfoPanelManager`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``InfoPanelManager`` lives in ``gu_toolkit.figure_info``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_info import InfoPanelManager
        obj = InfoPanelManager(...)
    
    Discovery-oriented use::
    
        help(InfoPanelManager)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
    """

    _ID_REGEX = re.compile(r"^info:(\d+)$")
    _SIMPLE_ID_REGEX = re.compile(r"^info(\d+)$")

    @dataclass(frozen=True)
    class InfoChangeContext:
        """Update metadata for dynamic info segment evaluations.
        
        Full API
        --------
        ``InfoChangeContext(reason: str, trigger: Any=None, t: float=0.0, seq: int=0)``
        
        Public members exposed from this class: No additional public methods are declared directly on this class.
        
        Parameters
        ----------
        reason : str
            Short machine/human-readable reason recorded for scheduling or rendering. Required.
        
        trigger : Any, optional
            Event object or trigger payload that caused the current action. Defaults to ``None``.
        
        t : float, optional
            Value for ``t`` in this API. Defaults to ``0.0``.
        
        seq : int, optional
            Value for ``seq`` in this API. Defaults to ``0``.
        
        Returns
        -------
        InfoChangeContext
            New ``InfoChangeContext`` instance configured according to the constructor arguments.
        
        Optional arguments
        ------------------
        - ``trigger=None``: Event object or trigger payload that caused the current action.
        - ``t=0.0``: Value for ``t`` in this API.
        - ``seq=0``: Value for ``seq`` in this API.
        
        Architecture note
        -----------------
        ``InfoChangeContext`` lives in ``gu_toolkit.figure_info``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
        
        Examples
        --------
        Construction::
        
            from gu_toolkit.figure_info import InfoChangeContext
            obj = InfoChangeContext(...)
        
        Discovery-oriented use::
        
            help(InfoChangeContext)
            dir(obj)
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoChangeContext)`` and ``dir(InfoChangeContext)`` to inspect adjacent members.
        """

        reason: str
        trigger: Any = None
        t: float = 0.0
        seq: int = 0

    @dataclass
    class _StaticSegment:
        text: str
        widget: widgets.HTMLMath

    @dataclass
    class _DynamicSegment:
        fn: Callable[[Any, InfoPanelManager.InfoChangeContext], str]
        widget: widgets.HTMLMath
        last_text: str | None = None

    @dataclass
    class _SimpleInfoCard:
        id: Hashable
        output: widgets.Output
        container: widgets.VBox
        segments: list[
            InfoPanelManager._StaticSegment | InfoPanelManager._DynamicSegment
        ]
        debouncer: QueuedDebouncer
        pending_ctx: InfoPanelManager.InfoChangeContext | None = None
        view_id: str | None = None

    def __init__(self, layout_box: widgets.Box) -> None:
        """Initialize the info panel manager.

        Parameters
        ----------
        layout_box : ipywidgets.Box
            Container where info outputs will be added.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP

        Notes
        -----
        Use :meth:`get_output` to create outputs lazily as content is needed.
        """
        self._outputs: dict[Hashable, widgets.Output] = {}
        self._components: dict[Hashable, Any] = {}
        self._layout_box = layout_box
        self._counter = 0
        self._simple_cards: dict[Hashable, InfoPanelManager._SimpleInfoCard] = {}
        self._simple_counter = 0
        self._update_seq = 0
        self._active_view_id: str | None = None
        self._layout_change_callback: Callable[[str], Any] | None = None

    def bind_layout_change_callback(
        self, callback: Callable[[str], Any] | None
    ) -> None:
        """Bind a figure-owned callback notified when info widgets change.
        
        Full API
        --------
        ``obj.bind_layout_change_callback(callback: Callable[[str], Any] | None) -> None``
        
        Parameters
        ----------
        callback : Callable[[str], Any] | None
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
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            obj.bind_layout_change_callback(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        self._layout_change_callback = callback

    def _notify_layout_change(self, reason: str) -> None:
        callback = self._layout_change_callback
        if callback is not None:
            callback(reason)

    def get_output(
        self, id: Hashable | None = None, **layout_kwargs: Any
    ) -> widgets.Output:
        """Get or create an Info Output widget.
        
        Full API
        --------
        ``obj.get_output(id: Hashable | None=None, **layout_kwargs: Any) -> widgets.Output``
        
        Parameters
        ----------
        id : Hashable | None, optional
            Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
        
        **layout_kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        widgets.Output
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``id=None``: Stable identifier used to create, update, or look up the target object.
        - ``**layout_kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            result = obj.get_output(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        if id is None:
            self._counter += 1
            id = f"info:{self._counter}"

        if id in self._outputs:
            out = self._outputs[id]
            if layout_kwargs:
                out.layout = build_layout(
                    **self._normalize_output_layout_kwargs(layout_kwargs)
                )
            return out

        # Validate ID if string (avoids collision with auto-generated IDs)
        if isinstance(id, str):
            m = self._ID_REGEX.match(id)
            if m:
                self._counter = max(self._counter, int(m.group(1)))

        out = widgets.Output(
            layout=build_layout(**self._normalize_output_layout_kwargs(layout_kwargs))
        )
        out.id = id
        add_class = getattr(out, "add_class", None)
        if callable(add_class):
            add_class("gu-figure-info-output")

        self._outputs[id] = out
        self._layout_box.children += (out,)
        self._notify_layout_change("output_created")
        return out

    @staticmethod
    def _normalize_output_layout_kwargs(
        layout_kwargs: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Apply sane width/overflow defaults to sidebar info outputs."""

        normalized = {
            "width": "100%",
            "min_width": "0",
            "overflow_x": "hidden",
            "overflow_y": "auto",
        }
        if layout_kwargs:
            normalized.update(dict(layout_kwargs))
        return normalized

    def add_component(self, id: Hashable, component_inst: Any) -> None:
        """Register an info component instance.
        
        Full API
        --------
        ``obj.add_component(id: Hashable, component_inst: Any) -> None``
        
        Parameters
        ----------
        id : Hashable
            Stable identifier used to create, update, or look up the target object. Required.
        
        component_inst : Any
            Value for ``component_inst`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            obj.add_component(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        self._components[id] = component_inst

    def get_component(self, id: Hashable) -> Any:
        """Retrieve a previously registered info component.
        
        Full API
        --------
        ``obj.get_component(id: Hashable) -> Any``
        
        Parameters
        ----------
        id : Hashable
            Stable identifier used to create, update, or look up the target object. Required.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            result = obj.get_component(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        return self._components[id]

    @property
    def has_info(self) -> bool:
        """Whether the figure has any Info-section content.
        
        Full API
        --------
        ``obj.has_info -> bool``
        
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
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            current = obj.has_info
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        return len(self._outputs) > 0

    @property
    def outputs(self) -> Mapping[Hashable, widgets.Output]:
        """Read-only mapping of lazily created info outputs.
        
        Full API
        --------
        ``obj.outputs -> Mapping[Hashable, widgets.Output]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Mapping[Hashable, widgets.Output]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            current = obj.outputs
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        return MappingProxyType(self._outputs)

    def set_simple_card(
        self,
        spec: str | Callable | Sequence[str | Callable],
        id: Hashable | None = None,
        *,
        view: str | None = None,
    ) -> Hashable:
        """Create or replace a simple rich-text info card.
        
        Full API
        --------
        ``obj.set_simple_card(spec: str | Callable | Sequence[str | Callable], id: Hashable | None=None, *, view: str | None=None) -> Hashable``
        
        Parameters
        ----------
        spec : str | Callable | Sequence[str | Callable]
            Flexible specification object or shorthand accepted by this API. Required.
        
        id : Hashable | None, optional
            Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
        
        view : str | None, optional
            View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
        
        Returns
        -------
        Hashable
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``id=None``: Stable identifier used to create, update, or look up the target object.
        - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            result = obj.set_simple_card(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        if id is None:
            id = self._next_simple_id()
        elif isinstance(id, str):
            m = self._SIMPLE_ID_REGEX.match(id)
            if m:
                self._simple_counter = max(self._simple_counter, int(m.group(1)) + 1)

        out = self.get_output(id=id)

        normalized = self._normalize_spec(spec)
        card = self._simple_cards.get(id)
        if card is None:
            container = widgets.VBox(
                layout=widgets.Layout(gap="6px", width="100%", min_width="0")
            )
            add_class = getattr(container, "add_class", None)
            if callable(add_class):
                add_class("gu-figure-info-card")
            card = self._SimpleInfoCard(
                id=id,
                output=out,
                container=container,
                segments=[],
                debouncer=QueuedDebouncer(
                    lambda card_id=id: self._run_card_update(card_id),
                    execute_every_ms=33,
                    drop_overflow=True,
                ),
            )
            self._simple_cards[id] = card

        card.view_id = view
        self._rebuild_simple_card(card, normalized)
        self._apply_card_visibility(card)
        return id

    def _apply_card_visibility(self, card: _SimpleInfoCard) -> None:
        visible = card.view_id is None or card.view_id == self._active_view_id
        card.output.layout.display = "block" if visible else "none"

    def set_active_view(self, view_id: str) -> None:
        """Update which view-scoped cards are visible in the sidebar.
        
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
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            obj.set_active_view(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        self._active_view_id = str(view_id)
        for card in self._simple_cards.values():
            self._apply_card_visibility(card)

    def _next_simple_id(self) -> str:
        while True:
            id = f"info{self._simple_counter}"
            self._simple_counter += 1
            if id not in self._outputs:
                return id

    def schedule_info_update(self, reason: str, trigger: Any = None) -> None:
        """Queue updates for all simple cards with a shared reason payload.
        
        Full API
        --------
        ``obj.schedule_info_update(reason: str, trigger: Any=None) -> None``
        
        Parameters
        ----------
        reason : str
            Short machine/human-readable reason recorded for scheduling or rendering. Required.
        
        trigger : Any, optional
            Event object or trigger payload that caused the current action. Defaults to ``None``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``trigger=None``: Event object or trigger payload that caused the current action.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            obj.schedule_info_update(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        if not self._simple_cards:
            return

        self._update_seq += 1
        ctx = self.InfoChangeContext(
            reason=reason, trigger=trigger, t=time.time(), seq=self._update_seq
        )
        for card in self._simple_cards.values():
            card.pending_ctx = ctx
            card.debouncer()

    def _normalize_spec(
        self, spec: str | Callable | Sequence[str | Callable]
    ) -> list[str | Callable]:
        if isinstance(spec, str) or callable(spec):
            return [spec]
        if isinstance(spec, Sequence) and not isinstance(spec, (str, bytes)):
            values = list(spec)
            for idx, value in enumerate(values):
                if not isinstance(value, str) and not callable(value):
                    raise TypeError(
                        f"Info spec element at index {idx} must be a str or callable; got {type(value).__name__}"
                    )
            return values
        raise TypeError(
            f"Info spec must be a str, callable, or sequence of these; got {type(spec).__name__}"
        )

    def _rebuild_simple_card(
        self, card: _SimpleInfoCard, normalized: list[str | Callable]
    ) -> None:
        segment_widgets: list[widgets.HTMLMath] = []
        segments: list[
            InfoPanelManager._StaticSegment | InfoPanelManager._DynamicSegment
        ] = []
        for part in normalized:
            if isinstance(part, str):
                widget = widgets.HTMLMath(
                    value=part,
                    layout=widgets.Layout(margin="0px", width="100%", min_width="0"),
                )
                segments.append(self._StaticSegment(text=part, widget=widget))
            else:
                widget = widgets.HTMLMath(
                    value="",
                    layout=widgets.Layout(margin="0px", width="100%", min_width="0"),
                )
                segments.append(
                    self._DynamicSegment(fn=part, widget=widget, last_text=None)
                )
            segment_widgets.append(widget)

        card.segments = segments
        card.pending_ctx = self.InfoChangeContext(
            reason="manual", trigger=None, t=time.time(), seq=self._update_seq
        )
        card.container.children = tuple(segment_widgets)

        with card.output:
            card.output.clear_output(wait=True)
            display(card.container)

        card.debouncer()

    def _run_card_update(self, card_id: Hashable) -> None:
        card = self._simple_cards.get(card_id)
        if card is None:
            return

        ctx = card.pending_ctx or self.InfoChangeContext(
            reason="manual", trigger=None, t=time.time(), seq=self._update_seq
        )
        for seg in card.segments:
            if isinstance(seg, self._StaticSegment):
                continue
            try:
                text = seg.fn(self._figure_owner, ctx)
                if text is None:
                    text = ""
                elif not isinstance(text, str):
                    text = str(text)
            except Exception as exc:
                text = self._format_segment_error(exc)
            if text != seg.last_text:
                seg.widget.value = text
                seg.last_text = text

    def _format_segment_error(self, exc: Exception) -> str:
        lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        payload = "".join(lines)
        capped = "\n".join(payload.splitlines()[:20])
        safe = html.escape(capped)
        return (
            '<pre style="max-height: 12em; overflow-y:auto; overflow-x:hidden; white-space: pre-wrap; overflow-wrap:anywhere; margin:0;">'
            f"{safe}"
            "</pre>"
        )

    @property
    def _figure_owner(self) -> Any:
        owner = getattr(self, "__figure_owner", None)
        if owner is None:
            raise RuntimeError("InfoPanelManager owner figure not set")
        return owner

    def bind_figure(self, fig: Any) -> None:
        """Bind the owning figure used when dynamic card callables run.
        
        Full API
        --------
        ``obj.bind_figure(fig: Any) -> None``
        
        Parameters
        ----------
        fig : Any
            Figure instance that owns the relevant state. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            obj.bind_figure(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        setattr(self, "__figure_owner", fig)

    def snapshot(self) -> tuple[InfoCardSnapshot, ...]:
        """Return immutable snapshots of all simple info cards.
        
        Full API
        --------
        ``obj.snapshot() -> tuple[InfoCardSnapshot, ...]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[InfoCardSnapshot, Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``InfoPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = InfoPanelManager(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(InfoPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(InfoPanelManager)`` and ``dir(InfoPanelManager)`` to inspect adjacent members.
        """
        results: list[InfoCardSnapshot] = []
        for card in self._simple_cards.values():
            segs: list[str] = []
            for seg in card.segments:
                if isinstance(seg, self._StaticSegment):
                    segs.append(seg.text)
                else:
                    segs.append("<dynamic>")
            results.append(
                InfoCardSnapshot(id=card.id, segments=tuple(segs), view_id=card.view_id)
            )
        return tuple(results)


# =============================================================================
