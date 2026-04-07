"""Plot-style metadata and helpers shared by plotting APIs.

This module centralizes the public style contract accepted by
:meth:`gu_toolkit.Figure.Figure.plot` and the module-level :func:`plot`
helper.  The contract is represented as structured metadata so the package can
derive human-readable help text, alias resolution, and lightweight validation
from one source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlotStyleSpec:
    """Structured metadata describing one accepted plot-style keyword.
    
    Full API
    --------
    ``PlotStyleSpec(name: str, aliases: tuple[str, Ellipsis]=(), type_doc: str='', default_doc: str='', description: str='', accepted_values: tuple[str, Ellipsis]=())``
    
    Public members exposed from this class: ``format_help``, ``format_alias_help``
    
    Parameters
    ----------
    name : str
        Human-readable or canonical name for the target object. Required.
    
    aliases : tuple[str, Ellipsis], optional
        Value for ``aliases`` in this API. Defaults to ``()``.
    
    type_doc : str, optional
        Value for ``type_doc`` in this API. Defaults to ``''``.
    
    default_doc : str, optional
        Value for ``default_doc`` in this API. Defaults to ``''``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    accepted_values : tuple[str, Ellipsis], optional
        Value for ``accepted_values`` in this API. Defaults to ``()``.
    
    Returns
    -------
    PlotStyleSpec
        New ``PlotStyleSpec`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``aliases=()``: Value for ``aliases`` in this API.
    - ``type_doc=''``: Value for ``type_doc`` in this API.
    - ``default_doc=''``: Value for ``default_doc`` in this API.
    - ``description=''``: Value for ``description`` in this API.
    - ``accepted_values=()``: Value for ``accepted_values`` in this API.
    
    Architecture note
    -----------------
    ``PlotStyleSpec`` lives in ``gu_toolkit.figure_plot_style``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_plot_style import PlotStyleSpec
        obj = PlotStyleSpec(...)
    
    Discovery-oriented use::
    
        help(PlotStyleSpec)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(PlotStyleSpec)`` and ``dir(PlotStyleSpec)`` to inspect adjacent members.
    """

    name: str
    aliases: tuple[str, ...] = ()
    type_doc: str = ""
    default_doc: str = ""
    description: str = ""
    accepted_values: tuple[str, ...] = ()

    def format_help(self) -> str:
        """Return the user-facing help text for the canonical keyword.
        
        Full API
        --------
        ``obj.format_help() -> str``
        
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
        This member belongs to ``PlotStyleSpec``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotStyleSpec(...)
            result = obj.format_help(...)
        
        Discovery-oriented use::
        
            help(PlotStyleSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(PlotStyleSpec)`` and ``dir(PlotStyleSpec)`` to inspect adjacent members.
        """
        parts: list[str] = [self.description.rstrip(".") + "."] if self.description else []
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(self.accepted_values) + "."
            )
        if self.aliases:
            alias_word = "Alias" if len(self.aliases) == 1 else "Aliases"
            parts.append(f"{alias_word}: {', '.join(self.aliases)}.")
        if self.type_doc:
            parts.append(f"Type: {self.type_doc}.")
        if self.default_doc:
            parts.append(f"Default: {self.default_doc}.")
        return " ".join(parts)

    def format_alias_help(self, alias: str) -> str:
        """Return help text for one alias keyword.
        
        Full API
        --------
        ``obj.format_alias_help(alias: str) -> str``
        
        Parameters
        ----------
        alias : str
            Value for ``alias`` in this API. Required.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``PlotStyleSpec``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = PlotStyleSpec(...)
            result = obj.format_alias_help(...)
        
        Discovery-oriented use::
        
            help(PlotStyleSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/legend-plot-editor.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
        - In a notebook or REPL, run ``help(PlotStyleSpec)`` and ``dir(PlotStyleSpec)`` to inspect adjacent members.
        """
        alias_name = str(alias)
        if alias_name not in self.aliases:
            raise KeyError(f"{alias_name!r} is not an alias of {self.name!r}")
        parts = [f"Alias for {self.name}."]
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(self.accepted_values) + "."
            )
        if self.type_doc:
            parts.append(f"Type: {self.type_doc}.")
        if self.default_doc:
            parts.append(f"Default: {self.default_doc}.")
        return " ".join(parts)


PLOT_STYLE_OPTIONS: tuple[PlotStyleSpec, ...] = (
    PlotStyleSpec(
        name="color",
        type_doc="str | None",
        default_doc="Plotly/default colorway",
        description=(
            "Line color. Accepts CSS-like names (for example red), hex"
            " strings such as #RRGGBB, or rgb()/rgba() strings"
        ),
    ),
    PlotStyleSpec(
        name="thickness",
        aliases=("width",),
        type_doc="int | float | None",
        default_doc="Plotly line width",
        description="Line width in pixels. Larger values draw thicker lines",
    ),
    PlotStyleSpec(
        name="dash",
        type_doc="str | None",
        default_doc="solid",
        description="Line pattern",
        accepted_values=(
            "solid",
            "dot",
            "dash",
            "longdash",
            "dashdot",
            "longdashdot",
        ),
    ),
    PlotStyleSpec(
        name="opacity",
        aliases=("alpha",),
        type_doc="int | float | None",
        default_doc="1.0 / Plotly default trace opacity",
        description=(
            "Overall trace opacity from 0.0 (fully transparent) to 1.0"
            " (fully opaque)"
        ),
    ),
    PlotStyleSpec(
        name="line",
        type_doc="Mapping[str, Any] | None",
        default_doc="no extra line overrides",
        description="Extra line-style fields as a mapping for advanced per-line styling",
    ),
    PlotStyleSpec(
        name="trace",
        type_doc="Mapping[str, Any] | None",
        default_doc="no extra trace overrides",
        description="Extra full-trace fields as a mapping for advanced Plotly styling",
    ),
    PlotStyleSpec(
        name="autonormalization",
        type_doc="bool | None",
        default_doc="False / disabled",
        description=(
            "Per-plot sound setting. When enabled, playback automatically"
            " scales chunks whose absolute peak exceeds 1.0 back into"
            " [-1, 1] instead of raising an error"
        ),
    ),
)

_PLOT_STYLE_SPEC_BY_NAME = {spec.name: spec for spec in PLOT_STYLE_OPTIONS}
_PLOT_STYLE_ALIAS_TO_CANONICAL = {
    alias: spec.name for spec in PLOT_STYLE_OPTIONS for alias in spec.aliases
}


def plot_style_option_docs(*, include_aliases: bool = True) -> dict[str, str]:
    """Return discoverability text for accepted plot-style keywords.
    
    Full API
    --------
    ``plot_style_option_docs(*, include_aliases: bool=True) -> dict[str, str]``
    
    Parameters
    ----------
    include_aliases : bool, optional
        Value for ``include_aliases`` in this API. Defaults to ``True``.
    
    Returns
    -------
    dict[str, str]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``include_aliases=True``: Value for ``include_aliases`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_style``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_style import plot_style_option_docs
        result = plot_style_option_docs(...)
    
    Discovery-oriented use::
    
        help(plot_style_option_docs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(plot_style_option_docs)`` and inspect sibling APIs in the same module.
    """
    docs: dict[str, str] = {}
    for spec in PLOT_STYLE_OPTIONS:
        docs[spec.name] = spec.format_help()
        if include_aliases:
            for alias in spec.aliases:
                docs[alias] = spec.format_alias_help(alias)
    return docs


def resolve_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "plot()"
) -> dict[str, Any]:
    """Resolve alias keywords in ``style_kwargs`` into canonical names.
    
    Full API
    --------
    ``resolve_style_kwargs(style_kwargs: dict[str, Any], *, caller: str='plot()') -> dict[str, Any]``
    
    Parameters
    ----------
    style_kwargs : dict[str, Any]
        Value for ``style_kwargs`` in this API. Required.
    
    caller : str, optional
        Value for ``caller`` in this API. Defaults to ``'plot()'``.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``caller='plot()'``: Value for ``caller`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_style``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_style import resolve_style_kwargs
        result = resolve_style_kwargs(...)
    
    Discovery-oriented use::
    
        help(resolve_style_kwargs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(resolve_style_kwargs)`` and inspect sibling APIs in the same module.
    """
    resolved = dict(style_kwargs)

    for spec in PLOT_STYLE_OPTIONS:
        candidates = [
            (name, resolved[name])
            for name in (spec.name, *spec.aliases)
            if name in resolved and resolved[name] is not None
        ]
        if len(candidates) > 1:
            canonical_value = candidates[0][1]
            for other_name, other_value in candidates[1:]:
                if other_value != canonical_value:
                    raise ValueError(
                        f"{caller} received both {spec.name}= and {other_name}= "
                        "with different values; use only one."
                    )
        if candidates:
            resolved[spec.name] = candidates[0][1]
        for alias in spec.aliases:
            resolved.pop(alias, None)

    return resolved


def validate_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "plot()"
) -> dict[str, Any]:
    """Resolve aliases and validate metadata-driven style constraints.
    
    Full API
    --------
    ``validate_style_kwargs(style_kwargs: dict[str, Any], *, caller: str='plot()') -> dict[str, Any]``
    
    Parameters
    ----------
    style_kwargs : dict[str, Any]
        Value for ``style_kwargs`` in this API. Required.
    
    caller : str, optional
        Value for ``caller`` in this API. Defaults to ``'plot()'``.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``caller='plot()'``: Value for ``caller`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_style``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_style import validate_style_kwargs
        result = validate_style_kwargs(...)
    
    Discovery-oriented use::
    
        help(validate_style_kwargs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(validate_style_kwargs)`` and inspect sibling APIs in the same module.
    """
    resolved = resolve_style_kwargs(style_kwargs, caller=caller)
    for name, value in tuple(resolved.items()):
        spec = _PLOT_STYLE_SPEC_BY_NAME.get(name)
        if spec is None or value is None or not spec.accepted_values:
            continue
        if value not in spec.accepted_values:
            allowed = ", ".join(spec.accepted_values)
            raise ValueError(
                f"{caller} received invalid {name}={value!r}. "
                f"Supported values: {allowed}."
            )
    return resolved


def resolve_style_aliases(
    *,
    thickness: int | float | None,
    width: int | float | None,
    opacity: int | float | None,
    alpha: int | float | None,
    caller: str = "plot()",
) -> tuple[int | float | None, int | float | None]:
    """Resolve supported alias pairs into canonical values.
    
    Full API
    --------
    ``resolve_style_aliases(*, thickness: int | float | None, width: int | float | None, opacity: int | float | None, alpha: int | float | None, caller: str='plot()') -> tuple[int | float | None, int | float | None]``
    
    Parameters
    ----------
    thickness : int | float | None
        Value for ``thickness`` in this API. Required.
    
    width : int | float | None
        Value for ``width`` in this API. Required.
    
    opacity : int | float | None
        Opacity value applied to the rendered output. Required.
    
    alpha : int | float | None
        Value for ``alpha`` in this API. Required.
    
    caller : str, optional
        Value for ``caller`` in this API. Defaults to ``'plot()'``.
    
    Returns
    -------
    tuple[int | float | None, int | float | None]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``caller='plot()'``: Value for ``caller`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_plot_style``. Cartesian plotting routes through normalization and style metadata before traces are sampled and rendered, so validation, legends, and code generation stay aligned.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_plot_style import resolve_style_aliases
        result = resolve_style_aliases(...)
    
    Discovery-oriented use::
    
        help(resolve_style_aliases)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/legend-plot-editor.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``plot_style_options()`` and inspect ``Figure.plot`` to see the supported cartesian-curve options.
    - In a notebook or REPL, run ``help(resolve_style_aliases)`` and inspect sibling APIs in the same module.
    """
    resolved = resolve_style_kwargs(
        {
            "thickness": thickness,
            "width": width,
            "opacity": opacity,
            "alpha": alpha,
        },
        caller=caller,
    )
    return resolved.get("thickness"), resolved.get("opacity")


__all__ = [
    "PLOT_STYLE_OPTIONS",
    "PlotStyleSpec",
    "plot_style_option_docs",
    "resolve_style_aliases",
    "resolve_style_kwargs",
    "validate_style_kwargs",
]
