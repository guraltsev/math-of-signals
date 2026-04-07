"""Parameter-reference protocol and default widget-backed implementation.

This module defines the discoverable contract used by Figure parameter APIs
and a proxy implementation that wraps concrete controls.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, runtime_checkable

from sympy.core.symbol import Symbol

from .ParamEvent import ParamEvent


@runtime_checkable
class ParamRef(Protocol):
    """Protocol for parameter references used by Figure.
    
    Full API
    --------
    ``ParamRef()``
    
    Public members exposed from this class: ``parameter``, ``widget``, ``value``, ``observe``, ``reset``, ``capabilities``,
        ``animation_time``, ``animation_mode``, ``animation_running``, ``start_animation``,
        ``stop_animation``, ``toggle_animation``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    Any implementation of ``ParamRef``
        Objects matching this protocol/interface can be passed anywhere the toolkit expects ``ParamRef``.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``ParamRef`` lives in ``gu_toolkit.ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Implementation sketch::
    
        from gu_toolkit.ParamRef import ParamRef
    
        class MyParamRef(ParamRef):
            ...
    
    Discovery-oriented use::
    
        help(ParamRef)
        dir(MyParamRef)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
    """

    @property
    def parameter(self) -> Symbol:
        """Return the SymPy symbol this reference controls.
        
        Full API
        --------
        ``obj.parameter -> Symbol``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Symbol
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.parameter
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @property
    def widget(self) -> Any:
        """Return the underlying widget/control instance.
        
        Full API
        --------
        ``obj.widget -> Any``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.widget
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @property
    def value(self) -> Any:
        """Return the current parameter value.
        
        Full API
        --------
        ``obj.value -> Any``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.value
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @value.setter
    def value(self, v: Any) -> None:
        """Set the current parameter value.
        
        Full API
        --------
        ``obj.value = v``
        
        Parameters
        ----------
        v : Any
            Value for ``v`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.value = v
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    def observe(
        self, callback: Callable[[ParamEvent], None], *, fire: bool = False
    ) -> None:
        """Register a callback that receives :class:`ParamEvent` on changes.
        
        Full API
        --------
        ``obj.observe(callback: Callable[[ParamEvent], None], *, fire: bool=False) -> None``
        
        Parameters
        ----------
        callback : Callable[[ParamEvent], None]
            Callable that is invoked when the relevant event fires. Required.
        
        fire : bool, optional
            Boolean flag that requests an immediate callback with the current state. Defaults to ``False``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``fire=False``: Boolean flag that requests an immediate callback with the current state.
        
        Architecture note
        -----------------
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.observe(...)
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    def reset(self) -> None:
        """Reset the underlying control to its default value.
        
        Full API
        --------
        ``obj.reset() -> None``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.reset(...)
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @property
    def capabilities(self) -> Sequence[str]:
        """Return optional metadata keys supported by this reference.
        
        Full API
        --------
        ``obj.capabilities -> Sequence[str]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Sequence[str]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.capabilities
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @property
    def animation_time(self) -> Any:
        """Return the configured animation duration if supported.
        
        Full API
        --------
        ``obj.animation_time -> Any``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.animation_time
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @animation_time.setter
    def animation_time(self, value: Any) -> None:
        """Set the configured animation duration if supported.
        
        Full API
        --------
        ``obj.animation_time = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.animation_time = value
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @property
    def animation_mode(self) -> Any:
        """Return the configured animation mode if supported.
        
        Full API
        --------
        ``obj.animation_mode -> Any``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.animation_mode
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @animation_mode.setter
    def animation_mode(self, value: Any) -> None:
        """Set the configured animation mode if supported.
        
        Full API
        --------
        ``obj.animation_mode = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.animation_mode = value
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    @property
    def animation_running(self) -> Any:
        """Return whether animation is active if supported.
        
        Full API
        --------
        ``obj.animation_running -> Any``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            current = obj.animation_running
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    def start_animation(self) -> None:
        """Start animation if the underlying control supports it.
        
        Full API
        --------
        ``obj.start_animation() -> None``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.start_animation(...)
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    def stop_animation(self) -> None:
        """Stop animation if the underlying control supports it.
        
        Full API
        --------
        ``obj.stop_animation() -> None``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.stop_animation(...)
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """

    def toggle_animation(self) -> None:
        """Toggle animation if the underlying control supports it.
        
        Full API
        --------
        ``obj.toggle_animation() -> None``
        
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
        This member belongs to ``ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParamRef(...)
            obj.toggle_animation(...)
        
        Discovery-oriented use::
        
            help(ParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ParamRef)`` and ``dir(ParamRef)`` to inspect adjacent members.
        """


class ProxyParamRef:
    """Default ParamRef implementation that proxies to a widget/control.
    
    Full API
    --------
    ``ProxyParamRef(parameter: Symbol, widget: Any)``
    
    Public members exposed from this class: ``parameter``, ``widget``, ``value``, ``default_value``, ``observe``, ``reset``,
        ``capabilities``, ``min``, ``max``, ``step``, ``animation_time``,
        ``animation_mode``, ``animation_running``, ``start_animation``, ``stop_animation``,
        ``toggle_animation``
    
    Parameters
    ----------
    parameter : Symbol
        Parameter symbol or parameter reference associated with this API. Required.
    
    widget : Any
        Widget/control instance associated with this API. Required.
    
    Returns
    -------
    ProxyParamRef
        New ``ProxyParamRef`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``ProxyParamRef`` lives in ``gu_toolkit.ParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.ParamRef import ProxyParamRef
        obj = ProxyParamRef(...)
    
    Discovery-oriented use::
    
        help(ProxyParamRef)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
    """

    def __init__(self, parameter: Symbol, widget: Any) -> None:
        """Initialize a proxy reference for a widget-backed parameter.

        Parameters
        ----------
        parameter : sympy.Symbol
            Symbol associated with the control.
        widget : Any
            Widget/control instance providing a ``value`` trait.

        Returns
        -------
        None

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from Slider import FloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, FloatSlider())  # doctest: +SKIP
        """
        self._parameter = parameter
        self._widget = widget

    @property
    def parameter(self) -> Symbol:
        """Return the SymPy symbol for this reference.
        
        Full API
        --------
        ``obj.parameter -> Symbol``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Symbol
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.parameter
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._parameter

    @property
    def widget(self) -> Any:
        """Return the underlying widget/control instance.
        
        Full API
        --------
        ``obj.widget -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.widget
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._widget

    @property
    def value(self) -> Any:
        """Return the current value from the widget.
        
        Full API
        --------
        ``obj.value -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._widget.value

    @value.setter
    def value(self, v: Any) -> None:
        """Set the current value on the widget.
        
        Full API
        --------
        ``obj.value = v``
        
        Parameters
        ----------
        v : Any
            Value for ``v`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.value = v
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        self._widget.value = v

    @property
    def default_value(self) -> Any:
        """Return the stored default value if supported.
        
        Full API
        --------
        ``obj.default_value -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.default_value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("default_value")

    @default_value.setter
    def default_value(self, v: Any) -> None:
        """Set the stored default value if supported.
        
        Full API
        --------
        ``obj.default_value = v``
        
        Parameters
        ----------
        v : Any
            Value for ``v`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.default_value = v
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "default_value"):
            raise AttributeError("default_value not supported for this control.")
        self._widget.default_value = v

    def observe(
        self, callback: Callable[[ParamEvent], None], *, fire: bool = False
    ) -> None:
        """Register a callback for value changes.
        
        Full API
        --------
        ``obj.observe(callback: Callable[[ParamEvent], None], *, fire: bool=False) -> None``
        
        Parameters
        ----------
        callback : Callable[[ParamEvent], None]
            Callable that is invoked when the relevant event fires. Required.
        
        fire : bool, optional
            Boolean flag that requests an immediate callback with the current state. Defaults to ``False``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``fire=False``: Boolean flag that requests an immediate callback with the current state.
        
        Architecture note
        -----------------
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.observe(...)
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """

        def _handler(change: Any) -> None:
            event = ParamEvent(
                parameter=self._parameter,
                old=getattr(change, "old", None)
                if not isinstance(change, dict)
                else change.get("old"),
                new=getattr(change, "new", None)
                if not isinstance(change, dict)
                else change.get("new"),
                ref=self,
                raw=change,
            )
            callback(event)

        self._widget.observe(_handler, names="value")

        if fire:
            event = ParamEvent(
                parameter=self._parameter,
                old=self.value,
                new=self.value,
                ref=self,
                raw=None,
            )
            callback(event)

    def reset(self) -> None:
        """Reset the underlying widget if supported.
        
        Full API
        --------
        ``obj.reset() -> None``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.reset(...)
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if hasattr(self._widget, "reset"):
            self._widget.reset()
        else:
            raise AttributeError("reset not supported for this control.")

    def _require_attr(self, name: str) -> Any:
        """Return a widget attribute or raise if unsupported.

        Parameters
        ----------
        name : str
            Attribute name to access.

        Returns
        -------
        Any
            Attribute value from the widget.
        """
        if not hasattr(self._widget, name):
            raise AttributeError(f"{name} not supported for this control.")
        return getattr(self._widget, name)

    @property
    def capabilities(self) -> Sequence[str]:
        """Return the optional metadata keys supported by this control.
        
        Full API
        --------
        ``obj.capabilities -> Sequence[str]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Sequence[str]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.capabilities
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        supported = []
        for name in (
            "default_value",
            "min",
            "max",
            "step",
            "animation_time",
            "animation_mode",
            "animation_running",
        ):
            if hasattr(self._widget, name):
                supported.append(name)
        return tuple(supported)

    def __dir__(self) -> list[str]:
        """Return a dir listing that includes optional widget attributes.

        Returns
        -------
        list[str]
            Attribute names including supported optional properties.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from Slider import FloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, FloatSlider())  # doctest: +SKIP
        >>> "min" in dir(ref)  # doctest: +SKIP
        True
        """
        base = {
            "parameter",
            "widget",
            "value",
            "observe",
            "reset",
            "capabilities",
            "start_animation",
            "stop_animation",
            "toggle_animation",
        }
        optional = []
        for name in (
            "default_value",
            "min",
            "max",
            "step",
            "animation_time",
            "animation_mode",
            "animation_running",
        ):
            if hasattr(self._widget, name):
                optional.append(name)
        base.update(optional)
        return sorted(base.union(set(super().__dir__())))

    @property
    def min(self) -> Any:
        """Return the minimum value if supported.
        
        Full API
        --------
        ``obj.min -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.min
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("min")

    @min.setter
    def min(self, value: Any) -> None:
        """Set the minimum value if supported.
        
        Full API
        --------
        ``obj.min = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.min = value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "min"):
            raise AttributeError("min not supported for this control.")
        self._widget.min = value

    @property
    def max(self) -> Any:
        """Return the maximum value if supported.
        
        Full API
        --------
        ``obj.max -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.max
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("max")

    @max.setter
    def max(self, value: Any) -> None:
        """Set the maximum value if supported.
        
        Full API
        --------
        ``obj.max = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.max = value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "max"):
            raise AttributeError("max not supported for this control.")
        self._widget.max = value

    @property
    def step(self) -> Any:
        """Return the step value if supported.
        
        Full API
        --------
        ``obj.step -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.step
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("step")

    @step.setter
    def step(self, value: Any) -> None:
        """Set the step value if supported.
        
        Full API
        --------
        ``obj.step = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.step = value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "step"):
            raise AttributeError("step not supported for this control.")
        self._widget.step = value

    @property
    def animation_time(self) -> Any:
        """Return the animation duration if supported.
        
        Full API
        --------
        ``obj.animation_time -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.animation_time
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("animation_time")

    @animation_time.setter
    def animation_time(self, value: Any) -> None:
        """Set the animation duration if supported.
        
        Full API
        --------
        ``obj.animation_time = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.animation_time = value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "animation_time"):
            raise AttributeError("animation_time not supported for this control.")
        self._widget.animation_time = value

    @property
    def animation_mode(self) -> Any:
        """Return the animation mode if supported.
        
        Full API
        --------
        ``obj.animation_mode -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.animation_mode
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("animation_mode")

    @animation_mode.setter
    def animation_mode(self, value: Any) -> None:
        """Set the animation mode if supported.
        
        Full API
        --------
        ``obj.animation_mode = value``
        
        Parameters
        ----------
        value : Any
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.animation_mode = value
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "animation_mode"):
            raise AttributeError("animation_mode not supported for this control.")
        self._widget.animation_mode = value

    @property
    def animation_running(self) -> Any:
        """Return whether animation is active if supported.
        
        Full API
        --------
        ``obj.animation_running -> Any``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            current = obj.animation_running
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        return self._require_attr("animation_running")

    def start_animation(self) -> None:
        """Start animation if the widget supports it.
        
        Full API
        --------
        ``obj.start_animation() -> None``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.start_animation(...)
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "start_animation"):
            raise AttributeError("start_animation not supported for this control.")
        self._widget.start_animation()

    def stop_animation(self) -> None:
        """Stop animation if the widget supports it.
        
        Full API
        --------
        ``obj.stop_animation() -> None``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.stop_animation(...)
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "stop_animation"):
            raise AttributeError("stop_animation not supported for this control.")
        self._widget.stop_animation()

    def toggle_animation(self) -> None:
        """Toggle animation if the widget supports it.
        
        Full API
        --------
        ``obj.toggle_animation() -> None``
        
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
        This member belongs to ``ProxyParamRef``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ProxyParamRef(...)
            obj.toggle_animation(...)
        
        Discovery-oriented use::
        
            help(ProxyParamRef)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(ProxyParamRef)`` and ``dir(ProxyParamRef)`` to inspect adjacent members.
        """
        if not hasattr(self._widget, "toggle_animation"):
            raise AttributeError("toggle_animation not supported for this control.")
        self._widget.toggle_animation()
