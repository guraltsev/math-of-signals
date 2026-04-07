"""Shared UI system for notebook theming and layout.

This module defines the *single* shared presentation layer used by the toolkit's
widget-based surfaces. It intentionally separates four concerns:

* design tokens such as spacing, radii, control heights, typography, and colors;
* layout primitives such as panel surfaces, dialog shells, headers, action bars,
  section containers, and tab bars;
* shared control helpers for buttons and labelled form rows;
* CSS resource loading so generic chrome lives in readable stylesheet files.

Feature modules should compose these helpers instead of redefining generic
button or dialog styling locally. That keeps the theming code maintainable and
makes layout guardrails enforceable.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal

from ._widget_stubs import widgets

ButtonVariant = Literal["primary", "secondary", "tab"]
IconButtonRole = Literal[
    "animate",
    "reset",
    "settings",
    "close",
    "plus",
    "edit",
]
PanelVariant = Literal["card", "minimal", "toolbar"]


@dataclass(frozen=True)
class SectionPanel:
    """Shared figure/sidebar section panel bundle.
    
    Full API
    --------
    ``SectionPanel(panel: widgets.VBox, header: widgets.HBox, title: widgets.HTML, toolbar: widgets.HBox, body: widgets.VBox)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    panel : widgets.VBox
        Value for ``panel`` in this API. Required.
    
    header : widgets.HBox
        Value for ``header`` in this API. Required.
    
    title : widgets.HTML
        Human-readable title text shown in the UI or stored in snapshots. Required.
    
    toolbar : widgets.HBox
        Value for ``toolbar`` in this API. Required.
    
    body : widgets.VBox
        Value for ``body`` in this API. Required.
    
    Returns
    -------
    SectionPanel
        New ``SectionPanel`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``SectionPanel`` lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.ui_system import SectionPanel
        obj = SectionPanel(...)
    
    Discovery-oriented use::
    
        help(SectionPanel)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(SectionPanel)`` and ``dir(SectionPanel)`` to inspect adjacent members.
    """

    panel: widgets.VBox
    header: widgets.HBox
    title: widgets.HTML
    toolbar: widgets.HBox
    body: widgets.VBox


_CSS_DIR = Path(__file__).resolve().parent / "css"
_BASE_THEME_RESOURCES: tuple[str, ...] = (
    "tokens.css",
    "controls.css",
    "surfaces.css",
)


@lru_cache(maxsize=None)
def _read_css_resource(resource_name: str) -> str:
    path = _CSS_DIR / str(resource_name)
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def shared_theme_css() -> str:
    """Return the shared base theme CSS loaded from resource files.
    
    Full API
    --------
    ``shared_theme_css() -> str``
    
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
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import shared_theme_css
        result = shared_theme_css(...)
    
    Discovery-oriented use::
    
        help(shared_theme_css)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(shared_theme_css)`` and inspect sibling APIs in the same module.
    """

    return "\n\n".join(_read_css_resource(name) for name in _BASE_THEME_RESOURCES)


def load_ui_css(*resource_names: str) -> str:
    """Load one or more stylesheet resources from ``src/gu_toolkit/css``.
    
    Full API
    --------
    ``load_ui_css(*resource_names: str) -> str``
    
    Parameters
    ----------
    *resource_names : str, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``*resource_names``: Additional positional arguments are passed through when this API supports variadic input.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import load_ui_css
        result = load_ui_css(...)
    
    Discovery-oriented use::
    
        help(load_ui_css)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(load_ui_css)`` and inspect sibling APIs in the same module.
    """

    return "\n\n".join(
        _read_css_resource(name)
        for name in resource_names
        if str(name or "").strip()
    )


def style_widget_value(*css_fragments: str, include_base: bool = True) -> str:
    """Return the HTML payload used by hidden stylesheet widgets.
    
    Full API
    --------
    ``style_widget_value(*css_fragments: str, include_base: bool=True) -> str``
    
    Parameters
    ----------
    *css_fragments : str, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    include_base : bool, optional
        Value for ``include_base`` in this API. Defaults to ``True``.
    
    Returns
    -------
    str
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``*css_fragments``: Additional positional arguments are passed through when this API supports variadic input.
    - ``include_base=True``: Value for ``include_base`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import style_widget_value
        result = style_widget_value(...)
    
    Discovery-oriented use::
    
        help(style_widget_value)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(style_widget_value)`` and inspect sibling APIs in the same module.
    """

    css_parts: list[str] = []
    if include_base:
        css_parts.append(shared_theme_css())
    css_parts.extend(str(fragment or "") for fragment in css_fragments if str(fragment or ""))
    css = "\n\n".join(part for part in css_parts if part)
    if not css:
        return ""
    return f"<style>\n{css}\n</style>"


def _set_if_missing(layout: Any, attr_name: str, value: str) -> None:
    if layout is None:
        return
    current = getattr(layout, attr_name, None)
    if current in (None, ""):
        setattr(layout, attr_name, value)


def _layout_trait_names() -> frozenset[str]:
    try:
        probe = widgets.Layout()
    except Exception:
        return frozenset()
    keys = getattr(probe, "keys", ())
    if callable(keys):
        keys = keys()
    return frozenset(str(key) for key in keys)


_LAYOUT_TRAIT_NAMES = _layout_trait_names()


def build_layout(**kwargs: str) -> widgets.Layout:
    """Return a layout while preserving extra attrs unsupported by some builds.
    
    Full API
    --------
    ``build_layout(**kwargs: str) -> widgets.Layout``
    
    Parameters
    ----------
    **kwargs : str, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    widgets.Layout
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_layout
        result = build_layout(...)
    
    Discovery-oriented use::
    
        help(build_layout)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_layout)`` and inspect sibling APIs in the same module.
    """

    extras: dict[str, str] = {}
    overflow_x = kwargs.pop("overflow_x", None)
    overflow_y = kwargs.pop("overflow_y", None)
    overflow = kwargs.get("overflow")
    if overflow in (None, "") and (overflow_x is not None or overflow_y is not None):
        ox = "visible" if overflow_x is None else str(overflow_x)
        oy = ox if overflow_y is None else str(overflow_y)
        kwargs["overflow"] = f"{ox} {oy}"

    ctor_kwargs: dict[str, str] = {}
    for key, value in kwargs.items():
        if key in _LAYOUT_TRAIT_NAMES:
            ctor_kwargs[key] = value
        else:
            extras[key] = value

    layout = widgets.Layout(**ctor_kwargs)
    if overflow_x is not None:
        extras["overflow_x"] = str(overflow_x)
    if overflow_y is not None:
        extras["overflow_y"] = str(overflow_y)
    for key, value in extras.items():
        setattr(layout, key, value)
    return layout


def set_widget_class_state(widget: Any, class_name: str, enabled: bool) -> None:
    """Add or remove one CSS class when supported by ``widget``.
    
    Full API
    --------
    ``set_widget_class_state(widget: Any, class_name: str, enabled: bool) -> None``
    
    Parameters
    ----------
    widget : Any
        Widget/control instance associated with this API. Required.
    
    class_name : str
        Value for ``class_name`` in this API. Required.
    
    enabled : bool
        Boolean flag that turns a feature on or off. Required.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import set_widget_class_state
        set_widget_class_state(...)
    
    Discovery-oriented use::
    
        help(set_widget_class_state)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(set_widget_class_state)`` and inspect sibling APIs in the same module.
    """

    add_class = getattr(widget, "add_class", None)
    remove_class = getattr(widget, "remove_class", None)
    if enabled:
        if callable(add_class):
            add_class(class_name)
        return
    if callable(remove_class):
        remove_class(class_name)


def add_widget_classes(widget: Any, *class_names: str) -> Any:
    """Apply every non-empty CSS class to ``widget`` and return it.
    
    Full API
    --------
    ``add_widget_classes(widget: Any, *class_names: str) -> Any``
    
    Parameters
    ----------
    widget : Any
        Widget/control instance associated with this API. Required.
    
    *class_names : str, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``*class_names``: Additional positional arguments are passed through when this API supports variadic input.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import add_widget_classes
        result = add_widget_classes(...)
    
    Discovery-oriented use::
    
        help(add_widget_classes)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(add_widget_classes)`` and inspect sibling APIs in the same module.
    """

    add_class = getattr(widget, "add_class", None)
    if callable(add_class):
        for class_name in class_names:
            if class_name:
                add_class(class_name)
    return widget


def ensure_fill_layout(widget: Any) -> Any:
    """Give a widget the defensive width defaults used by shared forms.
    
    Full API
    --------
    ``ensure_fill_layout(widget: Any) -> Any``
    
    Parameters
    ----------
    widget : Any
        Widget/control instance associated with this API. Required.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import ensure_fill_layout
        result = ensure_fill_layout(...)
    
    Discovery-oriented use::
    
        help(ensure_fill_layout)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(ensure_fill_layout)`` and inspect sibling APIs in the same module.
    """

    layout = getattr(widget, "layout", None)
    if layout is None:
        return widget
    _set_if_missing(layout, "width", "100%")
    _set_if_missing(layout, "min_width", "0")
    _set_if_missing(layout, "max_width", "100%")
    return widget


def full_width_layout(**overrides: str) -> widgets.Layout:
    """Return a layout that stretches safely without causing x-overflow.
    
    Full API
    --------
    ``full_width_layout(**overrides: str) -> widgets.Layout``
    
    Parameters
    ----------
    **overrides : str, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    widgets.Layout
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**overrides``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import full_width_layout
        result = full_width_layout(...)
    
    Discovery-oriented use::
    
        help(full_width_layout)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(full_width_layout)`` and inspect sibling APIs in the same module.
    """

    base: dict[str, str] = {"width": "100%", "min_width": "0", "max_width": "100%"}
    base.update(overrides)
    return build_layout(**base)


def full_width_box_layout(**overrides: str) -> widgets.Layout:
    """Return shared box defaults that opt out of ipywidgets' auto scrollbars.
    
    Full API
    --------
    ``full_width_box_layout(**overrides: str) -> widgets.Layout``
    
    Parameters
    ----------
    **overrides : str, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    widgets.Layout
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**overrides``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import full_width_box_layout
        result = full_width_box_layout(...)
    
    Discovery-oriented use::
    
        help(full_width_box_layout)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(full_width_box_layout)`` and inspect sibling APIs in the same module.
    """

    base: dict[str, str] = {
        "width": "100%",
        "min_width": "0",
        "max_width": "100%",
        "overflow_x": "hidden",
        "overflow_y": "visible",
    }
    base.update(overrides)
    return build_layout(**base)


def hosted_modal_dimensions(
    *,
    preferred_width_px: int,
    minimum_width_px: int,
    gutter_px: int = 24,
) -> tuple[str, str, str]:
    """Return container-relative width strings for hosted modal panels.
    
    Full API
    --------
    ``hosted_modal_dimensions(*, preferred_width_px: int, minimum_width_px: int, gutter_px: int=24) -> tuple[str, str, str]``
    
    Parameters
    ----------
    preferred_width_px : int
        Value for ``preferred_width_px`` in this API. Required.
    
    minimum_width_px : int
        Value for ``minimum_width_px`` in this API. Required.
    
    gutter_px : int, optional
        Value for ``gutter_px`` in this API. Defaults to ``24``.
    
    Returns
    -------
    tuple[str, str, str]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``gutter_px=24``: Value for ``gutter_px`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import hosted_modal_dimensions
        result = hosted_modal_dimensions(...)
    
    Discovery-oriented use::
    
        help(hosted_modal_dimensions)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(hosted_modal_dimensions)`` and inspect sibling APIs in the same module.
    """

    inner_width = f"calc(100% - {int(gutter_px)}px)"
    return (
        f"min({int(preferred_width_px)}px, {inner_width})",
        f"min({int(minimum_width_px)}px, {inner_width})",
        inner_width,
    )


def shared_style_widget(*css_fragments: str, include_base: bool = True) -> widgets.HTML:
    """Return a hidden widget containing shared UI CSS and optional overrides.
    
    Full API
    --------
    ``shared_style_widget(*css_fragments: str, include_base: bool=True) -> widgets.HTML``
    
    Parameters
    ----------
    *css_fragments : str, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    include_base : bool, optional
        Value for ``include_base`` in this API. Defaults to ``True``.
    
    Returns
    -------
    widgets.HTML
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``*css_fragments``: Additional positional arguments are passed through when this API supports variadic input.
    - ``include_base=True``: Value for ``include_base`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import shared_style_widget
        result = shared_style_widget(...)
    
    Discovery-oriented use::
    
        help(shared_style_widget)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(shared_style_widget)`` and inspect sibling APIs in the same module.
    """

    return widgets.HTML(
        value=style_widget_value(*css_fragments, include_base=include_base),
        layout=build_layout(width="0px", height="0px", margin="0px"),
    )


def vbox(
    children: Iterable[widgets.Widget],
    *,
    gap: str = "8px",
    extra_classes: Iterable[str] = (),
    **layout_overrides: str,
) -> widgets.VBox:
    """Return a full-width vertical container with defensive layout defaults.
    
    Full API
    --------
    ``vbox(children: Iterable[widgets.Widget], *, gap: str='8px', extra_classes: Iterable[str]=(), **layout_overrides: str) -> widgets.VBox``
    
    Parameters
    ----------
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    gap : str, optional
        Value for ``gap`` in this API. Defaults to ``'8px'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    **layout_overrides : str, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    widgets.VBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``gap='8px'``: Value for ``gap`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    - ``**layout_overrides``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import vbox
        result = vbox(...)
    
    Discovery-oriented use::
    
        help(vbox)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(vbox)`` and inspect sibling APIs in the same module.
    """

    widget = widgets.VBox(
        list(children),
        layout=full_width_box_layout(gap=gap, **layout_overrides),
    )
    add_widget_classes(widget, "gu-modal-section", *tuple(extra_classes))
    return widget


def hbox(
    children: Iterable[widgets.Widget],
    *,
    gap: str = "8px",
    extra_classes: Iterable[str] = (),
    **layout_overrides: str,
) -> widgets.HBox:
    """Return a full-width horizontal container with defensive layout defaults.
    
    Full API
    --------
    ``hbox(children: Iterable[widgets.Widget], *, gap: str='8px', extra_classes: Iterable[str]=(), **layout_overrides: str) -> widgets.HBox``
    
    Parameters
    ----------
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    gap : str, optional
        Value for ``gap`` in this API. Defaults to ``'8px'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    **layout_overrides : str, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    widgets.HBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``gap='8px'``: Value for ``gap`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    - ``**layout_overrides``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import hbox
        result = hbox(...)
    
    Discovery-oriented use::
    
        help(hbox)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(hbox)`` and inspect sibling APIs in the same module.
    """

    overrides = {"gap": gap, "align_items": "center"}
    overrides.update(layout_overrides)
    widget = widgets.HBox(list(children), layout=full_width_box_layout(**overrides))
    add_widget_classes(widget, "gu-modal-row", *tuple(extra_classes))
    return widget


def responsive_row(
    children: Iterable[widgets.Widget],
    *,
    gap: str = "8px",
    extra_classes: Iterable[str] = (),
    **layout_overrides: str,
) -> widgets.HBox:
    """Return a wrapping form row for compact controls in responsive dialogs.
    
    Full API
    --------
    ``responsive_row(children: Iterable[widgets.Widget], *, gap: str='8px', extra_classes: Iterable[str]=(), **layout_overrides: str) -> widgets.HBox``
    
    Parameters
    ----------
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    gap : str, optional
        Value for ``gap`` in this API. Defaults to ``'8px'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    **layout_overrides : str, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    widgets.HBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``gap='8px'``: Value for ``gap`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    - ``**layout_overrides``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import responsive_row
        result = responsive_row(...)
    
    Discovery-oriented use::
    
        help(responsive_row)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(responsive_row)`` and inspect sibling APIs in the same module.
    """

    overrides = {"gap": gap, "align_items": "flex-start", "flex_flow": "row wrap"}
    overrides.update(layout_overrides)
    widget = widgets.HBox(list(children), layout=full_width_box_layout(**overrides))
    add_widget_classes(widget, "gu-modal-row", "gu-wrap-row", *tuple(extra_classes))
    return widget


def configure_control(
    widget: widgets.Widget,
    *,
    family: str = "text",
    extra_classes: Iterable[str] = (),
) -> widgets.Widget:
    """Apply shared control classes to a widget.
    
    Full API
    --------
    ``configure_control(widget: widgets.Widget, *, family: str='text', extra_classes: Iterable[str]=()) -> widgets.Widget``
    
    Parameters
    ----------
    widget : widgets.Widget
        Widget/control instance associated with this API. Required.
    
    family : str, optional
        Value for ``family`` in this API. Defaults to ``'text'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.Widget
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``family='text'``: Value for ``family`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import configure_control
        result = configure_control(...)
    
    Discovery-oriented use::
    
        help(configure_control)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(configure_control)`` and inspect sibling APIs in the same module.
    """

    ensure_fill_layout(widget)

    single_line_families = {"text", "numeric", "dropdown", "color"}
    shell_families = single_line_families | {"checkbox", "boolean"}
    layout = getattr(widget, "layout", None)
    if layout is not None and family in shell_families:
        _set_if_missing(layout, "overflow_x", "hidden")
    if layout is not None and family in single_line_families:
        _set_if_missing(layout, "overflow_y", "hidden")

    family_classes: dict[str, tuple[str, ...]] = {
        "text": ("gu-control-text",),
        "numeric": ("gu-control-numeric",),
        "dropdown": ("gu-control-dropdown",),
        "multiselect": ("gu-control-multiselect", "gu-control-targets"),
        "targets": ("gu-control-multiselect", "gu-control-targets"),
        "checkbox": ("gu-control-checkbox",),
        "boolean": ("gu-control-checkbox",),
        "readonly": ("gu-readonly-value",),
        "color": ("gu-control-color",),
    }
    add_widget_classes(
        widget,
        "gu-control",
        f"gu-control-{family}",
        *family_classes.get(family, ()),
        *tuple(extra_classes),
    )
    return widget


def labelled_field(
    title: str | widgets.Widget,
    field: widgets.Widget,
    *,
    flex: str | None = None,
    width: str | None = None,
    max_width: str | None = "100%",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Wrap one field in a labelled section that avoids intrinsic-width overflow.
    
    Full API
    --------
    ``labelled_field(title: str | widgets.Widget, field: widgets.Widget, *, flex: str | None=None, width: str | None=None, max_width: str | None='100%', extra_classes: Iterable[str]=()) -> widgets.VBox``
    
    Parameters
    ----------
    title : str | widgets.Widget
        Human-readable title text shown in the UI or stored in snapshots. Required.
    
    field : widgets.Widget
        Value for ``field`` in this API. Required.
    
    flex : str | None, optional
        Value for ``flex`` in this API. Defaults to ``None``.
    
    width : str | None, optional
        Value for ``width`` in this API. Defaults to ``None``.
    
    max_width : str | None, optional
        Value for ``max_width`` in this API. Defaults to ``'100%'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.VBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``flex=None``: Value for ``flex`` in this API.
    - ``width=None``: Value for ``width`` in this API.
    - ``max_width='100%'``: Value for ``max_width`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import labelled_field
        result = labelled_field(...)
    
    Discovery-oriented use::
    
        help(labelled_field)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(labelled_field)`` and inspect sibling APIs in the same module.
    """

    ensure_fill_layout(field)
    if isinstance(title, str):
        label: widgets.Widget = widgets.HTML(
            html.escape(title),
            layout=build_layout(margin="0px", min_width="0"),
        )
        add_widget_classes(label, "gu-form-field-label")
    else:
        label = title
        ensure_fill_layout(label)
    wrapper = vbox([label, field], gap="4px", extra_classes=("gu-form-field", *tuple(extra_classes)))
    if flex is not None:
        wrapper.layout.flex = flex
    if width is not None:
        wrapper.layout.width = width
    if max_width is not None:
        wrapper.layout.max_width = max_width
    return wrapper


def build_boolean_field(
    field: widgets.Widget,
    *,
    flex: str | None = None,
    width: str | None = None,
    max_width: str | None = "100%",
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Wrap an inline boolean control without reusing text-field composition.
    
    Full API
    --------
    ``build_boolean_field(field: widgets.Widget, *, flex: str | None=None, width: str | None=None, max_width: str | None='100%', extra_classes: Iterable[str]=()) -> widgets.HBox``
    
    Parameters
    ----------
    field : widgets.Widget
        Value for ``field`` in this API. Required.
    
    flex : str | None, optional
        Value for ``flex`` in this API. Defaults to ``None``.
    
    width : str | None, optional
        Value for ``width`` in this API. Defaults to ``None``.
    
    max_width : str | None, optional
        Value for ``max_width`` in this API. Defaults to ``'100%'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.HBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``flex=None``: Value for ``flex`` in this API.
    - ``width=None``: Value for ``width`` in this API.
    - ``max_width='100%'``: Value for ``max_width`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_boolean_field
        result = build_boolean_field(...)
    
    Discovery-oriented use::
    
        help(build_boolean_field)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_boolean_field)`` and inspect sibling APIs in the same module.
    """

    if getattr(field, "layout", None) is None:
        field.layout = widgets.Layout()
    _set_if_missing(field.layout, "width", "auto")
    _set_if_missing(field.layout, "min_width", "0")
    wrapper = hbox(
        [field],
        gap="0px",
        justify_content="flex-start",
        align_items="center",
        extra_classes=("gu-boolean-field", *tuple(extra_classes)),
    )
    if flex is not None:
        wrapper.layout.flex = flex
    if width is not None:
        wrapper.layout.width = width
    if max_width is not None:
        wrapper.layout.max_width = max_width
    return wrapper


def build_inline_alert(
    *,
    display: str = "none",
    extra_classes: Iterable[str] = (),
) -> widgets.HTML:
    """Create a shared inline alert widget for routine validation feedback.
    
    Full API
    --------
    ``build_inline_alert(*, display: str='none', extra_classes: Iterable[str]=()) -> widgets.HTML``
    
    Parameters
    ----------
    display : str, optional
        Compatibility display flag or display object, depending on the API. Defaults to ``'none'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.HTML
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``display='none'``: Compatibility display flag or display object, depending on the API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_inline_alert
        result = build_inline_alert(...)
    
    Discovery-oriented use::
    
        help(build_inline_alert)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_inline_alert)`` and inspect sibling APIs in the same module.
    """

    alert = widgets.HTML(value="", layout=full_width_layout(display=display))
    add_widget_classes(alert, "gu-inline-alert", *tuple(extra_classes))
    return alert


def build_action_bar(
    children: Iterable[widgets.Widget],
    *,
    justify_content: str = "flex-end",
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Create a footer action bar that wraps cleanly on narrow widths.
    
    Full API
    --------
    ``build_action_bar(children: Iterable[widgets.Widget], *, justify_content: str='flex-end', extra_classes: Iterable[str]=()) -> widgets.HBox``
    
    Parameters
    ----------
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    justify_content : str, optional
        Value for ``justify_content`` in this API. Defaults to ``'flex-end'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.HBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``justify_content='flex-end'``: Value for ``justify_content`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_action_bar
        result = build_action_bar(...)
    
    Discovery-oriented use::
    
        help(build_action_bar)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_action_bar)`` and inspect sibling APIs in the same module.
    """

    return hbox(
        list(children),
        justify_content=justify_content,
        align_items="center",
        gap="8px",
        flex_flow="row wrap",
        extra_classes=("gu-action-bar", *tuple(extra_classes)),
    )


def build_tab_bar(
    children: Iterable[widgets.Widget],
    *,
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Create a non-wrapping shared tab bar.
    
    Full API
    --------
    ``build_tab_bar(children: Iterable[widgets.Widget], *, extra_classes: Iterable[str]=()) -> widgets.HBox``
    
    Parameters
    ----------
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.HBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_tab_bar
        result = build_tab_bar(...)
    
    Discovery-oriented use::
    
        help(build_tab_bar)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_tab_bar)`` and inspect sibling APIs in the same module.
    """

    return hbox(
        list(children),
        justify_content="flex-start",
        align_items="stretch",
        gap="4px",
        flex_flow="row nowrap",
        extra_classes=("gu-tab-bar", *tuple(extra_classes)),
    )


def build_title_chip(text: str = "", *, display: str = "none") -> widgets.HTML:
    """Return a compact chip used for edit-mode or subject context.
    
    Full API
    --------
    ``build_title_chip(text: str='', *, display: str='none') -> widgets.HTML``
    
    Parameters
    ----------
    text : str, optional
        Human-readable text payload or label content. Defaults to ``''``.
    
    display : str, optional
        Compatibility display flag or display object, depending on the API. Defaults to ``'none'``.
    
    Returns
    -------
    widgets.HTML
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``text=''``: Human-readable text payload or label content.
    - ``display='none'``: Compatibility display flag or display object, depending on the API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_title_chip
        result = build_title_chip(...)
    
    Discovery-oriented use::
    
        help(build_title_chip)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_title_chip)`` and inspect sibling APIs in the same module.
    """

    chip = widgets.HTML(html.escape(text), layout=build_layout(display=display, min_width="0"))
    add_widget_classes(chip, "gu-title-chip")
    return chip


def build_readonly_value(value: str = "", *, display: str = "block") -> widgets.HTML:
    """Return a readonly value surface styled like the shared control family.
    
    Full API
    --------
    ``build_readonly_value(value: str='', *, display: str='block') -> widgets.HTML``
    
    Parameters
    ----------
    value : str, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``''``.
    
    display : str, optional
        Compatibility display flag or display object, depending on the API. Defaults to ``'block'``.
    
    Returns
    -------
    widgets.HTML
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``value=''``: New or current value for the relevant property, control, or calculation.
    - ``display='block'``: Compatibility display flag or display object, depending on the API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_readonly_value
        result = build_readonly_value(...)
    
    Discovery-oriented use::
    
        help(build_readonly_value)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_readonly_value)`` and inspect sibling APIs in the same module.
    """

    widget = widgets.HTML(html.escape(value), layout=full_width_layout(display=display))
    add_widget_classes(widget, "gu-readonly-value")
    return widget


def build_dialog_header(
    title_widget: widgets.Widget,
    close_button: widgets.Widget,
    *,
    chip_widget: widgets.Widget | None = None,
    subtitle_widget: widgets.Widget | None = None,
    extra_classes: Iterable[str] = (),
) -> widgets.HBox:
    """Create the standard dialog header with optional chip/subtitle rows.
    
    Full API
    --------
    ``build_dialog_header(title_widget: widgets.Widget, close_button: widgets.Widget, *, chip_widget: widgets.Widget | None=None, subtitle_widget: widgets.Widget | None=None, extra_classes: Iterable[str]=()) -> widgets.HBox``
    
    Parameters
    ----------
    title_widget : widgets.Widget
        Value for ``title_widget`` in this API. Required.
    
    close_button : widgets.Widget
        Value for ``close_button`` in this API. Required.
    
    chip_widget : widgets.Widget | None, optional
        Value for ``chip_widget`` in this API. Defaults to ``None``.
    
    subtitle_widget : widgets.Widget | None, optional
        Value for ``subtitle_widget`` in this API. Defaults to ``None``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.HBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``chip_widget=None``: Value for ``chip_widget`` in this API.
    - ``subtitle_widget=None``: Value for ``subtitle_widget`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_dialog_header
        result = build_dialog_header(...)
    
    Discovery-oriented use::
    
        help(build_dialog_header)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_dialog_header)`` and inspect sibling APIs in the same module.
    """

    title_row_children = [title_widget]
    if chip_widget is not None:
        title_row_children.append(chip_widget)
    title_row = hbox(
        title_row_children,
        gap="8px",
        align_items="center",
        extra_classes=("gu-modal-title-row",),
    )
    copy_children = [title_row]
    if subtitle_widget is not None:
        copy_children.append(subtitle_widget)
    copy = vbox(copy_children, gap="6px", extra_classes=("gu-modal-header-copy",))
    return hbox(
        [copy, close_button],
        justify_content="space-between",
        align_items="flex-start",
        gap="12px",
        extra_classes=("gu-modal-header", *tuple(extra_classes)),
    )


def build_form_section(
    title: str,
    children: Iterable[widgets.Widget],
    *,
    gap: str = "10px",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Create a titled form section used within dialogs and side panels.
    
    Full API
    --------
    ``build_form_section(title: str, children: Iterable[widgets.Widget], *, gap: str='10px', extra_classes: Iterable[str]=()) -> widgets.VBox``
    
    Parameters
    ----------
    title : str
        Human-readable title text shown in the UI or stored in snapshots. Required.
    
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    gap : str, optional
        Value for ``gap`` in this API. Defaults to ``'10px'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.VBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``gap='10px'``: Value for ``gap`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_form_section
        result = build_form_section(...)
    
    Discovery-oriented use::
    
        help(build_form_section)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_form_section)`` and inspect sibling APIs in the same module.
    """

    header = widgets.HTML(html.escape(title), layout=build_layout(margin="0px", min_width="0"))
    add_widget_classes(header, "gu-form-section-header")
    return vbox([header, *list(children)], gap=gap, extra_classes=("gu-form-section", *tuple(extra_classes)))


def build_section_panel(
    title_text: str,
    *,
    body: widgets.VBox | None = None,
    variant: PanelVariant = "card",
    display: str = "none",
    body_display: str = "flex",
    extra_classes: Iterable[str] = (),
    body_extra_classes: Iterable[str] = (),
) -> SectionPanel:
    """Create a shared panel surface with header, toolbar host, and body.
    
    Full API
    --------
    ``build_section_panel(title_text: str, *, body: widgets.VBox | None=None, variant: PanelVariant='card', display: str='none', body_display: str='flex', extra_classes: Iterable[str]=(), body_extra_classes: Iterable[str]=()) -> SectionPanel``
    
    Parameters
    ----------
    title_text : str
        Value for ``title_text`` in this API. Required.
    
    body : widgets.VBox | None, optional
        Value for ``body`` in this API. Defaults to ``None``.
    
    variant : PanelVariant, optional
        Value for ``variant`` in this API. Defaults to ``'card'``.
    
    display : str, optional
        Compatibility display flag or display object, depending on the API. Defaults to ``'none'``.
    
    body_display : str, optional
        Value for ``body_display`` in this API. Defaults to ``'flex'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    body_extra_classes : Iterable[str], optional
        Value for ``body_extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    SectionPanel
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``body=None``: Value for ``body`` in this API.
    - ``variant='card'``: Value for ``variant`` in this API.
    - ``display='none'``: Compatibility display flag or display object, depending on the API.
    - ``body_display='flex'``: Value for ``body_display`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    - ``body_extra_classes=()``: Value for ``body_extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_section_panel
        result = build_section_panel(...)
    
    Discovery-oriented use::
    
        help(build_section_panel)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_section_panel)`` and inspect sibling APIs in the same module.
    """

    title_display = "none" if variant == "toolbar" else "block"
    title = widgets.HTML(
        html.escape(title_text),
        layout=build_layout(margin="0px", min_width="0", display=title_display),
    )
    add_widget_classes(title, "gu-panel-title", f"gu-panel-title-variant-{variant}")

    toolbar = widgets.HBox(
        [],
        layout=build_layout(
            width="auto",
            min_width="0",
            align_items="center",
            justify_content="flex-end",
            gap="4px",
            overflow_x="hidden",
            overflow_y="visible",
        ),
    )
    add_widget_classes(toolbar, "gu-panel-toolbar")

    header = widgets.HBox(
        [title, toolbar],
        layout=build_layout(
            width="100%",
            min_width="0",
            align_items="center",
            justify_content="space-between",
            gap="8px",
            overflow_x="hidden",
            overflow_y="visible",
        ),
    )
    add_widget_classes(header, "gu-panel-header", f"gu-panel-header-variant-{variant}")

    if body is None:
        body = widgets.VBox(
            [],
            layout=build_layout(
                width="100%",
                min_width="0",
                max_width="100%",
                display=body_display,
                gap="8px",
                overflow_x="hidden",
                overflow_y="visible",
            ),
        )
    else:
        ensure_fill_layout(body)
        body.layout.display = body_display
        if not getattr(body.layout, "overflow_x", None):
            body.layout.overflow_x = "hidden"
        if not getattr(body.layout, "overflow_y", None):
            body.layout.overflow_y = "visible"
    add_widget_classes(body, "gu-panel-body", f"gu-panel-body-variant-{variant}", *tuple(body_extra_classes))

    panel = widgets.VBox(
        [header, body],
        layout=build_layout(
            width="100%",
            min_width="0",
            max_width="100%",
            display=display,
            overflow_x="hidden",
            overflow_y="visible",
        ),
    )
    add_widget_classes(panel, "gu-panel", f"gu-panel-variant-{variant}", *tuple(extra_classes))
    return SectionPanel(panel=panel, header=header, title=title, toolbar=toolbar, body=body)


def configure_icon_button(
    button: widgets.Button,
    *,
    role: IconButtonRole | None = None,
    size_px: int = 24,
    extra_classes: Iterable[str] = (),
) -> widgets.Button:
    """Apply shared icon-button chrome and the requested glyph role.
    
    Full API
    --------
    ``configure_icon_button(button: widgets.Button, *, role: IconButtonRole | None=None, size_px: int=24, extra_classes: Iterable[str]=()) -> widgets.Button``
    
    Parameters
    ----------
    button : widgets.Button
        Value for ``button`` in this API. Required.
    
    role : IconButtonRole | None, optional
        Value for ``role`` in this API. Defaults to ``None``.
    
    size_px : int, optional
        Value for ``size_px`` in this API. Defaults to ``24``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.Button
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``role=None``: Value for ``role`` in this API.
    - ``size_px=24``: Value for ``size_px`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import configure_icon_button
        result = configure_icon_button(...)
    
    Discovery-oriented use::
    
        help(configure_icon_button)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(configure_icon_button)`` and inspect sibling APIs in the same module.
    """

    width = f"{int(size_px)}px"
    if getattr(button, "layout", None) is None:
        button.layout = widgets.Layout()
    button.layout.width = width
    button.layout.min_width = width
    button.layout.height = width
    button.layout.margin = getattr(button.layout, "margin", None) or "0"
    button.layout.padding = "0px"
    add_widget_classes(
        button,
        "gu-icon-button",
        "smart-slider-icon-button",
        "gu-inline-icon-button",
        *tuple(extra_classes),
    )
    role_classes = {
        "animate": ("smart-slider-animate-button",),
        "reset": ("smart-slider-reset-button",),
        "settings": ("smart-slider-settings-button",),
        "close": ("smart-slider-close-button", "gu-icon-close-button"),
        "plus": ("gu-icon-plus-button",),
        "edit": ("gu-icon-edit-button",),
    }
    for class_name in role_classes.get(role, ()):  # pragma: no branch
        add_widget_classes(button, class_name)
    return button


def configure_action_button(
    button: widgets.Button,
    *,
    variant: ButtonVariant = "secondary",
    min_width_px: int = 88,
    extra_classes: Iterable[str] = (),
) -> widgets.Button:
    """Apply shared text-button chrome used by dialogs and tab selectors.
    
    Full API
    --------
    ``configure_action_button(button: widgets.Button, *, variant: ButtonVariant='secondary', min_width_px: int=88, extra_classes: Iterable[str]=()) -> widgets.Button``
    
    Parameters
    ----------
    button : widgets.Button
        Value for ``button`` in this API. Required.
    
    variant : ButtonVariant, optional
        Value for ``variant`` in this API. Defaults to ``'secondary'``.
    
    min_width_px : int, optional
        Value for ``min_width_px`` in this API. Defaults to ``88``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.Button
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``variant='secondary'``: Value for ``variant`` in this API.
    - ``min_width_px=88``: Value for ``min_width_px`` in this API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import configure_action_button
        result = configure_action_button(...)
    
    Discovery-oriented use::
    
        help(configure_action_button)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(configure_action_button)`` and inspect sibling APIs in the same module.
    """

    if getattr(button, "layout", None) is None:
        button.layout = widgets.Layout()
    if getattr(button.layout, "width", None) in (None, ""):
        button.layout.width = "auto"
    button.layout.min_width = f"{int(min_width_px)}px"
    add_widget_classes(button, "gu-action-button", f"gu-action-button-{variant}", *tuple(extra_classes))
    return button


def set_tab_button_selected(button: widgets.Button, selected: bool) -> None:
    """Toggle the CSS class used by shared tab buttons.
    
    Full API
    --------
    ``set_tab_button_selected(button: widgets.Button, selected: bool) -> None``
    
    Parameters
    ----------
    button : widgets.Button
        Value for ``button`` in this API. Required.
    
    selected : bool
        Value for ``selected`` in this API. Required.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import set_tab_button_selected
        set_tab_button_selected(...)
    
    Discovery-oriented use::
    
        help(set_tab_button_selected)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(set_tab_button_selected)`` and inspect sibling APIs in the same module.
    """

    set_widget_class_state(button, "mod-selected", bool(selected))


def build_modal_panel(
    children: Iterable[widgets.Widget],
    *,
    width: str,
    min_width: str,
    max_width: str = "calc(100vw - 32px)",
    padding: str = "16px",
    gap: str = "12px",
    display: str = "none",
    extra_classes: Iterable[str] = (),
) -> widgets.VBox:
    """Create a shared modal panel with consistent overflow protection.
    
    Full API
    --------
    ``build_modal_panel(children: Iterable[widgets.Widget], *, width: str, min_width: str, max_width: str='calc(100vw - 32px)', padding: str='16px', gap: str='12px', display: str='none', extra_classes: Iterable[str]=()) -> widgets.VBox``
    
    Parameters
    ----------
    children : Iterable[widgets.Widget]
        Child widgets or child elements to attach to a container. Required.
    
    width : str
        Value for ``width`` in this API. Required.
    
    min_width : str
        Value for ``min_width`` in this API. Required.
    
    max_width : str, optional
        Value for ``max_width`` in this API. Defaults to ``'calc(100vw - 32px)'``.
    
    padding : str, optional
        Value for ``padding`` in this API. Defaults to ``'16px'``.
    
    gap : str, optional
        Value for ``gap`` in this API. Defaults to ``'12px'``.
    
    display : str, optional
        Compatibility display flag or display object, depending on the API. Defaults to ``'none'``.
    
    extra_classes : Iterable[str], optional
        Value for ``extra_classes`` in this API. Defaults to ``()``.
    
    Returns
    -------
    widgets.VBox
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``max_width='calc(100vw - 32px)'``: Value for ``max_width`` in this API.
    - ``padding='16px'``: Value for ``padding`` in this API.
    - ``gap='12px'``: Value for ``gap`` in this API.
    - ``display='none'``: Compatibility display flag or display object, depending on the API.
    - ``extra_classes=()``: Value for ``extra_classes`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_modal_panel
        result = build_modal_panel(...)
    
    Discovery-oriented use::
    
        help(build_modal_panel)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_modal_panel)`` and inspect sibling APIs in the same module.
    """

    panel = widgets.VBox(
        list(children),
        layout=build_layout(
            width=width,
            min_width=min_width,
            max_width=max_width,
            display=display,
            padding=padding,
            gap=gap,
            background_color="white",
            opacity="1",
            align_items="stretch",
            overflow_x="hidden",
            overflow_y="auto",
        ),
    )
    add_widget_classes(panel, "smart-slider-settings-panel", "gu-modal-panel", *tuple(extra_classes))
    return panel


def build_modal_overlay(
    panel: widgets.Widget,
    *,
    modal_class: str = "",
    hosted: bool = True,
    z_index: str = "1000",
    background_color: str = "rgba(15, 23, 42, 0.12)",
) -> widgets.Box:
    """Create a shared modal overlay.
    
    Full API
    --------
    ``build_modal_overlay(panel: widgets.Widget, *, modal_class: str='', hosted: bool=True, z_index: str='1000', background_color: str='rgba(15, 23, 42, 0.12)') -> widgets.Box``
    
    Parameters
    ----------
    panel : widgets.Widget
        Value for ``panel`` in this API. Required.
    
    modal_class : str, optional
        Value for ``modal_class`` in this API. Defaults to ``''``.
    
    hosted : bool, optional
        Value for ``hosted`` in this API. Defaults to ``True``.
    
    z_index : str, optional
        Value for ``z_index`` in this API. Defaults to ``'1000'``.
    
    background_color : str, optional
        Value for ``background_color`` in this API. Defaults to ``'rgba(15, 23, 42, 0.12)'``.
    
    Returns
    -------
    widgets.Box
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``modal_class=''``: Value for ``modal_class`` in this API.
    - ``hosted=True``: Value for ``hosted`` in this API.
    - ``z_index='1000'``: Value for ``z_index`` in this API.
    - ``background_color='rgba(15, 23, 42, 0.12)'``: Value for ``background_color`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import build_modal_overlay
        result = build_modal_overlay(...)
    
    Discovery-oriented use::
    
        help(build_modal_overlay)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(build_modal_overlay)`` and inspect sibling APIs in the same module.
    """

    overlay = widgets.Box(
        [panel],
        layout=build_layout(
            display="none",
            position="absolute" if hosted else "fixed",
            top="0",
            left="0",
            width="100%" if hosted else "100vw",
            height="100%" if hosted else "100vh",
            align_items="center",
            justify_content="center",
            background_color=background_color,
            z_index=z_index,
            overflow_x="hidden",
            overflow_y="hidden",
        ),
    )
    add_widget_classes(
        overlay,
        "smart-slider-settings-modal",
        "gu-modal-overlay",
        "smart-slider-settings-modal-hosted" if hosted else "smart-slider-settings-modal-global",
        "gu-modal-overlay-hosted" if hosted else "gu-modal-overlay-global",
        modal_class,
    )
    return overlay


def attach_host_children(host: widgets.Box | None, *children: widgets.Widget) -> None:
    """Append unique widgets to one host container in order.
    
    Full API
    --------
    ``attach_host_children(host: widgets.Box | None, *children: widgets.Widget) -> None``
    
    Parameters
    ----------
    host : widgets.Box | None
        Value for ``host`` in this API. Required.
    
    *children : widgets.Widget, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    - ``*children``: Additional positional arguments are passed through when this API supports variadic input.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.ui_system``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.ui_system import attach_host_children
        attach_host_children(...)
    
    Discovery-oriented use::
    
        help(attach_host_children)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(attach_host_children)`` and inspect sibling APIs in the same module.
    """

    if host is None:
        return
    current = list(host.children)
    changed = False
    add_class = getattr(host, "add_class", None)
    if callable(add_class):
        add_class("smart-slider-modal-host")
        add_class("gu-modal-host")
    for child in children:
        if child not in current:
            current.append(child)
            changed = True
    if changed:
        host.children = tuple(current)


__all__ = [
    "ButtonVariant",
    "IconButtonRole",
    "PanelVariant",
    "SectionPanel",
    "add_widget_classes",
    "attach_host_children",
    "build_action_bar",
    "build_boolean_field",
    "build_dialog_header",
    "build_form_section",
    "build_inline_alert",
    "build_modal_overlay",
    "build_modal_panel",
    "build_readonly_value",
    "build_section_panel",
    "build_tab_bar",
    "build_title_chip",
    "configure_action_button",
    "configure_control",
    "configure_icon_button",
    "ensure_fill_layout",
    "full_width_layout",
    "hbox",
    "hosted_modal_dimensions",
    "labelled_field",
    "load_ui_css",
    "responsive_row",
    "set_tab_button_selected",
    "set_widget_class_state",
    "shared_style_widget",
    "shared_theme_css",
    "style_widget_value",
    "vbox",
]
