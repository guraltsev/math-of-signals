# Streamline Parameter Evaluation — Detailed Blueprint

## Table of Contents

1. [New class: `NumpifiedFunction`](#1-new-class-numpifiedfunction)
2. [New class: `BoundNumpifiedFunction`](#2-new-class-boundnumpifiedfunction)
3. [Changes to `numpify.py`](#3-changes-to-numpifypy)
4. [Changes to `SmartFigure.py` context management](#4-changes-to-smartfigurepy-context-management)
5. [Fusion of `NumericExpression.py`](#5-fusion-of-numericexpressionpy)
6. [Changes to `SmartPlot`](#6-changes-to-smartplot)
7. [Changes to `ParameterSnapshot`](#7-changes-to-parametersnapshot)
8. [Public API / `__init__.py`](#8-public-api--__init__py)
9. [Architectural critique](#9-architectural-critique)

---

## 1. New class: `NumpifiedFunction`

**File:** `numpify.py` (add near top, after imports)

```python
from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING

import sympy as sp

if TYPE_CHECKING:
    from .SmartFigure import SmartFigure


class NumpifiedFunction:
    """A compiled sympy->numpy callable that carries its own metadata.

    Attributes
    ----------
    expr : sp.Basic
        The sympy expression (post-expansion) that was compiled.
    args : tuple[sp.Symbol, ...]
        Ordered argument symbols matching the positional signature.
    source : str
        Generated Python source code of the inner function.
    """

    __slots__ = ("_fn", "expr", "args", "source")

    def __init__(
        self,
        fn: Callable[..., Any],
        expr: sp.Basic,
        args: tuple[sp.Symbol, ...],
        source: str,
    ) -> None:
        self._fn = fn
        self.expr = expr
        self.args = args
        self.source = source

    # --- Callable protocol -------------------------------------------

    def __call__(self, *positional_args: Any) -> Any:
        """Evaluate with positional args in the same order as self.args."""
        return self._fn(*positional_args)

    # --- Binding -----------------------------------------------------

    def bind(
        self,
        source: "ParameterProvider | dict[sp.Symbol, Any] | None" = None,
    ) -> "BoundNumpifiedFunction":
        """Bind parameter values and return a partially-applied callable.

        Parameters
        ----------
        source
            - ``dict[Symbol, value]`` ->
              dead (snapshot) binding.  Values are captured immediately.
            - Any object satisfying the ``ParameterProvider`` protocol
              (has ``.params`` returning a ``Mapping[Symbol, ParamRef]``)
              -> live binding.  ``SmartFigure`` satisfies this.
            - ``None`` -> live binding to the current figure from the
              context stack.

        Returns
        -------
        BoundNumpifiedFunction
        """
        if source is None:
            from .SmartFigure import current_figure as _current_figure
            fig = _current_figure(required=True)
            return BoundNumpifiedFunction(parent=self, provider=fig)

        if isinstance(source, dict):
            return BoundNumpifiedFunction(parent=self, snapshot=source)

        # Duck-type: anything with a .params attribute exposing values
        if hasattr(source, "params"):
            return BoundNumpifiedFunction(parent=self, provider=source)

        raise TypeError(
            f"bind() expects a ParameterProvider (e.g. SmartFigure), "
            f"dict[Symbol, value], or None; got {type(source).__name__}"
        )

    # --- Introspection -----------------------------------------------

    @property
    def arg_names(self) -> tuple[str, ...]:
        """Symbol names in argument order."""
        return tuple(s.name for s in self.args)

    def __repr__(self) -> str:
        args_str = ", ".join(s.name for s in self.args)
        return f"NumpifiedFunction({self.expr!r}, args=({args_str}))"
```

### Design decisions

- **`__slots__`** keeps the object lightweight — these are created frequently
  via `numpify_cached`.
- **`_fn`** is the raw compiled function (the `_generated` from `exec`).
  Keeping it private discourages bypassing the wrapper.
- The class is intentionally **not a dataclass** because `__call__` semantics
  and custom `__repr__` are cleaner on a plain class, and frozen dataclasses
  forbid setting `_fn`.
- **Protocol-based binding** — `bind()` duck-types on `hasattr(source, "params")`
  rather than importing `SmartFigure`.  This keeps `numpify.py` decoupled from
  the UI layer.  The only lazy import is for `bind(None)` which needs the
  context stack.

---

## 2. New class: `BoundNumpifiedFunction`

**File:** `numpify.py` (immediately after `NumpifiedFunction`)

### `ParameterProvider` protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ParameterProvider(Protocol):
    """Anything that exposes a ParameterManager via .params.

    The ParameterManager must support ``__getitem__(symbol)`` returning
    an object with a ``.value`` attribute (i.e. a ``ParamRef``).

    ``SmartFigure`` satisfies this protocol.
    """
    @property
    def params(self) -> Any: ...
```

This protocol lives in `numpify.py` (or a small `_protocols.py` if preferred)
and is the **only** contract between the compilation layer and the figure layer.

### Class definition

```python
class BoundNumpifiedFunction:
    """A NumpifiedFunction with some or all parameters pre-bound.

    Supports two mutually exclusive modes:

    Dead (snapshot) mode
        Parameter values captured at bind-time from a dict.  Deterministic.

    Live (provider) mode
        Parameter values read from a ParameterProvider (e.g. SmartFigure)
        on every __call__.  Essential for exploratory/interactive math.
    """

    __slots__ = ("parent", "_provider", "_snapshot_values", "_free_indices")

    def __init__(
        self,
        parent: NumpifiedFunction,
        *,
        provider: "ParameterProvider | None" = None,
        snapshot: "dict[sp.Symbol, Any] | None" = None,
    ) -> None:
        self.parent = parent
        self._provider = provider
        self._snapshot_values: tuple[Any, ...] | None = None
        self._free_indices: tuple[int, ...] | None = None

        if snapshot is not None:
            self._resolve_snapshot(snapshot)

    def _resolve_snapshot(self, value_map: dict) -> None:
        """Order dict values according to parent.args, track free slots."""
        vals: list[Any] = []
        free: list[int] = []
        for i, sym in enumerate(self.parent.args):
            if sym in value_map:
                vals.append(value_map[sym])
            else:
                vals.append(None)  # placeholder
                free.append(i)

        self._snapshot_values = tuple(vals)
        self._free_indices = tuple(free)

    # --- Callable protocol -------------------------------------------

    def __call__(self, *free_args: Any) -> Any:
        """Evaluate the function.

        In dead-bind mode
            ``free_args`` fills any unbound argument slots.
        In live-bind mode
            ``free_args`` fills the independent-variable slot(s).
            Remaining args are fetched live from the provider.
        """
        if self._provider is not None:
            return self._eval_live(*free_args)
        return self._eval_dead(*free_args)

    def _eval_live(self, *free_args: Any) -> Any:
        """Read parameter values from the bound provider."""
        assert self._provider is not None
        params = self._provider.params
        full: list[Any] = list(free_args)
        n_free = len(free_args)
        for sym in self.parent.args[n_free:]:
            full.append(params[sym].value)
        return self.parent._fn(*full)

    def _eval_dead(self, *free_args: Any) -> Any:
        """Evaluate using captured snapshot values."""
        assert self._snapshot_values is not None
        assert self._free_indices is not None

        full = list(self._snapshot_values)
        if len(free_args) != len(self._free_indices):
            raise TypeError(
                f"Expected {len(self._free_indices)} free arg(s), "
                f"got {len(free_args)}"
            )
        for idx, val in zip(self._free_indices, free_args):
            full[idx] = val
        return self.parent._fn(*full)

    # --- Navigation --------------------------------------------------

    def unbind(self) -> NumpifiedFunction:
        """Return the original unwrapped NumpifiedFunction."""
        return self.parent

    @property
    def is_live(self) -> bool:
        return self._provider is not None

    def __repr__(self) -> str:
        mode = "live" if self.is_live else "dead"
        return f"BoundNumpifiedFunction({self.parent!r}, mode={mode})"
```

### Design decisions

- **`_provider` instead of `_figure`** — the field holds any `ParameterProvider`,
  not specifically a `SmartFigure`.  This makes the binding layer independent
  of the UI layer.
- **`_resolve_snapshot` accepts only `dict`** — no `ParameterSnapshot` coercion.
  Callers who have a snapshot use `snapshot.values()` before passing.  This
  keeps the binding interface narrow and explicit.
- **Live mode convention:** free args are the *leading* positional args (the
  independent variable `x`), and the rest are fetched from the provider.  This
  mirrors the existing `[var] + parameters` ordering in `SmartPlot.set_func()`.

---

## 3. Changes to `numpify.py`

### 3a. `numpify()` return type

Replace the final section (currently lines 270-297) that builds docstring and
attaches `_generated_source`:

```python
    # Current code (to be replaced):
    #   fn.__doc__ = ...
    #   setattr(fn, "_generated_source", src)
    #   setattr(fn, "_generated_expr_code", expr_code)
    #   return fn

    # New:
    return NumpifiedFunction(fn=fn, expr=expr, args=args_tuple, source=src)
```

The `NumpifiedFunction` wraps the raw `fn` and carries `expr`, `args`, and
`source` as first-class attributes.

### 3b. `numpify_cached()` — cache identity design

The LRU cache must store `NumpifiedFunction` instances and the wrapping must
**not** defeat caching.  Concretely:

**Current flow:**
```
numpify_cached(expr, args=...) -> _numpify_cached_impl(key) -> numpify() -> fn
```
The LRU cache in `_numpify_cached_impl` returns the same `fn` object on cache
hit.

**New flow:**
```
numpify_cached(expr, args=...) -> _numpify_cached_impl(key) -> numpify() -> NumpifiedFunction
```
Since `numpify()` now returns `NumpifiedFunction`, and `_numpify_cached_impl`
caches whatever `numpify()` returns, the LRU cache stores `NumpifiedFunction`
directly.  On cache hit, the **same `NumpifiedFunction` instance** is returned.

**What must be verified:**
- `NumpifiedFunction` is **not** re-wrapped on each call.  Since
  `_numpify_cached_impl` is the cached function and it calls `numpify()`
  only on miss, this is satisfied by construction.
- `NumpifiedFunction` must be **safe to share** — it is effectively immutable
  (`__slots__`, no mutable state).  The inner `_fn` captures `_sym_bindings`
  by reference (same as today), which is fine.
- `numpify_cached.cache_info` / `cache_clear` forwarding is unchanged.

**No code changes needed** beyond the `numpify()` return-type change in 3a.
The cache wraps transparently.

### 3c. No backward-compatibility shims

The toolkit is the only consumer of `numpify`.  There are no external users.
All internal callers (`SmartPlot`, `NumericExpression`, tests) will be updated
directly.  No deprecation shims, no `_generated_source` property aliases.

Callers to audit and update:
- `SmartPlot.set_func()` — stores `_core`, switch to `_numpified`
- `SmartPlot._eval_numeric_live()` — calls `self._core(...)`, switch to
  `self._numpified(...)`
- `NumericExpression._coerce_bound_values()` — removed (see section 5)
- Tests that access `_generated_source` — switch to `.source`

---

## 4. Changes to `SmartFigure.py` context management

### 4a. Expose a public `current_figure()` function

Currently the stack helpers are private (`_current_figure`,
`_require_current_figure`).  Add a thin public API:

```python
# SmartFigure.py — module level, after _require_current_figure

def current_figure(*, required: bool = True) -> "SmartFigure | None":
    """Return the active SmartFigure from the context stack.

    This is essential for exploratory math workflows where the user
    operates inside a ``with fig:`` block and expects functions to
    resolve the figure implicitly.

    Parameters
    ----------
    required : bool
        If True (default), raise RuntimeError when no figure is active.
        If False, return None silently.
    """
    fig = _current_figure()
    if fig is None and required:
        raise RuntimeError(
            "No active SmartFigure. Use `with fig:` to set one, "
            "or pass an explicit figure to .bind()."
        )
    return fig
```

### 4b. Export from `__init__.py`

```python
from .SmartFigure import current_figure
```

### 4c. `NumpifiedFunction.bind(None)` uses this

```python
# In NumpifiedFunction.bind():
if source is None:
    from .SmartFigure import current_figure as _current_figure
    fig = _current_figure(required=True)
    return BoundNumpifiedFunction(parent=self, provider=fig)
```

This is the **only** lazy import from `SmartFigure` in `numpify.py`.  It fires
only when the user explicitly asks for implicit context binding — the common
exploratory-math path.

### 4d. Coupling direction

`numpify.py` importing from `SmartFigure.py` is an **upward dependency**
(compilation layer -> UI layer).  It is acceptable because:

- The import is **lazy** (inside `bind()` only when `source is None`).
- All other binding paths use the `ParameterProvider` protocol — no import
  needed.
- `numpify` can still be used standalone without SmartFigure loaded.

---

## 5. Fusion of `NumericExpression.py`

### Decision: fuse immediately, no transitional facade

The existing `DeadUnboundNumericExpression`, `DeadBoundNumericExpression`, and
`LiveNumericExpression` are replaced, not wrapped.

### What replaces what

| Old class | Replacement |
|-|-|
| `DeadUnboundNumericExpression` | `NumpifiedFunction` directly |
| `DeadBoundNumericExpression` | `BoundNumpifiedFunction` (dead mode) |
| `LiveNumericExpression` | **`PlotView`** — a thin "live view" of a plot |

### New: `PlotView` (replaces `LiveNumericExpression`)

A `LiveNumericExpression` today is a "view" into a `SmartPlot` — it delegates
`__call__` to `plot._eval_numeric_live(x)`.  This is conceptually different
from a live-bound `NumpifiedFunction` because it is tied to a *plot* (which
owns the var/parameter split), not just to a parameter source.

The replacement keeps this distinction explicit:

```python
# NumericExpression.py — slimmed down

@dataclass(frozen=True)
class PlotView:
    """Live view of a SmartPlot's numeric evaluation.

    Forwards every call to the plot's live-bound NumpifiedFunction.
    This is what SmartPlot.numeric_expression returns.
    """
    _numpified: NumpifiedFunction
    _provider: Any  # ParameterProvider (SmartFigure)

    def __call__(self, x: "np.ndarray") -> "np.ndarray":
        """Evaluate using current live parameter values."""
        bound = self._numpified.bind(self._provider)
        return bound(x)

    def bind(self, values: dict[Symbol, Any]) -> BoundNumpifiedFunction:
        """Snapshot-bind with explicit values dict.

        Parameters
        ----------
        values : dict[Symbol, Any]
            Parameter values keyed by symbol.  Obtain from
            ``fig.params.snapshot().values()`` or build manually.
        """
        return self._numpified.bind(values)

    def unbind(self) -> NumpifiedFunction:
        """Return the underlying NumpifiedFunction."""
        return self._numpified

    @property
    def expr(self) -> sp.Basic:
        return self._numpified.expr

    @property
    def args(self) -> tuple[Symbol, ...]:
        return self._numpified.args
```

### `bind()` accepts only `dict[Symbol, value]`

This is a deliberate narrowing.  The old code accepted both `ParameterSnapshot`
and `dict`.  The new rule:

- **`NumpifiedFunction.bind()`** accepts: `dict`, `ParameterProvider`, or `None`.
- **`PlotView.bind()`** accepts: `dict` only.
- **`BoundNumpifiedFunction`** stores snapshot as `dict` internally.

If the caller has a `ParameterSnapshot`, they call `.values()` first (see
section 7 for the rename).  This makes the data flow explicit and removes the
hidden `values_only()` coercion inside binding logic.

### Remove `_coerce_bound_values()`

The helper `_coerce_bound_values()` in `NumericExpression.py` is deleted.
Its logic (validate keys, order by parameters, check for missing) moves into
`BoundNumpifiedFunction._resolve_snapshot()`, simplified because it only
handles `dict`.

### Removed classes

- `DeadUnboundNumericExpression` — replaced by `NumpifiedFunction`
- `DeadBoundNumericExpression` — replaced by `BoundNumpifiedFunction`
- `LiveNumericExpression` — replaced by `PlotView`

For a short transition, type aliases can be kept in `NumericExpression.py`:

```python
# Temporary aliases for any lingering references
DeadUnboundNumericExpression = NumpifiedFunction
DeadBoundNumericExpression = BoundNumpifiedFunction
LiveNumericExpression = PlotView
```

These aliases should be removed once all references are updated.

---

## 6. Changes to `SmartPlot`

### Current state (`SmartFigure.py` ~line 1550)

```python
def set_func(self, var, func, parameters=[]):
    self._core = numpify_cached(func, args=[var] + parameters)
    self._var = var
    self._parameters = tuple(parameters)
    self._func = func
```

And evaluation (`~line 1602`):

```python
def _eval_numeric_live(self, x):
    fig = self._smart_figure
    args = [x]
    for symbol in self._parameters:
        args.append(fig.params[symbol].value)
    return self._core(*args)
```

### Target state

```python
def set_func(self, var, func, parameters=[]):
    self._numpified = numpify_cached(func, args=[var] + parameters)
    self._var = var
    self._func = func
    # _parameters is gone — derived from self._numpified.args[1:]

def _eval_numeric_live(self, x):
    # Direct call for hot-path performance (no wrapper allocation)
    params = self._smart_figure.params
    args = [x]
    for sym in self._numpified.args[1:]:  # skip var (args[0])
        args.append(params[sym].value)
    return self._numpified(*args)
```

The render hot path uses the manual loop (zero overhead).  The
`numeric_expression` property provides the ergonomic `PlotView` for external
consumers.

### Property migration

```python
@property
def parameters(self) -> tuple[Symbol, ...]:
    """Parameter symbols (excludes independent variable)."""
    return self._numpified.args[1:]  # args[0] is var

@property
def numpified(self) -> NumpifiedFunction:
    """The compiled NumpifiedFunction for this plot."""
    return self._numpified

@property
def numeric_expression(self) -> PlotView:
    """Live view for external consumers."""
    return PlotView(
        _numpified=self._numpified,
        _provider=self._smart_figure,
    )
```

The separate `_parameters` field is **removed**; it is derived from
`_numpified.args`.

---

## 7. Changes to `ParameterSnapshot`

### Rename `values_only()` -> `values()`

```python
# ParameterSnapshot.py

class ParameterSnapshot(Mapping[Symbol, Mapping[str, Any]]):

    def values(self) -> Dict[Symbol, Any]:          # was values_only()
        """Return an ordered Symbol -> value projection."""
        return {symbol: entry["value"] for symbol, entry in self._entries.items()}
```

**Note:** `Mapping` already defines `.values()` returning dict values.  Since
`ParameterSnapshot` inherits from `Mapping[Symbol, Mapping[str, Any]]`, the
inherited `.values()` returns the metadata dicts, not scalars.  We are
**overriding** that inherited method with a different return type — this is
intentional and desirable because the scalar projection is what users want
99% of the time.

If this override causes confusion, an alternative name like `.param_values()`
could be used, but `.values()` is the most natural and concise choice.

### Update callers

All places that call `.values_only()` switch to `.values()`:
- `NumericExpression.py` `_coerce_bound_values()` — deleted entirely
- Tests: `test_parameter_snapshot_numeric_expression.py`

### Usage pattern for binding

```python
# Old:
bound_expr = expr.bind(snapshot)                   # snapshot coerced internally

# New:
bound_fn = numpified.bind(snapshot.values())       # explicit dict
```

---

## 8. Public API / `__init__.py`

### New exports

```python
from .numpify import NumpifiedFunction, BoundNumpifiedFunction, ParameterProvider
from .SmartFigure import current_figure
from .NumericExpression import PlotView
```

### Removed exports (after transition)

```python
# These are replaced:
# LiveNumericExpression  -> PlotView
# DeadBoundNumericExpression  -> BoundNumpifiedFunction
# DeadUnboundNumericExpression  -> NumpifiedFunction
```

### Unchanged exports

All existing `plot`, `params`, `parameter`, `render`, etc. remain.

---

## 9. Architectural Critique

### Strengths of this design

1. **Single source of truth** — argument order and expression live with the
   compiled function, not duplicated across `SmartPlot._parameters`,
   `DeadUnboundNumericExpression.parameters`, etc.

2. **Standalone usability** — `NumpifiedFunction` is useful outside the figure
   context (batch evaluation, testing, serialization) because it carries its
   own metadata.

3. **Clean decoupling via protocol** — `ParameterProvider` is a duck-typed
   protocol.  `SmartFigure` satisfies it, but so could any mock or alternative
   parameter source.  `numpify.py` never imports `SmartFigure` except lazily
   for the `bind(None)` context-stack path.

4. **Explicit data flow** — `bind()` accepts only `dict[Symbol, value]` for
   dead binding.  No hidden coercion of `ParameterSnapshot`.  The caller writes
   `snapshot.values()` — one explicit step.

5. **Immediate fusion** — no transitional period with two parallel binding
   hierarchies.  `NumericExpression` classes are replaced in one pass.

### Weaknesses / risks

1. **Implicit context (`bind(None)`)** — global mutable state via
   `_FIGURE_STACK` is not thread-safe.  This is acceptable: the toolkit targets
   single-threaded Jupyter notebooks, and implicit context is essential for
   exploratory math to feel natural.  Document the thread-safety limitation.

2. **Live binding holds a strong reference** to the provider.  If a
   `BoundNumpifiedFunction` outlives the figure, it silently reads stale widget
   values or crashes.  Consider a `weakref` to the provider with a clear error
   on access-after-close — but only if this becomes a real problem.  For now
   the Jupyter lifecycle makes this unlikely.

3. **`Mapping.values()` override** in `ParameterSnapshot` — overriding
   inherited `.values()` with a different return type may confuse type checkers
   and users who expect `Mapping` semantics.  If this is problematic, use
   `.param_values()` instead.  But `.values()` is the most intuitive name for
   the 99% use case.

4. **Partial binding ambiguity** — `BoundNumpifiedFunction` supports partial
   binding (some args bound, some free).  The caller must know which positional
   slots are free.  Document the convention: *leading args are free (independent
   variable), trailing args are bound (parameters)*.

5. **`PlotView` vs `BoundNumpifiedFunction`** — there are now two "live
   callable" types.  `BoundNumpifiedFunction` is the general-purpose one;
   `PlotView` is the plot-specific wrapper that exposes `.expr` and `.args` for
   convenience.  The distinction is meaningful (plot view = specific curve,
   bound function = any binding), but users may wonder why both exist.
   `PlotView` should be documented as "what `SmartPlot.numeric_expression`
   returns" rather than a standalone public concept.

### Recommended implementation order

1. Rename `ParameterSnapshot.values_only()` -> `.values()`.  Update tests.
2. Add `ParameterProvider` protocol, `NumpifiedFunction`, and
   `BoundNumpifiedFunction` to `numpify.py`.
3. Change `numpify()` return to `NumpifiedFunction`.
4. Add `current_figure()` public helper to `SmartFigure.py`.
5. Update `SmartPlot`: replace `_core`/`_parameters`/`_func` with `_numpified`.
6. Rewrite `NumericExpression.py`: delete old classes, add `PlotView`.
7. Update `__init__.py` exports.
8. Update tests.
