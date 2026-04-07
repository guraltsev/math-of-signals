"""Style metadata and validation helpers for scalar-field plotting APIs.

The scalar-field subsystem accepts a separate, field-oriented style contract
from line plots. This module mirrors :mod:`gu_toolkit.figure_plot_style` so the
public API, discoverability helpers, and lightweight validation all derive from
one source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plotly.colors import named_colorscales


@dataclass(frozen=True)
class FieldPaletteSpec:
    """Structured metadata for one curated scalar-field palette name.
    
    Full API
    --------
    ``FieldPaletteSpec(name: str, colorscale: str | tuple[tuple[float, str], Ellipsis], aliases: tuple[str, Ellipsis]=(), description: str='', best_for: str='')``
    
    Public members exposed from this class: ``format_help``, ``format_alias_help``
    
    Parameters
    ----------
    name : str
        Human-readable or canonical name for the target object. Required.
    
    colorscale : str | tuple[tuple[float, str], Ellipsis]
        Colorscale specification passed to the renderer. Required.
    
    aliases : tuple[str, Ellipsis], optional
        Value for ``aliases`` in this API. Defaults to ``()``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``''``.
    
    best_for : str, optional
        Value for ``best_for`` in this API. Defaults to ``''``.
    
    Returns
    -------
    FieldPaletteSpec
        New ``FieldPaletteSpec`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``aliases=()``: Value for ``aliases`` in this API.
    - ``description=''``: Value for ``description`` in this API.
    - ``best_for=''``: Value for ``best_for`` in this API.
    
    Architecture note
    -----------------
    ``FieldPaletteSpec`` lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_field_style import FieldPaletteSpec
        obj = FieldPaletteSpec(...)
    
    Discovery-oriented use::
    
        help(FieldPaletteSpec)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(FieldPaletteSpec)`` and ``dir(FieldPaletteSpec)`` to inspect adjacent members.
    """

    name: str
    colorscale: str | tuple[tuple[float, str], ...]
    aliases: tuple[str, ...] = ()
    description: str = ""
    best_for: str = ""

    def format_help(self) -> str:
        """Format help.
        
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
        This member belongs to ``FieldPaletteSpec``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldPaletteSpec(...)
            result = obj.format_help(...)
        
        Discovery-oriented use::
        
            help(FieldPaletteSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldPaletteSpec)`` and ``dir(FieldPaletteSpec)`` to inspect adjacent members.
        """

        parts: list[str] = []
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.best_for:
            parts.append(f"Best for: {self.best_for}.")
        parts.append(f"Resolves to Plotly colorscale {self.colorscale!r}.")
        if self.aliases:
            alias_word = "Alias" if len(self.aliases) == 1 else "Aliases"
            parts.append(f"{alias_word}: {', '.join(self.aliases)}.")
        return " ".join(parts)

    def format_alias_help(self, alias: str) -> str:
        """Format alias help.
        
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
        This member belongs to ``FieldPaletteSpec``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldPaletteSpec(...)
            result = obj.format_alias_help(...)
        
        Discovery-oriented use::
        
            help(FieldPaletteSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldPaletteSpec)`` and ``dir(FieldPaletteSpec)`` to inspect adjacent members.
        """

        alias_name = str(alias)
        if alias_name not in self.aliases:
            raise KeyError(f"{alias_name!r} is not an alias of {self.name!r}")
        parts = [f"Alias for {self.name}."]
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.best_for:
            parts.append(f"Best for: {self.best_for}.")
        parts.append(f"Resolves to Plotly colorscale {self.colorscale!r}.")
        return " ".join(parts)


@dataclass(frozen=True)
class FieldStyleSpec:
    """Structured metadata for one public scalar-field style keyword.
    
    Full API
    --------
    ``FieldStyleSpec(name: str, aliases: tuple[str, Ellipsis]=(), type_doc: str='', default_doc: str='', description: str='', accepted_values: tuple[Any, Ellipsis]=())``
    
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
    
    accepted_values : tuple[Any, Ellipsis], optional
        Value for ``accepted_values`` in this API. Defaults to ``()``.
    
    Returns
    -------
    FieldStyleSpec
        New ``FieldStyleSpec`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``aliases=()``: Value for ``aliases`` in this API.
    - ``type_doc=''``: Value for ``type_doc`` in this API.
    - ``default_doc=''``: Value for ``default_doc`` in this API.
    - ``description=''``: Value for ``description`` in this API.
    - ``accepted_values=()``: Value for ``accepted_values`` in this API.
    
    Architecture note
    -----------------
    ``FieldStyleSpec`` lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_field_style import FieldStyleSpec
        obj = FieldStyleSpec(...)
    
    Discovery-oriented use::
    
        help(FieldStyleSpec)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(FieldStyleSpec)`` and ``dir(FieldStyleSpec)`` to inspect adjacent members.
    """

    name: str
    aliases: tuple[str, ...] = ()
    type_doc: str = ""
    default_doc: str = ""
    description: str = ""
    accepted_values: tuple[Any, ...] = ()

    def format_help(self) -> str:
        """Format help.
        
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
        This member belongs to ``FieldStyleSpec``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldStyleSpec(...)
            result = obj.format_help(...)
        
        Discovery-oriented use::
        
            help(FieldStyleSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldStyleSpec)`` and ``dir(FieldStyleSpec)`` to inspect adjacent members.
        """

        parts = []
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(repr(v) for v in self.accepted_values) + "."
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
        """Format alias help.
        
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
        This member belongs to ``FieldStyleSpec``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FieldStyleSpec(...)
            result = obj.format_alias_help(...)
        
        Discovery-oriented use::
        
            help(FieldStyleSpec)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/scalar-field-styling.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
        - In a notebook or REPL, run ``help(FieldStyleSpec)`` and ``dir(FieldStyleSpec)`` to inspect adjacent members.
        """

        alias_name = str(alias)
        if alias_name not in self.aliases:
            raise KeyError(f"{alias_name!r} is not an alias of {self.name!r}")
        parts = [f"Alias for {self.name}."]
        if self.description:
            parts.append(self.description.rstrip(".") + ".")
        if self.accepted_values:
            parts.append(
                "Supported values: " + ", ".join(repr(v) for v in self.accepted_values) + "."
            )
        if self.type_doc:
            parts.append(f"Type: {self.type_doc}.")
        if self.default_doc:
            parts.append(f"Default: {self.default_doc}.")
        return " ".join(parts)


FIELD_PALETTE_OPTIONS: tuple[FieldPaletteSpec, ...] = (
    FieldPaletteSpec(
        name="thermal",
        colorscale="thermal",
        aliases=("temperature",),
        description="Perceptual thermal palette with strong dynamic range",
        best_for="temperature-like scalar fields and thermal energy maps",
    ),
    FieldPaletteSpec(
        name="hot",
        colorscale="hot",
        aliases=("heat",),
        description="Classic black-red-yellow-white thermal ramp",
        best_for="intensity and magnitude fields with bright peaks",
    ),
    FieldPaletteSpec(
        name="viridis",
        colorscale="viridis",
        aliases=("amplitude",),
        description="Perceptually uniform scientific palette",
        best_for="general scalar amplitudes and smooth quantitative fields",
    ),
    FieldPaletteSpec(
        name="plasma",
        colorscale="plasma",
        description="Bright, high-contrast scientific palette",
        best_for="strong visual separation across the full range",
    ),
    FieldPaletteSpec(
        name="magma",
        colorscale="magma",
        description="Dark-to-bright palette that preserves detail near low values",
        best_for="fields with subtle low-amplitude structure",
    ),
    FieldPaletteSpec(
        name="cividis",
        colorscale="cividis",
        description="Color-vision-friendly scientific palette",
        best_for="publication-oriented quantitative heatmaps",
    ),
    FieldPaletteSpec(
        name="ice",
        colorscale="ice",
        description="Cold blue-white palette",
        best_for="negative or cold-valued fields",
    ),
    FieldPaletteSpec(
        name="icefire",
        colorscale="icefire",
        aliases=("diffraction",),
        description="High-contrast diverging palette with cold and hot extremes",
        best_for="interference and diffraction intensity maps",
    ),
    FieldPaletteSpec(
        name="phase",
        colorscale="twilight",
        aliases=("twilight",),
        description="Cyclic palette for wrapped scalar values",
        best_for="phase fields and angle-valued quantities",
    ),
    FieldPaletteSpec(
        name="potential",
        colorscale="balance",
        aliases=("balance",),
        description="Balanced diverging palette around a neutral midpoint",
        best_for="signed potentials and positive/negative deviations",
    ),
    FieldPaletteSpec(
        name="grayscale",
        colorscale="greys",
        aliases=("greyscale", "gray", "grey"),
        description="Neutral grayscale palette",
        best_for="print-friendly scalar fields and background maps",
    ),
    FieldPaletteSpec(
        name="turbo",
        colorscale="turbo",
        description="Very vivid rainbow-like palette",
        best_for="maximal contrast when perceptual uniformity is secondary",
    ),
)

_FIELD_PALETTE_ALIAS_TO_SPEC = {
    name: spec
    for spec in FIELD_PALETTE_OPTIONS
    for name in (spec.name, *spec.aliases)
}
_PLOTLY_NAMED_COLORCALES = {name.lower(): name for name in named_colorscales()}


FIELD_STYLE_OPTIONS: tuple[FieldStyleSpec, ...] = (
    FieldStyleSpec(
        name="colorscale",
        type_doc="str | sequence[tuple[float, str]] | None",
        default_doc="Plotly/default field colorscale",
        description=(
            "Scalar-field colorscale used for contour or heatmap coloring."
            " Accepts toolkit palette names from field_palette_options(), any"
            " Plotly named colorscale, or an explicit stop list"
        ),
    ),
    FieldStyleSpec(
        name="z_range",
        type_doc="tuple[int | float | str, int | float | str] | None",
        default_doc="automatic from data when None",
        description="Explicit scalar range shown by the colorscale as (zmin, zmax)",
    ),
    FieldStyleSpec(
        name="z_step",
        type_doc="int | float | None",
        default_doc="continuous heatmap coloring",
        description=(
            "Heatmap/temperature color step in scalar-value units. When set,"
            " the heatmap is quantized into discrete color bands"
        ),
    ),
    FieldStyleSpec(
        name="under_color",
        type_doc="str | None",
        default_doc="lowest in-range color",
        description=(
            "Special heatmap color for values below the active z_range lower bound"
        ),
    ),
    FieldStyleSpec(
        name="over_color",
        type_doc="str | None",
        default_doc="highest in-range color",
        description=(
            "Special heatmap color for values above the active z_range upper bound"
        ),
    ),
    FieldStyleSpec(
        name="show_colorbar",
        aliases=("showscale",),
        type_doc="bool | None",
        default_doc="False for contour, True for heatmap/temperature",
        description="Show or hide the Plotly colorbar",
    ),
    FieldStyleSpec(
        name="opacity",
        aliases=("alpha",),
        type_doc="int | float | None",
        default_doc="1.0 / Plotly default trace opacity",
        description="Overall field opacity from 0.0 (transparent) to 1.0 (opaque)",
    ),
    FieldStyleSpec(
        name="reversescale",
        type_doc="bool | None",
        default_doc="False",
        description="Reverse the colorscale direction",
    ),
    FieldStyleSpec(
        name="colorbar",
        type_doc="dict[str, Any] | None",
        default_doc="no extra colorbar overrides",
        description="Extra Plotly colorbar fields as a mapping",
    ),
    FieldStyleSpec(
        name="trace",
        type_doc="dict[str, Any] | None",
        default_doc="no extra trace overrides",
        description="Extra full-trace fields as a mapping for advanced Plotly styling",
    ),
    FieldStyleSpec(
        name="levels",
        type_doc="int | None",
        default_doc="Plotly contour default",
        description=(
            "Approximate number of contour levels when exact level_step is not used"
        ),
    ),
    FieldStyleSpec(
        name="level_step",
        type_doc="int | float | None",
        default_doc="automatic from levels/Plotly",
        description="Exact spacing between contour levels in scalar-value units",
    ),
    FieldStyleSpec(
        name="level_start",
        type_doc="int | float | None",
        default_doc="automatic from Plotly or z_range[0]",
        description="Starting contour value when level_step is used",
    ),
    FieldStyleSpec(
        name="level_end",
        type_doc="int | float | None",
        default_doc="automatic from Plotly or z_range[1]",
        description="Final contour value when level_step is used",
    ),
    FieldStyleSpec(
        name="filled",
        type_doc="bool | None",
        default_doc="False for contour",
        description="Fill contour bands instead of drawing contour lines only",
    ),
    FieldStyleSpec(
        name="show_labels",
        type_doc="bool | None",
        default_doc="False",
        description="Show contour labels on contour lines",
    ),
    FieldStyleSpec(
        name="line_color",
        type_doc="str | None",
        default_doc="Plotly/default contour line coloring",
        description="Explicit contour-line color override",
    ),
    FieldStyleSpec(
        name="line_width",
        type_doc="int | float | None",
        default_doc="Plotly contour line width",
        description="Contour-line width in pixels",
    ),
    FieldStyleSpec(
        name="line_dash",
        aliases=("dash",),
        type_doc="str | None",
        default_doc="solid",
        description="Contour-line dash pattern",
        accepted_values=(
            "solid",
            "dot",
            "dash",
            "longdash",
            "dashdot",
            "longdashdot",
        ),
    ),
    FieldStyleSpec(
        name="smoothing",
        aliases=("zsmooth",),
        type_doc="str | bool | None",
        default_doc="False",
        description="Heatmap smoothing policy",
        accepted_values=(False, "fast", "best"),
    ),
    FieldStyleSpec(
        name="connectgaps",
        type_doc="bool | None",
        default_doc="Plotly default",
        description="Whether missing heatmap cells should be gap-connected",
    ),
)

_FIELD_STYLE_SPEC_BY_NAME = {spec.name: spec for spec in FIELD_STYLE_OPTIONS}


def field_palette_option_docs(*, include_aliases: bool = True) -> dict[str, str]:
    """Return discoverability text for curated scalar-field palette names.
    
    Full API
    --------
    ``field_palette_option_docs(*, include_aliases: bool=True) -> dict[str, str]``
    
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
    This callable lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field_style import field_palette_option_docs
        result = field_palette_option_docs(...)
    
    Discovery-oriented use::
    
        help(field_palette_option_docs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(field_palette_option_docs)`` and inspect sibling APIs in the same module.
    """
    docs: dict[str, str] = {}
    for spec in FIELD_PALETTE_OPTIONS:
        docs[spec.name] = spec.format_help()
        if include_aliases:
            for alias in spec.aliases:
                docs[alias] = spec.format_alias_help(alias)
    return docs


def resolve_field_colorscale(value: Any) -> Any:
    """Resolve curated palette aliases to Plotly-compatible colorscale values.
    
    Full API
    --------
    ``resolve_field_colorscale(value: Any) -> Any``
    
    Parameters
    ----------
    value : Any
        New or current value for the relevant property, control, or calculation. Required.
    
    Returns
    -------
    Any
        Result produced by this API.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field_style import resolve_field_colorscale
        result = resolve_field_colorscale(...)
    
    Discovery-oriented use::
    
        help(resolve_field_colorscale)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(resolve_field_colorscale)`` and inspect sibling APIs in the same module.
    """
    if value is None or not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    lower = text.lower()
    curated = _FIELD_PALETTE_ALIAS_TO_SPEC.get(lower)
    if curated is not None:
        return curated.colorscale
    plotly_name = _PLOTLY_NAMED_COLORCALES.get(lower)
    if plotly_name is not None:
        return plotly_name
    return value


def field_style_option_docs(*, include_aliases: bool = True) -> dict[str, str]:
    """Return discoverability text for scalar-field style keywords.
    
    Full API
    --------
    ``field_style_option_docs(*, include_aliases: bool=True) -> dict[str, str]``
    
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
    This callable lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field_style import field_style_option_docs
        result = field_style_option_docs(...)
    
    Discovery-oriented use::
    
        help(field_style_option_docs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(field_style_option_docs)`` and inspect sibling APIs in the same module.
    """
    docs: dict[str, str] = {}
    for spec in FIELD_STYLE_OPTIONS:
        docs[spec.name] = spec.format_help()
        if include_aliases:
            for alias in spec.aliases:
                docs[alias] = spec.format_alias_help(alias)
    return docs


def resolve_field_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "scalar_field()"
) -> dict[str, Any]:
    """Resolve alias keywords in ``style_kwargs`` into canonical names.
    
    Full API
    --------
    ``resolve_field_style_kwargs(style_kwargs: dict[str, Any], *, caller: str='scalar_field()') -> dict[str, Any]``
    
    Parameters
    ----------
    style_kwargs : dict[str, Any]
        Value for ``style_kwargs`` in this API. Required.
    
    caller : str, optional
        Value for ``caller`` in this API. Defaults to ``'scalar_field()'``.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``caller='scalar_field()'``: Value for ``caller`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field_style import resolve_field_style_kwargs
        result = resolve_field_style_kwargs(...)
    
    Discovery-oriented use::
    
        help(resolve_field_style_kwargs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(resolve_field_style_kwargs)`` and inspect sibling APIs in the same module.
    """
    resolved = dict(style_kwargs)

    for spec in FIELD_STYLE_OPTIONS:
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
                        f"{caller} received both {spec.name}= and {other_name}= with different values; use only one."
                    )
        if candidates:
            resolved[spec.name] = candidates[0][1]
        for alias in spec.aliases:
            resolved.pop(alias, None)

    return resolved


def validate_field_style_kwargs(
    style_kwargs: dict[str, Any], *, caller: str = "scalar_field()"
) -> dict[str, Any]:
    """Resolve aliases and validate metadata-driven scalar-field style constraints.
    
    Full API
    --------
    ``validate_field_style_kwargs(style_kwargs: dict[str, Any], *, caller: str='scalar_field()') -> dict[str, Any]``
    
    Parameters
    ----------
    style_kwargs : dict[str, Any]
        Value for ``style_kwargs`` in this API. Required.
    
    caller : str, optional
        Value for ``caller`` in this API. Defaults to ``'scalar_field()'``.
    
    Returns
    -------
    dict[str, Any]
        Result produced by this API.
    
    Optional arguments
    ------------------
    - ``caller='scalar_field()'``: Value for ``caller`` in this API.
    
    Architecture note
    -----------------
    This callable lives in ``gu_toolkit.figure_field_style``. Scalar-field helpers share the main figure pipeline while isolating palette metadata, normalization, and renderer-specific options in dedicated modules.
    
    Examples
    --------
    Basic use::
    
        from gu_toolkit.figure_field_style import validate_field_style_kwargs
        result = validate_field_style_kwargs(...)
    
    Discovery-oriented use::
    
        help(validate_field_style_kwargs)
        # then follow the guide/test links listed below
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/scalar-field-styling.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: call ``field_style_options()`` and ``field_palette_options()`` to see supported scalar-field keywords and palettes.
    - In a notebook or REPL, run ``help(validate_field_style_kwargs)`` and inspect sibling APIs in the same module.
    """
    resolved = resolve_field_style_kwargs(style_kwargs, caller=caller)
    for name, value in tuple(resolved.items()):
        spec = _FIELD_STYLE_SPEC_BY_NAME.get(name)
        if spec is None or value is None or not spec.accepted_values:
            continue
        if value not in spec.accepted_values:
            allowed = ", ".join(repr(v) for v in spec.accepted_values)
            raise ValueError(
                f"{caller} received invalid {name}={value!r}. Supported values: {allowed}."
            )

    levels = resolved.get("levels")
    if levels is not None and int(levels) <= 0:
        raise ValueError(f"{caller} requires levels to be a positive integer.")

    opacity = resolved.get("opacity")
    if opacity is not None:
        opacity_value = float(opacity)
        if not 0.0 <= opacity_value <= 1.0:
            raise ValueError(f"{caller} requires opacity to be between 0.0 and 1.0.")

    z_range = resolved.get("z_range")
    if z_range is not None:
        if not isinstance(z_range, tuple) or len(z_range) != 2:
            raise ValueError(f"{caller} requires z_range to have shape (zmin, zmax).")

    z_step = resolved.get("z_step")
    if z_step is not None and float(z_step) <= 0.0:
        raise ValueError(f"{caller} requires z_step to be a positive number.")

    level_step = resolved.get("level_step")
    if level_step is not None and float(level_step) <= 0.0:
        raise ValueError(f"{caller} requires level_step to be a positive number.")

    if levels is not None and level_step is not None:
        raise ValueError(
            f"{caller} cannot combine levels= with level_step=; choose approximate levels or exact spacing."
        )

    level_start = resolved.get("level_start")
    level_end = resolved.get("level_end")
    if (level_start is not None or level_end is not None) and level_step is None:
        raise ValueError(
            f"{caller} requires level_step= when level_start= or level_end= is provided."
        )
    if (
        level_start is not None
        and level_end is not None
        and float(level_start) > float(level_end)
    ):
        raise ValueError(f"{caller} requires level_start to be <= level_end.")

    return resolved


__all__ = [
    "FIELD_PALETTE_OPTIONS",
    "FIELD_STYLE_OPTIONS",
    "FieldPaletteSpec",
    "FieldStyleSpec",
    "field_palette_option_docs",
    "field_style_option_docs",
    "resolve_field_colorscale",
    "resolve_field_style_kwargs",
    "validate_field_style_kwargs",
]
