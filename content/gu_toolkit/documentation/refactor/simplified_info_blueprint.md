# Simplified Blueprint: List-Based Info Cards for SmartFigure

## 0. Design principle

An info card is a **flat list of segments**: literal strings and callables. Strings render as static LaTeX. Callables receive `fig`, return one object, and their result is rendered as LaTeX. That's it.

No f-strings, no `eval()`, no frame inspection, no template parsing, no expression compilation, no `env=` argument, no `run_now`, no `on=...`.

---

## 1. Public API

### 1.1 `SmartFigure.info`

```python
SmartFigure.info(
    segments: list[str | Callable[[SmartFigure], Any]],
    id: Hashable | None = None,
) -> Hashable
```

**`segments`** — ordered list where each element is either:

- **`str`** — rendered once as LaTeX via `widgets.HTMLMath`. Never re-evaluated. Example: `"$f(x) = $"`, `"Value of a: "`, `"$$\\int_0^1$$"`.
- **`callable`** — called as `segment(fig)` on every parameter-change render. Must return exactly one object. The return value is converted to a string (`str(result)`) and rendered via `widgets.HTMLMath`. The callable accesses figure state through `fig`:
  - `fig.params[symbol].value` for parameter values
  - `fig.plots['id']` for plot objects (and from there `.symbolic_expression`, `.numeric_expression`, `.numpified`, etc.)
  - `fig.x_range`, `fig.y_range`, etc.

**`id`** — card identifier:

- `None` → auto-allocate `"info:1"`, `"info:2"`, …
- existing id → **replace** that card's segments and rebuild its content (reuse the same root `widgets.Output`; preserve ordering)
- new id → append at end

**Returns** the effective id.

### 1.2 Usage examples

```python
import sympy as sp
x, a = sp.symbols("x a")

fig = SmartFigure()
fig.plot(x, a * sp.sin(x), id="wave")

# Static-only card
fig.info(["$f(x) = a \\sin(x)$"])

# Mixed static + dynamic
fig.info([
    "Current value of $a$: ",
    lambda fig: f"${sp.latex(fig.params[a].value)}$",
], id="param_display")

# Dynamic using plot data
fig.info([
    "Expression: ",
    lambda fig: f"${sp.latex(fig.plots['wave'].symbolic_expression)}$",
])
```

### 1.3 Convenience module-level function

```python
def info(
    segments: list[str | Callable],
    id: Hashable | None = None,
) -> Hashable:
    return _require_current_figure().info(segments, id=id)
```

---

## 2. Architecture

### 2.1 Responsibilities

| Component | Does | Does not |
|---|---|---|
| **SmartFigure** | Forwards `info(...)` to manager. Calls `_info.update_all(fig)` inside `render()` **only when `reason == "param_change"`**. Updates sidebar visibility after add/remove. | Store per-card logic. |
| **InfoPanelManager** | Stores `id → InfoCard` (ordered). Allocates auto-ids. Replaces cards. Rebuilds `info_box.children`. Provides `update_all(fig)`. | Parse templates. Manage hooks. |
| **InfoCard** | Stores the segment list. Holds one `widgets.HTMLMath` per segment. On update, re-calls dynamic segments and updates only changed widgets. | Anything else. |

### 2.2 Integration into `SmartFigure.render`

Current `render()` does:

```
1. Update all plots
2. If reason == "param_change": fire hooks
```

Change to:

```
1. Update all plots
2. If reason == "param_change": update info cards, then fire hooks
```

Specifically, add one line before the hook loop:

```python
if reason == "param_change" and trigger:
    self._info.update_all(self)          # ← NEW
    hooks = self._params.get_hooks()
    ...
```

Info cards update **after** plots (so they see fresh plot state) and **before** hooks (so hooks can still override if needed). Info cards do **not** update on relayout/manual renders — only parameter changes.

The initial `info(...)` call renders once immediately (evaluates all callables, builds widgets). No `run_now` flag needed.

---

## 3. Data structures

### 3.1 InfoPanelManager

```python
class InfoPanelManager:
    _cards: dict[Hashable, InfoCard]   # ordered, id → card
    _counter: int                       # next auto-id number
    _layout_box: widgets.VBox           # the info_box from layout
```

### 3.2 InfoCard

```python
class InfoCard:
    id: Hashable
    segments: list[str | Callable]
    _widgets: list[widgets.HTMLMath]    # one per segment
    _last_values: list[str]            # cached rendered text per segment
    _is_dynamic: list[bool]            # True for callable segments
    root: widgets.Box                  # flex-wrap container holding _widgets
```

### 3.3 Segment classification

At card construction, each segment is classified once:

- `isinstance(seg, str)` → **static**. Rendered into an `HTMLMath` widget immediately. Never touched again.
- `callable(seg)` → **dynamic**. Called as `seg(fig)` immediately for initial render, and again on every `update(fig)`.
- Anything else → `TypeError` at construction time.

---

## 4. InfoCard lifecycle

### 4.1 Construction (`__init__`)

```python
def __init__(self, id: Hashable, segments: list, fig: SmartFigure):
    self.id = id
    self.segments = list(segments)
    self._is_dynamic = [callable(s) for s in segments]
    self._widgets = []
    self._last_values = []

    for i, seg in enumerate(segments):
        text = self._eval_segment(seg, fig)
        self._last_values.append(text)
        self._widgets.append(widgets.HTMLMath(value=text))

    self.root = widgets.Box(
        children=self._widgets,
        layout=widgets.Layout(
            display="flex",
            flex_flow="row wrap",
            align_items="baseline",
        ),
    )
```

### 4.2 Segment evaluation

```python
def _eval_segment(self, seg, fig: SmartFigure) -> str:
    if isinstance(seg, str):
        return seg
    try:
        result = seg(fig)
        return str(result)
    except Exception as e:
        return f"<span style='color:red'>[ERROR: {type(e).__name__}: {e}]</span>"
```

Key points:
- The callable receives `fig` — nothing else.
- The callable is responsible for accessing what it needs through `fig`.
- Errors are rendered inline in red. They never propagate. They never break the figure.

### 4.3 Update (called on param change)

```python
def update(self, fig: SmartFigure) -> None:
    for i, seg in enumerate(self.segments):
        if not self._is_dynamic[i]:
            continue                        # skip static segments entirely
        text = self._eval_segment(seg, fig)
        if text != self._last_values[i]:    # skip if unchanged
            self._last_values[i] = text
            self._widgets[i].value = text
```

This is the entire incremental update logic. No run splitting, no state machine, no structure-change detection. Static widgets are never touched. Dynamic widgets are updated only when their text changes. The `HTMLMath` widget handles mixed text and LaTeX natively — there is no need for a separate HTML-vs-math split because `HTMLMath` already renders both.

---

## 5. InfoPanelManager

### 5.1 `info(...)` — add or replace

```python
def info(self, segments: list, id: Hashable | None, fig: SmartFigure) -> Hashable:
    # 1. Resolve id
    if id is None:
        self._counter += 1
        id = f"info:{self._counter}"
    elif isinstance(id, str):
        m = self._ID_REGEX.match(id)
        if m:
            n = int(m.group(1))
            self._counter = max(self._counter, n + 1)  # ← fixed: n+1, not n

    # 2. Build new card
    card = InfoCard(id, segments, fig)

    # 3. Insert or replace
    replacing = id in self._cards
    self._cards[id] = card              # preserves position if key exists

    # 4. Rebuild children
    self._layout_box.children = tuple(c.root for c in self._cards.values())

    return id
```

**Auto-id counter fix:** The existing code sets `self._counter = max(self._counter, int(n))`. After `get_output("info:5")`, `_counter == 5`, then `get_output(None)` increments to 6 before use, so it happens to work. But the intent is clearer and safer as `max(self._counter, n + 1)`. This also avoids a bug if the counter were ever used without pre-increment (as in the new `info()` method above where `_counter += 1` happens only for `id is None`).

**Replace semantics:** Replacing an id builds a **new** `InfoCard` with new widgets. The old card's widgets are discarded when `_layout_box.children` is reassigned. The ordering is preserved because Python dicts preserve insertion order on key reassignment.

### 5.2 `update_all(...)`

```python
def update_all(self, fig: SmartFigure) -> None:
    for card in self._cards.values():
        card.update(fig)
```

### 5.3 `remove(id)` and `clear()`

```python
def remove(self, id: Hashable) -> bool:
    if id not in self._cards:
        return False
    del self._cards[id]
    self._layout_box.children = tuple(c.root for c in self._cards.values())
    return True

def clear(self) -> None:
    self._cards.clear()
    self._layout_box.children = ()
```

Both must be followed by a sidebar visibility update in `SmartFigure`.

### 5.4 `has_info`

```python
@property
def has_info(self) -> bool:
    return len(self._cards) > 0
```

---

## 6. SmartFigure integration

### 6.1 `SmartFigure.info`

```python
def info(
    self,
    segments: list,
    id: Hashable | None = None,
) -> Hashable:
    effective_id = self._info.info(segments, id=id, fig=self)
    self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
    return effective_id
```

### 6.2 `SmartFigure.remove_info` / `SmartFigure.clear_info`

```python
def remove_info(self, id: Hashable) -> bool:
    removed = self._info.remove(id)
    if removed:
        self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
    return removed

def clear_info(self) -> None:
    self._info.clear()
    self._layout.update_sidebar_visibility(self._params.has_params, self._info.has_info)
```

### 6.3 `SmartFigure.render` modification

```python
def render(self, reason: str = "manual", trigger: Optional[ParamEvent] = None) -> None:
    self._log_render(reason, trigger)

    # 1. Update all plots
    for plot in self.plots.values():
        plot.render()

    # 2. On param change: update info cards, then run hooks
    if reason == "param_change" and trigger:
        self._info.update_all(self)                          # ← NEW
        hooks = self._params.get_hooks()
        for h_id, callback in list(hooks.items()):
            try:
                callback(trigger)
            except Exception as e:
                warnings.warn(f"Hook {h_id} failed: {e}")
```

---

## 7. Error handling

All errors are isolated to the individual segment that caused them.

| Failure | Behavior |
|---|---|
| Callable raises during initial render | Segment displays `[ERROR: ExcType: message]` in red |
| Callable raises during update | Same — segment shows error, other segments unaffected |
| Callable returns non-stringifiable object | Caught by `str()` failing — same error display |
| Bad segment type (not str, not callable) | `TypeError` raised at `InfoCard.__init__` time (fail fast) |

Errors never propagate to `render()`. The `update()` method catches per-segment, and the `update_all()` caller in `render()` should additionally be wrapped:

```python
# In render():
try:
    self._info.update_all(self)
except Exception as e:
    warnings.warn(f"Info panel update failed: {e}")
```

---

## 8. What callable authors use

The callable's only argument is `fig: SmartFigure`. From there:

| Need | Access pattern |
|---|---|
| Parameter value | `fig.params[a].value` |
| All parameter values as dict | `fig.params.snapshot()` → `dict[Symbol, float]` |
| Full parameter metadata | `fig.params.snapshot(full=True)` → `ParameterSnapshot` |
| Plot's symbolic expression | `fig.plots['id'].symbolic_expression` |
| Plot's numeric evaluator | `fig.plots['id'].numeric_expression` (returns `PlotView`) |
| Plot's compiled function | `fig.plots['id'].numpified` (returns `NumpifiedFunction`) |
| Axis ranges | `fig.x_range`, `fig.y_range` |

Typical pattern:

```python
fig.info([
    "Slope at $x=0$: ",
    lambda fig: f"${sp.latex(sp.diff(fig.plots['line'].symbolic_expression, x).subs(x, 0))}$",
])
```

Or for something that uses live parameter values:

```python
def show_value(fig):
    val = fig.params[a].value
    return f"$a = {val:.3f}$"

fig.info(["Parameter: ", show_value])
```

---

## 9. Backward compatibility and removal

### Remove

- `SmartFigure.add_info_component(...)` and the hook it registers
- `InfoPanelManager.add_component(...)` / `get_component(...)`
- `InfoPanelManager._components` dict

### Keep (separate concern, not replaced)

- `SmartFigure.get_info_output(...)` — raw `widgets.Output` for advanced use cases (direct printing, matplotlib embeds, etc.). This is orthogonal to the template card system.
- `InfoPanelManager.get_output(...)` — underlying implementation for the above.
- `InfoPanelManager._outputs` — storage for raw outputs.

### Coexistence

`_cards` and `_outputs` are separate dicts. Both contribute children to `info_box`. Rebuild children as:

```python
children = tuple(c.root for c in self._cards.values()) + tuple(self._outputs.values())
self._layout_box.children = children
```

Update `has_info`:

```python
@property
def has_info(self) -> bool:
    return len(self._cards) > 0 or len(self._outputs) > 0
```

---

## 10. Implementation steps

1. **`InfoCard` class** — segment classification, `_eval_segment`, `__init__`, `update()`.
2. **`InfoPanelManager` additions** — `info()`, `remove()`, `clear()`, `update_all()`. Fix auto-id counter to use `n + 1`. Rebuild children to include both `_cards` and `_outputs`.
3. **`SmartFigure.info()`** — forward to manager, update sidebar visibility.
4. **`SmartFigure.remove_info()` / `clear_info()`** — forward + visibility.
5. **`SmartFigure.render()` modification** — add `self._info.update_all(self)` gated on `reason == "param_change"`.
6. **Module-level `info()` function** — delegates to current figure.
7. **Remove** `add_info_component`, `add_component`, `get_component`, `_components`.

---

## 11. Testing checklist

- Static-only card: strings render as LaTeX, never re-evaluated on param change.
- Dynamic-only card: callable receives `fig`, result renders, updates on param change.
- Mixed card: static segments untouched during update; dynamic segments refresh.
- Unchanged dynamic values: `widget.value` is **not** reassigned (no unnecessary MathJax re-render).
- Error in callable: red inline error, other segments and other cards unaffected.
- Auto-id: `info(segs)` → `"info:1"`, again → `"info:2"`.
- Explicit id bump: `info(segs, id="info:5")` → next auto-id is `"info:6"`.
- Replace: `info(new_segs, id=existing)` replaces content, preserves order.
- Remove: `remove_info(id)` removes card, sidebar hides if empty.
- Relayout does **not** trigger info update.
- `get_info_output` still works alongside `info()` cards.
