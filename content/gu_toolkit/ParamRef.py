"""Parameter-reference protocol and default widget-backed implementation.

This module defines the discoverable contract used by SmartFigure parameter APIs
and a proxy implementation that wraps concrete controls.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, Sequence, runtime_checkable

from sympy.core.symbol import Symbol

from .ParamEvent import ParamEvent


@runtime_checkable
class ParamRef(Protocol):
    """Protocol for parameter references used by SmartFigure.

    A ``ParamRef`` exposes the current value of a parameter (typically from a
    slider widget), a reference to the underlying widget, and observation hooks
    that emit :class:`ParamEvent` objects.

    Notes
    -----
    Implementations should emit :class:`ParamEvent` on value changes and support
    ``reset`` if the underlying control provides it.
    """

    @property
    def parameter(self) -> Symbol:
        """Return the SymPy symbol this reference controls.

        Returns
        -------
        sympy.Symbol
            The parameter symbol associated with this reference.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, object())  # doctest: +SKIP
        >>> ref.parameter  # doctest: +SKIP
        a

        Notes
        -----
        This symbol is used when constructing :class:`ParamEvent` objects.
        """

    @property
    def widget(self) -> Any:
        """Return the underlying widget/control instance.

        Returns
        -------
        Any
            Widget instance providing a ``value`` trait.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, object())  # doctest: +SKIP
        >>> ref.widget  # doctest: +SKIP
        <...>
        """

    @property
    def value(self) -> Any:
        """Return the current parameter value.

        Returns
        -------
        Any
            The current widget value.

        Notes
        -----
        In a typical slider-based implementation, this is a ``float``.
        """

    @value.setter
    def value(self, v: Any) -> None:
        """Set the current parameter value.

        Parameters
        ----------
        v : Any
            New value to set on the underlying widget.
        """

    def observe(self, callback: Callable[[ParamEvent], None], *, fire: bool = False) -> None:
        """Register a callback that receives :class:`ParamEvent` on changes.

        Parameters
        ----------
        callback : callable
            Function invoked with a :class:`ParamEvent` instance.
        fire : bool, optional
            If ``True``, invoke the callback immediately with a synthetic event.

        Returns
        -------
        None

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.observe(lambda event: None, fire=False)  # doctest: +SKIP

        See Also
        --------
        ParamEvent : Normalized event payload delivered to callbacks.
        """

    def reset(self) -> None:
        """Reset the underlying control to its default value.

        Returns
        -------
        None

        Notes
        -----
        Implementations should raise ``AttributeError`` if the control does not
        support resetting.
        """

    @property
    def capabilities(self) -> Sequence[str]:
        """Return optional metadata keys supported by this reference.

        Returns
        -------
        Sequence[str]
            Zero or more of: ``default_value``, ``min``, ``max``, ``step``.
        """


class ProxyParamRef:
    """Default ParamRef implementation that proxies to a widget/control.

    Parameters
    ----------
    parameter : sympy.Symbol
        Symbol associated with the control.
    widget : Any
        Widget/control instance providing a ``value`` trait.

    Notes
    -----
    Optional attributes such as ``min``/``max``/``step`` and ``default_value``
    are exposed when the underlying widget supports them. Use
    :attr:`capabilities` to feature-detect support at runtime.
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
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        """
        self._parameter = parameter
        self._widget = widget

    @property
    def parameter(self) -> Symbol:
        """Return the SymPy symbol for this reference.

        Returns
        -------
        sympy.Symbol
            The symbol associated with the control.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.parameter  # doctest: +SKIP
        a
        """
        return self._parameter

    @property
    def widget(self) -> Any:
        """Return the underlying widget/control instance.

        Returns
        -------
        Any
            Widget or control providing a ``value`` trait.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> isinstance(ref.widget, SmartFloatSlider)  # doctest: +SKIP
        True
        """
        return self._widget

    @property
    def value(self) -> Any:
        """Return the current value from the widget.

        Returns
        -------
        Any
            Current parameter value.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider(value=2.0))  # doctest: +SKIP
        >>> float(ref.value)  # doctest: +SKIP
        2.0
        """
        return self._widget.value

    @value.setter
    def value(self, v: Any) -> None:
        """Set the current value on the widget.

        Parameters
        ----------
        v : Any
            New parameter value.

        Returns
        -------
        None

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.value = 3.0  # doctest: +SKIP
        """
        self._widget.value = v

    @property
    def default_value(self) -> Any:
        """Return the stored default value if supported.

        Returns
        -------
        Any
            Default value used by ``reset``.

        Notes
        -----
        Raises ``AttributeError`` if the underlying widget does not expose a
        ``default_value`` attribute.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider(value=1.5))  # doctest: +SKIP
        >>> ref.default_value  # doctest: +SKIP
        1.5
        """
        return self._require_attr("default_value")

    @default_value.setter
    def default_value(self, v: Any) -> None:
        """Set the stored default value if supported.

        Parameters
        ----------
        v : Any
            New default value.

        Returns
        -------
        None

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.default_value = 2.0  # doctest: +SKIP
        """
        if not hasattr(self._widget, "default_value"):
            raise AttributeError("default_value not supported for this control.")
        self._widget.default_value = v

    def observe(self, callback: Callable[[ParamEvent], None], *, fire: bool = False) -> None:
        """Register a callback for value changes.

        Parameters
        ----------
        callback : callable
            Function accepting a single :class:`ParamEvent` argument.
        fire : bool, optional
            If ``True``, invoke the callback immediately with a synthetic event.

        Returns
        -------
        None

        Notes
        -----
        Events are normalized into :class:`ParamEvent` regardless of the
        underlying widget's change payload shape.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.observe(lambda event: None, fire=False)  # doctest: +SKIP
        """
        def _handler(change: Any) -> None:
            event = ParamEvent(
                parameter=self._parameter,
                old=getattr(change, "old", None) if not isinstance(change, dict) else change.get("old"),
                new=getattr(change, "new", None) if not isinstance(change, dict) else change.get("new"),
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

        Returns
        -------
        None

        Raises
        ------
        AttributeError
            If the widget does not implement ``reset``.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider(value=2.0))  # doctest: +SKIP
        >>> ref.reset()  # doctest: +SKIP
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

        Returns
        -------
        Sequence[str]
            Zero or more of: ``default_value``, ``min``, ``max``, ``step``.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> "min" in ref.capabilities  # doctest: +SKIP
        True

        Notes
        -----
        This is useful for generic code that supports multiple widget types.
        """
        supported = []
        for name in ("default_value", "min", "max", "step"):
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
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
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
        }
        optional = []
        for name in ("default_value", "min", "max", "step"):
            if hasattr(self._widget, name):
                optional.append(name)
        base.update(optional)
        return sorted(base.union(set(super().__dir__())))

    @property
    def min(self) -> Any:
        """Return the minimum value if supported.

        Returns
        -------
        Any
            Minimum value from the widget.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider(min=-1.0, max=1.0))  # doctest: +SKIP
        >>> ref.min  # doctest: +SKIP
        -1.0
        """
        return self._require_attr("min")

    @min.setter
    def min(self, value: Any) -> None:
        """Set the minimum value if supported.

        Parameters
        ----------
        value : Any
            New minimum value.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.min = -2.0  # doctest: +SKIP
        """
        if not hasattr(self._widget, "min"):
            raise AttributeError("min not supported for this control.")
        self._widget.min = value

    @property
    def max(self) -> Any:
        """Return the maximum value if supported.

        Returns
        -------
        Any
            Maximum value from the widget.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider(min=-1.0, max=1.0))  # doctest: +SKIP
        >>> ref.max  # doctest: +SKIP
        1.0
        """
        return self._require_attr("max")

    @max.setter
    def max(self, value: Any) -> None:
        """Set the maximum value if supported.

        Parameters
        ----------
        value : Any
            New maximum value.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.max = 2.0  # doctest: +SKIP
        """
        if not hasattr(self._widget, "max"):
            raise AttributeError("max not supported for this control.")
        self._widget.max = value

    @property
    def step(self) -> Any:
        """Return the step value if supported.

        Returns
        -------
        Any
            Step size from the widget.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider(step=0.5))  # doctest: +SKIP
        >>> ref.step  # doctest: +SKIP
        0.5
        """
        return self._require_attr("step")

    @step.setter
    def step(self, value: Any) -> None:
        """Set the step value if supported.

        Parameters
        ----------
        value : Any
            New step size.

        Examples
        --------
        >>> import sympy as sp  # doctest: +SKIP
        >>> from SmartSlider import SmartFloatSlider  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> ref = ProxyParamRef(a, SmartFloatSlider())  # doctest: +SKIP
        >>> ref.step = 0.1  # doctest: +SKIP
        """
        if not hasattr(self._widget, "step"):
            raise AttributeError("step not supported for this control.")
        self._widget.step = value
