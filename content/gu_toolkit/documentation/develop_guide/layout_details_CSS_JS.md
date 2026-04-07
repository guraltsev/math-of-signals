# SmartFigure / SmartSlider Layout Details

This document explains the current layout design for SmartFigure + SmartFloatSlider settings modal behavior,
and captures **what worked** and **what failed** during implementation.

The goal is to make future changes predictable and avoid repeating the regressions that happened while
fixing modal placement.

---

## 1) What the current design is

### 1.1 SmartFigure layout structure (host side)

SmartFigure builds a `root_widget` that contains:

1. title row
2. content wrapper with:
   - plot container
   - sidebar container (parameters + info)

The slider modal must appear **over this whole root output view** (plot + parameter area), not below,
and not necessarily over the full browser viewport.

### 1.2 SmartSlider modal structure (control side)

Each `SmartFloatSlider` contains:

- top row with slider controls
- `settings_modal` wrapper box
  - `settings_panel` (actual dialog)

Important classes used by the modal system:

- `.smart-slider-settings-modal`
- `.smart-slider-settings-modal-hosted`
- `.smart-slider-settings-modal-global`
- `.smart-slider-modal-host`
- `.smart-slider-settings-panel`

### 1.3 Hosted vs global modes

The slider modal has two positioning modes:

- **Hosted mode** (preferred in SmartFigure)
  - Modal is moved into the SmartFigure host container.
  - Classes force overlay behavior relative to host:
    - host gets `position: relative` via `.smart-slider-modal-host`
    - modal gets `position: absolute; inset: 0; width: 100%; height: 100%` via `.smart-slider-settings-modal-hosted`
  - Result: modal centers over the output widget region.

- **Global mode** (fallback)
  - Modal remains attached locally and uses full viewport overlay
    via `.smart-slider-settings-modal-global`.
  - Result: modal centers over browser viewport.

---

## 2) Why this approach is used

### 2.1 Cross-version ipywidgets compatibility

Directly reading/writing `host.layout.position` caused runtime failures in some environments
(e.g. `AttributeError: 'Layout' object has no attribute 'position'`).

So positioning is now applied with CSS classes (`add_class`) and `!important` rules.
This avoids depending on unavailable layout traits.

### 2.2 Reliable overlay behavior

The modal previously appeared at the bottom of the figure because it was still participating in normal
layout flow in certain cases.

Class-based absolute/fixed positioning with `inset: 0` is robust and forces overlay semantics.

---

## 3) Wrong approaches (do not repeat)

### 3.1 Relying only on `layout.position/top/left/...` writes

**Why wrong:** Not portable across all ipywidgets versions/configurations and may silently fail or crash.

### 3.2 Mixing host intent with viewport-forcing CSS

If hosted modal CSS still forces `position: fixed`/viewport behavior, it will not center in output view.

**Rule:** Hosted mode and global mode must remain separate and mutually exclusive classes.

### 3.3 Leaving modal attached to slider subtree when host overlay is needed

If modal is not moved under host, absolute positioning references the wrong box and can appear misplaced
or below content.

### 3.4 Weak CSS specificity

Notebook themes/lab CSS can override widget styles.

**Rule:** Keep modal-critical styles in explicit classes with `!important` where necessary
(positioning, size, z-index, panel surface/shadow).

### 3.5 Partial state switches

Changing position without removing old class can create conflicting rules.

**Rule:** `set_modal_host(...)` must always:

- remove class for previous mode
- add class for target mode
- move modal to correct parent

in a single operation.

---

## 4) Right approaches (recommended)

### 4.1 Keep mode-switching centralized in `set_modal_host`

All parent re-attachment and class swapping should stay in one method.

### 4.2 Keep host setup explicit

When hosting modal in a container, ensure that container has the host class
(`.smart-slider-modal-host`) so absolute overlay has the correct containing block.

### 4.3 Use class-driven positioning contracts

Treat these as contracts:

- hosted class = in-host overlay
- global class = viewport overlay

Avoid ad-hoc geometry changes scattered through code.

### 4.4 Preserve visual layering

Panel should stay opaque and elevated:

- solid white background
- visible box shadow
- high enough z-index on modal wrapper

### 4.5 Validate with minimal checks after edits

At minimum run:

```bash
python -m py_compile SmartSlider.py SmartFigure.py
```

And manually verify in notebook:

1. settings opens centered over output widget (hosted mode)
2. not appended below figure
3. shadow visible
4. panel remains opaque
5. title includes parameter label (LaTeX)

---

## 5) Safe change checklist

Before merging layout-related changes:

- [ ] Hosted modal still uses hosted class and is attached under host children.
- [ ] Global fallback still works when no host is provided.
- [ ] No direct dependency on fragile layout traits for critical behavior.
- [ ] Mode class swap removes previous class and adds target class.
- [ ] Opaque panel + shadow preserved.
- [ ] Step input width still sufficient for values like `0.01`.
- [ ] `py_compile` passes.

---

## 6) If you must refactor

If you refactor this area:

1. Keep host/global behavior explicit and test both modes.
2. Avoid introducing intermediate states where modal has no valid positioning class.
3. Preserve the ability of `ParameterManager` to inject modal host for controls that support it.
4. Update this document when behavior contracts change.

