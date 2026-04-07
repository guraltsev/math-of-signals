"""Top-level public API for the ``gu_toolkit`` package.

This module re-exports the notebook-facing convenience surface so users can
import from a single namespace, for example:

>>> from gu_toolkit import Figure, parameter, plot  # doctest: +SKIP

It intentionally exposes both high-level plotting helpers and lower-level
building blocks (parameter events/references and numeric-expression wrappers)
for advanced integrations.
"""

# Optional explicit module handle to avoid callable/module name ambiguity.
from . import numpify as numpify_module
from .codegen import CodegenOptions, figure_to_code, sympy_to_code
from .Figure import (
    Figure,
    FigureViews,
    FigureLayout,
    ParametricPlot,
    Plot,
    ScalarFieldPlot,
    View,
    contour,
    current_figure,
    density,
    field_palette_options,
    field_style_options,
    get_default_samples,
    get_default_x_range,
    get_default_y_range,
    get_samples,
    get_sampling_points,
    get_title,
    get_x_range,
    get_y_range,
    info,
    parameter,
    parameters,
    parametric_plot,
    plot,
    plots,
    render,
    scalar_field,
    sound_generation_enabled,
    temperature,
    set_default_samples,
    set_default_x_range,
    set_default_y_range,
    set_samples,
    set_sampling_points,
    set_title,
    set_x_range,
    set_y_range,
)
from .Figure import (
    parametric_plot as toolkit_parametric_plot,
)
from .Figure import (
    contour as toolkit_contour,
)
from .Figure import (
    density as toolkit_density,
)
from .Figure import (
    field_palette_options as toolkit_field_palette_options,
)
from .Figure import (
    field_style_options as toolkit_field_style_options,
)
from .Figure import (
    plot as toolkit_plot,
)
from .Figure import (
    plot_style_options as toolkit_plot_style_options,
)
from .Figure import (
    scalar_field as toolkit_scalar_field,
)
from .Figure import (
    temperature as toolkit_temperature,
)
from .FigureSnapshot import FigureSnapshot, InfoCardSnapshot, ViewSnapshot
from .FieldPlotSnapshot import FieldPlotSnapshot
from .NamedFunction import NamedFunction as NamedFunction
from .identifiers import parse_identifier, render_latex, symbol
from .Notebook import *
from .math_input import IdentifierInput, MathInput
from .numeric_callable import (
    DYNAMIC_PARAMETER,
    UNFREEZE,
    NumericFunction,
    ParameterContext,
    numpify,
    numpify_cached,
)
from .ParameterSnapshot import ParameterSnapshot
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
from .ParseLaTeX import parse_latex
from .PlotSnapshot import PlotSnapshot
from .animation import (
    AnimationClock,
    AnimationController,
    DEFAULT_ANIMATION_HZ,
    DEFAULT_ANIMATION_TIME,
    get_default_animation_clock,
)
from .Slider import FloatSlider
from .runtime_support import runtime_diagnostics, runtime_support_performance_snapshot

# Keep toolkit helpers authoritative after notebook namespace wildcard imports.
# ``Notebook`` intentionally exports SymPy's ``plot`` helper via
# ``from sympy import *`` for convenience, but package-level plotting helpers
# should resolve to gu_toolkit's module helpers for notebook examples and docs.
contour = toolkit_contour
density = toolkit_density
field_palette_options = toolkit_field_palette_options
field_style_options = toolkit_field_style_options
parametric_plot = toolkit_parametric_plot
plot = toolkit_plot
plot_style_options = toolkit_plot_style_options
scalar_field = toolkit_scalar_field
temperature = toolkit_temperature
