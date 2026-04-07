# Summary: Template-Based Info Cards (SmartFigure)

## Goal
Replace the existing “component factory + update hook” info-card system with a **template-string API**:

```python
fig.info("Text with {python_expr} and LaTeX $...$")
```

Dynamic expressions are evaluated; their results may contain LaTeX; and only changed parts are rerendered.

---

## Public API
```python
fig.info(template: str, id: Hashable | None = None) -> Hashable
```

- `id=None` ⇒ auto-id `info:1`, `info:2`, …
- `id=existing` ⇒ replace card in place (preserve order)
- renders immediately; subsequent updates occur during `SmartFigure.render()` (no `run_now`, no `on=...`)

No registration, no callable factories, no `env=` argument.

---

## Core design
### InfoPanelManager (thin)
- stores `id -> InfoCard` (ordered)
- allocates auto-ids; bumps counter when user supplies `info:n`
- replaces/clears cards and rebuilds `info_box.children`
- `update_all(fig)` refreshes all cards

### InfoCard (does the work)
1) Parse template as an f-string using `ast.JoinedStr`  
2) Compile slot expressions once  
3) On update:
   - evaluate each `{...}` slot in notebook/user namespace
   - convert to string
   - **wrap each dynamic result as `{<result>}`** in the final expanded text
4) Split expanded text into runs:
   - HTML runs (`widgets.HTML`)
   - Math runs (`widgets.HTMLMath`) recognizing `$...$`, `$$...$$`, `\(...\)`, `\[...\]`
5) Incremental update:
   - if run structure unchanged, update only runs whose text changed
   - if structure changed, rebuild run widgets

---

## Update integration
- Refresh info cards inside `SmartFigure.render()` after plot updates:
  - `self._info.update_all(fig=self, ...)`

This eliminates separate info hooks and removes “run_now”.

---

## Error handling
- Slot evaluation errors render as `{ERROR: ...}` inside the card (isolated; never breaks rendering).
- Unclosed LaTeX delimiters handled deterministically (fallback to HTML or explicit marker).

---

## Implementation steps
1. Implement `CompiledTemplate` (AST parsing + compiled slots)
2. Implement `split_runs(expanded_str)` (state machine)
3. Implement `InfoCard.update(fig)` with caching + incremental widget updates
4. Simplify `InfoPanelManager` to store/replace/update cards
5. Add `SmartFigure.info(...)` forwarding to manager
6. Call `update_all` from `SmartFigure.render()`
7. Remove old `add_info_component` / registry logic
