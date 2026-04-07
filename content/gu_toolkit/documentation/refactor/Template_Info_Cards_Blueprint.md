# Blueprint: Template-Based Info Cards for SmartFigure

## 0. Scope and constraints (non-negotiable)

This blueprint implements **template-string-only** Info cards in the SmartFigure Info panel.

Hard constraints:

- **No callable factories** for cards (template strings only).
- **No registration system** for card types.
- **No public knobs** like `on="params"` or `run_now`.
- **No public `env=` argument**.
- **Replacing behavior:** calling `info(..., id=existing_id)` **replaces** that card.
- **Auto-ID behavior:** calling `info(..., id=None)` **auto-allocates** an id using the existing “auto-incremented id” convention already used elsewhere (e.g. `info:1`, `info:2`, …).
- **Dynamic content must remain visibly wrapped in `{...}`** after evaluation (so the “possibly changed parts” are emphasized).
- **Dynamic expression results may contain LaTeX**, and the rendering pipeline must detect that.
- **Rerender only what changed**: do not touch static text runs or unchanged dynamic runs.
- You already have a system to evaluate plotted functions with attached parameters. This design **does not** add parameter binding logic; it only evaluates template expressions in a suitable context and renders results efficiently.

Implementation objective:

- Replace the current “component factory + update hook” approach with a single, intuitive entry point:
  - `SmartFigure.info(template, id=None)`

---

## 1. Public API

### 1.1 SmartFigure.info

Add:

```python
SmartFigure.info(template: str, id: Hashable | None = None) -> Hashable
```

Behavior:

1. If `id` is `None`, allocate an auto-id such as `info:1`, `info:2`, … and return it.
2. If `id` exists, replace the card at that id (preserving ordering).
3. If `id` is new, append it at the end of the info panel.
4. Render immediately (the initial render is part of the call; no “run_now” flag).
5. On subsequent parameter-driven figure refreshes, the info cards refresh automatically (see §6).

Return value:
- The effective card id (useful to update/replace later).

### 1.2 Optional small convenience (if desired)

If you want a “set/replace” semantic name:

```python
SmartFigure.set_info(id: Hashable, template: str) -> Hashable
```

But this is optional. The single `info(..., id=...)` method is sufficient.

---

## 2. Architecture and responsibilities

### 2.1 SmartFigure responsibilities (orchestration)

SmartFigure is responsible for:

- Forwarding user calls: `SmartFigure.info(...)` delegates to `InfoPanelManager.info(...)`.
- Ensuring info cards refresh when the figure refreshes (see §6).
- Toggling sidebar visibility based on whether info cards exist (reusing the layout logic already present).

SmartFigure should not store per-card parsing logic; that belongs in card objects.

### 2.2 InfoPanelManager responsibilities (thin manager)

InfoPanelManager remains, but it becomes a thin container and dispatcher:

- Stores cards by id (ordered).
- Allocates auto-ids.
- Replaces cards by id.
- Rebuilds the `info_box.children` list when cards are added/removed/replaced.
- Provides `update_all(...)` to refresh all cards on figure render.

It should not implement a registry of card classes or a “component factory” system.

### 2.3 InfoCard responsibilities (workhorse)

Each card:

- Stores the raw template string.
- Compiles the template into “static + dynamic slot” segments.
- On update, evaluates dynamic slots, formats them, wraps them in braces, then splits into rendering runs.
- Updates only the widgets whose values changed.

---

## 3. Data structures

### 3.1 InfoPanelManager state

- `self._cards: dict[Hashable, InfoCard]`  
  Ordered map from id to InfoCard. In Python 3.7+, dict preserves insertion order. Replacing an existing key preserves position.

- `self._counter: int`  
  Next counter for auto-id allocation.

- `self._box: ipywidgets.VBox` (or whatever container you use for the info panel)  
  The widget container that displays the cards.

### 3.2 InfoCard state

- `self.id: Hashable`
- `self.template_raw: str`
- `self.program: CompiledTemplate`
- `self.root: ipywidgets.Widget` (container for runs, typically a `HBox`/`Box` with flex-wrap)
- `self._runs: list[RunNode]` (current widgets and cached values)
  - `RunNode.kind: "html" | "math"`
  - `RunNode.widget: widgets.HTML | widgets.HTMLMath`
  - `RunNode.last_value: str`

### 3.3 CompiledTemplate

Represents the parsed template:

- `self.parts: list[TemplatePart]`
  - `LiteralPart(text: str)`
  - `SlotPart(code: CodeType, format_spec: str | None, conversion: str | None, source_text: str)`  
    - `code` is compiled once from the slot expression AST.
    - `source_text` is the original `{...}` expression for diagnostics.

---

## 4. Template parsing and compilation

### 4.1 Why use AST instead of ad hoc splitting

Requirements include:
- nested braces in Python expressions
- escaped braces `{{` / `}}`
- format specs `:.3g` etc.

Hand splitting on `{`/`}` is fragile. Instead, parse using Python’s f-string machinery.

### 4.2 Parsing strategy

Given user `template_raw` (a normal string, not an f-string), parse it as an f-string by wrapping:

- Build a Python expression source: `expr_src = "f" + repr(template_raw)`
- Parse: `node = ast.parse(expr_src, mode="eval")`
- Expect: `node.body` is `ast.JoinedStr`

From the `JoinedStr.values` list:
- `ast.Constant(str)` → LiteralPart
- `ast.FormattedValue` → SlotPart:
  - Extract the expression AST (`.value`)
  - Extract format spec (if present):
    - Start with support for **constant** format specs only. If the format spec contains `FormattedValue` nodes, raise a clear error (“dynamic format specs not supported yet”).
  - Extract conversion (e.g. `!r`, `!s`) if used

Compilation:
- Compile each slot expression AST: `compile(ast.Expression(expr_ast), filename="<SmartFigure.info>", mode="eval")`

Store the compiled `code` in SlotPart.

---

## 5. Evaluation context (no `env` argument)

### 5.1 Context principle

Expressions inside `{...}` should “feel like notebook code”: they can reference user names already defined in the cell.

Therefore, evaluation needs access to the caller’s namespace.

### 5.2 Context sources (priority)

On each evaluation (and/or at card construction), build:

1. **User namespace**:
   - If running in IPython/Jupyter: use `get_ipython().user_ns` when available.
   - Otherwise: fall back to `inspect.currentframe().f_back.f_globals` and `f_locals` captured at the call site.

2. **Injected locals** (added on top):
   - `fig`: the SmartFigure instance
   - Optional convenience aliases (only if already consistent with your codebase):
     - `plots`: `fig.plots`
     - `params`: `fig.params` (or whatever the public parameter view is)
   - Any other minimal helpers that are already stable in your codebase.

3. **No `env=` parameter**:
   - Users can always define names in the notebook (functions/constants/sympy symbols) and reference them inside `{...}`.

### 5.3 Evaluation behavior

For each SlotPart:
- `val = eval(code, user_globals, user_locals)`
- Apply conversion (`!r`, `!s`, `!a`) if present.
- Apply format spec if present:
  - Use `format(val, spec)` (after conversion, if you follow f-string rules).
- Convert to string:
  - If already `str`, keep as is.
  - Else use `str(val)`.

---

## 6. Update cycle integration (no `on=...`, no `run_now`)

### 6.1 Single source of truth: SmartFigure.render

Your figure already refreshes on parameter changes (and presumably calls `render`).

Integrate info updates into that existing cycle:

- In `SmartFigure.render(...)` (or wherever you commit plot updates), call:

```python
self._info.update_all(fig=self, reason="render", event=event)
```

This ensures:
- initial `info(...)` call renders once immediately
- subsequent parameter changes cause `render` (already) and thereby update the cards
- no special hook interface is exposed for info cards

### 6.2 Ordering of operations in render

Recommended:
1. Update plots/traces
2. Then update info cards (so info sees the latest plot state)
3. Then any final layout/visibility toggles

---

## 7. Building the “expanded string” with brace-wrapped dynamic parts

You requested:

> output of python function calls should be obtained first (it can contain LaTeX). Then the string should be split. One emphasizing changed parts would be to require that all dynamic content be still wrapped in {} after the function calls.

Implement exactly:

- For each slot:
  - compute `slot_text` (a string, possibly containing LaTeX)
  - replace the slot with `"{" + slot_text + "}"` in the expanded string

This makes dynamic regions explicit in the final rendered text.

Notes:
- If users want literal braces, they use `{{` / `}}` in the template, which is handled by the f-string parser.

---

## 8. Splitting into render runs (HTML vs HTMLMath)

Goal:
- Rerender minimal parts by keeping stable widgets for each run.

### 8.1 Run splitting requirement

The expanded string may contain LaTeX segments introduced by:
- static template text
- dynamic slot output strings

Therefore, splitting must happen **after** slot evaluation.

### 8.2 Recognized math delimiters

Support at least:
- `$...$`
- `$$...$$`
- `\(...\)`
- `\[...\]`

### 8.3 Splitting algorithm (state machine)

Implement a single left-to-right scan that emits runs:

- Maintain index `i` into the expanded string.
- At each position, detect whether a math delimiter starts:
  - `$$` (priority over `$`)
  - `$`
  - `\(`, `\)`
  - `\[`, `\]`

When outside math:
- emit HTML run for maximal substring up to the next math-start delimiter.

When inside math:
- find the matching closing delimiter (same kind).
- emit MATH run including delimiters (so HTMLMath renders it).

If a delimiter is unclosed:
- treat the remainder as HTML run (or render an error marker; choose one).

Output:
- `runs: list[tuple[kind, text]]`, where `kind ∈ {"html","math"}`

---

## 9. Incremental rendering and caching

### 9.1 Widget strategy

For each run:
- `kind == "html"` → `widgets.HTML(value=...)`
- `kind == "math"` → `widgets.HTMLMath(value=...)`

Container:
- Use a `widgets.Box` with CSS for inline flow and wrapping, e.g. flex-wrap:
  - `display: flex; flex-flow: row wrap; align-items: baseline; gap: ...;`
  - This keeps long sentences readable and avoids huge vertical blocks.

### 9.2 Update algorithm

Given `new_runs` from §8:

Case A: Structure stable
- If `len(new_runs) == len(old_runs)` and all `kind` match:
  - For each run `k`:
    - If `new_text != last_value`:
      - update `widget.value = new_text`
      - update cache `last_value = new_text`
    - Else do nothing

Case B: Structure changed
- Rebuild the entire run widget list:
  - create new widgets for all runs
  - replace `root.children`
  - set `_runs = new_runs_nodes`

Rationale:
- Numerical changes typically keep structure stable (same LaTeX delimiters), so updates are cheap.
- If a slot begins/ends a LaTeX environment dynamically, structure changes; rebuilding is acceptable.

---

## 10. Replace semantics by id

### 10.1 Replace in-place (preserve ordering)

In InfoPanelManager:

- If `id` exists in `self._cards`:
  - overwrite: `self._cards[id] = new_card`
  - insertion order remains unchanged
- Else:
  - insert at end

After add/replace:
- rebuild children once:
  - `self._box.children = tuple(card.root for card in self._cards.values())`

### 10.2 Auto-id allocation

Adopt the same approach used in existing manager code:
- Prefer ids like `info:<n>`
- Maintain `self._counter`
- If user passes `id="info:17"` explicitly, bump counter to at least 18.

Algorithm:
1. If `id is None`:
   - allocate `f"info:{self._counter}"`
   - increment `self._counter` until unused id found (or use a while loop)
2. If `id matches r"^info:(\d+)$"`:
   - bump counter to `max(counter, int(n)+1)`

---

## 11. Error handling

Per-slot errors should never break the figure:

- If evaluation raises:
  - Render `"{ERROR: <ExceptionName>: <message>}"` for that slot.
- If template parsing fails:
  - Card renders a single HTML run containing a readable error message.
- If LaTeX splitting finds unclosed delimiters:
  - Choose a deterministic fallback:
    - treat remainder as HTML, or
    - show an explicit `"[UNTERMINATED MATH]"` marker.

All errors are isolated to the card.

---

## 12. Sidebar visibility integration

InfoPanelManager should expose:

- `has_info: bool` (`len(self._cards) > 0`)

SmartFigure should call:

```python
self._layout.update_sidebar_visibility(has_params=..., has_info=self._info.has_info)
```

after add/remove/clear operations.

---

## 13. Refactor/removal plan (no backwards compatibility required)

Remove or retire the previous API surface for info cards:

- Remove `SmartFigure.add_info_component(...)`
- Remove InfoPanelManager’s “component registry / instances” logic if present
- Remove “run_now” variants associated with info-card updates

If you want to keep an escape hatch:
- keep a method like `SmartFigure.info_output(id=...)` returning a raw `widgets.Output`, but it should be considered advanced and not the primary card system.

---

## 14. Implementation steps (ordered)

1. **Introduce new classes**
   - `CompiledTemplate`
   - `InfoCard`
2. **Implement template parser**
   - `CompiledTemplate.from_string(template_raw)`
3. **Implement evaluator**
   - `CompiledTemplate.evaluate(context) -> expanded_str` (brace-wrapped dynamic results)
4. **Implement run splitter**
   - `split_runs(expanded_str) -> list[(kind,text)]`
5. **Implement InfoCard rendering**
   - `InfoCard.__init__` builds empty root container
   - `InfoCard.update(fig)` evaluates → splits → incremental widget update
6. **Thin InfoPanelManager**
   - store cards
   - allocate ids
   - replace semantics
   - `update_all(fig)` calls `card.update(fig)` for each card
7. **SmartFigure.info**
   - delegates to manager: `id = self._info.info(template, id=id, fig=self)`
   - renders card immediately; updates sidebar visibility
8. **Wire into SmartFigure.render**
   - call `self._info.update_all(...)` after plot updates
9. **Delete old path**
   - remove `add_info_component` and component registries

---

## 15. Testing checklist

### Parsing and formatting
- `{{` and `}}` render literal braces
- `{x:.3g}` formatting works
- invalid template produces deterministic error message in-card

### Auto-id and replace
- `info(None)` produces `info:1`, `info:2`, ...
- `info(template, id="info:17")` bumps future auto-id to `info:18`
- replacing an existing id preserves ordering

### Incremental update
- slider/parameter movement changes only the dynamic runs (static runs untouched)
- if structure unchanged, widget list unchanged (only `.value` updates)
- if structure changes (e.g. dynamic LaTeX delimiter introduced), card rebuild is correct

### Error isolation
- slot evaluation error doesn’t break figure render
- LaTeX delimiter mismatch handled predictably

### Performance
- repeated updates with unchanged values do not assign `.value` (no unnecessary MathJax activity)

---

## 16. Notes on future extensions (out of scope)

- Rich card layouts (tables, multi-line, plots inside cards)
- Dynamic format specs (format spec itself computed)
- Card-level throttling/debouncing for very high-frequency updates
- User-configurable math delimiter policies

These can be layered on without changing the public API.
