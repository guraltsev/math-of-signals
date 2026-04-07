from gu_toolkit import *

__all__ = ["create_mystery_function", "Sq", "Tr"]

@NamedFunction
def Sq(x):
    return sign(sin(2 * pi * x))

@NamedFunction
def Tr(x):
    return asin(sin(2 * pi * x)) / (pi / 2)


def create_mystery_function(N, debug=False, grid_size=20000):
    r"""
    Create a mystery function of the form
    $$
    F(x)= α_1\,\sin(2 π x)+α_2\,\sin(2 π 2 x) + \ldots +α_{N} \,\sin(2 π N x)
    $$

    The numbers $α_n$ are chosen randomly with step 0.1, and the final
    function is normalized in L^\infty:
    $$
    \|F\|_{L^\infty}=1.
    $$
    """
    x = symbols("x")

    @NamedFunction
    def F(arg):
        return None

    # Generate the mystery coefficients and build the symbolic expression.
    expr = 0
    for n in range(1, N + 1):
        j = np.random.randint(3, 10 + 1)
        sign = np.random.randint(0, 1 + 1)
        a_n = sp.Integer(-1) ** sp.Integer(sign) * sp.Rational(j, 10)
        expr += a_n * sp.sin(2 * sp.pi * n * x)

    # Compute an approximate L^\infty norm on [0, 1]
    f_numpy_raw = numpify(expr)
    xs = np.linspace(0.0, 1.0, grid_size, endpoint=True)
    vals = np.abs(f_numpy_raw(xs))
    linfty_norm = np.max(vals)

    if linfty_norm == 0:
        raise ValueError("Generated function is identically zero, cannot normalize.")

    # Normalize the symbolic expression
    expr = expr / linfty_norm

    if debug:
        print("Raw expression:", expr * linfty_norm)
        print("Approximate L^infty norm:", linfty_norm)
        print("Normalized expression:", expr)

    f_numpy = numpify(expr)
    F.f_numpy = f_numpy
    F.expr = expr
    F.linfty_norm = linfty_norm

    return F
