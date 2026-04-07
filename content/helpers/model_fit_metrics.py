import numpy as np
import sympy as sp
import ipywidgets as widgets
from IPython.display import clear_output, display

from gu_toolkit.numpify import numpify_cached

__all__ = [
    "FitDistanceStats",
    "compute_model_fit_distances",
    "add_model_fit_distance_info",
    "SupNormCard",
    "MaxDistanceCard",
    "L1AvgNormCard",
    "AvgDistanceCard",
]


def _sorted_params(expr, var):
    expr = sp.sympify(expr)
    return tuple(
        sorted((symbol for symbol in expr.free_symbols if symbol != var), key=lambda s: s.sort_key())
    )


def _normalize_interval(interval):
    if interval is None:
        interval = (-sp.Rational(1, 2), sp.Rational(1, 2))
    left, right = interval
    left_float = float(sp.N(left))
    right_float = float(sp.N(right))
    if right_float < left_float:
        left, right = right, left
        left_float, right_float = right_float, left_float
    return (left, right), (left_float, right_float)


def _format_interval_label(interval):
    (left, right), _ = _normalize_interval(interval)
    return rf"$\left[{sp.latex(sp.sympify(left))},\,{sp.latex(sp.sympify(right))}\right]$"


class FitDistanceStats:
    def __init__(self, var, difference, *, interval=None, samples=2000):
        self.var = var
        self.difference = sp.sympify(difference)
        self.abs_difference = sp.Abs(self.difference)
        self.params = _sorted_params(self.abs_difference, self.var)
        self.samples = max(int(samples), 2)

        self.interval_symbolic, interval_float = _normalize_interval(interval)
        self.xs = np.linspace(interval_float[0], interval_float[1], self.samples)
        self.expr_np = numpify_cached(self.abs_difference, vars=[self.var] + list(self.params))

        self._last_key = None
        self._last_stats = None

    def ensure_parameters(self, fig):
        if self.params:
            fig.parameter(self.params)
        return self

    def _coerce_scalar(self, value):
        if isinstance(value, np.generic):
            return value.item()
        return value

    def _resolve_values_from_mapping(self, parameter_values):
        resolved = []
        for param in self.params:
            if param in parameter_values:
                resolved.append(parameter_values[param])
                continue
            name = str(param)
            if name in parameter_values:
                resolved.append(parameter_values[name])
                continue
            raise KeyError(f"Missing parameter value for {param!s}.")
        return tuple(self._coerce_scalar(value) for value in resolved)

    def _resolve_values_from_figure(self, fig):
        resolved = []
        params = fig.parameters
        for param in self.params:
            try:
                ref = params[param]
            except Exception:
                ref = params[str(param)]
            resolved.append(ref.value)
        return tuple(self._coerce_scalar(value) for value in resolved)

    def _evaluate(self, parameter_values):
        values = np.asarray(self.expr_np(self.xs, *parameter_values), dtype=float)
        values = np.real_if_close(values)
        if values.ndim == 0:
            values = np.full_like(self.xs, float(values))
        else:
            values = np.broadcast_to(values, self.xs.shape)
        values = np.abs(values)
        return {
            "max_distance": float(np.max(values)),
            "avg_distance": float(np.mean(values)),
        }

    def compute_for_parameter_values(self, parameter_values=None):
        parameter_values = {} if parameter_values is None else parameter_values
        return self._evaluate(self._resolve_values_from_mapping(parameter_values))

    def compute_for_figure(self, fig):
        values = self._resolve_values_from_figure(fig)
        cache_key = tuple(values)
        if cache_key != self._last_key:
            self._last_key = cache_key
            self._last_stats = self._evaluate(values)
        return self._last_stats

    def max_text(self, fig, _ctx=None):
        stats = self.compute_for_figure(fig)
        return f"<code>{stats['max_distance']:.6g}</code>"

    def avg_text(self, fig, _ctx=None):
        stats = self.compute_for_figure(fig)
        return f"<code>{stats['avg_distance']:.6g}</code>"


def compute_model_fit_distances(
    var,
    target,
    model,
    *,
    interval=None,
    samples=2000,
    parameter_values=None,
):
    evaluator = FitDistanceStats(var, model - target, interval=interval, samples=samples)
    return evaluator.compute_for_parameter_values(parameter_values=parameter_values)


class _DistanceMetricCard:
    def __init__(self, out, evaluator, metric_key, prefix_text):
        self.evaluator = evaluator
        self.metric_key = metric_key
        self.prefix = widgets.HTMLMath(value=prefix_text)
        self.value = widgets.HTML(value="<code>…</code>")
        with out:
            clear_output(wait=True)
            display(widgets.VBox([self.prefix, self.value]))

    def update(self, change, fig, out):
        stats = self.evaluator.compute_for_figure(fig)
        self.value.value = f"<code>{stats[self.metric_key]:.6g}</code>"


def _attach_metric_card(fig, evaluator, *, card_id, hook_id, metric_key, prefix_text):
    out = fig.info_manager.get_output(id=card_id)
    card = _DistanceMetricCard(out, evaluator, metric_key, prefix_text)
    fig.info_manager.add_component(card_id, card)
    card.update(None, fig, out)
    fig.add_param_change_hook(
        lambda change, _card=card, _out=out: _card.update(change, fig, _out),
        hook_id=hook_id,
        run_now=False,
    )
    return card


def add_model_fit_distance_info(
    fig,
    var,
    target,
    model,
    *,
    interval=None,
    interval_label=None,
    model_name=r"$\mathrm{model}$",
    target_name=r"$\mathrm{target}$",
    samples=2000,
    card_id_prefix="fit_distance",
):
    if interval is None:
        interval = getattr(fig, "x_range", None)
    evaluator = FitDistanceStats(var, model - target, interval=interval, samples=samples)
    evaluator.ensure_parameters(fig)

    if interval_label is None:
        interval_label = _format_interval_label(evaluator.interval_symbolic)

    _attach_metric_card(
        fig,
        evaluator,
        card_id=f"{card_id_prefix}_max",
        hook_id=f"{card_id_prefix}_max_hook",
        metric_key="max_distance",
        prefix_text=(
            rf"The largest distance between {model_name} and {target_name} on {interval_label} is: "
        ),
    )
    _attach_metric_card(
        fig,
        evaluator,
        card_id=f"{card_id_prefix}_avg",
        hook_id=f"{card_id_prefix}_avg_hook",
        metric_key="avg_distance",
        prefix_text=(
            rf"The average distance between {model_name} and {target_name} on {interval_label} is: "
        ),
    )
    return evaluator


def SupNormCard(var, F, *, interval=None, interval_label=None, samples=2000):
    class SupNormCard_for_specific_functions:
        def __init__(self, out, fig):
            self.metrics = FitDistanceStats(var, F, interval=interval, samples=samples)
            self.metrics.ensure_parameters(fig)
            if interval_label is None:
                label = _format_interval_label(self.metrics.interval_symbolic)
            else:
                label = interval_label

            self.prefix = widgets.HTMLMath(
                value=(
                    r"The largest distance between the two functions on "
                    + label
                    + r" is: "
                )
            )
            self.value = widgets.HTML(value="<code>…</code>")
            with out:
                clear_output(wait=True)
                display(widgets.VBox([self.prefix, self.value]))
            self.update(None, fig, out)

        def update(self, change, fig, out):
            stats = self.metrics.compute_for_figure(fig)
            self.value.value = f"<code>{stats['max_distance']:.6g}</code>"

    return SupNormCard_for_specific_functions


def MaxDistanceCard(var, F, G, **kwargs):
    return SupNormCard(var, F - G, **kwargs)


def L1AvgNormCard(var, F, *, interval=None, interval_label=None, samples=2000):
    class L1AvgNormCard_for_specific_functions:
        def __init__(self, out, fig):
            self.metrics = FitDistanceStats(var, F, interval=interval, samples=samples)
            self.metrics.ensure_parameters(fig)
            if interval_label is None:
                label = _format_interval_label(self.metrics.interval_symbolic)
            else:
                label = interval_label

            self.prefix = widgets.HTMLMath(
                value=(
                    r"The average distance between the two functions on "
                    + label
                    + r" is: "
                )
            )
            self.value = widgets.HTML(value="<code>…</code>")
            with out:
                clear_output(wait=True)
                display(widgets.VBox([self.prefix, self.value]))
            self.update(None, fig, out)

        def update(self, change, fig, out):
            stats = self.metrics.compute_for_figure(fig)
            self.value.value = f"<code>{stats['avg_distance']:.6g}</code>"

    return L1AvgNormCard_for_specific_functions


def AvgDistanceCard(var, F, G, **kwargs):
    return L1AvgNormCard(var, F - G, **kwargs)
