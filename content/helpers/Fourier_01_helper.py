import numpy as np
import sympy as sp
from gu_toolkit.NamedFunction import NamedFunction
from gu_toolkit.numpify import numpify, numpify_cached

__all__ = ["create_mystery_function"]


def create_mystery_function(N, debug=False):
    """
    Create a mystery function of the form
    $$
    F(x)= α_1\\,\\sin(2 π x)+α_2\\,\\sin(2 π 2 x) + \\ldots +α_{N} \\,\\sin(2 π N x)
    $$

    The numbers $α_n$ are chosen randomly **between -1 and 1** with **step 0.1**.
    """
    x = sp.Symbol("x")

    @NamedFunction
    def F(arg):
        return None

    # Generate the mystery coefficients and build the symbolic expression.
    expr = 0
    for n in [n + 1 for n in range(N)]:  # n goes from 1 to modes inclusive
        # Generate random integer j from 0 to 20
        j = np.random.randint(3, 10 + 1)
        sign = np.random.randint(0, 1 + 1)
        a_n = sp.Integer(-1) ** (sp.Integer(sign)) * sp.Rational(j, 10)
        # Add term to the expression
        expr = expr + a_n * sp.sin(2 * sp.pi * n * x)
    if debug:
        print(expr)
    f_numpy = numpify(expr)
    F.f_numpy = f_numpy
    return F


import ipywidgets as widgets
from IPython.display import clear_output, display

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
