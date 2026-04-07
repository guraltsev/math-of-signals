# Implementing SmartPad2D (2D draggable control for two parameters)

## Scope and goals

### Goals
- Implement a new parameter control widget `SmartPad2D` that controls **two symbols** via a draggable point in a square domain.
- Integrate with the refactored ParameterManager (Document 1) so that:
  - registering a pad for `(a, b)` prevents creation of separate sliders for `a` and `b` during parameter autodetection,
  - `fig.params.get_value(a)` / `fig.params.get_value(b)` return current values,
  - changes (dragging, typing values) trigger rerender/hook pipeline.

### Non-goals
- No polar/simplex controls here (but design must not preclude them).
- No new hook API; reuse the existing “param change → render” behavior.

---

## User-facing API

### Primary API (explicit control registration)
Add to `SmartFigure`:
- `fig.add_control(control) -> control`

Usage:
```python
a, b = sp.symbols("a b")
pad = SmartPad2D(symbols=(a, b), label="(a,b)")
fig.add_control(pad)
fig.plot(x, sp.sin(a*x + b))
```

### Optional convenience helper
- `fig.add_pad2d((a, b), **kwargs) -> SmartPad2D`
  - constructs and registers the pad

### Autodetection interaction
If `SmartPad2D` owns `a` and `b`, then `SmartFigure.plot(..., parameters=None)` must not create sliders for `a` or `b`. This is achieved if `ParameterManager.ensure_param(sym)` no-ops when `sym` is already owned.

---

## Widget UI specification

`SmartPad2D` appears as a single entry in the parameter sidebar, analogous to a slider entry.

### Layout
- **Header row**
  - label (HTMLMath or plain): e.g. `$(a,b)$` or user-supplied label
  - reset button ↺
  - settings toggle ⚙ (optional)

- **Body row**
  - left: square pad (canvas or SVG), representing normalized coordinates `[-1,1]×[-1,1]`
    - boundary box
    - optional faint grid / axes
    - draggable handle (dot)
  - right: two numeric fields (Text inputs), one per symbol
    - `a = [text]`
    - `b = [text]`
    Parsing and validation should match `SmartFloatSlider` style:
    - use `InputConvert`
    - invalid input reverts to last valid value

- **Settings panel** (collapsed by default)
  - for each symbol: min/max/step/value editors (Text inputs using `InputConvert`)
  - live update toggle (continuous during drag vs commit-on-release)
  - optional throttle parameter for drag events

### Styling
- Compact, visually consistent with existing slider widgets in the sidebar.

---

## Semantics: values and mapping

### Required external contract
`SmartPad2D` must expose a dictionary indexed by symbols:

- `values() -> dict[Symbol, float]`
  - returns `{a: a_value, b: b_value}`

Also support:
- `symbols = (a, b)`
- `widget` (displayable ipywidget; usually `self`)
- `get_value(symbol)` / `set_value(symbol, value)`
- `on_change(callback)`

### Coordinate model
To keep the figure agnostic and enable alternative coordinate systems later:
- the pad maintains **normalized** coordinates:
  - `u, v ∈ [-1, 1]` (pure UI coordinate system)
- the actual parameter values are derived internally using per-axis min/max/step:
  - `a_value = map_axis(u, a_min, a_max, a_step)`
  - `b_value = map_axis(v, b_min, b_max, b_step)`

#### Default mapping (linear)
- Map `[-1,1]` to `[min,max]` via affine transform.
- Apply `step` quantization in **parameter space** (after mapping).

Inverse mapping (value → normalized):
- Convert `a_value` back to `u` in `[-1,1]` for handle placement.
- Same for `b_value`.

All min/max/step behavior is internal to the widget.

---

## Implementation architecture

## 1) Composition strategy (recommended)
Implement `SmartPad2D` as a Python-side composite widget that contains:
- a small anywidget-based drawing/dragging component for the pad,
- standard ipywidgets controls for numeric fields and settings panel.

This keeps JS focused only on pointer events + drawing.

### Sub-widget: `Pad2DCanvas` (anywidget)
Implement an `anywidget.AnyWidget` that:
- renders a square pad with a draggable handle,
- computes normalized coordinates `(u,v)` from pointer position,
- syncs `u` and `v` to Python via traitlets.

Traitlets synced to JS:
- `u: Float` (default 0.0)
- `v: Float` (default 0.0)
- `live_drag: Bool`
- `throttle_ms: Int`
- optional purely-visual toggles (grid, etc.)

The JS layer does not know about SymPy symbols.

## 2) SmartPad2D core state (Python)
Python-side fields:
- `symbols: tuple[Symbol, Symbol]`
- per-axis config:
  - `a_min, a_max, a_step, a_value`
  - `b_min, b_max, b_step, b_value`
- `pad: Pad2DCanvas`
- numeric input widgets for `a` and `b`
- settings widgets for min/max/step/live_drag/throttle

Expose:
- `widget` (usually `self`)
- `values()` / `get_value()` / `set_value()` / `configure()`
- `on_change(cb)`

## 3) Synchronization and wiring

### A) Dragging updates values
Observe `pad.u` and `pad.v` changes:
- compute new `a_value, b_value`
- update numeric text fields (formatted values)
- emit a single “values changed” event via registered callbacks

### B) Numeric edits update handle
On committing a new numeric value for `a` or `b`:
- parse with `InputConvert`
- clamp to `[min,max]`
- quantize by `step` if set
- update internal `*_value`
- compute inverse mapping to update `pad.u/v` so the handle moves

### C) Prevent feedback loops
Use a `_syncing` guard flag during programmatic updates to avoid infinite observer loops.

---

## Change notification: `on_change(callback)`

### Required behavior
`SmartPad2D.on_change(cb)` should invoke `cb(change)` whenever either parameter changes due to:
- drag
- numeric edit
- reset
- config changes that affect current values (e.g., min/max tightening)

### Payload shape (recommended)
Use a stable, self-describing payload for pad changes:
```python
{
  "owner": self,
  "name": "values",
  "type": "change",
  "old": {a: old_a, b: old_b},
  "new": {a: new_a, b: new_b},
}
```
Slider-origin events remain unchanged in the system (raw observe dict), preserving any slider-only expectations.

Recommendation: hooks should use `fig.params.get_value(sym)` for correctness.

---

## ParameterManager integration

With Document 1’s manager:
- `fig.add_control(pad)` calls `ParameterManager.register_control(pad)`.
- `_owner[a] = pad`, `_owner[b] = pad`.
- autodetection calls `ensure_param(a)`, `ensure_param(b)`; both no-op.

`get_value(a)` and `get_value(b)` forward into `pad.get_value(...)`.

---

## Performance considerations

### Drag throttling
During drag, avoid excessive rerenders:
- implement throttling in `Pad2DCanvas` JS layer using `throttle_ms` (e.g. 30–60ms).
- optionally expose `live_drag` toggle:
  - True: continuous updates during drag
  - False: only commit on pointer release (safer for expensive plots)

### Quantization
Apply `step` quantization in parameter space to match user expectations.

---

## Validation plan

### Manual tests
1. Register pad for `(a,b)` and plot something depending on both; dragging changes plot.
2. No separate sliders appear for `a` and `b`.
3. Typing numeric values updates plot and moves handle.
4. Editing min/max/step clamps/quantizes correctly and keeps handle in bounds.
5. Reset returns defaults (values + handle).
6. Existing `add_param_change_hook` hooks execute on pad changes.

### Edge cases
- Invalid numeric input: revert to last valid value.
- min > max: define internal policy (swap or reject); document and implement consistently.
- step <= 0: ignore/revert.
- values outside bounds: clamp.

---

## Extension points (future controls)
This design supports other coordinate systems (e.g., polar) because the system only requires:
- `symbols`
- `values dict`
- `get_value/set_value/configure`
- `on_change`

A polar control implements its own internal mapping and UI; ParameterManager does not change.

---

## Decisions to fix before implementation (if you want defaults baked in)
- Default `live_drag`: True vs False
- Default min/max/step for each axis if not provided
- Conflict policy if a symbol already has a slider when registering `SmartPad2D` (raise vs replace)
