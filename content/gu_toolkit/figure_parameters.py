"""Parameter manager for Figure.

Parameter identity is name-authoritative: the canonical key for a parameter is
its string name (``symbol.name``). SymPy symbols remain accepted throughout the
API, but are normalized to their name before lookup, storage, or snapshotting.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Hashable, Iterator, Mapping
from typing import Any

from ._widget_stubs import widgets
import sympy as sp
from sympy.core.symbol import Symbol

from .ParameterSnapshot import ParameterSnapshot, ParameterValueSnapshot
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .Slider import FloatSlider
from .performance_monitor import PerformanceMonitor, format_performance_snapshot
from .parameter_keys import (
    ParameterKey,
    ParameterKeyOrKeys,
    normalize_parameter_sequence,
    parameter_name,
    parameter_symbol,
)


class _ParameterContextView(Mapping[str, Any]):
    """Live name-keyed view over parameter values.

    Symbol keys remain accepted as aliases. Iteration exposes canonical string
    names because parameter names are the authoritative identifiers.
    """

    def __init__(self, refs: Mapping[str, ParamRef]) -> None:
        self._refs = refs

    def __getitem__(self, key: ParameterKey) -> Any:
        return self._refs[parameter_name(key, role="parameter")].value

    def __iter__(self) -> Iterator[str]:
        return iter(self._refs)

    def __len__(self) -> int:
        return len(self._refs)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - simple
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._refs


class _RenderParameterContext(Mapping[str, Any]):
    """Stable snapshot-backed parameter provider reused across render passes."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def replace(self, values: Mapping[ParameterKey, Any]) -> None:
        """Replace the stored snapshot with a detached copy of ``values``.
        
        Full API
        --------
        ``obj.replace(values: Mapping[ParameterKey, Any]) -> None``
        
        Parameters
        ----------
        values : Mapping[ParameterKey, Any]
            Value for ``values`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``_RenderParameterContext``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = _RenderParameterContext(...)
            obj.replace(...)
        
        Discovery-oriented use::
        
            help(_RenderParameterContext)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(_RenderParameterContext)`` and ``dir(_RenderParameterContext)`` to inspect adjacent members.
        """
        self._values.clear()
        for raw_key, value in values.items():
            self._values[parameter_name(raw_key, role="parameter")] = value

    def __getitem__(self, key: ParameterKey) -> Any:
        return self._values[parameter_name(key, role="parameter")]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - simple
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._values

    def __repr__(self) -> str:
        return f"_RenderParameterContext({self._values!r})"


# SECTION: ParameterManager (The Model for Parameters) [id: ParameterManager]
# =============================================================================


class ParameterManager(Mapping[str, ParamRef]):
    """Manage parameter controls, refs, snapshots, and hooks.
    
    Full API
    --------
    ``ParameterManager(render_callback: Callable[[str, ParamEvent], None], layout_box: widgets.Box, modal_host: widgets.Box | None=None)``
    
    Public members exposed from this class: ``parameter``, ``snapshot``, ``parameter_context``, ``render_parameter_context``,
        ``refresh_render_parameter_context``, ``performance_snapshot``,
        ``performance_report``, ``has_params``, ``add_hook``, ``fire_hook``, ``get_hooks``,
        ``items``, ``keys``, ``symbols``, ``symbol_for_name``, ``values``, ``get``,
        ``widget``, ``widgets``
    
    Parameters
    ----------
    render_callback : Callable[[str, ParamEvent], None]
        Value for ``render_callback`` in this API. Required.
    
    layout_box : widgets.Box
        Value for ``layout_box`` in this API. Required.
    
    modal_host : widgets.Box | None, optional
        Value for ``modal_host`` in this API. Defaults to ``None``.
    
    Returns
    -------
    ParameterManager
        New ``ParameterManager`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``modal_host=None``: Value for ``modal_host`` in this API.
    
    Architecture note
    -----------------
    ``ParameterManager`` lives in ``gu_toolkit.figure_parameters``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_parameters import ParameterManager
        obj = ParameterManager(...)
    
    Discovery-oriented use::
    
        help(ParameterManager)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
    """

    def __init__(
        self,
        render_callback: Callable[[str, ParamEvent], None],
        layout_box: widgets.Box,
        modal_host: widgets.Box | None = None,
    ) -> None:
        self._refs: dict[str, ParamRef] = {}
        self._symbols: dict[str, Symbol] = {}
        self._parameter_context_view = _ParameterContextView(self._refs)
        self._render_parameter_context = _RenderParameterContext()
        self._controls: list[Any] = []
        self._hooks: dict[Hashable, Callable[[ParamEvent], Any]] = {}
        self._hook_counter: int = 0
        self._render_callback = render_callback
        self._layout_box = layout_box
        self._modal_host = modal_host
        self._performance = PerformanceMonitor("ParameterManager")
        self._performance.increment("created")
        self._performance.set_state(parameter_count=0, control_count=0, hook_count=0)

    def _resolve_name(self, key: ParameterKey) -> str:
        name = parameter_name(key, role="parameter")
        if name not in self._refs:
            raise KeyError(name)
        return name

    @staticmethod
    def _lookup_control_ref(
        refs: Mapping[object, ParamRef],
        *,
        name: str,
        symbol: Symbol,
    ) -> ParamRef:
        """Extract the control ref for ``name`` from a custom control mapping."""
        if name in refs:
            ref = refs[name]
        elif symbol in refs:
            ref = refs[symbol]
        else:
            matches: list[ParamRef] = []
            for raw_key, ref_candidate in refs.items():
                try:
                    raw_name = parameter_name(raw_key, role="parameter")  # type: ignore[arg-type]
                except TypeError:
                    continue
                if raw_name == name:
                    matches.append(ref_candidate)
            if not matches:
                raise KeyError(
                    f"Control did not provide a ref for parameter {name!r}."
                )
            if len(matches) > 1 and len({id(ref) for ref in matches}) > 1:
                raise KeyError(
                    f"Control provided multiple refs for parameter name {name!r}."
                )
            ref = matches[0]

        ref_symbol = getattr(ref, "parameter", symbol)
        if isinstance(ref_symbol, Symbol) and ref_symbol.name != name:
            raise ValueError(
                f"Control ref parameter {ref_symbol!r} does not match requested name {name!r}."
            )
        return ref

    def parameter(
        self,
        symbols: ParameterKeyOrKeys,
        *,
        control: Any | None = None,
        **control_kwargs: Any,
    ) -> ParamRef | dict[str, ParamRef]:
        """Create or reuse parameter references for the given keys.
        
        Full API
        --------
        ``obj.parameter(symbols: ParameterKeyOrKeys, *, control: Any | None=None, **control_kwargs: Any) -> ParamRef | dict[str, ParamRef]``
        
        Parameters
        ----------
        symbols : ParameterKeyOrKeys
            Parameter symbols, names, or other accepted parameter keys. Required.
        
        control : Any | None, optional
            Control/widget style to construct when parameter widgets are created. Defaults to ``None``.
        
        **control_kwargs : Any, optional
            Additional keyword arguments forwarded by this API. Optional variadic input.
        
        Returns
        -------
        ParamRef | dict[str, ParamRef]
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``control=None``: Control/widget style to construct when parameter widgets are created.
        - ``**control_kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.parameter(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        started = time.perf_counter()
        requested, single = normalize_parameter_sequence(symbols, role="parameter")
        self._performance.increment("parameter_calls")
        self._performance.set_state(last_requested=[name for name, _symbol in requested])

        existing = [(name, symbol) for name, symbol in requested if name in self._refs]
        missing = [(name, symbol) for name, symbol in requested if name not in self._refs]

        if control is not None and existing:
            for name, _symbol in existing:
                if self._refs[name].widget is not control:
                    raise ValueError(
                        f"Parameter {name!r} is already bound to a different control."
                    )

        if existing:
            self._performance.increment("parameters_reused", delta=len(existing))

        defaults = {"value": 0.0, "min": -1.0, "max": 1.0, "step": 0.01}

        if control is None:
            for name, symbol in missing:
                config = {**defaults, **control_kwargs}
                new_control = FloatSlider(
                    description=f"${sp.latex(symbol)}$",
                    accessibility_label=f"Parameter {symbol.name}",
                    value=float(config["value"]),
                    min=float(config["min"]),
                    max=float(config["max"]),
                    step=float(config["step"]),
                )
                self._attach_modal_host(new_control)
                refs = new_control.make_refs([symbol])
                ref = self._lookup_control_ref(refs, name=name, symbol=symbol)
                ref.observe(self._on_param_change)
                self._refs[name] = ref
                self._symbols.setdefault(name, symbol)
                self._performance.increment("parameters_created")
                if new_control not in self._controls:
                    self._controls.append(new_control)
                    self._layout_box.children += (new_control,)
                    self._performance.increment("controls_created")
        elif missing:
            self._attach_modal_host(control)
            refs = control.make_refs([symbol for _, symbol in missing])
            for name, symbol in missing:
                ref = self._lookup_control_ref(refs, name=name, symbol=symbol)
                ref.observe(self._on_param_change)
                self._refs[name] = ref
                self._symbols.setdefault(name, symbol)
                self._performance.increment("parameters_created")
            if control not in self._controls:
                self._controls.append(control)
                self._layout_box.children += (control,)
                self._performance.increment("custom_controls_bound")

        for name, symbol in requested:
            ref = self._refs[name]
            self._symbols.setdefault(name, symbol)
            for attr_name, value in control_kwargs.items():
                setattr(ref, attr_name, value)

        self._performance.set_state(
            parameter_count=len(self._refs),
            control_count=len(self._controls),
            hook_count=len(self._hooks),
        )
        self._performance.record_duration(
            "parameter_bind_ms",
            (time.perf_counter() - started) * 1000.0,
            requested_count=len(requested),
            missing_count=len(missing),
            existing_count=len(existing),
        )

        if single:
            return self._refs[requested[0][0]]
        return {name: self._refs[name] for name, _ in requested}

    def _attach_modal_host(self, control: Any) -> None:
        """Attach modal host to controls that support it."""
        if self._modal_host is None:
            return
        attach_fn = getattr(control, "set_modal_host", None)
        if callable(attach_fn):
            attach_fn(self._modal_host)

    def snapshot(
        self, *, full: bool = False
    ) -> ParameterValueSnapshot | ParameterSnapshot:
        """Return parameter values or a full immutable metadata snapshot.
        
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
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.snapshot(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        entries: dict[str, dict[str, Any]] = {}
        for name, ref in self._refs.items():
            entry: dict[str, Any] = {"value": ref.value}
            caps = list(ref.capabilities)
            entry["capabilities"] = caps
            for cap_name in caps:
                entry[cap_name] = getattr(ref, cap_name)
            entries[name] = entry

        snapshot = ParameterSnapshot(entries, symbols=self._symbols)
        if full:
            return snapshot
        return snapshot.value_map()

    @property
    def parameter_context(self) -> Mapping[str, Any]:
        """Live name-keyed view for numeric evaluation contexts.
        
        Full API
        --------
        ``obj.parameter_context -> Mapping[str, Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Mapping[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            current = obj.parameter_context
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return self._parameter_context_view

    @property
    def render_parameter_context(self) -> Mapping[str, Any]:
        """Stable snapshot-backed mapping used during actual renders.
        
        Full API
        --------
        ``obj.render_parameter_context -> Mapping[str, Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Mapping[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            current = obj.render_parameter_context
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return self._render_parameter_context

    def refresh_render_parameter_context(self) -> Mapping[str, Any]:
        """Capture current live values into the reusable render provider.
        
        Full API
        --------
        ``obj.refresh_render_parameter_context() -> Mapping[str, Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Mapping[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.refresh_render_parameter_context(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        started = time.perf_counter()
        self._render_parameter_context.replace(
            {name: ref.value for name, ref in self._refs.items()}
        )
        self._performance.increment("render_context_refreshes")
        self._performance.record_duration(
            "render_context_refresh_ms",
            (time.perf_counter() - started) * 1000.0,
            parameter_count=len(self._refs),
        )
        return self._render_parameter_context

    def _control_snapshot(self, control: Any) -> dict[str, Any]:
        capabilities: dict[str, Any] = {}
        control_ref = None
        for ref in self._refs.values():
            if getattr(ref, "widget", None) is control:
                control_ref = ref
                break
        if control_ref is not None:
            caps = list(getattr(control_ref, "capabilities", ()))
            for cap_name in caps:
                try:
                    capabilities[cap_name] = getattr(control_ref, cap_name)
                except Exception as exc:  # pragma: no cover - defensive diagnostics
                    capabilities[cap_name] = f"<error: {exc}>"
        animation = getattr(control, "_animation", None)
        snapshot = {
            "widget_type": type(control).__name__,
            "value": getattr(control, "value", None),
            "description": getattr(control, "description", None),
            "capabilities": capabilities,
            "animation_running": getattr(control, "animation_running", None),
            "animation_mode": getattr(control, "animation_mode", None),
            "animation_time": getattr(control, "animation_time", None),
        }
        if animation is not None and hasattr(animation, "performance_snapshot"):
            try:
                snapshot["animation"] = animation.performance_snapshot(recent_event_limit=5)
            except Exception as exc:  # pragma: no cover - defensive diagnostics
                snapshot["animation"] = {"error": str(exc)}
        return snapshot

    def performance_snapshot(self, *, recent_event_limit: int = 25) -> dict[str, Any]:
        """Work with performance snapshot on ``ParameterManager``.
        
        Full API
        --------
        ``obj.performance_snapshot(*, recent_event_limit: int=25) -> dict[str, Any]``
        
        Parameters
        ----------
        recent_event_limit : int, optional
            Value for ``recent_event_limit`` in this API. Defaults to ``25``.
        
        Returns
        -------
        dict[str, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_event_limit=25``: Value for ``recent_event_limit`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.performance_snapshot(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """

        snapshot = self._performance.snapshot(recent_limit=recent_event_limit)
        snapshot["controls"] = {
            name: self._control_snapshot(ref.widget)
            for name, ref in self._refs.items()
        }
        snapshot["hook_ids"] = [str(hook_id) for hook_id in self._hooks]
        return snapshot

    def performance_report(self, *, recent_event_limit: int = 10) -> str:
        """Work with performance report on ``ParameterManager``.
        
        Full API
        --------
        ``obj.performance_report(*, recent_event_limit: int=10) -> str``
        
        Parameters
        ----------
        recent_event_limit : int, optional
            Value for ``recent_event_limit`` in this API. Defaults to ``10``.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``recent_event_limit=10``: Value for ``recent_event_limit`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.performance_report(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """

        sections = [
            format_performance_snapshot(
                self.performance_snapshot(recent_event_limit=recent_event_limit),
                title="Parameter manager",
            )
        ]
        for name, ref in self._refs.items():
            widget = getattr(ref, "widget", None)
            animation = getattr(widget, "_animation", None)
            if animation is not None and hasattr(animation, "performance_snapshot"):
                sections.append(
                    format_performance_snapshot(
                        animation.performance_snapshot(recent_event_limit=recent_event_limit),
                        title=f"Parameter animation {name}",
                    )
                )
        return "\n\n".join(section for section in sections if section)

    @property
    def has_params(self) -> bool:
        """Whether any parameters have been created.
        
        Full API
        --------
        ``obj.has_params -> bool``
        
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
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            current = obj.has_params
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return len(self._refs) > 0

    def add_hook(
        self,
        callback: Callable[[ParamEvent | None], Any],
        hook_id: Hashable | None = None,
    ) -> Hashable:
        """Register a parameter change hook.
        
        Full API
        --------
        ``obj.add_hook(callback: Callable[[ParamEvent | None], Any], hook_id: Hashable | None=None) -> Hashable``
        
        Parameters
        ----------
        callback : Callable[[ParamEvent | None], Any]
            Callable that is invoked when the relevant event fires. Required.
        
        hook_id : Hashable | None, optional
            Value for ``hook_id`` in this API. Defaults to ``None``.
        
        Returns
        -------
        Hashable
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``hook_id=None``: Value for ``hook_id`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.add_hook(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        if hook_id is None:
            self._hook_counter += 1
            hook_id = f"hook:{self._hook_counter}"
        elif isinstance(hook_id, str):
            match = re.fullmatch(r"hook:(\d+)", hook_id)
            if match is not None:
                self._hook_counter = max(self._hook_counter, int(match.group(1)))
        self._hooks[hook_id] = callback
        self._performance.increment("hooks_registered")
        self._performance.set_state(hook_count=len(self._hooks))
        return hook_id

    def fire_hook(self, hook_id: Hashable, event: ParamEvent | None) -> None:
        """Fire a specific hook with a ParamEvent.
        
        Full API
        --------
        ``obj.fire_hook(hook_id: Hashable, event: ParamEvent | None) -> None``
        
        Parameters
        ----------
        hook_id : Hashable
            Value for ``hook_id`` in this API. Required.
        
        event : ParamEvent | None
            Event object describing what changed. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            obj.fire_hook(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        callback = self._hooks.get(hook_id)
        if callback is None:
            self._performance.increment("hook_misses")
            return
        started = time.perf_counter()
        try:
            callback(event)
        except Exception:
            self._performance.increment("hook_failures")
            raise
        finally:
            self._performance.record_duration(
                "hook_callback_ms",
                (time.perf_counter() - started) * 1000.0,
                hook_id=str(hook_id),
            )

    def _on_param_change(self, event: ParamEvent) -> None:
        """Handle parameter changes by triggering the render callback."""
        started = time.perf_counter()
        self._performance.increment("param_changes")
        self._performance.set_state(
            last_param_change_name=getattr(getattr(event, "parameter", None), "name", None),
            last_param_change_old=getattr(event, "old", None),
            last_param_change_new=getattr(event, "new", None),
        )
        try:
            self._render_callback("param_change", event)
        except Exception:
            self._performance.increment("render_callback_failures")
            raise
        finally:
            self._performance.record_duration(
                "render_callback_ms",
                (time.perf_counter() - started) * 1000.0,
                event_type=type(event).__name__,
            )

    def get_hooks(self) -> dict[Hashable, Callable]:
        """Return a shallow copy of the registered hook dictionary.
        
        Full API
        --------
        ``obj.get_hooks() -> dict[Hashable, Callable]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        dict[Hashable, Callable]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.get_hooks(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return self._hooks.copy()

    def __getitem__(self, key: ParameterKey) -> ParamRef:
        """Return the param ref for ``key`` (string-authoritative)."""
        return self._refs[self._resolve_name(key)]

    def __contains__(self, key: object) -> bool:  # pragma: no cover - simple
        try:
            name = parameter_name(key, role="parameter")  # type: ignore[arg-type]
        except TypeError:
            return False
        return name in self._refs

    def items(self) -> Iterator[tuple[str, ParamRef]]:
        """Iterate over ``(name, ParamRef)`` pairs.
        
        Full API
        --------
        ``obj.items() -> Iterator[tuple[str, ParamRef]]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Iterator[tuple[str, ParamRef]]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.items(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return iter(self._refs.items())

    def keys(self) -> Iterator[str]:
        """Iterate over canonical parameter names.
        
        Full API
        --------
        ``obj.keys() -> Iterator[str]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Iterator[str]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.keys(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return iter(self._refs.keys())

    def symbols(self) -> tuple[Symbol, ...]:
        """Return canonical symbols in insertion order.
        
        Full API
        --------
        ``obj.symbols() -> tuple[Symbol, ...]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        tuple[Symbol, Ellipsis]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.symbols(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return tuple(self._symbols[name] for name in self._refs)

    def symbol_for_name(self, key: ParameterKey) -> Symbol:
        """Return the representative symbol registered for ``key``.
        
        Full API
        --------
        ``obj.symbol_for_name(key: ParameterKey) -> Symbol``
        
        Parameters
        ----------
        key : ParameterKey
            Value for ``key`` in this API. Required.
        
        Returns
        -------
        Symbol
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.symbol_for_name(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        name = self._resolve_name(key)
        return self._symbols[name]

    def values(self) -> Iterator[ParamRef]:
        """Iterate over parameter refs.
        
        Full API
        --------
        ``obj.values() -> Iterator[ParamRef]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        Iterator[ParamRef]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.values(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return iter(self._refs.values())

    def get(self, key: ParameterKey, default: Any = None) -> Any:
        """Return a param ref if present; otherwise return ``default``.
        
        Full API
        --------
        ``obj.get(key: ParameterKey, default: Any=None) -> Any``
        
        Parameters
        ----------
        key : ParameterKey
            Value for ``key`` in this API. Required.
        
        default : Any, optional
            Value for ``default`` in this API. Defaults to ``None``.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        - ``default=None``: Value for ``default`` in this API.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.get(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        try:
            name = parameter_name(key, role="parameter")
        except TypeError:
            return default
        return self._refs.get(name, default)

    def __iter__(self) -> Iterator[str]:
        """Iterate over canonical parameter names."""
        return iter(self._refs)

    def __len__(self) -> int:
        """Return the number of stored parameter refs."""
        return len(self._refs)

    def widget(self, symbol: ParameterKey) -> Any:
        """Return the widget/control for ``symbol`` or parameter name.
        
        Full API
        --------
        ``obj.widget(symbol: ParameterKey) -> Any``
        
        Parameters
        ----------
        symbol : ParameterKey
            Value for ``symbol`` in this API. Required.
        
        Returns
        -------
        Any
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.widget(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return self[self._resolve_name(symbol)].widget

    def widgets(self) -> list[Any]:
        """Return unique widgets/controls suitable for display.
        
        Full API
        --------
        ``obj.widgets() -> list[Any]``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        list[Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``ParameterManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = ParameterManager(...)
            result = obj.widgets(...)
        
        Discovery-oriented use::
        
            help(ParameterManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(ParameterManager)`` and ``dir(ParameterManager)`` to inspect adjacent members.
        """
        return list(self._controls)


# =============================================================================
