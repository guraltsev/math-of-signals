"""Core SmartFigure plotting system for interactive symbolic exploration.

The module hosts the coordinator class, plot abstraction, layout/parameter/info
managers, and notebook helper functions used to build responsive, parameterized
Plotly visualizations from SymPy expressions.
"""

from __future__ import annotations

# NOTE: This file is SmartFigure.py with the Info Components API implemented.
#       It is intended as a drop-in replacement.

"""Widgets and interactive plotting helpers for math exploration in Jupyter.

This file defines two main ideas:

1) OneShotOutput
   A small safety wrapper around ``ipywidgets.Output`` that can only be displayed once.
   This prevents a common notebook confusion: accidentally displaying the *same* widget
   in multiple places and then wondering which one is “live”.

2) SmartFigure (+ SmartPlot)
   A thin, student-friendly wrapper around ``plotly.graph_objects.FigureWidget`` that:
   - plots SymPy expressions by compiling them to NumPy via ``numpify_cached``,
   - supports interactive parameter sliders (via ``SmartFloatSlider``),
   - optionally provides an *Info* area (a stack of ``ipywidgets.Output`` widgets),
   - re-renders automatically when you pan/zoom (throttled) or move a slider.

The intended workflow is:

- define symbols with SymPy (e.g. ``x, a = sp.symbols("x a")``),
- create a ``SmartFigure``,
- add one or more plots with ``SmartFigure.plot(...)``,
- optionally add parameters (sliders) explicitly by passing ``parameters=[a, ...]``.
- otherwise, parameters are autodetected from the expression (all free symbols that are not the plot variable) and added automatically.

---------------------------------------------------------------------------
Quick start (in a Jupyter notebook)
---------------------------------------------------------------------------

>>> import sympy as sp
>>> from SmartFigure import SmartFigure  # wherever this file lives
>>>
>>> x, a = sp.symbols("x a")
>>> fig = SmartFigure(x_range=(-6, 6), y_range=(-3, 3))
>>> fig.plot(x, sp.sin(x), id="sin")
>>> fig.plot(x, a*sp.cos(x), id="a_cos")  # adds a slider for a
>>> fig.title = "Sine and a·Cosine"
>>> fig  # display in the output cell (or use display(fig))

Tip: if you omit ``parameters`` when calling ``plot``, SmartFigure will infer them
from the expression and create sliders automatically. Pass ``[]`` to disable that.

Info panel
----------
The sidebar has two sections:

- **Parameters**: auto-created sliders for SymPy symbols.
- **Info**: a container that holds *Output widgets* created by
  :meth:`SmartFigure.get_info_output`. This design is deliberate: printing directly
  into a container widget is ambiguous in Jupyter, but printing into an
  ``Output`` widget is well-defined.
  Info outputs are keyed by id, so you can retrieve them via
  ``fig.info_output[id]`` or create/reuse them via ``fig.get_info_output(id)``.

Notes for students
------------------
- SymPy expressions are symbolic. They are like *formulas*.
- Plotly needs numerical values (arrays of numbers).
- ``numpify_cached`` bridges the two: it turns a SymPy expression into a NumPy-callable function.
- Sliders provide the numeric values of parameters like ``a`` in real time.

Architecture Note (For Developers)
----------------------------------
To avoid a "God Object," responsibilities are split via composition:
- SmartFigure: The main coordinator/facade.
- SmartFigureLayout: Handles all UI/Widget construction, CSS/JS injection, and layout logic.
- ParameterManager: Handles slider creation, storage, and change hooks. Acts as a dict proxy.
- InfoPanelManager: Handles the info sidebar and component registry.
- SmartPlot: Handles the specific math-to-trace rendering logic.


Logging / debugging
-------------------
This module uses the standard Python ``logging`` framework (no prints). By default it installs a
``NullHandler``, so you will see nothing unless you configure logging.

In a Jupyter/JupyterLab notebook, enable logs like this:

    import logging
    logging.basicConfig(level=logging.INFO)   # or logging.DEBUG

To limit output to just this module, set its logger level instead:

    import logging
    logging.getLogger(__name__).setLevel(logging.DEBUG)

Notes:
- INFO render messages are rate-limited to ~1.0s.
- DEBUG range messages (x_range/y_range) are rate-limited to ~0.5s.
"""

import re
import time
import warnings
import logging
from contextlib import ExitStack, contextmanager
from collections.abc import Mapping
from typing import Any, Callable, Hashable, Optional, Sequence, Tuple, Union, Dict, Iterator, List

import ipywidgets as widgets
import numpy as np
import plotly.graph_objects as go
import sympy as sp
from IPython.display import display
from sympy.core.expr import Expr
from sympy.core.symbol import Symbol

# Internal imports (assumed to exist in the same package)
from .InputConvert import InputConvert
from .numpify import NumpifiedFunction, numpify_cached
from .PlotlyPane import PlotlyPane, PlotlyPaneStyle
from .SmartSlider import SmartFloatSlider
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .ParameterSnapshot import ParameterSnapshot
from .NumericExpression import PlotView


# Module logger
# - Uses a NullHandler so importing this module never configures global logging.
# - Callers can enable logs via standard logging configuration.
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_FIGURE_STACK: List["SmartFigure"] = []



class _FigureDefaultSentinel:
    """Sentinel value meaning "inherit from figure defaults"."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return the stable debug token for the figure-default sentinel."""
        return "FIGURE_DEFAULT"


FIGURE_DEFAULT = _FigureDefaultSentinel()


def _is_figure_default(value: Any) -> bool:
    """Return True when *value* requests figure-default behavior."""
    return value is FIGURE_DEFAULT or (isinstance(value, str) and value.lower() == "figure_default")

def _current_figure() -> Optional["SmartFigure"]:
    """Return the most recently pushed SmartFigure, if any.

    Returns
    -------
    SmartFigure or None
        The current figure on the stack, or ``None`` if no figure is active.
    """
    if not _FIGURE_STACK:
        return None
    return _FIGURE_STACK[-1]


def _require_current_figure() -> "SmartFigure":
    """Return the current SmartFigure, or raise if none is active.

    Returns
    -------
    SmartFigure
        The active SmartFigure on the stack.

    Raises
    ------
    RuntimeError
        If no SmartFigure is active.
    """
    fig = _current_figure()
    if fig is None:
        raise RuntimeError("No current SmartFigure. Use `with fig:` first.")
    return fig


def current_figure(*, required: bool = True) -> Optional["SmartFigure"]:
    """Return the active SmartFigure from the context stack.

    Parameters
    ----------
    required : bool, default=True
        If True, raise when no figure is currently active.

    Returns
    -------
    SmartFigure or None
        Active figure, or None when ``required=False`` and no context is active.
    """
    fig = _current_figure()
    if fig is None and required:
        raise RuntimeError(
            "No active SmartFigure. Use `with fig:` to set one, "
            "or pass an explicit figure to .bind()."
        )
    return fig


def _push_current_figure(fig: "SmartFigure") -> None:
    """Push a SmartFigure onto the global stack.

    Parameters
    ----------
    fig : SmartFigure
        The figure to mark as current.

    Returns
    -------
    None
    """
    _FIGURE_STACK.append(fig)


def _pop_current_figure(fig: "SmartFigure") -> None:
    """Remove a specific SmartFigure from the global stack if present.

    Parameters
    ----------
    fig : SmartFigure
        The figure to remove.

    Returns
    -------
    None
    """
    if not _FIGURE_STACK:
        return
    if _FIGURE_STACK[-1] is fig:
        _FIGURE_STACK.pop()
        return
    for i in range(len(_FIGURE_STACK) - 1, -1, -1):
        if _FIGURE_STACK[i] is fig:
            del _FIGURE_STACK[i]
            break


@contextmanager
def _use_figure(fig: "SmartFigure") -> Iterator["SmartFigure"]:
    """Context manager that temporarily sets a SmartFigure as current.

    Parameters
    ----------
    fig : SmartFigure
        The figure to make current within the context.

    Yields
    ------
    SmartFigure
        The same figure passed in.
    """
    _push_current_figure(fig)
    try:
        yield fig
    finally:
        _pop_current_figure(fig)


# -----------------------------
# Small type aliases
# -----------------------------
NumberLike = Union[int, float]
NumberLikeOrStr = Union[int, float, str]
RangeLike = Tuple[NumberLikeOrStr, NumberLikeOrStr]
VisibleSpec = Union[bool, str]  # Plotly uses True/False or the string "legendonly".

PLOT_STYLE_OPTIONS: Dict[str, str] = {
    "color": "Line color. Accepts CSS-like names (e.g., red), hex (#RRGGBB), or rgb()/rgba() strings.",
    "thickness": "Line width in pixels. Larger values draw thicker lines.",
    "dash": "Line pattern. Supported values: solid, dot, dash, longdash, dashdot, longdashdot.",
    "opacity": "Overall trace opacity from 0.0 (fully transparent) to 1.0 (fully opaque).",
    "line": "Extra line-style fields as a mapping (for advanced per-line styling).",
    "trace": "Extra trace fields as a mapping (for advanced full-trace styling).",
}


# =============================================================================
# SECTION: OneShotOutput [id: OneShotOutput]
# =============================================================================

class OneShotOutput(widgets.Output):
    """
    A specialized Output widget that can only be displayed once.

    Why this exists
    ---------------
    In Jupyter, widgets are *live objects* connected to the frontend by a comm channel.
    If you display the same widget instance multiple times, it is easy to end up with
    confusing UI behavior (e.g., “Which copy should update?”, “Why did output appear
    in two places?”, etc.).

    ``OneShotOutput`` prevents accidental duplication by raising an error on the
    second display attempt.

    What counts as “display”?
    -------------------------
    Any of the following will count as displaying the widget:
    - having it be the last expression in a cell,
    - calling ``display(output)``,
    - placing it inside another widget/layout that is displayed.
   
     Attributes
    ----------
    _displayed : bool
        Internal flag tracking whether the widget has been displayed.
    
      Examples
    --------
    Basic output usage:

    >>> out = OneShotOutput()
    >>> with out:
    ...     print("Hello from inside the Output widget!")
    >>> out  # first display works

    Attempting to display again raises:

    >>> out  # doctest: +SKIP
    RuntimeError: OneShotOutput has already been displayed...

    Use case: preventing accidental double-display:

    >>> out = OneShotOutput()
    >>> with out:
    ...     print("I only want this shown once.")
    >>> display(out)  # ok
    >>> display(out)  # raises RuntimeError

    If you *really* need to display it again (advanced / use with caution),
    you can reset:

    >>> out.reset_display_state()
    >>> display(out)  # now allowed again

    (See ``reset_display_state`` for warnings.)
    """

    __slots__ = ("_displayed",)

    def __init__(self) -> None:
        """Initialize a new OneShotOutput widget.

        Returns
        -------
        None

        Examples
        --------
        >>> out = OneShotOutput()  # doctest: +SKIP
        >>> out.has_been_displayed
        False

        Notes
        -----
        Use :meth:`reset_display_state` only if you intentionally want to reuse
        the same widget instance across multiple displays.
        """
        super().__init__()
        self._displayed = False

    def _repr_mimebundle_(self, include: Any = None, exclude: Any = None, **kwargs: Any) -> Any:
        """
        IPython rich display hook used by ipywidgets.

        This is what gets called when the widget is displayed (including via
        `display(self)` or by being the last expression in a cell).

        Parameters
        ----------
        include : Any, optional
            MIME types to include, forwarded to the base widget.
        exclude : Any, optional
            MIME types to exclude, forwarded to the base widget.
        **kwargs : Any
            Additional arguments passed to ``ipywidgets.Output``.

        Returns
        -------
        Any
            The rich display representation.

        Notes
        -----
        This method is invoked automatically by IPython during display; users
        should not call it directly. See :meth:`reset_display_state` if you need
        to re-display the widget intentionally.
        """
        if self._displayed:
            raise RuntimeError(
                "OneShotOutput has already been displayed. "
                "This widget supports only one-time display."
            )
        self._displayed = True
        return super()._repr_mimebundle_(include=include, exclude=exclude, **kwargs)

    @property
    def has_been_displayed(self) -> bool:
        """
        Check if the widget has been displayed.

        Returns
        -------
        bool
            True if the widget has been displayed, False otherwise.

        Examples
        --------
        >>> out = OneShotOutput()  # doctest: +SKIP
        >>> out.has_been_displayed
        False

        Notes
        -----
        This is a read-only convenience property; use
        :meth:`reset_display_state` to clear the flag.
        """
        return self._displayed

    def reset_display_state(self) -> None:
        """
        Reset the display state to allow re-display.

        Warning
        -------
        This method should be used with caution as it bypasses the
        one-time display protection.

        Returns
        -------
        None

        Examples
        --------
        >>> out = OneShotOutput()  # doctest: +SKIP
        >>> out.reset_display_state()

        See Also
        --------
        has_been_displayed : Check whether the widget has already been displayed.
        """
        self._displayed = False


# =============================================================================
# SECTION: SmartFigureLayout (The View) [id: SmartFigureLayout]
# =============================================================================

class SmartFigureLayout:
    """
    Manages the visual structure and widget hierarchy of a SmartFigure.
    
    This class isolates all the "messy" UI code (CSS strings, JavaScript injection,
    VBox/HBox nesting) from the mathematical logic.

    Responsibilities:
    - Building the HBox/VBox structure.
    - Providing the plot container and layout toggles.
    - Exposing containers for Plots, Parameters, and Info.
    - Handling layout toggles (e.g. full width, sidebar visibility).
    """

    def __init__(self, title: str = "") -> None:
        """Initialize the layout manager and build the widget tree.

        Parameters
        ----------
        title : str, optional
            Initial title text (rendered as HTML/LaTeX in the header).

        Returns
        -------
        None

        Examples
        --------
        >>> layout = SmartFigureLayout(title="My Plot")  # doctest: +SKIP
        >>> layout.get_title()  # doctest: +SKIP
        'My Plot'

        Notes
        -----
        This class focuses on widget composition; :class:`SmartFigure` handles
        plotting logic and parameter updates.
        """
        self._reflow_callback: Optional[Callable[[], None]] = None

        # 1. Title Bar
        #    We use HTMLMath for proper LaTeX title rendering.
        self.title_html = widgets.HTMLMath(value=title, layout=widgets.Layout(margin="0px"))
        self.full_width_checkbox = widgets.Checkbox(
            value=False,
            description="Full width plot",
            indent=False,
            layout=widgets.Layout(width="160px", margin="0px"),
        )
        self._titlebar = widgets.HBox(
            [self.title_html, self.full_width_checkbox],
            layout=widgets.Layout(
                width="100%", align_items="center", justify_content="space-between", margin="0 0 6px 0"
            ),
        )

        # 2. Plot Area (The "Left" Panel)
        #    Ensure a real pixel height for Plotly sizing.
        self.plot_container = widgets.Box(
            children=(),
            layout=widgets.Layout(
                width="100%",
                height="60vh",
                min_width="320px",
                min_height="260px",
                margin="0px",
                padding="0px",
                flex="1 1 560px",
            ),
        )

        # 3. Controls Sidebar (The "Right" Panel)
        #    Initially hidden (display="none") until parameters or info widgets are added.
        self.params_header = widgets.HTML("<b>Parameters</b>", layout=widgets.Layout(display="none", margin="0"))
        self.params_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.info_header = widgets.HTML("<b>Info</b>", layout=widgets.Layout(display="none", margin="10px 0 0 0"))
        self.info_box = widgets.VBox(
            layout=widgets.Layout(
                width="100%",
                display="none",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
            )
        )

        self.sidebar_container = widgets.VBox(
            [self.params_header, self.params_box, self.info_header, self.info_box],
            layout=widgets.Layout(
                margin="0px", padding="0px 0px 0px 10px", flex="0 1 380px",
                min_width="300px", max_width="400px", display="none"
            ),
        )

        # 4. Main Content Wrapper (Flex)
        #    Uses flex-wrap so the sidebar drops below the plot on narrow screens.
        self.content_wrapper = widgets.Box(
            [self.plot_container, self.sidebar_container],
            layout=widgets.Layout(
                display="flex", flex_flow="row wrap", align_items="flex-start",
                width="100%", gap="8px"
            ),
        )

        # 4.5. Default print/output area (below the entire figure content)
        self.print_header = widgets.HTML("<b>Output</b>", layout=widgets.Layout(margin="8px 0 4px 0"))
        self.print_output = widgets.Output(
            layout=widgets.Layout(
                width="100%",
                min_height="48px",
                padding="8px",
                border="1px solid rgba(15,23,42,0.08)",
                border_radius="10px",
                overflow="auto",
            )
        )
        self.print_area = widgets.VBox(
            [self.print_header, self.print_output],
            layout=widgets.Layout(width="100%", margin="6px 0 0 0"),
        )

        # 5. Root Widget
        self.root_widget = widgets.VBox(
            [self._titlebar, self.content_wrapper, self.print_area],
            layout=widgets.Layout(width="100%", position="relative")
        )

        # Wire up internal logic
        self.full_width_checkbox.observe(self._on_full_width_change, names="value")

    @property
    def output_widget(self) -> OneShotOutput:
        """Return a OneShotOutput wrapping the layout, ready for display.

        Returns
        -------
        OneShotOutput
            A display-ready output widget containing the layout.

        Examples
        --------
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> out = layout.output_widget  # doctest: +SKIP

        See Also
        --------
        OneShotOutput : Prevents accidental multiple display of the same widget.
        """
        out = OneShotOutput()
        with out:
            display(self.root_widget)
        return out

    def set_title(self, text: str) -> None:
        """Set the title text shown above the plot.

        Parameters
        ----------
        text : str
            Title text (HTML/LaTeX supported).

        Returns
        -------
        None

        Examples
        --------
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> layout.set_title("Demo")  # doctest: +SKIP

        See Also
        --------
        get_title : Retrieve the current title.
        """
        self.title_html.value = text

    def get_title(self) -> str:
        """Get the current title text.

        Returns
        -------
        str
            The current title string.

        Examples
        --------
        >>> layout = SmartFigureLayout(title="Demo")  # doctest: +SKIP
        >>> layout.get_title()  # doctest: +SKIP
        'Demo'

        See Also
        --------
        set_title : Update the title text.
        """
        return self.title_html.value

    def update_sidebar_visibility(self, has_params: bool, has_info: bool) -> None:
        """
        Updates visibility of headers and the sidebar itself based on content.
        
        This prevents empty "Parameters" or "Info" headers from cluttering the UI.

        Parameters
        ----------
        has_params : bool
            Whether parameter sliders exist.
        has_info : bool
            Whether info outputs exist.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> layout.update_sidebar_visibility(has_params=True, has_info=False)  # doctest: +SKIP

        Notes
        -----
        Call this after adding or removing parameters/info outputs to ensure the
        UI reflects the current state.
        """
        self.params_header.layout.display = "block" if has_params else "none"
        self.params_box.layout.display = "flex" if has_params else "none"
        
        self.info_header.layout.display = "block" if has_info else "none"
        self.info_box.layout.display = "flex" if has_info else "none"

        show_sidebar = has_params or has_info
        self.sidebar_container.layout.display = "flex" if show_sidebar else "none"

    def set_plot_widget(
        self,
        widget: widgets.Widget,
        *,
        reflow_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Attach the plot widget to the layout and store a reflow callback.

        Parameters
        ----------
        widget : ipywidgets.Widget
            The plot widget to display.
        reflow_callback : callable, optional
            Callback to trigger when layout changes (e.g., full-width toggle).

        Returns
        -------
        None

        Examples
        --------
        >>> layout = SmartFigureLayout()  # doctest: +SKIP
        >>> dummy = widgets.Box()  # doctest: +SKIP
        >>> layout.set_plot_widget(dummy)  # doctest: +SKIP

        Notes
        -----
        The ``reflow_callback`` is typically used to notify Plotly of size
        changes when the sidebar toggles.
        """
        self.plot_container.children = (widget,)
        self._reflow_callback = reflow_callback

    def _on_full_width_change(self, change: Dict[str, Any]) -> None:
        """Toggle CSS flex properties for full-width mode.

        Parameters
        ----------
        change : dict
            Traitlets change dictionary from the checkbox.

        Returns
        -------
        None
        """
        is_full = change["new"]
        layout = self.content_wrapper.layout
        plot_layout = self.plot_container.layout
        sidebar_layout = self.sidebar_container.layout

        if is_full:
            # Stack vertically, full width
            layout.flex_flow = "column"
            plot_layout.flex = "0 0 auto"
            sidebar_layout.flex = "0 0 auto"
            sidebar_layout.max_width = ""
            sidebar_layout.width = "100%"
            sidebar_layout.padding = "0px"
        else:
            # Side-by-side (wrapping), restricted width for sidebar
            layout.flex_flow = "row wrap"
            plot_layout.flex = "1 1 560px"
            sidebar_layout.flex = "0 1 380px"
            sidebar_layout.max_width = "400px"
            sidebar_layout.width = "auto"
            sidebar_layout.padding = "0px 0px 0px 10px"
        if self._reflow_callback is not None:
            self._reflow_callback()


# =============================================================================
# SECTION: ParameterManager (The Model for Parameters) [id: ParameterManager]
# =============================================================================

class ParameterManager(Mapping[Symbol, ParamRef]):
    """
    Manages the collection of parameter sliders and change hooks.

    Responsibilities:
    - Creating and reusing parameter controls.
    - Storing parameter refs.
    - Executing hooks when parameters change.
    - Acts like a dictionary so `fig.parameters[sym]` works.

    Design Note:
    ------------
    By centralizing parameter logic here, we decouple the "state" of the math
    from the "rendering" of the figure.
    """

    def __init__(self, render_callback: Callable[[str, ParamEvent], None], layout_box: widgets.Box, modal_host: Optional[widgets.Box] = None) -> None:
        """Initialize the manager with a render callback and layout container.

        Parameters
        ----------
        render_callback : callable
            Function invoked when parameters change. Signature: ``(reason, event)``.
        layout_box : ipywidgets.Box
            Container where slider widgets will be added.
        modal_host : ipywidgets.Box, optional
            Host container used by controls that support full-layout modal overlays.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP

        Notes
        -----
        ``render_callback`` is invoked by :meth:`_on_param_change` whenever any
        parameter value updates.
        """
        self._refs: Dict[Symbol, ParamRef] = {}
        self._controls: List[Any] = []
        self._hooks: Dict[Hashable, Callable[[ParamEvent], Any]] = {}
        self._hook_counter: int = 0
        self._render_callback = render_callback
        self._layout_box = layout_box # The VBox where sliders live
        self._modal_host = modal_host

    def parameter(self, symbols: Union[Symbol, Sequence[Symbol]], *, control: Optional[Any] = None, **control_kwargs: Any):
        """
        Create or reuse parameter references for the given symbols.

        Parameters
        ----------
        symbols : sympy.Symbol or sequence[sympy.Symbol]
            Parameter symbol(s) to ensure.
        control : Any, optional
            Optional control instance (or compatible) to use. When provided, the
            control must implement ``make_refs`` and return a mapping for the
            requested symbol(s).
        **control_kwargs :
            Control configuration (min, max, value, step). These are applied to
            the resulting :class:`ParamRef` objects.

        Returns
        -------
        ParamRef or dict[Symbol, ParamRef]
            ParamRef for a single symbol, or mapping for multiple symbols.

        Examples
        --------
        Create a single slider and fetch its ref:

        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = mgr.parameter(a, min=-2, max=2)  # doctest: +SKIP
        >>> ref.symbol  # doctest: +SKIP
        a

        Notes
        -----
        For custom controls, pass ``control`` with a ``make_refs`` method that
        returns a ``{Symbol: ParamRef}`` mapping.
        """
        if isinstance(symbols, Symbol):
            symbols = [symbols]
            single = True
        else:
            symbols = list(symbols)
            single = False

        existing = [s for s in symbols if s in self._refs]
        missing = [s for s in symbols if s not in self._refs]

        if control is not None and existing:
            for symbol in existing:
                if self._refs[symbol].widget is not control:
                    raise ValueError(f"Symbol {symbol} is already bound to a different control.")

        defaults = {'value': 0.0, 'min': -1.0, 'max': 1.0, 'step': 0.01}

        if control is None:
            for symbol in missing:
                config = {**defaults, **control_kwargs}
                new_control = SmartFloatSlider(
                    description=f"${sp.latex(symbol)}$",
                    value=float(config['value']),
                    min=float(config['min']),
                    max=float(config['max']),
                    step=float(config['step'])
                )
                self._attach_modal_host(new_control)
                refs = new_control.make_refs([symbol])
                if symbol not in refs:
                    raise KeyError(f"Control did not provide a ref for symbol {symbol}.")
                ref = refs[symbol]
                ref.observe(self._on_param_change)
                self._refs[symbol] = ref
                if new_control not in self._controls:
                    self._controls.append(new_control)
                    self._layout_box.children += (new_control,)
        elif missing:
            self._attach_modal_host(control)
            refs = control.make_refs(missing)
            for symbol in missing:
                if symbol not in refs:
                    raise KeyError(f"Control did not provide a ref for symbol {symbol}.")
                ref = refs[symbol]
                ref.observe(self._on_param_change)
                self._refs[symbol] = ref
            if control not in self._controls:
                self._controls.append(control)
                self._layout_box.children += (control,)

        for symbol in symbols:
            ref = self._refs[symbol]
            for name, value in control_kwargs.items():
                setattr(ref, name, value)

        if single:
            return self._refs[symbols[0]]
        return {symbol: self._refs[symbol] for symbol in symbols}

    def _attach_modal_host(self, control: Any) -> None:
        """Attach modal host to controls that support it.

        Parameters
        ----------
        control : Any
            Candidate control widget.

        Returns
        -------
        None
            Applies host binding when supported.
        """
        if self._modal_host is None:
            return
        attach_fn = getattr(control, "set_modal_host", None)
        if callable(attach_fn):
            attach_fn(self._modal_host)

    def snapshot(self, *, full: bool = False) -> Dict[Symbol, Any] | ParameterSnapshot:
        """Return parameter values or a full immutable metadata snapshot.

        Parameters
        ----------
        full : bool, default=False
            If False, return a detached ``dict[Symbol, value]``.
            If True, return a full :class:`ParameterSnapshot` including metadata.
        """
        entries: Dict[Symbol, Dict[str, Any]] = {}
        for symbol, ref in self._refs.items():
            entry: Dict[str, Any] = {"value": ref.value}
            caps = list(ref.capabilities)
            entry["capabilities"] = caps
            for name in caps:
                entry[name] = getattr(ref, name)
            entries[symbol] = entry

        snapshot = ParameterSnapshot(entries)
        if full:
            return snapshot
        return snapshot.value_map()

    @property
    def has_params(self) -> bool:
        """Whether any parameters have been created.

        Returns
        -------
        bool
            ``True`` if at least one slider exists.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> mgr.has_params
        False

        See Also
        --------
        parameter : Create or reuse parameter controls.
        """
        return len(self._refs) > 0

    def add_hook(self, callback: Callable[[Optional[ParamEvent]], Any], hook_id: Optional[Hashable] = None) -> Hashable:
        """
        Register a parameter change hook.
        
        Parameters
        ----------
        callback: Callable
            The function to call (signature: (event)).
        hook_id: Hashable, optional
            Optional unique identifier.
        Returns
        -------
        Hashable
            The hook ID.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> hook_id = mgr.add_hook(lambda *_: None)  # doctest: +SKIP

        Notes
        -----
        Hooks are called after :class:`SmartFigure` re-renders on parameter
        updates.
        """
        if hook_id is None:
            self._hook_counter += 1
            hook_id = f"hook:{self._hook_counter}"
        self._hooks[hook_id] = callback
        
        return hook_id

    def fire_hook(self, hook_id: Hashable, event: Optional[ParamEvent]) -> None:
        """Fire a specific hook with a ParamEvent.

        Parameters
        ----------
        hook_id : hashable
            Identifier for the hook to invoke.
        event : ParamEvent or None
            Event payload to forward to the callback.

        Returns
        -------
        None

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> hook_id = mgr.add_hook(lambda *_: None)  # doctest: +SKIP
        >>> mgr.fire_hook(hook_id, None)  # doctest: +SKIP

        Notes
        -----
        Use :meth:`add_hook` to register callbacks before firing them.
        """
        callback = self._hooks.get(hook_id)
        if callback is None:
            return
        callback(event)

    def _on_param_change(self, event: ParamEvent) -> None:
        """Handle parameter changes by triggering the render callback.

        Parameters
        ----------
        event : ParamEvent
            Parameter change payload.

        Returns
        -------
        None
        """
        self._render_callback("param_change", event)
    
    def get_hooks(self) -> Dict[Hashable, Callable]:
        """Return a copy of the registered hook dictionary.

        Returns
        -------
        dict
            Mapping of hook IDs to callbacks.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> isinstance(mgr.get_hooks(), dict)
        True

        Notes
        -----
        The returned mapping is a shallow copy; mutating it will not affect
        internal registrations.
        """
        return self._hooks.copy()

    # --- Dict-like Interface for Backward Compatibility ---
    # This allows `fig.parameters[symbol]` to work in user hooks.
    
    def __getitem__(self, key: Symbol) -> ParamRef:
        """Return the param ref for the given symbol.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        ParamRef
            Ref associated with the symbol.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.parameter(a)  # doctest: +SKIP
        >>> mgr[a]  # doctest: +SKIP

        See Also
        --------
        get : Safe lookup with a default.
        """
        return self._refs[key]
    
    def __contains__(self, key: Symbol) -> bool:
        """Check if a slider exists for a symbol.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        bool
            ``True`` if the symbol is present.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> a in mgr
        False

        See Also
        --------
        has_params : Determine whether any parameters exist.
        """
        return key in self._refs
    
    def items(self) -> Iterator[Tuple[Symbol, ParamRef]]:
        """Iterate over ``(Symbol, ParamRef)`` pairs.

        Returns
        -------
        iterator
            Iterator over the internal ref mapping.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.items())
        []

        Notes
        -----
        This mirrors the behavior of ``dict.items`` for compatibility.
        """
        return self._refs.items()
    
    def keys(self) -> Iterator[Symbol]:
        """Iterate over parameter symbols.

        Returns
        -------
        iterator
            Iterator over parameter symbols.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.keys())
        []

        See Also
        --------
        values : Iterate over parameter references.
        """
        return self._refs.keys()
    
    def values(self) -> Iterator[ParamRef]:
        """Iterate over param refs.

        Returns
        -------
        iterator
            Iterator over param refs.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(mgr.values())
        []

        See Also
        --------
        keys : Iterate over parameter symbols.
        """
        return self._refs.values()
    
    def get(self, key: Symbol, default: Any = None) -> Any:
        """Return a param ref if present; otherwise return a default.

        Parameters
        ----------
        key : sympy.Symbol
            Parameter symbol.
        default : Any, optional
            Default value returned if no slider exists.

        Returns
        -------
        Any
            Param ref or the default value.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.get(a) is None
        True

        Notes
        -----
        This mirrors ``dict.get`` semantics for compatibility.
        """
        return self._refs.get(key, default)

    def __iter__(self) -> Iterator[Symbol]:
        """Iterate over parameter symbols.

        Returns
        -------
        iterator
            Iterator over parameter symbols.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> list(iter(mgr))
        []
        """
        return iter(self._refs)

    def __len__(self) -> int:
        """Return the number of stored parameter refs.

        Returns
        -------
        int
            Number of parameter refs in the manager.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> len(mgr)
        0
        """
        return len(self._refs)

    def widget(self, symbol: Symbol) -> Any:
        """Return the widget/control for a symbol.

        Parameters
        ----------
        symbol : sympy.Symbol
            Parameter symbol.

        Returns
        -------
        Any
            The underlying widget/control instance.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> mgr.parameter(a)  # doctest: +SKIP
        >>> mgr.widget(a)  # doctest: +SKIP

        See Also
        --------
        __getitem__ : Retrieve the :class:`ParamRef` for a symbol.
        """
        return self._refs[symbol].widget

    def widgets(self) -> List[Any]:
        """Return unique widgets/controls suitable for display.

        Returns
        -------
        list
            Unique control instances created by the manager.

        Examples
        --------
        >>> layout = widgets.VBox()  # doctest: +SKIP
        >>> mgr = ParameterManager(lambda *_: None, layout)  # doctest: +SKIP
        >>> mgr.widgets()  # doctest: +SKIP
        []

        Notes
        -----
        Use this when you need to manually lay out controls outside the default
        sidebar.
        """
        return list(self._controls)


# =============================================================================
# SECTION: InfoPanelManager (The Model for Info) [id: InfoPanelManager]
# =============================================================================

class InfoPanelManager:
    """
    Manages the 'Info' section output widgets and interactive components.

    It allows adding "Output" widgets (where you can print text or display charts)
    and registering "Stateful Components" (classes that update when sliders move).
    """
    
    _ID_REGEX = re.compile(r"^info:(\d+)$")

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
        self._outputs: Dict[Hashable, widgets.Output] = {}
        self._components: Dict[Hashable, Any] = {}
        self._layout_box = layout_box
        self._counter = 0

    def get_output(self, id: Optional[Hashable] = None, **layout_kwargs: Any) -> widgets.Output:
        """
        Get or create an Info Output widget.

        Parameters
        ----------
        id : hashable, optional
            Unique identifier for the output. If omitted, a new ID is generated.
        **layout_kwargs : Any
            Keyword arguments forwarded to ``ipywidgets.Layout``.

        Returns
        -------
        ipywidgets.Output
            Output widget associated with the ID.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> out = panel.get_output("info:1")  # doctest: +SKIP

        Notes
        -----
        IDs are stored on the widget as ``out.id`` for convenience.
        """
        if id is None:
            self._counter += 1
            id = f"info:{self._counter}"
        
        if id in self._outputs:
            out = self._outputs[id]
            if layout_kwargs:
                out.layout = widgets.Layout(**layout_kwargs)
            return out
        
        # Validate ID if string (avoids collision with auto-generated IDs)
        if isinstance(id, str):
            m = self._ID_REGEX.match(id)
            if m:
                self._counter = max(self._counter, int(m.group(1)))

        out = widgets.Output(layout=widgets.Layout(**layout_kwargs))
        setattr(out, 'id', id)
        
        self._outputs[id] = out
        self._layout_box.children += (out,)
        return out

    def add_component(self, id: Hashable, component_inst: Any) -> None:
        """Register an info component instance.

        Parameters
        ----------
        id : hashable
            Unique identifier for the component.
        component_inst : Any
            Component instance to store.

        Returns
        -------
        None

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP

        See Also
        --------
        get_component : Retrieve a registered component.
        """
        self._components[id] = component_inst

    def get_component(self, id: Hashable) -> Any:
        """Retrieve a previously registered info component.

        Parameters
        ----------
        id : hashable
            Component identifier.

        Returns
        -------
        Any
            The registered component instance.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.add_component("demo", object())  # doctest: +SKIP
        >>> panel.get_component("demo")  # doctest: +SKIP

        See Also
        --------
        add_component : Register a component instance.
        """
        return self._components[id]

    @property
    def has_info(self) -> bool:
        """Whether any info outputs exist.

        Returns
        -------
        bool
            ``True`` if at least one output has been created.

        Examples
        --------
        >>> panel = InfoPanelManager(widgets.VBox())  # doctest: +SKIP
        >>> panel.has_info
        False

        See Also
        --------
        get_output : Create an output widget in the info panel.
        """
        return len(self._outputs) > 0


# =============================================================================
# SECTION: SmartPlot (The specific logic for one curve) [id: SmartPlot]
# =============================================================================

class SmartPlot:
    """
    A single plotted curve managed by a :class:`SmartFigure`.

    Conceptually, a ``SmartPlot`` is “one function on one set of axes”.
    It owns a single Plotly trace (a line plot) and knows how to:

    - compile the SymPy expression to a fast NumPy function (via ``numpify_cached``),
    - sample x-values on an appropriate domain,
    - evaluate y-values (including current slider parameter values),
    - push the sampled data into the Plotly trace.
    """

    def __init__(
        self,
        var: Symbol,
        func: Expr,
        smart_figure: "SmartFigure",
        parameters: Sequence[Symbol] = [],
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[int,str] = None,
        label: str = "",
        visible: VisibleSpec = True,
        color: Optional[str] = None,
        thickness: Optional[Union[int, float]] = None,
        dash: Optional[str] = None,
        line: Optional[Mapping[str, Any]] = None,
        opacity: Optional[Union[int, float]] = None,
        trace: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """
        Create a new SmartPlot instance. (Usually called by SmartFigure.plot)

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable for the function.
        func : sympy.Expr
            Symbolic expression to plot.
        smart_figure : SmartFigure
            Owning figure.
        parameters : sequence[sympy.Symbol], optional
            Parameter symbols used in the expression.
        x_domain : RangeLike or None, optional
            Optional domain override for this plot.
        sampling_points : int or str, optional
            Number of samples; use ``"figure_default"`` to inherit from the figure.
        label : str, optional
            Trace label shown in the legend.
        visible : bool or "legendonly", optional
            Plotly visibility setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        trace : mapping or None, optional
            Extra full-trace style fields as a mapping (advanced usage).

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP

        Notes
        -----
        End users typically call :meth:`SmartFigure.plot` instead of instantiating
        ``SmartPlot`` directly.
        """
        self._smart_figure = smart_figure
        
        # Add trace to figure
        self._smart_figure.figure_widget.add_scatter(x=[], y=[], mode="lines", name=label, visible=visible)
        self._plot_handle = self._smart_figure.figure_widget.data[-1]

        self._suspend_render = True
        self._update_line_style(color=color, thickness=thickness, dash=dash, line=line)
        self.opacity = opacity
        if trace:
            self._plot_handle.update(**dict(trace))
        self.set_func(var, func, parameters)
        self.x_domain = x_domain
        
        if _is_figure_default(sampling_points):
            sampling_points = None
        self.sampling_points = sampling_points

        self._suspend_render = False
        
        self.render()

    def set_func(self, var: Symbol, func: Expr, parameters: Sequence[Symbol] = []) -> None:
        """
        Set the independent variable and symbolic function for this plot.
        Triggers recompilation via ``numpify_cached``.

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable.
        func : sympy.Expr
            Symbolic expression to plot.
        parameters : sequence[sympy.Symbol], optional
            Parameter symbols used in the expression.

        Returns
        -------
        None

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.set_func(x, a * sp.cos(x), parameters=[a])  # doctest: +SKIP

        See Also
        --------
        update : Update multiple plot attributes at once.
        """
        parameters = list(parameters) 
        # Compile
        self._numpified = numpify_cached(func, args=[var] + parameters)
        # Store
        self._var = var
        self._func = func

    @property
    def symbolic_expression(self) -> Expr:
        """Return the symbolic expression used by this plot."""
        return self._func

    @property
    def parameters(self) -> tuple[Symbol, ...]:
        """Return parameter symbols in deterministic numeric-argument order."""
        return self._numpified.args[1:]

    @property
    def numpified(self) -> NumpifiedFunction:
        """Return compiled numpified callable for this plot."""
        return self._numpified

    @property
    def numeric_expression(self) -> PlotView:
        """Return a live numeric evaluator proxy for this plot."""
        return PlotView(_numpified=self._numpified, _provider=self._smart_figure)

    def _eval_numeric_live(self, x: np.ndarray) -> np.ndarray:
        """Evaluate the numeric core against current figure parameter values."""
        fig = self._smart_figure
        args = [x]
        for symbol in self._numpified.args[1:]:
            args.append(fig.parameters[symbol].value)
        return self._numpified(*args)

    @property
    def label(self) -> str:
        """Return the legend label for this plot.

        Returns
        -------
        str
            The trace name.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig, label="sin")  # doctest: +SKIP
        >>> plot.label  # doctest: +SKIP
        'sin'

        See Also
        --------
        update : Update the label alongside other plot attributes.
        """
        return self._plot_handle.name

    @label.setter
    def label(self, value: str) -> None:
        """Set the legend label for this plot.

        Parameters
        ----------
        value : str
            New legend label.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.label = "sin(x)"  # doctest: +SKIP

        See Also
        --------
        label : Read the current legend label.
        """
        self._plot_handle.name = value

    @property
    def color(self) -> Optional[str]:
        """Return the current line color for this plot."""
        if self._plot_handle.line is None:
            return None
        return self._plot_handle.line.color

    @color.setter
    def color(self, value: Optional[str]) -> None:
        """Set the line color for this plot."""
        self._update_line_style(color=value)

    @property
    def thickness(self) -> Optional[float]:
        """Return the current line thickness for this plot."""
        if self._plot_handle.line is None:
            return None
        return self._plot_handle.line.width

    @thickness.setter
    def thickness(self, value: Optional[Union[int, float]]) -> None:
        """Set the line thickness for this plot."""
        self._update_line_style(thickness=value)

    @property
    def dash(self) -> Optional[str]:
        """Return the current line dash style for this plot."""
        if self._plot_handle.line is None:
            return None
        return self._plot_handle.line.dash

    @dash.setter
    def dash(self, value: Optional[str]) -> None:
        """Set the line dash style for this plot."""
        self._update_line_style(dash=value)

    @property
    def opacity(self) -> Optional[float]:
        """Return the current trace opacity for this plot."""
        return self._plot_handle.opacity

    @opacity.setter
    def opacity(self, value: Optional[Union[int, float]]) -> None:
        """Set the trace opacity for this plot (0.0 to 1.0)."""
        if value is None:
            self._plot_handle.opacity = None
            return
        opacity = float(InputConvert(value, float))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        self._plot_handle.opacity = opacity

    def figure(self) -> "SmartFigure":
        """Return the SmartFigure that owns this plot.

        Returns
        -------
        SmartFigure
            Owning figure instance.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.figure() is fig  # doctest: +SKIP
        True

        See Also
        --------
        SmartFigure.plot : Create or update plots on a figure.
        """
        return self._smart_figure

    @property
    def x_domain(self) -> Optional[Tuple[float, float]]:
        """Return the explicit x-domain override for this plot.

        Returns
        -------
        tuple[float, float] or None
            Explicit domain override or ``None`` to use the figure range.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig, x_domain=(-2, 2))  # doctest: +SKIP
        >>> plot.x_domain  # doctest: +SKIP
        (-2.0, 2.0)

        Notes
        -----
        When set, the plot may extend beyond the current viewport to ensure the
        full domain is drawn.
        """
        return self._x_domain

    @x_domain.setter
    def x_domain(self, value: Optional[RangeLike]) -> None:
        """Set the explicit x-domain for this plot.

        Parameters
        ----------
        value : RangeLike or None
            Domain override or ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
            to use the figure range.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.x_domain = (-1, 1)  # doctest: +SKIP

        See Also
        --------
        SmartFigure.x_range : Update the figure-wide x-axis range.
        """
        
        if value is None:
            self._x_domain = None
        elif _is_figure_default(value):
            self._x_domain = None
        else:
            raw_min, raw_max = value
            self._x_domain = (float(InputConvert(raw_min, float)), float(InputConvert(raw_max, float)))
            if self._x_domain[0] > self._x_domain[1]:
                raise ValueError("x_min must be <= x_max")
        self.render()

    @property
    def sampling_points(self) -> Optional[int]:
        """Return the number of sampling points for this plot.

        Returns
        -------
        int or None
            Number of samples, or ``None`` to use the figure default.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig, sampling_points=200)  # doctest: +SKIP
        >>> plot.sampling_points  # doctest: +SKIP
        200

        See Also
        --------
        SmartFigure.sampling_points : Figure-level default sampling.
        """
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, value: Optional[Union[int, str, _FigureDefaultSentinel]]) -> None:
        """Set the number of sampling points for this plot.

        Parameters
        ----------
        value : int, str, FIGURE_DEFAULT, or None
            Number of samples, or ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
            to inherit from the figure.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.sampling_points = 400  # doctest: +SKIP

        See Also
        --------
        sampling_points : Read the current sampling density.
        """
        self._sampling_points = int(InputConvert(value, int)) if value is not None and not _is_figure_default(value) else None
        self.render()

    @property
    def visible(self) -> VisibleSpec:
        """Return Plotly's visibility state for the trace.

        Returns
        -------
        bool or str
            ``True``, ``False``, or ``"legendonly"``.

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.visible  # doctest: +SKIP
        True

        Notes
        -----
        ``"legendonly"`` hides the trace while keeping it in the legend.
        """
        return self._plot_handle.visible

    @visible.setter
    def visible(self, value: VisibleSpec) -> None:
        """Set Plotly's visibility state for the trace.

        Parameters
        ----------
        value : bool or "legendonly"
            Visibility state.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.visible = "legendonly"  # doctest: +SKIP

        See Also
        --------
        render : Recompute samples when a plot becomes visible.
        """
        self._plot_handle.visible = value
        if value is True:
            self.render()

    def render(self) -> None:
        """
        Compute (x, y) samples and update the Plotly trace.
        Skips computation if the plot is hidden.

        Returns
        -------
        None

        Examples
        --------
        >>> x = sp.symbols("x")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.render()  # doctest: +SKIP

        Notes
        -----
        Rendering uses the figure's current viewport if it has been panned or
        zoomed.
        """
        if self._suspend_render or self.visible is not True:
            return

        # 1. Determine Range
        fig = self._smart_figure
        viewport = fig.current_x_range or fig.x_range
        
        if self.x_domain is None:
            x_min, x_max = float(viewport[0]), float(viewport[1])
        else:
            x_min = min(float(viewport[0]), float(self.x_domain[0]))
            x_max = max(float(viewport[1]), float(self.x_domain[1]))

        # 2. Determine Sampling
        num = self.sampling_points or fig.sampling_points or 500
        
        # 3. Compute
        x_values = np.linspace(x_min, x_max, num=int(num))
        y_values = np.asarray(self.numeric_expression(x_values))
        
        # 4. Update Trace
        with fig.figure_widget.batch_update():
            self._plot_handle.x = x_values
            self._plot_handle.y = y_values

    def _update_line_style(
        self,
        *,
        color: Optional[str] = None,
        thickness: Optional[Union[int, float]] = None,
        dash: Optional[str] = None,
        line: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Apply incremental line-style updates to the backing Plotly trace."""

        def _coerce_line_value(value: Any) -> Dict[str, Any]:
            """Normalize Plotly line-like structures to mutable dictionaries."""
            if not value:
                return {}
            if isinstance(value, Mapping):
                return dict(value)
            if hasattr(value, "to_plotly_json"):
                return value.to_plotly_json()
            try:
                return dict(value)
            except (TypeError, ValueError):
                return {}

        line_updates: Dict[str, Any] = {}
        if line:
            line_updates.update(_coerce_line_value(line))
        if color is not None:
            line_updates["color"] = color
        if thickness is not None:
            line_updates["width"] = float(InputConvert(thickness, float))
        if dash is not None:
            line_updates["dash"] = dash
        if line_updates:
            current_line = _coerce_line_value(self._plot_handle.line)
            current_line.update(line_updates)
            self._plot_handle.line = current_line
    
    def update(self, **kwargs: Any) -> None:
        """Update multiple plot attributes at once.

        Parameters
        ----------
        **kwargs : Any
            Supported keys include ``label``, ``x_domain``, ``sampling_points``,
            ``var``, ``func``, ``parameters``, ``color``, ``thickness``, ``dash``,
            ``opacity``, ``line``, and ``trace``.

        Returns
        -------
        None

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> plot = SmartPlot(x, sp.sin(x), fig)  # doctest: +SKIP
        >>> plot.update(label="sin", func=a * sp.sin(x), parameters=[a])  # doctest: +SKIP

        Notes
        -----
        This method is used internally by :meth:`SmartFigure.plot` when
        updating an existing plot.
        """
        if 'label' in kwargs: 
            self.label = kwargs['label']
        
        if 'x_domain' in kwargs: 
            val = kwargs['x_domain']
            if val is None:
                # None means "no change" during in-place updates.
                pass
            elif _is_figure_default(val):
                self.x_domain = None
            else:
                x_min = InputConvert(val[0], float)
                x_max = InputConvert(val[1], float)
                self.x_domain = (x_min, x_max)
        
        if 'sampling_points' in kwargs:
            val = kwargs['sampling_points']
            if val is None:
                # None means "no change" during in-place updates.
                pass
            elif _is_figure_default(val):
                self.sampling_points = None
            else:
                self.sampling_points = InputConvert(val, int)

        self._update_line_style(
            color=kwargs.get("color"),
            thickness=kwargs.get("thickness"),
            dash=kwargs.get("dash"),
            line=kwargs.get("line"),
        )
        if "opacity" in kwargs:
            self.opacity = kwargs["opacity"]
        if kwargs.get("trace"):
            self._plot_handle.update(**dict(kwargs["trace"]))
        
        # Function update
        if any(k in kwargs for k in ('var', 'func', 'parameters')):
            v = kwargs.get('var', self._var)
            f = kwargs.get('func', self._func)
            p = kwargs.get('parameters', self.parameters)
            self.set_func(v, f, p)
            self.render()


# =============================================================================
# SECTION: SmartFigure (The Coordinator) [id: SmartFigure]
# =============================================================================

class SmartFigure:
    """
    An interactive Plotly figure for plotting SymPy functions with slider parameters.

    What problem does this solve?
    -----------------------------
    We often want to:
    - type a symbolic function like ``sin(x)`` or ``a*x**2 + b`` (SymPy),
    - *see* it immediately (Plotly),
    - and then explore “What happens if I change a parameter?”

    ``SmartFigure`` provides a simple API that encourages experimentation.

    Key features
    ------------
    - Uses Plotly ``FigureWidget`` so it is interactive inside notebooks.
    - Uses a right-side controls panel for parameter sliders.
    - Supports plotting multiple curves identified by an ``id``.
    - Re-renders curves on:
      - slider changes,
      - pan/zoom changes (throttled to at most once every 0.5 seconds).

    Examples
    --------
    >>> import sympy as sp
    >>> x, a = sp.symbols("x a")
    >>> fig = SmartFigure()
    >>> fig.plot(x, a*sp.sin(x), parameters=[a], id="a_sin")
    >>> fig
    """
    
    __slots__ = [
        "_layout", "_params", "_info", "_figure", "_pane", "plots",
        "_x_range", "_y_range", "_sampling_points", "_debug",
        "_last_relayout", "_render_info_last_log_t", "_render_debug_last_log_t",
        "_has_been_displayed", "_print_capture"
    ]

    def __init__(
        self,
        sampling_points: int = 500,
        x_range: RangeLike = (-4, 4),
        y_range: RangeLike = (-3, 3),
        debug: bool = False,
    ) -> None:
        """Initialize a SmartFigure instance with default ranges and sampling.

        Parameters
        ----------
        sampling_points : int, optional
            Default number of samples per plot.
        x_range : RangeLike, optional
            Initial x-axis range.
        y_range : RangeLike, optional
            Initial y-axis range.
        debug : bool, optional
            Enable debug logging for renders and ranges.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure(x_range=(-6, 6), y_range=(-2, 2))  # doctest: +SKIP
        >>> fig.sampling_points  # doctest: +SKIP
        500

        Notes
        -----
        Parameters are managed by :class:`ParameterManager` and exposed through
        :attr:`params`.
        """
        self._debug = debug
        self._sampling_points = sampling_points
        self.plots: Dict[str, SmartPlot] = {}
        self._has_been_displayed = False
        self._print_capture: Optional[ExitStack] = None

        # 1. Initialize Layout (View)
        self._layout = SmartFigureLayout()
        
        # 2. Initialize Managers
        # Note: we pass a callback for rendering so params can trigger updates
        self._params = ParameterManager(
            self.render,
            self._layout.params_box,
            modal_host=self._layout.root_widget,
        )
        self._info = InfoPanelManager(self._layout.info_box)

        # 3. Initialize Plotly Figure
        self._figure = go.FigureWidget()
        self._figure.update_layout(
            autosize=True,
            template="plotly_white",
            showlegend=True,
            margin=dict(l=48, r=28, t=48, b=44),
            font=dict(
                family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                size=14,
                color="#1f2933",
            ),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            legend=dict(
                bgcolor="rgba(255,255,255,0.7)",
                bordercolor="rgba(15,23,42,0.08)",
                borderwidth=1,
            ),
            xaxis=dict(
                zeroline=True,
                zerolinewidth=1.5,
                zerolinecolor="#334155",
                showline=True,
                linecolor="#94a3b8",
                linewidth=1,
                mirror=True,
                ticks="outside",
                tickcolor="#94a3b8",
                ticklen=6,
                showgrid=True,
                gridcolor="rgba(148,163,184,0.35)",
                gridwidth=1,
            ),
            yaxis=dict(
                zeroline=True,
                zerolinewidth=1.5,
                zerolinecolor="#334155",
                showline=True,
                linecolor="#94a3b8",
                linewidth=1,
                mirror=True,
                ticks="outside",
                tickcolor="#94a3b8",
                ticklen=6,
                showgrid=True,
                gridcolor="rgba(148,163,184,0.35)",
                gridwidth=1,
            ),
        )
        self._pane = PlotlyPane(
            self._figure,
            style=PlotlyPaneStyle(
                padding_px=8,
                border="1px solid rgba(15,23,42,0.08)",
                border_radius_px=10,
                overflow="hidden",
            ),
            autorange_mode="none",
            defer_reveal=True,
        )
        self._layout.set_plot_widget(self._pane.widget, reflow_callback=self._pane.reflow)

        # 4. Set Initial State
        self.x_range = x_range
        self.y_range = y_range
        
        # 5. Bind Events
        self._last_relayout = time.monotonic()
        self._render_info_last_log_t = 0.0
        self._render_debug_last_log_t = 0.0
        self._figure.layout.on_change(self._throttled_relayout, "xaxis.range", "yaxis.range")

    # --- Properties ---

    @property
    def title(self) -> str:
        """Return the title text shown above the figure.

        Returns
        -------
        str
            Current title (HTML/LaTeX is allowed).

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.title = "Demo"  # doctest: +SKIP
        >>> fig.title  # doctest: +SKIP
        'Demo'

        See Also
        --------
        SmartFigureLayout.set_title : Underlying layout helper.
        """
        return self._layout.get_title()

    @title.setter
    def title(self, value: str) -> None:
        """Set the title text shown above the figure.

        Parameters
        ----------
        value : str
            Title text (HTML/LaTeX supported).

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.title = r"$y=\\sin(x)$"  # doctest: +SKIP

        See Also
        --------
        title : Read the current title text.
        """
        self._layout.set_title(value)
    
    @property
    def figure_widget(self) -> go.FigureWidget:
        """Access the underlying Plotly FigureWidget.

        Returns
        -------
        plotly.graph_objects.FigureWidget
            The interactive Plotly widget.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> isinstance(fig.figure_widget, go.FigureWidget)  # doctest: +SKIP
        True

        Notes
        -----
        Directly mutating the widget is supported, but changes may bypass
        SmartFigure's helper methods.
        """
        return self._figure
    
    @property
    def parameters(self) -> ParameterManager:
        """The figure ParameterManager (preferred name)."""
        return self._params

    @property
    def params(self) -> ParameterManager:
        """Alias for :attr:`parameters` for backward compatibility."""
        return self.parameters
    
    @property
    def info_output(self) -> Dict[Hashable, widgets.Output]:
        """Dictionary of Info Output widgets indexed by id.

        Returns
        -------
        dict
            Mapping of output IDs to ``ipywidgets.Output`` instances.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> isinstance(fig.info_output, dict)  # doctest: +SKIP
        True

        See Also
        --------
        get_info_output : Create or fetch an info output widget.
        """
        return self._info._outputs # Direct access for backward compat or advanced use

    @property
    def x_range(self) -> Tuple[float, float]:
        """Return the default x-axis range.

        Returns
        -------
        tuple[float, float]
            Default x-axis range restored on double-click.

        Examples
        --------
        >>> fig = SmartFigure(x_range=(-2, 2))  # doctest: +SKIP
        >>> fig.x_range  # doctest: +SKIP
        (-2.0, 2.0)

        See Also
        --------
        y_range : The default y-axis range.
        """
        return self._x_range
    
    @x_range.setter
    def x_range(self, value: RangeLike) -> None:
        """Set the default x-axis range.

        Parameters
        ----------
        value : RangeLike
            New axis range (min, max).

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.x_range = (-5, 5)  # doctest: +SKIP

        Notes
        -----
        This updates the Plotly axis range immediately.
        """
        self._x_range = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._figure.update_xaxes(range=self._x_range)

    @property
    def y_range(self) -> Tuple[float, float]:
        """Return the default y-axis range.

        Returns
        -------
        tuple[float, float]
            Default y-axis range.

        Examples
        --------
        >>> fig = SmartFigure(y_range=(-1, 1))  # doctest: +SKIP
        >>> fig.y_range  # doctest: +SKIP
        (-1.0, 1.0)

        See Also
        --------
        x_range : The default x-axis range.
        """
        return self._y_range
    
    @y_range.setter
    def y_range(self, value: RangeLike) -> None:
        """Set the default y-axis range.

        Parameters
        ----------
        value : RangeLike
            New axis range (min, max).

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.y_range = (-2, 2)  # doctest: +SKIP

        Notes
        -----
        This updates the Plotly axis range immediately.
        """
        self._y_range = (float(InputConvert(value[0], float)), float(InputConvert(value[1], float)))
        self._figure.update_yaxes(range=self._y_range)

    @property
    def current_x_range(self) -> Optional[Tuple[float, float]]:
        """Return the current viewport x-range (read-only).

        Returns
        -------
        tuple[float, float] or None
            Current Plotly x-axis range, or ``None`` if not set.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.current_x_range  # doctest: +SKIP

        Notes
        -----
        This reflects the Plotly widget state after panning or zooming.
        """
        return self._figure.layout.xaxis.range

    @property
    def current_y_range(self) -> Optional[Tuple[float, float]]:
        """Return the current viewport y-range (read-only).

        Returns
        -------
        tuple[float, float] or None
            Current Plotly y-axis range, or ``None`` if not set.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.current_y_range  # doctest: +SKIP

        Notes
        -----
        This reflects the Plotly widget state after panning or zooming.
        """
        return self._figure.layout.yaxis.range
    
    @property
    def sampling_points(self) -> Optional[int]:
        """Return the default number of sampling points per plot.

        Returns
        -------
        int or None
            Default sample count, or ``None`` for Plotly defaults.

        Examples
        --------
        >>> fig = SmartFigure(sampling_points=300)  # doctest: +SKIP
        >>> fig.sampling_points  # doctest: +SKIP
        300

        See Also
        --------
        SmartPlot.sampling_points : Per-plot overrides.
        """
        return self._sampling_points

    @sampling_points.setter
    def sampling_points(self, val: Union[int, str, _FigureDefaultSentinel, None]) -> None:
        """Set the default number of sampling points per plot.

        Parameters
        ----------
        val : int, str, FIGURE_DEFAULT, or None
            Sample count, or ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
            to clear.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.sampling_points = 200  # doctest: +SKIP

        Notes
        -----
        Use ``None``/``"figure_default"``/``"FIGURE_DEFAULT"``/``FIGURE_DEFAULT``
        to clear the override.
        """
        self._sampling_points = int(InputConvert(val, int)) if isinstance(val, (int, float, str)) and not _is_figure_default(val) else None

    # --- Public API ---

    @staticmethod
    def plot_style_options() -> Dict[str, str]:
        """Return discoverable plot-style options supported by :meth:`plot`.

        Returns
        -------
        dict[str, str]
            Mapping of option names to short descriptions.

        Notes
        -----
        These options can be passed directly to :meth:`plot` and :func:`plot`.
        Current supported shortcut keys are: ``color``, ``thickness``,
        ``dash``, ``opacity``, ``line``, and ``trace``.
        """
        return dict(PLOT_STYLE_OPTIONS)

    def plot(
        self,
        var: Symbol,
        func: Expr,
        parameters: Optional[Sequence[Symbol]] = None,
        id: Optional[str] = None,
        x_domain: Optional[RangeLike] = None,
        sampling_points: Optional[Union[int, str]] = None,
        color: Optional[str] = None,
        thickness: Optional[Union[int, float]] = None,
        dash: Optional[str] = None,
        line: Optional[Mapping[str, Any]] = None,
        opacity: Optional[Union[int, float]] = None,
        trace: Optional[Mapping[str, Any]] = None,
    ) -> SmartPlot:
        """
        Plot a SymPy expression on the figure (and keep it “live”).

        Parameters
        ----------
        var : sympy.Symbol
            Independent variable (e.g. ``x``).
        func : sympy.Expr
            SymPy expression (e.g. ``sin(x)``).
        parameters : list[sympy.Symbol] or None, optional
            Parameter symbols. If None, they are inferred from the expression.
            If [], that means explicitly no parameters. Parameter creation and
            updates are delegated to :class:`ParameterManager` (refactored API).
        x_domain : RangeLike or None, optional
            Domain of the independent variable (e.g. ``(-10, 10)``).
            If "figure_default", the figure's range is used when plotting. 
            If None, it is the same as "figure_default" for new plots while no change for existing plots.
        id : str, optional
            Unique identifier. If exists, the existing plot is updated in-place.

        sampling_points : int or str, optional
            Number of sampling points for this plot. Use ``"figure_default"``
            to inherit from the figure setting.
        color : str or None, optional
            Line color. Common formats include named colors (e.g., ``"red"``),
            hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
        thickness : int or float, optional
            Line width in pixels. ``1`` is thin; larger values produce thicker lines.
        dash : str or None, optional
            Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
            ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
        line : mapping or None, optional
            Extra per-line style fields as a mapping (advanced usage).
        opacity : int or float, optional
            Overall curve opacity between ``0.0`` (fully transparent) and
            ``1.0`` (fully opaque).
        trace : mapping or None, optional
            Extra full-trace style fields as a mapping (advanced usage).

        Returns
        -------
        SmartPlot
            The created or updated plot instance.

        Examples
        --------
        >>> x, a = sp.symbols("x a")  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.plot(x, a * sp.sin(x), parameters=[a], id="a_sin")  # doctest: +SKIP

        Notes
        -----
        Passing ``parameters=[]`` disables automatic parameter creation even if
        the expression has free symbols other than ``var``.

        All supported style options for this method are discoverable via
        :meth:`SmartFigure.plot_style_options`.

        See Also
        --------
        parameter : Create sliders without plotting.
        plot_style_options : List supported style kwargs and meanings
            (`color`, `thickness`, `dash`, `opacity`, `line`, `trace`).
        """
        # ID Generation
        if id is None:
            for i in range(100):
                if f"f_{i}" not in self.plots:
                    id = f"f_{i}"
                    break
            if id is None: raise ValueError("Too many auto-generated IDs")

        # Parameter Autodetection
        if parameters is None:
            parameters = sorted([s for s in func.free_symbols if s != var], key=lambda s: s.sort_key())

        # Ensure Parameters Exist (Delegate to Manager)
        if parameters:
            self.parameter(parameters)
        
        # Update UI visibility
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)

        # Create or Update Plot
        if id in self.plots:
            update_dont_create = True
        else: 
            update_dont_create = False

        if update_dont_create:
            self.plots[id].update(
                var=var,
                func=func,
                parameters=parameters,
                x_domain=x_domain,
                sampling_points=sampling_points,
                color=color,
                thickness=thickness,
                dash=dash,
                line=line,
                opacity=opacity,
                trace=trace,
            )
            plot = self.plots[id]    
        else: 
            plot = SmartPlot(
                var=var, func=func, smart_figure=self, parameters=parameters,
                x_domain=x_domain, sampling_points=sampling_points, label=id,
                color=color, thickness=thickness, dash=dash, line=line, opacity=opacity, trace=trace
            )
            self.plots[id] = plot
        
        return plot

    def parameter(self, symbols: Union[Symbol, Sequence[Symbol]], *, control: Optional[Any] = None, **control_kwargs: Any):
        """
        Create or ensure parameters and return refs.

        Parameters
        ----------
        symbols : sympy.Symbol or sequence[sympy.Symbol]
            Parameter symbol(s) to ensure.
        control : Any, optional
            Optional control instance to use for the parameter(s).
        **control_kwargs : Any
            Control configuration options (min, max, value, step).

        Returns
        -------
        ParamRef or dict[Symbol, ParamRef]
            ParamRef for a single symbol, or mapping for multiple symbols.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> fig.parameter(a, min=-2, max=2)  # doctest: +SKIP

        See Also
        --------
        add_param : Backward-compatible alias.
        """
        result = self._params.parameter(symbols, control=control, **control_kwargs)
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
        return result
        

    def render(self, reason: str = "manual", trigger: Optional[ParamEvent] = None) -> None:
        """
        Render all plots on the figure.

        This is a *hot* method: it is called during slider drags and (throttled)
        pan/zoom relayout events.

        Parameters
        ----------
        reason : str, optional
            Reason for rendering (e.g., ``"manual"``, ``"param_change"``, ``"relayout"``).
        trigger : Any, optional
            Change payload from the event that triggered rendering.

        Returns
        -------
        None

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.render()  # doctest: +SKIP

        Notes
        -----
        When called due to a parameter change, hooks registered via
        :meth:`add_param_change_hook` are invoked after plotting.
        """
        self._log_render(reason, trigger)
        
        # 1. Update all plots
        for plot in self.plots.values():
            plot.render()
        
        # 2. Run hooks (if triggered by parameter change)
        # Note: ParameterManager triggers this render, then we run hooks.
        if reason == "param_change" and trigger:
            hooks = self._params.get_hooks()
            for h_id, callback in list(hooks.items()):
                try:
                    callback(trigger)
                except Exception as e:
                    warnings.warn(f"Hook {h_id} failed: {e}")

    def add_param(self, symbol: Symbol, **kwargs: Any) -> ParamRef:
        """
        Add a parameter manually.

        Parameters
        ----------
        symbol : sympy.Symbol
            Parameter symbol to create a slider for.
        **kwargs : Any
            Slider configuration (min, max, value, step).

        Returns
        -------
        ParamRef
            The created or reused parameter reference.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> fig.add_param(a, min=-2, max=2)  # doctest: +SKIP

        See Also
        --------
        parameter : Preferred API for parameter creation.
        """
        return self.parameter(symbol, **kwargs)

    def get_info_output(self, id: Optional[Hashable] = None, **kwargs: Any) -> widgets.Output:
        """
        Create (or retrieve) an Output widget in the Info sidebar.

        Parameters
        ----------
        id : hashable, optional
            Unique identifier for the output. If omitted, a new ID is generated.
        **kwargs : Any
            Layout keyword arguments for ``ipywidgets.Layout``.

        Returns
        -------
        ipywidgets.Output
            Output widget for the info panel.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> out = fig.get_info_output("summary")  # doctest: +SKIP

        Notes
        -----
        Output widgets are added to the sidebar in the order they are created.
        """
        out = self._info.get_output(id, **kwargs)
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
        return out

    # Alias for backward compatibility
    new_info_output = get_info_output

    def add_info_component(self, id: Hashable, component_factory: Callable, hook_id: Optional[Hashable] = None, **kwargs: Any) -> Any:
        """
        Register (or replace) a stateful *info component*.

        An info component is a class/function that:
        1. Draws into an Info Output widget.
        2. Implements an `update(event, fig, out)` method.

        Parameters
        ----------
        id : hashable
            Unique identifier for the component.
        component_factory : callable
            Callable that accepts ``(out, fig)`` and returns a component instance.
        hook_id : hashable, optional
            Hook identifier for updates; defaults to ``("info_component", id)``.
        **kwargs : Any
            Layout keyword arguments forwarded to the output widget.

        Returns
        -------
        Any
            The created component instance.

        Examples
        --------
        >>> class ExampleComponent:  # doctest: +SKIP
        ...     def __init__(self, out, fig):  # doctest: +SKIP
        ...         self.out = out  # doctest: +SKIP
        ...     def update(self, event, fig, out):  # doctest: +SKIP
        ...         pass  # doctest: +SKIP
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.add_info_component("example", ExampleComponent)  # doctest: +SKIP

        Notes
        -----
        Components are updated via hooks registered in
        :meth:`add_param_change_hook`.
        """
        out = self.get_info_output(id, **kwargs)
        inst = component_factory(out, self)
        
        if not hasattr(inst, 'update'):
            raise TypeError(f"Component {id} must have an 'update' method")
        
        self._info.add_component(id, inst)
        
        # Register hook to update component on param change
        if hook_id is None: hook_id = ("info_component", id)
        
        def _hook(event: Optional[ParamEvent]) -> None:
            inst.update(event, self, out)
            
        self.add_param_change_hook(_hook, hook_id=hook_id)
        return inst

    def add_hook(self, callback: Callable[[Optional[ParamEvent]], Any], *, run_now: bool = True) -> Hashable:
        """Alias for :meth:`add_param_change_hook`.

        Parameters
        ----------
        callback : callable
            Function with signature ``(event)``.
        run_now : bool, optional
            Whether to run once immediately with a ``None`` event.

        Returns
        -------
        hashable
            The hook identifier used for registration.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.add_hook(lambda *_: None)  # doctest: +SKIP

        See Also
        --------
        add_param_change_hook : Full API with explicit hook IDs.
        """
        return self.add_param_change_hook(callback, hook_id=None, run_now=run_now)

    def add_param_change_hook(
        self,
        callback: Callable[[Optional[ParamEvent]], Any],
        hook_id: Optional[Hashable] = None,
        *,
        run_now: bool = True,
    ) -> Hashable:
        """
        Register a callback to run when *any* parameter value changes.

        Parameters
        ----------
        callback : callable
            Function with signature ``(event)``. For ``run_now=True``, the
            callback is invoked once with ``None`` after a manual render.
        hook_id : hashable, optional
            Unique identifier for the hook.
        run_now : bool, optional
            Whether to run once immediately with a ``None`` event.

        Returns
        -------
        hashable
            The hook identifier used for registration.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> fig.add_param_change_hook(lambda *_: None, run_now=False)  # doctest: +SKIP

        Notes
        -----
        Hooks are executed after the figure re-renders in response to changes.
        """
        def _wrapped(event: Optional[ParamEvent]) -> Any:
            with _use_figure(self):
                return callback(event)

        hook_id = self._params.add_hook(_wrapped, hook_id)

        if run_now:
            try:
                self.render(reason="manual", trigger=None)
                _wrapped(None)
            except Exception as e:
                warnings.warn(f"Hook failed on init: {e}")

        return hook_id

    # --- Internal / Plumbing ---

    def _throttled_relayout(self, *args: Any) -> None:
        """Handle plot relayout events with throttling.

        Parameters
        ----------
        *args : Any
            Plotly relayout event payload (unused).

        Returns
        -------
        None
        """
        now = time.monotonic()
        if now - self._last_relayout > 0.5:
            self._last_relayout = now
            self.render(reason="relayout")

    def _log_render(self, reason: str, trigger: Any) -> None:
        """Log render information with rate-limiting.

        Parameters
        ----------
        reason : str
            Render reason string.
        trigger : Any
            Trigger payload (unused except for context).

        Returns
        -------
        None
        """
        # Simple rate-limited logging implementation
        now = time.monotonic()
        if logger.isEnabledFor(logging.INFO) and (now - self._render_info_last_log_t) > 1.0:
            self._render_info_last_log_t = now
            logger.info(f"render(reason={reason}) plots={len(self.plots)}")
        
        if logger.isEnabledFor(logging.DEBUG) and (now - self._render_debug_last_log_t) > 0.5:
            self._render_debug_last_log_t = now
            logger.debug(f"ranges x={self.x_range} y={self.y_range}")

    def _ipython_display_(self, **kwargs: Any) -> None:
        """
        Special method called by IPython to display the object.
        Uses IPython.display.display() to render the underlying widget.

        Parameters
        ----------
        **kwargs : Any
            Display keyword arguments forwarded by IPython (unused).

        Returns
        -------
        None
        """
        self._has_been_displayed = True
        display(self._layout.output_widget)

    def __enter__(self) -> "SmartFigure":
        """Enter a context where this figure is the current target.

        Returns
        -------
        SmartFigure
            The same instance, for use with ``with`` blocks.

        Examples
        --------
        >>> fig = SmartFigure()  # doctest: +SKIP
        >>> with fig:  # doctest: +SKIP
        ...     pass

        See Also
        --------
        plot : Module-level helper that uses the current figure if available.
        """
        _push_current_figure(self)
        if self._print_capture is None:
            stack = ExitStack()
            stack.enter_context(self._layout.print_output)
            self._print_capture = stack
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit the current-figure context.

        Parameters
        ----------
        exc_type : Any
            Exception type, if any.
        exc : Any
            Exception instance, if any.
        tb : Any
            Traceback, if any.

        Returns
        -------
        None

        Notes
        -----
        This removes the figure from the module-level stack used by
        :func:`plot` and :func:`parameter`.
        """
        try:
            _pop_current_figure(self)
        finally:
            if self._print_capture is not None:
                self._print_capture.close()
                self._print_capture = None


class _CurrentParametersProxy(Mapping):
    """Module-level proxy to the current figure's ParameterManager.

    Examples
    --------
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> fig = SmartFigure()  # doctest: +SKIP
    >>> with fig:  # doctest: +SKIP
    ...     fig.plot(x, a * sp.sin(x), parameters=[a])  # doctest: +SKIP
    ...     params[a].value = 5  # doctest: +SKIP
    ...     parameter(a, min=-10, max=10)  # doctest: +SKIP
    """

    def _fig(self) -> "SmartFigure":
        """Return the current SmartFigure from the module stack."""
        return _require_current_figure()

    def _mgr(self) -> "ParameterManager":
        """Return the current figure's ParameterManager."""
        return self._fig().parameters

    def __getitem__(self, key: Hashable) -> ParamRef:
        """Return the current figure's parameter reference for ``key``."""
        return self._mgr()[key]

    def __iter__(self) -> Iterator[Hashable]:
        """Iterate parameter symbols from the active figure manager."""
        return iter(self._mgr())

    def __len__(self) -> int:
        """Return number of parameters on the active figure."""
        return len(self._mgr())

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` is present on the active figure."""
        return key in self._mgr()

    def __setitem__(self, key: Hashable, value: Any) -> None:
        """Set the active figure parameter value via mapping syntax."""
        self[key].value = value

    def parameter(
        self,
        symbols: Union[Symbol, Sequence[Symbol]],
        *,
        control: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[ParamRef, Dict[Symbol, ParamRef]]:
        """Proxy to the current figure's :meth:`ParameterManager.parameter`."""
        return self._mgr().parameter(symbols, control=control, **kwargs)

    def snapshot(self, *, full: bool = False) -> Dict[Symbol, Any] | ParameterSnapshot:
        """Return current-figure parameter values or full snapshot metadata."""
        return self._mgr().snapshot(full=full)

    def __getattr__(self, name: str) -> Any:
        """Forward unknown attributes/methods to active figure parameters."""
        return getattr(self._mgr(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Forward attribute assignment to active figure parameters."""
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._mgr(), name, value)


class _CurrentPlotsProxy(Mapping):
    """Module-level proxy to the current figure's plots mapping."""

    def _fig(self) -> "SmartFigure":
        return _require_current_figure()

    def __getitem__(self, key: Hashable) -> SmartPlot:
        return self._fig().plots[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._fig().plots)

    def __len__(self) -> int:
        return len(self._fig().plots)

    def __contains__(self, key: object) -> bool:
        return key in self._fig().plots


parameters = _CurrentParametersProxy()
params = parameters
plots = _CurrentPlotsProxy()


def set_title(text: str) -> None:
    """Set the title of the current figure."""
    _require_current_figure().title = text


def get_title() -> str:
    """Get the title of the current figure."""
    return _require_current_figure().title

def render(reason: str = "manual", trigger: Optional[ParamEvent] = None) -> None:
    """Render the current figure.

    Parameters
    ----------
    reason : str, optional
        Render reason string for logging/debugging.
    trigger : ParamEvent or None, optional
        Optional event payload forwarded to :meth:`SmartFigure.render`.
    """
    _require_current_figure().render(reason=reason, trigger=trigger)


def get_info_output(id: Optional[Hashable] = None, **kwargs: Any) -> widgets.Output:
    """Return or create an output widget in the current figure's info panel."""
    return _require_current_figure().get_info_output(id=id, **kwargs)


def add_info_component(
    id: Hashable,
    component_factory: Callable,
    hook_id: Optional[Hashable] = None,
    **kwargs: Any,
) -> Any:
    """Register an info component on the current figure and return it."""
    return _require_current_figure().add_info_component(
        id,
        component_factory,
        hook_id=hook_id,
        **kwargs,
    )


def set_x_range(value: RangeLike) -> None:
    """Set x-axis range on the current figure."""
    _require_current_figure().x_range = value


def get_x_range() -> Tuple[float, float]:
    """Get x-axis range from the current figure."""
    return _require_current_figure().x_range


def set_y_range(value: RangeLike) -> None:
    """Set y-axis range on the current figure."""
    _require_current_figure().y_range = value


def get_y_range() -> Tuple[float, float]:
    """Get y-axis range from the current figure."""
    return _require_current_figure().y_range


def set_sampling_points(value: Union[int, str, _FigureDefaultSentinel, None]) -> None:
    """Set default sampling points on the current figure."""
    _require_current_figure().sampling_points = value


def get_sampling_points() -> Optional[int]:
    """Get default sampling points from the current figure."""
    return _require_current_figure().sampling_points


def plot_style_options() -> Dict[str, str]:
    """Return discoverable SmartFigure plot-style options.

    Returns
    -------
    dict[str, str]
        Mapping of style keyword names to descriptions.

    Notes
    -----
    Current supported shortcut keys are: ``color``, ``thickness``, ``dash``,
    ``opacity``, ``line``, and ``trace``.
    """
    return SmartFigure.plot_style_options()



def parameter(
    symbols: Union[Symbol, Sequence[Symbol]],
    *,
    control: Optional[str] = None,
    **kwargs: Any,
) -> Union[ParamRef, Dict[Symbol, ParamRef]]:
    """Ensure parameter(s) exist on the current figure and return their refs.

    Parameters
    ----------
    symbols : sympy.Symbol or sequence[sympy.Symbol]
        Parameter symbol(s) to create or reuse.
    control : str or None, optional
        Optional control identifier passed to the underlying manager.
    **kwargs : Any
        Control configuration (min, max, value, step).

    Returns
    -------
    ParamRef or dict[Symbol, ParamRef]
        Parameter reference(s) for the requested symbol(s).

    Examples
    --------
    >>> import sympy as sp  # doctest: +SKIP
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> fig = SmartFigure()  # doctest: +SKIP
    >>> with fig:  # doctest: +SKIP
    ...     parameter(a, min=-1, max=1)  # doctest: +SKIP

    Notes
    -----
    This helper requires an active figure context (see :meth:`SmartFigure.__enter__`).

    See Also
    --------
    SmartFigure.parameter : Instance method for parameter creation.
    """
    fig = _require_current_figure()
    return fig.parameters.parameter(symbols, control=control, **kwargs)


def plot(
    var: Symbol,
    func: Expr,
    parameters: Optional[Sequence[Symbol]] = None,
    id: Optional[str] = None,
    x_domain: Optional[RangeLike] = None,
    sampling_points: Optional[Union[int, str]] = None,
    color: Optional[str] = None,
    thickness: Optional[Union[int, float]] = None,
    dash: Optional[str] = None,
    opacity: Optional[Union[int, float]] = None,
    line: Optional[Mapping[str, Any]] = None,
    trace: Optional[Mapping[str, Any]] = None,
) -> SmartPlot:
    """
    Plot a SymPy expression on the current figure, or create a new figure per call.

    Parameters
    ----------
    var : sympy.Symbol
        Independent variable for the expression.
    func : sympy.Expr
        SymPy expression to plot.
    parameters : sequence[sympy.Symbol], optional
        Parameter symbols used in the expression. If ``None``, they are inferred.
    id : str, optional
        Plot identifier for update or creation.
    x_domain : RangeLike or None, optional
        Explicit x-domain override.
    sampling_points : int or str, optional
        Number of samples, or ``"figure_default"`` to inherit from the figure.
    color : str or None, optional
        Line color. Common formats include named colors (e.g., ``"red"``),
        hex values (e.g., ``"#ff0000"``), and ``rgb(...)``/``rgba(...)``.
    thickness : int or float, optional
        Line width in pixels. ``1`` is thin; larger values produce thicker lines.
    dash : str or None, optional
        Line pattern. Supported values: ``"solid"``, ``"dot"``, ``"dash"``,
        ``"longdash"``, ``"dashdot"``, ``"longdashdot"``.
    line : mapping or None, optional
        Extra per-line style fields as a mapping (advanced usage).
    opacity : int or float, optional
        Overall curve opacity between ``0.0`` (fully transparent) and
        ``1.0`` (fully opaque).
    trace : mapping or None, optional
        Extra full-trace style fields as a mapping (advanced usage).

    Returns
    -------
    SmartPlot
        The created or updated plot instance.

    Examples
    --------
    >>> x, a = sp.symbols("x a")  # doctest: +SKIP
    >>> plot(x, a * sp.sin(x), parameters=[a], id="a_sin")  # doctest: +SKIP

    Notes
    -----
    If no current figure is active, this function creates and displays a new
    :class:`SmartFigure`.

    All supported style options for this helper are discoverable via
    :func:`plot_style_options`.

    See Also
    --------
    SmartFigure.plot : Instance method with the same signature.
    plot_style_options : List supported style kwargs and meanings
        (`color`, `thickness`, `dash`, `opacity`, `line`, `trace`).
    """
    fig = _current_figure()
    if fig is None:
        fig = SmartFigure()
        display(fig)
    return fig.plot(
        var,
        func,
        parameters=parameters,
        id=id,
        x_domain=x_domain,
        sampling_points=sampling_points,
        color=color,
        thickness=thickness,
        dash=dash,
        line=line,
        opacity=opacity,
        trace=trace,
    )
