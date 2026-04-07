"""Compatibility helpers for widget-centric test and fallback environments.

This module centralizes the toolkit's optional dependency fallback for
``ipywidgets`` and ``anywidget``. In normal notebook environments the real
packages are imported unchanged. In minimal or offline test environments a
small traitlets-based shim is provided instead so the pure-Python parts of the
repository remain importable and testable.

The shim intentionally implements only the subset of the widget API exercised by
this repository's unit tests. It is **not** a drop-in replacement for the full
ipywidgets stack and should be treated as a last-resort compatibility layer.
"""

from __future__ import annotations

from contextlib import contextmanager
import sys
import types
from typing import Any, Callable

import traitlets


class _SimpleNamespace:
    """Tiny mutable object used for ``layout`` and ``style`` traits."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__!r})"


class Layout(_SimpleNamespace):
    """Minimal stand-in for :class:`ipywidgets.Layout`.
    
    Full API
    --------
    ``Layout()``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    Layout
        New ``Layout`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``Layout`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Layout
        obj = Layout(...)
    
    Discovery-oriented use::
    
        help(Layout)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Layout)`` and ``dir(Layout)`` to inspect adjacent members.
    """


class _Style(_SimpleNamespace):
    """Mutable style container used by fallback widgets."""


class Widget(traitlets.HasTraits):
    """Minimal traitlets-backed widget base class.
    
    Full API
    --------
    ``Widget(*args: Any, layout: Layout | None=None, style: Any=None, **kwargs: Any)``
    
    Public members exposed from this class: ``add_class``, ``remove_class``, ``on_msg``, ``send``, ``close``
    
    Parameters
    ----------
    *args : Any, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    layout : Layout | None, optional
        Layout object or layout specification. Defaults to ``None``.
    
    style : Any, optional
        Value for ``style`` in this API. Defaults to ``None``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Widget
        New ``Widget`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
    - ``layout=None``: Layout object or layout specification.
    - ``style=None``: Value for ``style`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Widget`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Widget
        obj = Widget(...)
    
    Discovery-oriented use::
    
        help(Widget)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Widget)`` and ``dir(Widget)`` to inspect adjacent members.
    """

    layout = traitlets.Any()
    style = traitlets.Any()

    def __init__(
        self,
        *args: Any,
        layout: Layout | None = None,
        style: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.layout = layout if layout is not None else Layout()
        self.style = style if style is not None else _Style()
        self._classes: set[str] = set()
        self._dom_classes: tuple[str, ...] = ()
        self._msg_handlers: list[Callable[[Any, Any, Any], None]] = []
        for key, value in kwargs.items():
            setattr(self, key, value)

    def add_class(self, name: str) -> None:
        """Add class.
        
        Full API
        --------
        ``obj.add_class(name: str) -> None``
        
        Parameters
        ----------
        name : str
            Human-readable or canonical name for the target object. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Widget``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Widget(...)
            obj.add_class(...)
        
        Discovery-oriented use::
        
            help(Widget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Widget)`` and ``dir(Widget)`` to inspect adjacent members.
        """

        self._classes.add(str(name))
        self._dom_classes = tuple(sorted(self._classes))

    def remove_class(self, name: str) -> None:
        """Remove class.
        
        Full API
        --------
        ``obj.remove_class(name: str) -> None``
        
        Parameters
        ----------
        name : str
            Human-readable or canonical name for the target object. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Widget``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Widget(...)
            obj.remove_class(...)
        
        Discovery-oriented use::
        
            help(Widget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Widget)`` and ``dir(Widget)`` to inspect adjacent members.
        """

        self._classes.discard(str(name))
        self._dom_classes = tuple(sorted(self._classes))

    def on_msg(self, callback: Callable[[Any, Any, Any], None]) -> None:
        """Work with on msg on ``Widget``.
        
        Full API
        --------
        ``obj.on_msg(callback: Callable[[Any, Any, Any], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[Any, Any, Any], None]
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
        This member belongs to ``Widget``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Widget(...)
            obj.on_msg(...)
        
        Discovery-oriented use::
        
            help(Widget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Widget)`` and ``dir(Widget)`` to inspect adjacent members.
        """

        self._msg_handlers.append(callback)

    def send(self, *args: Any, **kwargs: Any) -> None:
        """No-op message transport used by tests.
        
        Full API
        --------
        ``obj.send(*args: Any, **kwargs: Any) -> None``
        
        Parameters
        ----------
        *args : Any, optional
            Additional positional arguments forwarded by this API. Optional variadic input.
        
        **kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
        - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``Widget``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Widget(...)
            obj.send(...)
        
        Discovery-oriented use::
        
            help(Widget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Widget)`` and ``dir(Widget)`` to inspect adjacent members.
        """

    def _emit_msg(self, content: Any = None, buffers: Any = None) -> None:
        for callback in list(self._msg_handlers):
            callback(self, content, buffers)

    def close(self) -> None:
        """Work with close on ``Widget``.
        
        Full API
        --------
        ``obj.close() -> None``
        
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
        This member belongs to ``Widget``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Widget(...)
            obj.close(...)
        
        Discovery-oriented use::
        
            help(Widget)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Widget)`` and ``dir(Widget)`` to inspect adjacent members.
        """

        return None

    def _repr_mimebundle_(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"text/plain": repr(self)}


class Box(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Box``.
    
    Full API
    --------
    ``Box(children: tuple[Any, Ellipsis] | list[Any]=(), **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    children : tuple[Any, Ellipsis] | list[Any], optional
        Child widgets or child elements to attach to a container. Defaults to ``()``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Box
        New ``Box`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``children=()``: Child widgets or child elements to attach to a container.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Box`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Box
        obj = Box(...)
    
    Discovery-oriented use::
    
        help(Box)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Box)`` and ``dir(Box)`` to inspect adjacent members.
    """

    children = traitlets.Any(())

    def __init__(self, children: tuple[Any, ...] | list[Any] = (), **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.children = tuple(children)


class VBox(Box):
    """Testing stub that mirrors the public shape of ``ipywidgets.VBox``.
    
    Full API
    --------
    ``VBox()``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    VBox
        New ``VBox`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``VBox`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import VBox
        obj = VBox(...)
    
    Discovery-oriented use::
    
        help(VBox)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(VBox)`` and ``dir(VBox)`` to inspect adjacent members.
    """

    pass


class HBox(Box):
    """Testing stub that mirrors the public shape of ``ipywidgets.HBox``.
    
    Full API
    --------
    ``HBox()``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    HBox
        New ``HBox`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``HBox`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import HBox
        obj = HBox(...)
    
    Discovery-oriented use::
    
        help(HBox)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(HBox)`` and ``dir(HBox)`` to inspect adjacent members.
    """

    pass


class Label(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Label``.
    
    Full API
    --------
    ``Label(value: str='', **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : str, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``''``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Label
        New ``Label`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=''``: New or current value for the relevant property, control, or calculation.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Label`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Label
        obj = Label(...)
    
    Discovery-oriented use::
    
        help(Label)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Label)`` and ``dir(Label)`` to inspect adjacent members.
    """

    value = traitlets.Unicode("")

    def __init__(self, value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.value = str(value)


class HTML(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.HTML``.
    
    Full API
    --------
    ``HTML(value: str='', **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : str, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``''``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    HTML
        New ``HTML`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=''``: New or current value for the relevant property, control, or calculation.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``HTML`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import HTML
        obj = HTML(...)
    
    Discovery-oriented use::
    
        help(HTML)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(HTML)`` and ``dir(HTML)`` to inspect adjacent members.
    """

    value = traitlets.Unicode("")

    def __init__(self, value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.value = str(value)


class HTMLMath(HTML):
    """Testing stub that mirrors the public shape of ``ipywidgets.HTMLMath``.
    
    Full API
    --------
    ``HTMLMath()``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    HTMLMath
        New ``HTMLMath`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``HTMLMath`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import HTMLMath
        obj = HTMLMath(...)
    
    Discovery-oriented use::
    
        help(HTMLMath)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(HTMLMath)`` and ``dir(HTMLMath)`` to inspect adjacent members.
    """

    pass


class Text(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Text``.
    
    Full API
    --------
    ``Text(value: str='', continuous_update: bool=True, description: str='', placeholder: str='', **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : str, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``''``.
    
    continuous_update : bool, optional
        Value for ``continuous_update`` in this API. Defaults to ``True``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    placeholder : str, optional
        Value for ``placeholder`` in this API. Defaults to ``''``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Text
        New ``Text`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=''``: New or current value for the relevant property, control, or calculation.
    - ``continuous_update=True``: Value for ``continuous_update`` in this API.
    - ``description=''``: Value for ``description`` in this API.
    - ``placeholder=''``: Value for ``placeholder`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Text`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Text
        obj = Text(...)
    
    Discovery-oriented use::
    
        help(Text)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Text)`` and ``dir(Text)`` to inspect adjacent members.
    """

    value = traitlets.Unicode("")
    continuous_update = traitlets.Bool(True)
    description = traitlets.Unicode("")
    placeholder = traitlets.Unicode("")

    def __init__(
        self,
        value: str = "",
        *,
        continuous_update: bool = True,
        description: str = "",
        placeholder: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.continuous_update = bool(continuous_update)
        self.description = str(description)
        self.placeholder = str(placeholder)
        self.value = str(value)


class FloatSlider(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.FloatSlider``.
    
    Full API
    --------
    ``FloatSlider(value: float=0.0, min: float=0.0, max: float=1.0, step: float=0.1, continuous_update: bool=True, readout: bool=True, disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : float, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0.0``.
    
    min : float, optional
        Lower bound used by sliders, domains, or range validators. Defaults to ``0.0``.
    
    max : float, optional
        Upper bound used by sliders, domains, or range validators. Defaults to ``1.0``.
    
    step : float, optional
        Increment or resolution used for stepping through numeric values. Defaults to ``0.1``.
    
    continuous_update : bool, optional
        Value for ``continuous_update`` in this API. Defaults to ``True``.
    
    readout : bool, optional
        Value for ``readout`` in this API. Defaults to ``True``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    FloatSlider
        New ``FloatSlider`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0.0``: New or current value for the relevant property, control, or calculation.
    - ``min=0.0``: Lower bound used by sliders, domains, or range validators.
    - ``max=1.0``: Upper bound used by sliders, domains, or range validators.
    - ``step=0.1``: Increment or resolution used for stepping through numeric values.
    - ``continuous_update=True``: Value for ``continuous_update`` in this API.
    - ``readout=True``: Value for ``readout`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``FloatSlider`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import FloatSlider
        obj = FloatSlider(...)
    
    Discovery-oriented use::
    
        help(FloatSlider)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
    """

    value = traitlets.Float(0.0)
    min = traitlets.Float(0.0)
    max = traitlets.Float(1.0)
    step = traitlets.Float(0.1)
    continuous_update = traitlets.Bool(True)
    readout = traitlets.Bool(True)
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: float = 0.0,
        *,
        min: float = 0.0,
        max: float = 1.0,
        step: float = 0.1,
        continuous_update: bool = True,
        readout: bool = True,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min = float(min)
        self.max = float(max)
        self.step = float(step)
        self.continuous_update = bool(continuous_update)
        self.readout = bool(readout)
        self.disabled = bool(disabled)
        self.value = float(value)


class IntSlider(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.IntSlider``.
    
    Full API
    --------
    ``IntSlider(value: int=0, min: int=0, max: int=100, step: int=1, continuous_update: bool=True, readout: bool=True, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : int, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0``.
    
    min : int, optional
        Lower bound used by sliders, domains, or range validators. Defaults to ``0``.
    
    max : int, optional
        Upper bound used by sliders, domains, or range validators. Defaults to ``100``.
    
    step : int, optional
        Increment or resolution used for stepping through numeric values. Defaults to ``1``.
    
    continuous_update : bool, optional
        Value for ``continuous_update`` in this API. Defaults to ``True``.
    
    readout : bool, optional
        Value for ``readout`` in this API. Defaults to ``True``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    IntSlider
        New ``IntSlider`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0``: New or current value for the relevant property, control, or calculation.
    - ``min=0``: Lower bound used by sliders, domains, or range validators.
    - ``max=100``: Upper bound used by sliders, domains, or range validators.
    - ``step=1``: Increment or resolution used for stepping through numeric values.
    - ``continuous_update=True``: Value for ``continuous_update`` in this API.
    - ``readout=True``: Value for ``readout`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``IntSlider`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import IntSlider
        obj = IntSlider(...)
    
    Discovery-oriented use::
    
        help(IntSlider)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(IntSlider)`` and ``dir(IntSlider)`` to inspect adjacent members.
    """

    value = traitlets.Int(0)
    min = traitlets.Int(0)
    max = traitlets.Int(100)
    step = traitlets.Int(1)
    continuous_update = traitlets.Bool(True)
    readout = traitlets.Bool(True)

    def __init__(
        self,
        value: int = 0,
        *,
        min: int = 0,
        max: int = 100,
        step: int = 1,
        continuous_update: bool = True,
        readout: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min = int(min)
        self.max = int(max)
        self.step = int(step)
        self.continuous_update = bool(continuous_update)
        self.readout = bool(readout)
        self.value = int(value)


class Button(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Button``.
    
    Full API
    --------
    ``Button(description: str='', tooltip: str='', button_style: str='', icon: str='', disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: ``on_click``, ``click``
    
    Parameters
    ----------
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    tooltip : str, optional
        Value for ``tooltip`` in this API. Defaults to ``''``.
    
    button_style : str, optional
        Value for ``button_style`` in this API. Defaults to ``''``.
    
    icon : str, optional
        Value for ``icon`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Button
        New ``Button`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``description=''``: Value for ``description`` in this API.
    - ``tooltip=''``: Value for ``tooltip`` in this API.
    - ``button_style=''``: Value for ``button_style`` in this API.
    - ``icon=''``: Value for ``icon`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Button`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Button
        obj = Button(...)
    
    Discovery-oriented use::
    
        help(Button)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Button)`` and ``dir(Button)`` to inspect adjacent members.
    """

    description = traitlets.Unicode("")
    tooltip = traitlets.Unicode("")
    button_style = traitlets.Unicode("")
    icon = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        description: str = "",
        *,
        tooltip: str = "",
        button_style: str = "",
        icon: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.description = str(description)
        self.tooltip = str(tooltip)
        self.button_style = str(button_style)
        self.icon = str(icon)
        self.disabled = bool(disabled)
        self._click_handlers: list[Callable[[Any], None]] = []

    def on_click(self, callback: Callable[[Any], None]) -> None:
        """Work with on click on ``Button``.
        
        Full API
        --------
        ``obj.on_click(callback: Callable[[Any], None]) -> None``
        
        Parameters
        ----------
        callback : Callable[[Any], None]
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
        This member belongs to ``Button``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Button(...)
            obj.on_click(...)
        
        Discovery-oriented use::
        
            help(Button)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Button)`` and ``dir(Button)`` to inspect adjacent members.
        """

        self._click_handlers.append(callback)

    def click(self) -> None:
        """Work with click on ``Button``.
        
        Full API
        --------
        ``obj.click() -> None``
        
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
        This member belongs to ``Button``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Button(...)
            obj.click(...)
        
        Discovery-oriented use::
        
            help(Button)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Button)`` and ``dir(Button)`` to inspect adjacent members.
        """

        for callback in list(self._click_handlers):
            callback(self)


class ToggleButton(Button):
    """Testing stub that mirrors the public shape of ``ipywidgets.ToggleButton``.
    
    Full API
    --------
    ``ToggleButton(value: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : bool, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ToggleButton
        New ``ToggleButton`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=False``: New or current value for the relevant property, control, or calculation.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``ToggleButton`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import ToggleButton
        obj = ToggleButton(...)
    
    Discovery-oriented use::
    
        help(ToggleButton)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(ToggleButton)`` and ``dir(ToggleButton)`` to inspect adjacent members.
    """

    value = traitlets.Bool(False)

    def __init__(self, value: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.value = bool(value)


class ToggleButtons(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.ToggleButtons``.
    
    Full API
    --------
    ``ToggleButtons(options: Any=(), value: Any=None, description: str='', disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    options : Any, optional
        Value for ``options`` in this API. Defaults to ``()``.
    
    value : Any, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``None``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ToggleButtons
        New ``ToggleButtons`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``options=()``: Value for ``options`` in this API.
    - ``value=None``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``ToggleButtons`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import ToggleButtons
        obj = ToggleButtons(...)
    
    Discovery-oriented use::
    
        help(ToggleButtons)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(ToggleButtons)`` and ``dir(ToggleButtons)`` to inspect adjacent members.
    """

    value = traitlets.Any(None)
    options = traitlets.Any(())
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        *,
        options: Any = (),
        value: Any = None,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.description = str(description)
        self.disabled = bool(disabled)
        self.value = value


class Checkbox(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Checkbox``.
    
    Full API
    --------
    ``Checkbox(value: bool=False, description: str='', indent: bool=True, disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : bool, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``False``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    indent : bool, optional
        Value for ``indent`` in this API. Defaults to ``True``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Checkbox
        New ``Checkbox`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=False``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``indent=True``: Value for ``indent`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Checkbox`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Checkbox
        obj = Checkbox(...)
    
    Discovery-oriented use::
    
        help(Checkbox)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Checkbox)`` and ``dir(Checkbox)`` to inspect adjacent members.
    """

    value = traitlets.Bool(False)
    description = traitlets.Unicode("")
    indent = traitlets.Bool(True)
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: bool = False,
        *,
        description: str = "",
        indent: bool = True,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.value = bool(value)
        self.description = str(description)
        self.indent = bool(indent)
        self.disabled = bool(disabled)


class FloatText(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.FloatText``.
    
    Full API
    --------
    ``FloatText(value: float=0.0, description: str='', disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : float, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0.0``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    FloatText
        New ``FloatText`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0.0``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``FloatText`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import FloatText
        obj = FloatText(...)
    
    Discovery-oriented use::
    
        help(FloatText)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(FloatText)`` and ``dir(FloatText)`` to inspect adjacent members.
    """

    value = traitlets.Float(0.0)
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: float = 0.0,
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.value = float(value)
        self.description = str(description)
        self.disabled = bool(disabled)


class BoundedFloatText(FloatText):
    """Testing stub that mirrors the public shape of ``ipywidgets.BoundedFloatText``.
    
    Full API
    --------
    ``BoundedFloatText(value: float=0.0, min: float=0.0, max: float=1e+308, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : float, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0.0``.
    
    min : float, optional
        Lower bound used by sliders, domains, or range validators. Defaults to ``0.0``.
    
    max : float, optional
        Upper bound used by sliders, domains, or range validators. Defaults to ``1e+308``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    BoundedFloatText
        New ``BoundedFloatText`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0.0``: New or current value for the relevant property, control, or calculation.
    - ``min=0.0``: Lower bound used by sliders, domains, or range validators.
    - ``max=1e+308``: Upper bound used by sliders, domains, or range validators.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``BoundedFloatText`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import BoundedFloatText
        obj = BoundedFloatText(...)
    
    Discovery-oriented use::
    
        help(BoundedFloatText)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(BoundedFloatText)`` and ``dir(BoundedFloatText)`` to inspect adjacent members.
    """

    min = traitlets.Float(0.0)
    max = traitlets.Float(1.0e308)

    def __init__(
        self,
        value: float = 0.0,
        *,
        min: float = 0.0,
        max: float = 1.0e308,
        **kwargs: Any,
    ) -> None:
        super().__init__(value=value, **kwargs)
        self.min = float(min)
        self.max = float(max)


class IntText(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.IntText``.
    
    Full API
    --------
    ``IntText(value: int=0, description: str='', disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : int, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    IntText
        New ``IntText`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``IntText`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import IntText
        obj = IntText(...)
    
    Discovery-oriented use::
    
        help(IntText)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(IntText)`` and ``dir(IntText)`` to inspect adjacent members.
    """

    value = traitlets.Int(0)
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        value: int = 0,
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.value = int(value)
        self.description = str(description)
        self.disabled = bool(disabled)


class BoundedIntText(IntText):
    """Testing stub that mirrors the public shape of ``ipywidgets.BoundedIntText``.
    
    Full API
    --------
    ``BoundedIntText(value: int=0, min: int=0, max: int=2147483647, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : int, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0``.
    
    min : int, optional
        Lower bound used by sliders, domains, or range validators. Defaults to ``0``.
    
    max : int, optional
        Upper bound used by sliders, domains, or range validators. Defaults to ``2147483647``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    BoundedIntText
        New ``BoundedIntText`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0``: New or current value for the relevant property, control, or calculation.
    - ``min=0``: Lower bound used by sliders, domains, or range validators.
    - ``max=2147483647``: Upper bound used by sliders, domains, or range validators.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``BoundedIntText`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import BoundedIntText
        obj = BoundedIntText(...)
    
    Discovery-oriented use::
    
        help(BoundedIntText)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(BoundedIntText)`` and ``dir(BoundedIntText)`` to inspect adjacent members.
    """

    min = traitlets.Int(0)
    max = traitlets.Int(2147483647)

    def __init__(
        self,
        value: int = 0,
        *,
        min: int = 0,
        max: int = 2147483647,
        **kwargs: Any,
    ) -> None:
        super().__init__(value=value, **kwargs)
        self.min = int(min)
        self.max = int(max)


class Dropdown(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Dropdown``.
    
    Full API
    --------
    ``Dropdown(options: Any=(), value: Any=None, description: str='', disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    options : Any, optional
        Value for ``options`` in this API. Defaults to ``()``.
    
    value : Any, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``None``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Dropdown
        New ``Dropdown`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``options=()``: Value for ``options`` in this API.
    - ``value=None``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Dropdown`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Dropdown
        obj = Dropdown(...)
    
    Discovery-oriented use::
    
        help(Dropdown)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Dropdown)`` and ``dir(Dropdown)`` to inspect adjacent members.
    """

    value = traitlets.Any()
    options = traitlets.Any(())
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        options: Any = (),
        value: Any = None,
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.description = str(description)
        self.disabled = bool(disabled)
        self.value = value


class SelectMultiple(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.SelectMultiple``.
    
    Full API
    --------
    ``SelectMultiple(options: Any=(), value: tuple[Any, Ellipsis]=(), description: str='', disabled: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    options : Any, optional
        Value for ``options`` in this API. Defaults to ``()``.
    
    value : tuple[Any, Ellipsis], optional
        New or current value for the relevant property, control, or calculation. Defaults to ``()``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    SelectMultiple
        New ``SelectMultiple`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``options=()``: Value for ``options`` in this API.
    - ``value=()``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``SelectMultiple`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import SelectMultiple
        obj = SelectMultiple(...)
    
    Discovery-oriented use::
    
        help(SelectMultiple)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(SelectMultiple)`` and ``dir(SelectMultiple)`` to inspect adjacent members.
    """

    value = traitlets.Tuple()
    options = traitlets.Any(())
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)

    def __init__(
        self,
        options: Any = (),
        value: tuple[Any, ...] = (),
        *,
        description: str = "",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.description = str(description)
        self.disabled = bool(disabled)
        self.value = tuple(value)


class ColorPicker(Widget):
    """Minimal stand-in for :class:`ipywidgets.ColorPicker`.
    
    Full API
    --------
    ``ColorPicker(value: str='#000000', description: str='', disabled: bool=False, concise: bool=False, **kwargs: Any)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    value : str, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``'#000000'``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    disabled : bool, optional
        Value for ``disabled`` in this API. Defaults to ``False``.
    
    concise : bool, optional
        Value for ``concise`` in this API. Defaults to ``False``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ColorPicker
        New ``ColorPicker`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value='#000000'``: New or current value for the relevant property, control, or calculation.
    - ``description=''``: Value for ``description`` in this API.
    - ``disabled=False``: Value for ``disabled`` in this API.
    - ``concise=False``: Value for ``concise`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``ColorPicker`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import ColorPicker
        obj = ColorPicker(...)
    
    Discovery-oriented use::
    
        help(ColorPicker)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(ColorPicker)`` and ``dir(ColorPicker)`` to inspect adjacent members.
    """

    value = traitlets.Unicode("#000000")
    description = traitlets.Unicode("")
    disabled = traitlets.Bool(False)
    concise = traitlets.Bool(False)

    def __init__(
        self,
        value: str = "#000000",
        *,
        description: str = "",
        disabled: bool = False,
        concise: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.description = str(description)
        self.disabled = bool(disabled)
        self.concise = bool(concise)
        self.value = str(value)


class Output(Widget):
    """Testing stub that mirrors the public shape of ``ipywidgets.Output``.
    
    Full API
    --------
    ``Output(*args: Any, **kwargs: Any)``
    
    Public members exposed from this class: ``capture``, ``clear_output``, ``append_stdout``, ``append_stderr``,
        ``append_display_data``
    
    Parameters
    ----------
    *args : Any, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    Output
        New ``Output`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``Output`` lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._widget_stubs import Output
        obj = Output(...)
    
    Discovery-oriented use::
    
        help(Output)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(Output)`` and ``dir(Output)`` to inspect adjacent members.
    """

    outputs = traitlets.List(trait=traitlets.Any())

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.outputs = []

    @contextmanager
    def capture(self, *args: Any, **kwargs: Any):
        """Work with capture on ``Output``.
        
        Full API
        --------
        ``obj.capture(*args: Any, **kwargs: Any)``
        
        Parameters
        ----------
        *args : Any, optional
            Additional positional arguments forwarded by this API. Optional variadic input.
        
        **kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
        - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``Output``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Output(...)
            result = obj.capture(...)
        
        Discovery-oriented use::
        
            help(Output)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Output)`` and ``dir(Output)`` to inspect adjacent members.
        """

        yield self

    def clear_output(self, wait: bool = False) -> None:
        """Work with clear output on ``Output``.
        
        Full API
        --------
        ``obj.clear_output(wait: bool=False) -> None``
        
        Parameters
        ----------
        wait : bool, optional
            Value for ``wait`` in this API. Defaults to ``False``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``wait=False``: Value for ``wait`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``Output``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Output(...)
            obj.clear_output(...)
        
        Discovery-oriented use::
        
            help(Output)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Output)`` and ``dir(Output)`` to inspect adjacent members.
        """

        self.outputs = []

    def append_stdout(self, text: str) -> None:
        """Work with append stdout on ``Output``.
        
        Full API
        --------
        ``obj.append_stdout(text: str) -> None``
        
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
        This member belongs to ``Output``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Output(...)
            obj.append_stdout(...)
        
        Discovery-oriented use::
        
            help(Output)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Output)`` and ``dir(Output)`` to inspect adjacent members.
        """

        self.outputs = [*self.outputs, {"name": "stdout", "text": str(text)}]

    def append_stderr(self, text: str) -> None:
        """Work with append stderr on ``Output``.
        
        Full API
        --------
        ``obj.append_stderr(text: str) -> None``
        
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
        This member belongs to ``Output``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Output(...)
            obj.append_stderr(...)
        
        Discovery-oriented use::
        
            help(Output)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Output)`` and ``dir(Output)`` to inspect adjacent members.
        """

        self.outputs = [*self.outputs, {"name": "stderr", "text": str(text)}]

    def append_display_data(self, obj: Any) -> None:
        """Work with append display data on ``Output``.
        
        Full API
        --------
        ``obj.append_display_data(obj: Any) -> None``
        
        Parameters
        ----------
        obj : Any
            Value for ``obj`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``Output``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = Output(...)
            obj.append_display_data(...)
        
        Discovery-oriented use::
        
            help(Output)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/ui-layout-system.md``.
        - Example notebook: ``examples/layout_debug.ipynb``.
        - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
        - In a notebook or REPL, run ``help(Output)`` and ``dir(Output)`` to inspect adjacent members.
        """

        self.outputs = [*self.outputs, {"data": obj}]

    def __enter__(self) -> "Output":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


_widgets_module = types.ModuleType("ipywidgets")
_widgets_module.Layout = Layout
_widgets_module.Widget = Widget
_widgets_module.Box = Box
_widgets_module.VBox = VBox
_widgets_module.HBox = HBox
_widgets_module.Label = Label
_widgets_module.HTML = HTML
_widgets_module.HTMLMath = HTMLMath
_widgets_module.Text = Text
_widgets_module.FloatSlider = FloatSlider
_widgets_module.IntSlider = IntSlider
_widgets_module.Button = Button
_widgets_module.ToggleButton = ToggleButton
_widgets_module.ToggleButtons = ToggleButtons
_widgets_module.Checkbox = Checkbox
_widgets_module.FloatText = FloatText
_widgets_module.BoundedFloatText = BoundedFloatText
_widgets_module.IntText = IntText
_widgets_module.BoundedIntText = BoundedIntText
_widgets_module.Dropdown = Dropdown
_widgets_module.SelectMultiple = SelectMultiple
_widgets_module.ColorPicker = ColorPicker
_widgets_module.Output = Output
_widgets_module.link = traitlets.link
_widgets_module.dlink = traitlets.dlink
_widgets_module.Widget.widget_types = {}


IPYWIDGETS_IS_FALLBACK = False
IPYWIDGETS_IMPORT_ERROR: str | None = None

try:  # pragma: no cover - exercised only when real dependency exists
    import ipywidgets as widgets  # type: ignore[import-not-found]
except ModuleNotFoundError as exc:  # pragma: no cover - covered via unit tests
    IPYWIDGETS_IS_FALLBACK = True
    IPYWIDGETS_IMPORT_ERROR = repr(exc)
    widgets = _widgets_module
else:  # pragma: no cover - depends on environment
    _class_owner = getattr(widgets, "DOMWidget", getattr(widgets, "Widget", None))
    _original_add_class = getattr(_class_owner, "add_class", None)
    _original_remove_class = getattr(_class_owner, "remove_class", None)

    def _patched_add_class(self, class_name: str):
        result = _original_add_class(self, class_name) if callable(_original_add_class) else None
        classes = set(getattr(self, "_classes", set()) or set())
        classes.add(str(class_name))
        try:
            setattr(self, "_classes", classes)
        except Exception:
            pass
        return result

    def _patched_remove_class(self, class_name: str):
        result = _original_remove_class(self, class_name) if callable(_original_remove_class) else None
        classes = set(getattr(self, "_classes", set()) or set())
        classes.discard(str(class_name))
        try:
            setattr(self, "_classes", classes)
        except Exception:
            pass
        return result

    if _class_owner is not None and callable(_original_add_class):
        _class_owner.add_class = _patched_add_class
    if _class_owner is not None and callable(_original_remove_class):
        _class_owner.remove_class = _patched_remove_class


ANYWIDGET_IS_FALLBACK = False
ANYWIDGET_IMPORT_ERROR: str | None = None

try:  # pragma: no cover - exercised only when real dependency exists
    import anywidget  # type: ignore[import-not-found]
except ModuleNotFoundError as exc:  # pragma: no cover - covered via unit tests
    ANYWIDGET_IS_FALLBACK = True
    ANYWIDGET_IMPORT_ERROR = repr(exc)
    if widgets is _widgets_module:
        class _FallbackAnyWidget(Widget):
            """Small ``anywidget.AnyWidget`` substitute used in tests."""

            _esm = ""
    else:
        class _FallbackAnyWidget(widgets.DOMWidget):  # type: ignore[misc, valid-type]
            """Fallback ``anywidget.AnyWidget`` compatible with real ipywidgets."""

            _esm = ""
            _view_name = traitlets.Unicode("FallbackAnyWidgetView").tag(sync=True)
            _model_name = traitlets.Unicode("FallbackAnyWidgetModel").tag(sync=True)
            _view_module = traitlets.Unicode("@jupyter-widgets/base").tag(sync=True)
            _model_module = traitlets.Unicode("@jupyter-widgets/base").tag(sync=True)
            _view_module_version = traitlets.Unicode("*").tag(sync=True)
            _model_module_version = traitlets.Unicode("*").tag(sync=True)

            def _emit_msg(self, content: Any = None, buffers: Any = None) -> None:
                self._handle_custom_msg(content if content is not None else {}, buffers)

    _anywidget_module = types.ModuleType("anywidget")
    _anywidget_module.AnyWidget = _FallbackAnyWidget
    anywidget = _anywidget_module


def install_widget_stubs() -> None:
    """Install fallback widget modules into :mod:`sys.modules` when missing.
    
    Full API
    --------
    ``install_widget_stubs() -> None``
    
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
    This callable lives in ``gu_toolkit._widget_stubs``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit._widget_stubs import install_widget_stubs
        install_widget_stubs(...)
    
    Discovery-oriented use::
    
        help(install_widget_stubs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(install_widget_stubs)`` and inspect sibling APIs in the same module.
    """

    sys.modules.setdefault("ipywidgets", widgets)
    sys.modules.setdefault("anywidget", anywidget)


__all__ = [
    "widgets",
    "anywidget",
    "install_widget_stubs",
    "IPYWIDGETS_IS_FALLBACK",
    "IPYWIDGETS_IMPORT_ERROR",
    "ANYWIDGET_IS_FALLBACK",
    "ANYWIDGET_IMPORT_ERROR",
]
