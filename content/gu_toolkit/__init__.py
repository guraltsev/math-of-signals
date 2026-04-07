"""Top-level public API for the ``gu_toolkit`` package.

This module re-exports the notebook-facing convenience surface so users can
import from a single namespace, for example:

>>> from gu_toolkit import SmartFigure, parameter, plot  # doctest: +SKIP

It intentionally exposes both high-level plotting helpers and lower-level
building blocks (parameter events/references and numeric-expression wrappers)
for advanced integrations.
"""

from .prelude import *
from .NamedFunction import NamedFunction as NamedFunction
from .numpify import (
    BoundNumpifiedFunction,
    NumpifiedFunction,
    ParameterProvider,
    numpify as numpify,
    numpify_cached,
)
from .SmartFigure import SmartFigure as Figure, SmartFigure, add_info_component, current_figure, get_info_output, get_sampling_points, get_title, get_x_range, get_y_range, parameter, parameters, params, plot, plot_style_options, plots, render, set_sampling_points, set_title, set_x_range, set_y_range
from .SmartParseLaTeX import parse_latex
from .ParamEvent import ParamEvent
from .ParamRef import ParamRef
# from .SmartException import *
# from .SmartFigure import *

from .ParameterSnapshot import ParameterSnapshot
from .NumericExpression import PlotView
