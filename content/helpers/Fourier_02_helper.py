import numpy as np
import sympy as sp
from gu_toolkit.NamedFunction import NamedFunction
from gu_toolkit.numpify import numpify, numpify_cached


import ipywidgets as widgets
from IPython.display import clear_output, display

__all__ = []

__all__ += ["SupNormCard","MaxDistanceCard"]

def MaxDistanceCard(var,F,G):
    return SupNormCard(var, F-G)
    
def SupNormCard(var,F):
    class SupNormCard_for_specific_functions:
        def __init__(self, out, fig):
            self.xs = np.linspace(-0.5, 0.5, 2000)
    
            self.prefix = widgets.HTMLMath(
                value=r"The largest distance between the two functions on "
                      r"$\left[-\tfrac12,\tfrac12\right]$ is: "
            )
            self.value = widgets.HTML(value="<code>…</code>")
            with out:
                clear_output()
                display(widgets.VBox([self.prefix, self.value]))
            self.expr = sp.Abs(F)
            self.var = var
            self.params = tuple(sorted([s for s in self.expr.free_symbols if s != self.var], key=lambda s: s.sort_key()))
            for p in self.params:
                    fig.add_param(p)
                    
        def update(self, change, fig, out):
            par_vals = [fig._params[p].value for p in self.params]  # current slider values
            expr_np= numpify_cached(self.expr, args=[self.var] + list(self.params))
            sup = float(np.max(expr_np(self.xs, *par_vals)))
            self.value.value = f"<code>{sup:g}</code>"
    return SupNormCard_for_specific_functions

__all__ += ["L1AvgNormCard","AvgDistanceCard"]

def AvgDistanceCard(var,F,G):
    return L1AvgNormCard(var, F-G)
    
def L1AvgNormCard(var,F):
    class L1AvgNormCard_for_specific_functions:
        def __init__(self, out, fig):
            self.xs = np.linspace(-0.5, 0.5, 2000)
    
            self.prefix = widgets.HTMLMath(
                value=r"The average distance between the two functions on "
                      r"$\left[-\tfrac12,\tfrac12\right]$ is: "
            )
            self.value = widgets.HTML(value="<code>…</code>")
            with out:
                clear_output()
                display(widgets.VBox([self.prefix, self.value]))
            self.expr = sp.Abs(F)
            self.var = var
            self.params = tuple(sorted([s for s in self.expr.free_symbols if s != self.var], key=lambda s: s.sort_key()))
            for p in self.params:
                    fig.add_param(p)
                    
        def update(self, change, fig, out):
            par_vals = [fig._params[p].value for p in self.params]  # current slider values
            expr_np= numpify_cached(self.expr, args=[self.var] + list(self.params))
            avg = float(np.mean(expr_np(self.xs, *par_vals)))
            self.value.value = f"<code>{avg:g}</code>"
    return L1AvgNormCard_for_specific_functions
