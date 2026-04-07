"""Module-level convenience API for current-figure workflows.

The helpers in this module do not own plotting state. They resolve the
*current figure* from :mod:`gu_toolkit.figure_context` and delegate to that
figure's public API.

Two context patterns matter:

- ``with fig:`` makes ``fig`` the current target while leaving the current view
  unchanged.
- ``with fig.views["detail"]:`` makes ``fig`` current *and* temporarily makes
  ``"detail"`` the active view, so module-level helpers route into that view.

Examples
--------
>>> import sympy as sp
>>> from gu_toolkit import Figure, parameter, plot, info
>>> x, a = sp.symbols("x a")
>>> fig = Figure()  # doctest: +SKIP
>>> fig.views.add("detail", x_range=(-1, 1), y_range=(-1, 1))  # doctest: +SKIP
>>> with fig.views["detail"]:  # doctest: +SKIP
...     parameter(a, min=-1, max=1)  # doctest: +SKIP
...     plot(a * sp.sin(x), x, id="wave")  # doctest: +SKIP
...     info("Zoomed view")  # doctest: +SKIP

Notes
-----
``plot(...)`` will auto-create a new figure when no current figure exists.
Other helpers such as ``parameter(...)``, ``info(...)``, and range/title
setters require an active figure context.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from IPython.display import display
from sympy.core.symbol import Symbol

from .figure_context import _current_figure, _require_current_figure
from .ParameterSnapshot import ParameterSnapshot, ParameterValueSnapshot
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .parameter_keys import ParameterKeyOrKeys

if TYPE_CHECKING:
    from .Figure import Figure
    from .figure_field import ScalarFieldPlot
    from .figure_plot import Plot
    from .figure_plot_normalization import PlotVarsSpec


class _CurrentParametersProxy(Mapping):
    """Module-level proxy to the current figure's ParameterManager."""

    def _fig(self) -> Figure:
        return _require_current_figure()

    def _mgr(self) -> Any:
        return self._fig().parameters

    def __getitem__(self, key: Hashable) -> ParamRef:
        return self._mgr()[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._mgr())

    def __len__(self) -> int:
        return len(self._mgr())

    def __contains__(self, key: object) -> bool:
        return key in self._mgr()

    def __setitem__(self, key: Hashable, value: Any) -> None:
        self[key].value = value

    def parameter(
        self,
        symbols: ParameterKeyOrKeys,
        *,
        control: str | None = None,
        **kwargs: Any,
    ) -> ParamRef | dict[str, ParamRef]:
        """Work with parameter on ``_CurrentParametersProxy``.
        
        Full API
        --------
        ``obj.parameter(symbols: ParameterKeyOrKeys, *, control: str | None=None, **kwargs: Any) -> ParamRef | dict[str, ParamRef]``
        
        Parameters
        ----------
        symbols : ParameterKeyOrKeys
            Parameter symbols, names, or other accepted parameter keys. Required.
        
        control : str | None, optional
            Control/widget style to construct when parameter widgets are created. Defaults to ``None``.
        
        **kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        ParamRef | dict[str, ParamRef]
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``control=None``: Control/widget style to construct when parameter widgets are created.
        - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``_CurrentParametersProxy``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _CurrentParametersProxy(...)
            result = obj.parameter(...)
        
        Discovery-oriented use::
        
            help(_CurrentParametersProxy)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(_CurrentParametersProxy)`` and ``dir(_CurrentParametersProxy)`` to inspect adjacent members.
        """

        return self._mgr().parameter(symbols, control=control, **kwargs)

    def snapshot(
        self, *, full: bool = False
    ) -> ParameterValueSnapshot | ParameterSnapshot:
        """Work with snapshot on ``_CurrentParametersProxy``.
        
        Full API
        --------
        ``obj.snapshot(*, full: bool=False) -> ParameterValueSnapshot | ParameterSnapshot``
        
        Parameters
        ----------
        full : bool, optional
            Boolean flag that asks for a more complete or verbose result. Defaults to ``False``.
        
        Returns
        -------
        ParameterValueSnapshot | ParameterSnapshot
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``full=False``: Boolean flag that asks for a more complete or verbose result.
        
        Architecture note
        -----------------
        This member belongs to ``_CurrentParametersProxy``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _CurrentParametersProxy(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(_CurrentParametersProxy)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(_CurrentParametersProxy)`` and ``dir(_CurrentParametersProxy)`` to inspect adjacent members.
        """

        return self._mgr().snapshot(full=full)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mgr(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._mgr(), name, value)


class _CurrentPlotsProxy(Mapping):
    """Module-level proxy to the current figure's plots mapping."""

    def _fig(self) -> Figure:
        return _require_current_figure()

    def __getitem__(self, key: Hashable) -> Plot:
        return self._fig().plots[key]

    def __iter__(self) -> Iterator[Hashable]:
        return iter(self._fig().plots)

    def __len__(self) -> int:
        return len(self._fig().plots)

    def __contains__(self, key: object) -> bool:
        return key in self._fig().plots


parameters = _CurrentParametersProxy()
plots = _CurrentPlotsProxy()


def set_title(text: str) -> None:
    """Set title.
    
    Full API
    --------
    ``set_title(text: str) -> None``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_title
        set_title(...)
    
    Discovery-oriented use::
    
        help(set_title)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_title)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().title = text


def get_title() -> str:
    """Return title.
    
    Full API
    --------
    ``get_title() -> str``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_title
        result = get_title(...)
    
    Discovery-oriented use::
    
        help(get_title)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_title)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().title


def render(
    reason: str = "manual",
    trigger: ParamEvent | None = None,
    *,
    force: bool = False,
) -> None:
    """Queue or synchronously execute a render on the current figure.
    
    Full API
    --------
    ``render(reason: str='manual', trigger: ParamEvent | None=None, *, force: bool=False) -> None``
    
    Parameters
    ----------
    reason : str, optional
        Short machine/human-readable reason recorded for scheduling or rendering. Defaults to ``'manual'``.
    
    trigger : ParamEvent | None, optional
        Event object or trigger payload that caused the current action. Defaults to ``None``.
    
    force : bool, optional
        Flag that requests eager execution or bypasses normal guards/debouncing. Defaults to ``False``.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    - ``reason='manual'``: Short machine/human-readable reason recorded for scheduling or rendering.
    - ``trigger=None``: Event object or trigger payload that caused the current action.
    - ``force=False``: Flag that requests eager execution or bypasses normal guards/debouncing.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import render
        render(...)
    
    Discovery-oriented use::
    
        help(render)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(render)`` and inspect sibling APIs in the same module.
    """
    _require_current_figure().render(reason=reason, trigger=trigger, force=force)


def sound_generation_enabled(enabled: bool | None = None) -> bool:
    """Query or set sound generation on the current figure.
    
    Full API
    --------
    ``sound_generation_enabled(enabled: bool | None=None) -> bool``
    
    Parameters
    ----------
    enabled : bool | None, optional
        Boolean flag that turns a feature on or off. Defaults to ``None``.
    
    Returns
    -------
    bool
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``enabled=None``: Boolean flag that turns a feature on or off.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import sound_generation_enabled
        result = sound_generation_enabled(...)
    
    Discovery-oriented use::
    
        help(sound_generation_enabled)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(sound_generation_enabled)`` and inspect sibling APIs in the same module.
    """
    return _require_current_figure().sound_generation_enabled(enabled)


def info(
    spec: str
    | Callable[[Figure, Any], str]
    | Sequence[str | Callable[[Figure, Any], str]],
    id: Hashable | None = None,
    *,
    view: str | None = None,
) -> None:
    """Create or replace a simple info card on the current figure.
    
    Full API
    --------
    ``info(spec: str | Callable[[Figure, Any], str] | Sequence[str | Callable[[Figure, Any], str]], id: Hashable | None=None, *, view: str | None=None) -> None``
    
    Parameters
    ----------
    spec : str | Callable[[Figure, Any], str] | Sequence[str | Callable[[Figure, Any], str]]
        Flexible specification object or shorthand accepted by this API. Required.
    
    id : Hashable | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    view : str | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    Returns
    -------
    None
        This call is used for side effects and does not return a value.
    
    Optional arguments
    ------------------
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import info
        info(...)
    
    Discovery-oriented use::
    
        help(info)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(info)`` and inspect sibling APIs in the same module.
    """
    _require_current_figure().info(spec=spec, id=id, view=view)


def set_x_range(value: tuple[int | float | str, int | float | str]) -> None:
    """Set x range.
    
    Full API
    --------
    ``set_x_range(value: tuple[int | float | str, int | float | str]) -> None``
    
    Parameters
    ----------
    value : tuple[int | float | str, int | float | str]
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_x_range
        set_x_range(...)
    
    Discovery-oriented use::
    
        help(set_x_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_x_range)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().x_range = value


def get_x_range() -> tuple[float, float]:
    """Return x range.
    
    Full API
    --------
    ``get_x_range() -> tuple[float, float]``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_x_range
        result = get_x_range(...)
    
    Discovery-oriented use::
    
        help(get_x_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_x_range)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().x_range


def set_default_x_range(value: tuple[int | float | str, int | float | str]) -> None:
    """Set default x range.
    
    Full API
    --------
    ``set_default_x_range(value: tuple[int | float | str, int | float | str]) -> None``
    
    Parameters
    ----------
    value : tuple[int | float | str, int | float | str]
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_default_x_range
        set_default_x_range(...)
    
    Discovery-oriented use::
    
        help(set_default_x_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_default_x_range)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().default_x_range = value


def get_default_x_range() -> tuple[float, float]:
    """Return default x range.
    
    Full API
    --------
    ``get_default_x_range() -> tuple[float, float]``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_default_x_range
        result = get_default_x_range(...)
    
    Discovery-oriented use::
    
        help(get_default_x_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_default_x_range)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().default_x_range


def set_y_range(value: tuple[int | float | str, int | float | str]) -> None:
    """Set y range.
    
    Full API
    --------
    ``set_y_range(value: tuple[int | float | str, int | float | str]) -> None``
    
    Parameters
    ----------
    value : tuple[int | float | str, int | float | str]
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_y_range
        set_y_range(...)
    
    Discovery-oriented use::
    
        help(set_y_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_y_range)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().y_range = value


def get_y_range() -> tuple[float, float]:
    """Return y range.
    
    Full API
    --------
    ``get_y_range() -> tuple[float, float]``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_y_range
        result = get_y_range(...)
    
    Discovery-oriented use::
    
        help(get_y_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_y_range)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().y_range


def set_default_y_range(value: tuple[int | float | str, int | float | str]) -> None:
    """Set default y range.
    
    Full API
    --------
    ``set_default_y_range(value: tuple[int | float | str, int | float | str]) -> None``
    
    Parameters
    ----------
    value : tuple[int | float | str, int | float | str]
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_default_y_range
        set_default_y_range(...)
    
    Discovery-oriented use::
    
        help(set_default_y_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_default_y_range)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().default_y_range = value


def get_default_y_range() -> tuple[float, float]:
    """Return default y range.
    
    Full API
    --------
    ``get_default_y_range() -> tuple[float, float]``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_default_y_range
        result = get_default_y_range(...)
    
    Discovery-oriented use::
    
        help(get_default_y_range)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_default_y_range)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().default_y_range


def set_samples(value: int | str | object | None) -> None:
    """Set samples.
    
    Full API
    --------
    ``set_samples(value: int | str | object | None) -> None``
    
    Parameters
    ----------
    value : int | str | object | None
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_samples
        set_samples(...)
    
    Discovery-oriented use::
    
        help(set_samples)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_samples)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().samples = value


def get_samples() -> int | None:
    """Return samples.
    
    Full API
    --------
    ``get_samples() -> int | None``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_samples
        result = get_samples(...)
    
    Discovery-oriented use::
    
        help(get_samples)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_samples)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().samples


def set_default_samples(value: int | str | object | None) -> None:
    """Set default samples.
    
    Full API
    --------
    ``set_default_samples(value: int | str | object | None) -> None``
    
    Parameters
    ----------
    value : int | str | object | None
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_default_samples
        set_default_samples(...)
    
    Discovery-oriented use::
    
        help(set_default_samples)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_default_samples)`` and inspect sibling APIs in the same module.
    """

    _require_current_figure().default_samples = value


def get_default_samples() -> int | None:
    """Return default samples.
    
    Full API
    --------
    ``get_default_samples() -> int | None``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_default_samples
        result = get_default_samples(...)
    
    Discovery-oriented use::
    
        help(get_default_samples)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_default_samples)`` and inspect sibling APIs in the same module.
    """

    return _require_current_figure().default_samples


def set_sampling_points(value: int | str | object | None) -> None:
    """Set sampling points.
    
    Full API
    --------
    ``set_sampling_points(value: int | str | object | None) -> None``
    
    Parameters
    ----------
    value : int | str | object | None
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import set_sampling_points
        set_sampling_points(...)
    
    Discovery-oriented use::
    
        help(set_sampling_points)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(set_sampling_points)`` and inspect sibling APIs in the same module.
    """

    set_samples(value)


def get_sampling_points() -> int | None:
    """Return sampling points.
    
    Full API
    --------
    ``get_sampling_points() -> int | None``
    
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
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import get_sampling_points
        result = get_sampling_points(...)
    
    Discovery-oriented use::
    
        help(get_sampling_points)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(get_sampling_points)`` and inspect sibling APIs in the same module.
    """

    return get_samples()


def plot_style_options() -> dict[str, str]:
    """Return help text for supported plot-style keywords.
    
    Full API
    --------
    ``plot_style_options() -> dict[str, str]``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    dict[str, str]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import plot_style_options
        result = plot_style_options(...)
    
    Discovery-oriented use::
    
        help(plot_style_options)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(plot_style_options)`` and inspect sibling APIs in the same module.
    """
    from .Figure import Figure

    return Figure.plot_style_options()


def field_style_options() -> dict[str, str]:
    """Return help text for supported scalar-field style keywords.
    
    Full API
    --------
    ``field_style_options() -> dict[str, str]``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    dict[str, str]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import field_style_options
        result = field_style_options(...)
    
    Discovery-oriented use::
    
        help(field_style_options)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(field_style_options)`` and inspect sibling APIs in the same module.
    """
    from .Figure import Figure

    return Figure.field_style_options()


def field_palette_options() -> dict[str, str]:
    """Return help text for curated scalar-field palette names.
    
    Full API
    --------
    ``field_palette_options() -> dict[str, str]``
    
    Parameters
    ----------
    None. This API does not declare user-supplied parameters beyond implicit object context.
    
    Returns
    -------
    dict[str, str]
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import field_palette_options
        result = field_palette_options(...)
    
    Discovery-oriented use::
    
        help(field_palette_options)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(field_palette_options)`` and inspect sibling APIs in the same module.
    """
    from .Figure import Figure

    return Figure.field_palette_options()


def parameter(
    symbols: ParameterKeyOrKeys,
    *,
    control: str | None = None,
    **kwargs: Any,
) -> ParamRef | dict[str, ParamRef]:
    """Work with parameter.
    
    Full API
    --------
    ``parameter(symbols: ParameterKeyOrKeys, *, control: str | None=None, **kwargs: Any) -> ParamRef | dict[str, ParamRef]``
    
    Parameters
    ----------
    symbols : ParameterKeyOrKeys
        Parameter symbols, names, or other accepted parameter keys. Required.
    
    control : str | None, optional
        Control/widget style to construct when parameter widgets are created. Defaults to ``None``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ParamRef | dict[str, ParamRef]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``control=None``: Control/widget style to construct when parameter widgets are created.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import parameter
        result = parameter(...)
    
    Discovery-oriented use::
    
        help(parameter)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(parameter)`` and inspect sibling APIs in the same module.
    """

    fig = _require_current_figure()
    return fig.parameters.parameter(symbols, control=control, **kwargs)


def plot(
    func: Any,
    var: Any,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    x_domain: tuple[int | float | str, int | float | str] | None = None,
    sampling_points: int | str | object | None = None,
    color: str | None = None,
    thickness: int | float | None = None,
    width: int | float | None = None,
    dash: str | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    line: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    autonormalization: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: PlotVarsSpec | None = None,
    samples: int | str | object | None = None,
) -> Plot:
    """Plot on the current figure, auto-creating one when needed.
    
    Full API
    --------
    ``plot(func: Any, var: Any, parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: bool=True, x_domain: tuple[int | float | str, int | float | str] | None=None, sampling_points: int | str | object | None=None, color: str | None=None, thickness: int | float | None=None, width: int | float | None=None, dash: str | None=None, opacity: int | float | None=None, alpha: int | float | None=None, line: Mapping[str, Any] | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, view: str | Sequence[str] | None=None, vars: PlotVarsSpec | None=None, samples: int | str | object | None=None) -> Plot``
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    var : Any
        Primary symbolic variable used for evaluation. Required.
    
    parameters : ParameterKeyOrKeys | None, optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``None``.
    
    id : str | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    label : str | None, optional
        Human-readable label used in UI or plotting output. Defaults to ``None``.
    
    visible : bool, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    x_domain : tuple[int | float | str, int | float | str] | None, optional
        Numeric x-domain used for evaluation or rendering. Defaults to ``None``.
    
    sampling_points : int | str | object | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    color : str | None, optional
        Explicit color value. Defaults to ``None``.
    
    thickness : int | float | None, optional
        Value for ``thickness`` in this API. Defaults to ``None``.
    
    width : int | float | None, optional
        Value for ``width`` in this API. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    alpha : int | float | None, optional
        Value for ``alpha`` in this API. Defaults to ``None``.
    
    line : Mapping[str, Any] | None, optional
        Value for ``line`` in this API. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    autonormalization : bool | None, optional
        Value for ``autonormalization`` in this API. Defaults to ``None``.
    
    view : str | Sequence[str] | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    vars : PlotVarsSpec | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    samples : int | str | object | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    Returns
    -------
    Plot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``parameters=None``: Parameter symbols/keys that should stay bound to this operation.
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``label=None``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
    - ``sampling_points=None``: Sampling density used when evaluating a curve or field.
    - ``color=None``: Explicit color value.
    - ``thickness=None``: Value for ``thickness`` in this API.
    - ``width=None``: Value for ``width`` in this API.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``alpha=None``: Value for ``alpha`` in this API.
    - ``line=None``: Value for ``line`` in this API.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``autonormalization=None``: Value for ``autonormalization`` in this API.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    - ``vars=None``: Value for ``vars`` in this API.
    - ``samples=None``: Sampling density used when evaluating a curve or field.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import plot
        result = plot(...)
    
    Discovery-oriented use::
    
        help(plot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(plot)`` and inspect sibling APIs in the same module.
    """
    fig = _current_figure()
    if fig is None:
        from .Figure import Figure

        fig = Figure()
        display(fig)
    return fig.plot(
        func,
        var,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        x_domain=x_domain,
        sampling_points=sampling_points,
        color=color,
        thickness=thickness,
        width=width,
        dash=dash,
        line=line,
        opacity=opacity,
        alpha=alpha,
        trace=trace,
        autonormalization=autonormalization,
        view=view,
        vars=vars,
        samples=samples,
    )


def parametric_plot(
    funcs: Sequence[Any],
    parameter_range: tuple[Any, Any, Any],
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    sampling_points: int | str | object | None = None,
    color: str | None = None,
    thickness: int | float | None = None,
    width: int | float | None = None,
    dash: str | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    line: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    autonormalization: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: PlotVarsSpec | None = None,
    samples: int | str | object | None = None,
) -> Plot:
    """Plot a parametric curve on the current figure.
    
    Full API
    --------
    ``parametric_plot(funcs: Sequence[Any], parameter_range: tuple[Any, Any, Any], parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: bool=True, sampling_points: int | str | object | None=None, color: str | None=None, thickness: int | float | None=None, width: int | float | None=None, dash: str | None=None, opacity: int | float | None=None, alpha: int | float | None=None, line: Mapping[str, Any] | None=None, trace: Mapping[str, Any] | None=None, autonormalization: bool | None=None, view: str | Sequence[str] | None=None, vars: PlotVarsSpec | None=None, samples: int | str | object | None=None) -> Plot``
    
    Parameters
    ----------
    funcs : Sequence[Any]
        Value for ``funcs`` in this API. Required.
    
    parameter_range : tuple[Any, Any, Any]
        Value for ``parameter_range`` in this API. Required.
    
    parameters : ParameterKeyOrKeys | None, optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``None``.
    
    id : str | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    label : str | None, optional
        Human-readable label used in UI or plotting output. Defaults to ``None``.
    
    visible : bool, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    sampling_points : int | str | object | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    color : str | None, optional
        Explicit color value. Defaults to ``None``.
    
    thickness : int | float | None, optional
        Value for ``thickness`` in this API. Defaults to ``None``.
    
    width : int | float | None, optional
        Value for ``width`` in this API. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    alpha : int | float | None, optional
        Value for ``alpha`` in this API. Defaults to ``None``.
    
    line : Mapping[str, Any] | None, optional
        Value for ``line`` in this API. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    autonormalization : bool | None, optional
        Value for ``autonormalization`` in this API. Defaults to ``None``.
    
    view : str | Sequence[str] | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    vars : PlotVarsSpec | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    samples : int | str | object | None, optional
        Sampling density used when evaluating a curve or field. Defaults to ``None``.
    
    Returns
    -------
    Plot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``parameters=None``: Parameter symbols/keys that should stay bound to this operation.
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``label=None``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``sampling_points=None``: Sampling density used when evaluating a curve or field.
    - ``color=None``: Explicit color value.
    - ``thickness=None``: Value for ``thickness`` in this API.
    - ``width=None``: Value for ``width`` in this API.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``alpha=None``: Value for ``alpha`` in this API.
    - ``line=None``: Value for ``line`` in this API.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``autonormalization=None``: Value for ``autonormalization`` in this API.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    - ``vars=None``: Value for ``vars`` in this API.
    - ``samples=None``: Sampling density used when evaluating a curve or field.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import parametric_plot
        result = parametric_plot(...)
    
    Discovery-oriented use::
    
        help(parametric_plot)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(parametric_plot)`` and inspect sibling APIs in the same module.
    """
    fig = _current_figure()
    if fig is None:
        from .Figure import Figure

        fig = Figure()
        display(fig)
    return fig.parametric_plot(
        funcs,
        parameter_range,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        sampling_points=sampling_points,
        color=color,
        thickness=thickness,
        width=width,
        dash=dash,
        opacity=opacity,
        alpha=alpha,
        line=line,
        trace=trace,
        autonormalization=autonormalization,
        view=view,
        vars=vars,
        samples=samples,
    )


def scalar_field(
    func: Any,
    x: Any,
    y: Any,
    parameters: ParameterKeyOrKeys | None = None,
    id: str | None = None,
    label: str | None = None,
    visible: bool = True,
    x_domain: tuple[int | float | str, int | float | str] | None = None,
    y_domain: tuple[int | float | str, int | float | str] | None = None,
    grid: tuple[int | str, int | str] | None = None,
    render_mode: str = "heatmap",
    preset: str | None = None,
    colorscale: Any | None = None,
    z_range: tuple[int | float | str, int | float | str] | None = None,
    z_step: int | float | None = None,
    under_color: str | None = None,
    over_color: str | None = None,
    show_colorbar: bool | None = None,
    opacity: int | float | None = None,
    alpha: int | float | None = None,
    reversescale: bool | None = None,
    colorbar: Mapping[str, Any] | None = None,
    trace: Mapping[str, Any] | None = None,
    levels: int | None = None,
    level_step: int | float | None = None,
    level_start: int | float | None = None,
    level_end: int | float | None = None,
    filled: bool | None = None,
    show_labels: bool | None = None,
    line_color: str | None = None,
    line_width: int | float | None = None,
    line_dash: str | None = None,
    dash: str | None = None,
    smoothing: str | bool | None = None,
    zsmooth: str | bool | None = None,
    connectgaps: bool | None = None,
    view: str | Sequence[str] | None = None,
    vars: Any | None = None,
) -> ScalarFieldPlot:
    """Plot a scalar field on the current figure, auto-creating one when needed.
    
    Full API
    --------
    ``scalar_field(func: Any, x: Any, y: Any, parameters: ParameterKeyOrKeys | None=None, id: str | None=None, label: str | None=None, visible: bool=True, x_domain: tuple[int | float | str, int | float | str] | None=None, y_domain: tuple[int | float | str, int | float | str] | None=None, grid: tuple[int | str, int | str] | None=None, render_mode: str='heatmap', preset: str | None=None, colorscale: Any | None=None, z_range: tuple[int | float | str, int | float | str] | None=None, z_step: int | float | None=None, under_color: str | None=None, over_color: str | None=None, show_colorbar: bool | None=None, opacity: int | float | None=None, alpha: int | float | None=None, reversescale: bool | None=None, colorbar: Mapping[str, Any] | None=None, trace: Mapping[str, Any] | None=None, levels: int | None=None, level_step: int | float | None=None, level_start: int | float | None=None, level_end: int | float | None=None, filled: bool | None=None, show_labels: bool | None=None, line_color: str | None=None, line_width: int | float | None=None, line_dash: str | None=None, dash: str | None=None, smoothing: str | bool | None=None, zsmooth: str | bool | None=None, connectgaps: bool | None=None, view: str | Sequence[str] | None=None, vars: Any | None=None) -> ScalarFieldPlot``
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    parameters : ParameterKeyOrKeys | None, optional
        Parameter symbols/keys that should stay bound to this operation. Defaults to ``None``.
    
    id : str | None, optional
        Stable identifier used to create, update, or look up the target object. Defaults to ``None``.
    
    label : str | None, optional
        Human-readable label used in UI or plotting output. Defaults to ``None``.
    
    visible : bool, optional
        Visibility flag for a plot, field, panel, or UI element. Defaults to ``True``.
    
    x_domain : tuple[int | float | str, int | float | str] | None, optional
        Numeric x-domain used for evaluation or rendering. Defaults to ``None``.
    
    y_domain : tuple[int | float | str, int | float | str] | None, optional
        Numeric y-domain used for evaluation or rendering. Defaults to ``None``.
    
    grid : tuple[int | str, int | str] | None, optional
        Grid resolution or grid specification used for field sampling. Defaults to ``None``.
    
    render_mode : str, optional
        Rendering mode or plot kind to create. Defaults to ``'heatmap'``.
    
    preset : str | None, optional
        Named preset that chooses a particular rendering style. Defaults to ``None``.
    
    colorscale : Any | None, optional
        Colorscale specification passed to the renderer. Defaults to ``None``.
    
    z_range : tuple[int | float | str, int | float | str] | None, optional
        Numeric value range used for scalar-field color mapping. Defaults to ``None``.
    
    z_step : int | float | None, optional
        Numeric spacing between scalar-field contour or color levels. Defaults to ``None``.
    
    under_color : str | None, optional
        Color used below the represented scalar range. Defaults to ``None``.
    
    over_color : str | None, optional
        Color used above the represented scalar range. Defaults to ``None``.
    
    show_colorbar : bool | None, optional
        Boolean flag controlling whether a colorbar is shown. Defaults to ``None``.
    
    opacity : int | float | None, optional
        Opacity value applied to the rendered output. Defaults to ``None``.
    
    alpha : int | float | None, optional
        Value for ``alpha`` in this API. Defaults to ``None``.
    
    reversescale : bool | None, optional
        Boolean flag controlling whether the colorscale is reversed. Defaults to ``None``.
    
    colorbar : Mapping[str, Any] | None, optional
        Renderer-specific colorbar configuration mapping. Defaults to ``None``.
    
    trace : Mapping[str, Any] | None, optional
        Renderer-specific trace configuration mapping. Defaults to ``None``.
    
    levels : int | None, optional
        Number of contour or scalar levels to generate. Defaults to ``None``.
    
    level_step : int | float | None, optional
        Spacing between contour or scalar levels. Defaults to ``None``.
    
    level_start : int | float | None, optional
        First contour/scalar level to include. Defaults to ``None``.
    
    level_end : int | float | None, optional
        Last contour/scalar level to include. Defaults to ``None``.
    
    filled : bool | None, optional
        Boolean flag controlling whether contour regions are filled. Defaults to ``None``.
    
    show_labels : bool | None, optional
        Boolean flag controlling whether labels are drawn on contour lines. Defaults to ``None``.
    
    line_color : str | None, optional
        Explicit line color for contour or curve rendering. Defaults to ``None``.
    
    line_width : int | float | None, optional
        Line width used for contour or curve rendering. Defaults to ``None``.
    
    line_dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    dash : str | None, optional
        Dash pattern used for contour or curve rendering. Defaults to ``None``.
    
    smoothing : str | bool | None, optional
        Smoothing option passed to the renderer or interpolation layer. Defaults to ``None``.
    
    zsmooth : str | bool | None, optional
        Value for ``zsmooth`` in this API. Defaults to ``None``.
    
    connectgaps : bool | None, optional
        Boolean flag controlling whether missing samples are connected. Defaults to ``None``.
    
    view : str | Sequence[str] | None, optional
        View identifier or view-scoped target. When omitted, the active view is used. Defaults to ``None``.
    
    vars : Any | None, optional
        Value for ``vars`` in this API. Defaults to ``None``.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``parameters=None``: Parameter symbols/keys that should stay bound to this operation.
    - ``id=None``: Stable identifier used to create, update, or look up the target object.
    - ``label=None``: Human-readable label used in UI or plotting output.
    - ``visible=True``: Visibility flag for a plot, field, panel, or UI element.
    - ``x_domain=None``: Numeric x-domain used for evaluation or rendering.
    - ``y_domain=None``: Numeric y-domain used for evaluation or rendering.
    - ``grid=None``: Grid resolution or grid specification used for field sampling.
    - ``render_mode='heatmap'``: Rendering mode or plot kind to create.
    - ``preset=None``: Named preset that chooses a particular rendering style.
    - ``colorscale=None``: Colorscale specification passed to the renderer.
    - ``z_range=None``: Numeric value range used for scalar-field color mapping.
    - ``z_step=None``: Numeric spacing between scalar-field contour or color levels.
    - ``under_color=None``: Color used below the represented scalar range.
    - ``over_color=None``: Color used above the represented scalar range.
    - ``show_colorbar=None``: Boolean flag controlling whether a colorbar is shown.
    - ``opacity=None``: Opacity value applied to the rendered output.
    - ``alpha=None``: Value for ``alpha`` in this API.
    - ``reversescale=None``: Boolean flag controlling whether the colorscale is reversed.
    - ``colorbar=None``: Renderer-specific colorbar configuration mapping.
    - ``trace=None``: Renderer-specific trace configuration mapping.
    - ``levels=None``: Number of contour or scalar levels to generate.
    - ``level_step=None``: Spacing between contour or scalar levels.
    - ``level_start=None``: First contour/scalar level to include.
    - ``level_end=None``: Last contour/scalar level to include.
    - ``filled=None``: Boolean flag controlling whether contour regions are filled.
    - ``show_labels=None``: Boolean flag controlling whether labels are drawn on contour lines.
    - ``line_color=None``: Explicit line color for contour or curve rendering.
    - ``line_width=None``: Line width used for contour or curve rendering.
    - ``line_dash=None``: Dash pattern used for contour or curve rendering.
    - ``dash=None``: Dash pattern used for contour or curve rendering.
    - ``smoothing=None``: Smoothing option passed to the renderer or interpolation layer.
    - ``zsmooth=None``: Value for ``zsmooth`` in this API.
    - ``connectgaps=None``: Boolean flag controlling whether missing samples are connected.
    - ``view=None``: View identifier or view-scoped target. When omitted, the active view is used.
    - ``vars=None``: Value for ``vars`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import scalar_field
        result = scalar_field(...)
    
    Discovery-oriented use::
    
        help(scalar_field)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(scalar_field)`` and inspect sibling APIs in the same module.
    """
    fig = _current_figure()
    if fig is None:
        from .Figure import Figure

        fig = Figure()
        display(fig)
    return fig.scalar_field(
        func,
        x,
        y,
        parameters=parameters,
        id=id,
        label=label,
        visible=visible,
        x_domain=x_domain,
        y_domain=y_domain,
        grid=grid,
        render_mode=render_mode,
        preset=preset,
        colorscale=colorscale,
        z_range=z_range,
        z_step=z_step,
        under_color=under_color,
        over_color=over_color,
        show_colorbar=show_colorbar,
        opacity=opacity,
        alpha=alpha,
        reversescale=reversescale,
        colorbar=colorbar,
        trace=trace,
        levels=levels,
        level_step=level_step,
        level_start=level_start,
        level_end=level_end,
        filled=filled,
        show_labels=show_labels,
        line_color=line_color,
        line_width=line_width,
        line_dash=line_dash,
        dash=dash,
        smoothing=smoothing,
        zsmooth=zsmooth,
        connectgaps=connectgaps,
        view=view,
        vars=vars,
    )


def contour(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Plot contour lines or filled contours on the current figure.
    
    Full API
    --------
    ``contour(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot``
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import contour
        result = contour(...)
    
    Discovery-oriented use::
    
        help(contour)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(contour)`` and inspect sibling APIs in the same module.
    """
    return scalar_field(func, x, y, render_mode="contour", **kwargs)


def density(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Plot a scalar field as a heatmap on the current figure.
    
    Full API
    --------
    ``density(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot``
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import density
        result = density(...)
    
    Discovery-oriented use::
    
        help(density)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(density)`` and inspect sibling APIs in the same module.
    """
    return scalar_field(func, x, y, render_mode="heatmap", **kwargs)


def temperature(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot:
    """Plot a scalar field with thermal heatmap defaults on the current figure.
    
    Full API
    --------
    ``temperature(func: Any, x: Any, y: Any, **kwargs: Any) -> ScalarFieldPlot``
    
    Parameters
    ----------
    func : Any
        Symbolic expression or callable to evaluate. Required.
    
    x : Any
        Primary symbolic variable or x-coordinate input. Required.
    
    y : Any
        Primary symbolic variable or y-coordinate input. Required.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    ScalarFieldPlot
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_api``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_api import temperature
        result = temperature(...)
    
    Discovery-oriented use::
    
        help(temperature)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(temperature)`` and inspect sibling APIs in the same module.
    """
    kwargs.setdefault("preset", "temperature")
    return scalar_field(func, x, y, render_mode="heatmap", **kwargs)


__all__ = [
    "get_default_samples",
    "get_default_x_range",
    "get_default_y_range",
    "get_samples",
    "get_sampling_points",
    "get_title",
    "get_x_range",
    "get_y_range",
    "info",
    "parameter",
    "parameters",
    "parametric_plot",
    "plot",
    "scalar_field",
    "contour",
    "density",
    "temperature",
    "plots",
    "plot_style_options",
    "field_style_options",
    "field_palette_options",
    "sound_generation_enabled",
    "render",
    "set_default_samples",
    "set_default_x_range",
    "set_default_y_range",
    "set_samples",
    "set_sampling_points",
    "set_title",
    "set_x_range",
    "set_y_range",
]
