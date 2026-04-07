# Comprehensive Code Analysis: gu_toolkit

*Analysis date: February 2026*

---

## 1. Executive Summary

**gu_toolkit** is a Jupyter-first interactive plotting toolkit (~7,300 lines across 13 Python modules) that bridges SymPy symbolic mathematics and Plotly interactive visualization. It targets students and researchers exploring mathematical functions with real-time parameter sliders.

**Overall health: Good.** The codebase demonstrates professional design patterns, strong type safety, comprehensive documentation, and clean separation of concerns. The main areas for improvement are file organization (one oversized module), packaging (no `pyproject.toml`), and test infrastructure (custom harness instead of standard tooling).

---

## 2. Architecture Overview

### 2.1 Component Hierarchy

The architecture follows a **composition-based coordinator pattern**. SmartFigure acts as a facade, delegating to specialized internal managers:

```
SmartFigure (coordinator/facade)
  ├── SmartFigureLayout    — Widget tree, CSS, sidebar toggle
  ├── ParameterManager     — Slider state, ParamRef registry, change hooks
  ├── InfoPanelManager     — Info output widgets, dynamic components
  ├── PlotlyPane           — FigureWidget wrapper, responsive resize
  └── SmartPlot[]          — Per-plot rendering logic (one per trace)
```

### 2.2 Module Dependency Graph

Most modules are **self-contained** — only SmartFigure ties them together:

```
                    SmartFigure.py (hub)
                   /   |    |   \    \
                  /    |    |    \    \
          numpify  PlotlyPane  SmartSlider  ParamRef  NumericExpression
            │                     │            │            │
           (none)            InputConvert   ParamEvent  ParameterSnapshot
                                              │
                                            (none)

  Standalone (zero gu_toolkit imports):
    - prelude.py
    - NamedFunction.py
    - PlotlyPane.py
    - numpify.py
```

This loose coupling is a significant strength — individual modules can be tested, reused, or replaced independently.

### 2.3 Data Flow

```
User adjusts slider
  → SmartFloatSlider emits traitlets change
    → ProxyParamRef normalizes to ParamEvent (immutable dataclass)
      → ParameterManager dispatches to registered hooks
        → SmartFigure._render() called with reason string
          → SmartPlot compiles SymPy → NumPy via numpify_cached
            → NumPy arrays fed to Plotly FigureWidget traces
              → PlotlyPane handles responsive display
```

### 2.4 Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Facade** | SmartFigure | Simple API hiding internal managers |
| **Protocol** | ParamRef, _NamedFunctionSpec | Duck-typed contracts without inheritance |
| **Proxy** | ProxyParamRef | Normalizes widget events to ParamEvent |
| **Observer** | ParameterManager hooks | Parameter change notification |
| **Decorator** | @NamedFunction | Wraps functions into SymPy Function classes |
| **Strategy** | numpify expand_definition flag | Selectable compilation behavior |
| **Context Manager** | _use_figure() | Temporary figure stack manipulation |
| **Caching** | numpify_cached, SymbolFamily | LRU memoization for compiled expressions |
| **Sentinel** | FIGURE_DEFAULT | Distinguishes "not set" from None |

---

## 3. Strengths

### 3.1 Loose Coupling

Most modules have **zero internal dependencies**. `numpify.py`, `NamedFunction.py`, `PlotlyPane.py`, and `prelude.py` depend only on external libraries. This makes the codebase highly modular — any component can be extracted, tested, or replaced without affecting others.

### 3.2 Protocol-Based Contracts

`ParamRef` (`ParamRef.py:17`) is a `@runtime_checkable` Protocol, not an abstract base class. This allows any widget implementing `observe`, `value`, and `parameter` to participate without explicit inheritance — true duck typing with type checker support.

### 3.3 Three-Tier Parameter Model

The parameter system cleanly separates concerns across four layers:

- **UI Layer:** SmartFloatSlider (ipywidgets)
- **Protocol Layer:** ParamRef (observe, value, capabilities)
- **Event Layer:** ParamEvent (immutable, normalized change events)
- **State Layer:** ParameterSnapshot (frozen symbol-to-metadata mapping)

This separation means the UI can change without affecting business logic, and parameter state can be captured/replayed independently.

### 3.4 Comprehensive Type Annotations

Every module uses `from __future__ import annotations`. Coverage is approximately 95% with consistent use of:
- Generic types (`Mapping[Symbol, ...]`, `Callable[..., ...]`)
- `@runtime_checkable` Protocols
- `TypeVar` for generic constraints
- `TYPE_CHECKING` guards for circular import avoidance
- Frozen dataclasses with full type specifications

### 3.5 Thorough Documentation

- NumPy-style docstrings with Parameters/Returns/Examples/Notes on most public APIs
- A comprehensive developer guide (`documentation/develop_guide/smartfigure_developer_guide.md`)
- Design documents for major subsystems (ParamRef ref-first system, numeric expressions)
- Interactive demo notebooks doubling as integration tests

### 3.6 Smart Caching

`numpify_cached` (`numpify.py`) uses `@lru_cache(maxsize=256)` to avoid recompiling the same SymPy expression repeatedly. `SymbolFamily` (`prelude.py`) caches indexed symbols. These prevent redundant work during interactive slider use.

### 3.7 Immutability Enforcement

`ParameterSnapshot` uses `MappingProxyType` to make parameter state truly read-only. `ParamEvent` and the `DeadBound/DeadUnbound` numeric expression classes are frozen dataclasses. This prevents subtle mutation bugs in the event pipeline.

### 3.8 Numeric Expression Lifecycle

The three-state expression model is well-designed:
- `LiveNumericExpression` — evaluates against current figure state
- `DeadBoundNumericExpression` — frozen parameter values from a snapshot
- `DeadUnboundNumericExpression` — parameters known, values not yet bound

This enables both real-time interactive evaluation and reproducible offline computation.

### 3.9 Graceful Degradation

`SmartParseLaTeX` tries the `lark` backend first and falls back to `antlr` automatically. Logging uses `NullHandler` by default so the toolkit is silent unless explicitly configured. `InputConvert` falls back to SymPy expression parsing when standard numeric conversion fails.

---

## 4. Bugs and Issues

### 4.1 Thread-Unsafe Global Figure Stack

**File:** `SmartFigure.py` (module-level `_FIGURE_STACK: List[SmartFigure]`)

The figure stack is a plain module-level list. In environments with concurrent execution (e.g., Jupyter with threaded callbacks, or async notebook cells), two figures could corrupt each other's stack state. This should use `contextvars.ContextVar` for proper isolation.

### 4.2 Missing Slider Bounds Validation

**File:** `SmartSlider.py`

`SmartFloatSlider.__init__` does not validate that `min < max`. If a user passes `min=5, max=2`, the behavior depends on ipywidgets internals and may fail silently or produce a non-functional slider.

### 4.3 Inconsistent Exception Chaining

Across the codebase, some exception re-raises use `raise ... from e` (preserving context) while others use bare `raise` or `raise NewError(...)` without `from`. This makes debugging harder when errors propagate through multiple layers. Notably, `SmartParseLaTeX.py` does this correctly, but other modules are inconsistent.

### 4.4 Loose Widget Typing on ParamRef

**File:** `ParamRef.py`

The `widget` property is typed as `-> Any`, which discards type information. Any code accessing `ref.widget` loses all type checker guarantees. A `WidgetLike` protocol defining the expected widget interface would restore type safety.

### 4.5 Commented-Out Imports in `__init__.py`

**File:** `__init__.py:20-21`

```python
# from .SmartException import *
# from .SmartFigure import *
```

These commented-out lines reference a `SmartException` module that doesn't exist in the repository. This is dead code that should be removed.

---

## 5. Points of Friction

### 5.1 Oversized SmartFigure.py (3,347 lines)

`SmartFigure.py` contains at least five distinct responsibilities:
- `OneShotOutput` — display-once widget wrapper
- `SmartFigureLayout` — CSS/widget tree management
- `ParameterManager` — slider state and hooks
- `InfoPanelManager` — info panel output management
- `SmartPlot` — per-trace rendering logic
- `SmartFigure` — the coordinator itself
- Module-level helper functions (`plot()`, `params`, `parameter()`, etc.)

Navigating, reviewing, and testing this file is significantly harder than it needs to be. Each major class could live in its own module.

### 5.2 No Packaging Configuration

There is no `pyproject.toml`, `setup.py`, or `setup.cfg`. The toolkit cannot be installed via `pip install` or managed as a proper dependency. Users must manually place the directory on their Python path or use relative imports.

### 5.3 Non-Standard Test Infrastructure

Tests use a custom pytest-free harness with manual assertion helpers (`_assert_raises`) and a `main()` runner pattern. While the rationale (minimal dependencies) is documented, this creates friction for contributors who expect `pytest` conventions and makes CI integration harder.

### 5.4 Magic Strings for Render Reasons

The render callback takes a `reason` parameter as a plain string (e.g., `"param_change"`, `"relayout"`). These magic strings are not validated, not documented in one place, and not discoverable via autocomplete. An enum would provide safety and discoverability.

### 5.5 Hard-Coded CSS and Layout Constants

CSS strings (~50+ lines in SmartSlider, more in SmartFigureLayout) and layout dimensions are embedded directly in Python code. Changing the visual appearance requires editing Python source rather than a centralized style configuration.

### 5.6 Platform-Specific Tooling

`strip_ipynb.cmd` is a Windows batch script. macOS/Linux users (a large portion of the Jupyter audience) cannot use it without translation.

### 5.7 No CI/CD Pipeline

There are no GitHub Actions, GitLab CI, or similar configuration files. Tests and linting are not automatically verified on commits or pull requests, relying entirely on manual developer discipline.

---

## 6. Future Development Directions

### 6.1 Simple Improvements

**Split SmartFigure.py into separate modules**
Extract `OneShotOutput`, `SmartFigureLayout`, `ParameterManager`, `InfoPanelManager`, and `SmartPlot` into their own files. Keep `SmartFigure` as the coordinator importing from them. This is the single highest-impact organizational change.

**Add `pyproject.toml`**
Enable `pip install -e .` for development and `pip install gu_toolkit` for users. Define dependencies (`sympy`, `numpy`, `plotly`, `ipywidgets`), optional dependencies (`anywidget`), and Python version requirement (`>=3.10`).

**Replace `_FIGURE_STACK` with `contextvars.ContextVar`**
A one-line change that makes the figure context thread-safe and async-safe:
```python
_FIGURE_CONTEXT: ContextVar[Optional[SmartFigure]] = ContextVar('_FIGURE_CONTEXT', default=None)
```

**Create `RenderReason` enum**
Replace magic strings with a typed enum. Provides autocomplete, validation, and a single source of truth for all render triggers.

**Add slider bounds validation**
Validate `min < max` in `SmartFloatSlider.__init__` and raise a clear `ValueError` if violated.

**Create `WidgetLike` protocol**
Define the expected widget interface (`value`, `observe`, `min`, `max`, `step`, etc.) so `ParamRef.widget` can return a typed object instead of `Any`.

**Cross-platform notebook stripping**
Replace `strip_ipynb.cmd` with a Python script or `Makefile` target that works on all platforms.

**Clean up `__init__.py`**
Remove the commented-out imports referencing non-existent modules.

### 6.2 Large-Scale Projects

**Full pytest migration with CI**
Adopt pytest with widget mocking (e.g., `unittest.mock` for ipywidgets). Set up GitHub Actions to run tests, type checking (`mypy`), and linting on every PR. This is foundational for sustainable development.

**Plugin/extension system for custom plot types**
Define a `PlotType` protocol that custom plot renderers can implement (e.g., polar plots, parametric curves, vector fields). Register via entry points or a simple decorator. This would significantly expand the toolkit's applicability.

**Multi-figure dashboard coordination**
Enable multiple SmartFigure instances to share parameters and synchronize state. A shared `ParameterManager` or event bus would let slider changes in one figure update all linked figures simultaneously.

**3D plotting support**
Extend SmartPlot to handle Plotly `Surface`, `Scatter3d`, and `Mesh3d` trace types. This requires a 2D sampling grid instead of 1D, and potentially a `z_range` parameter.

**SmartPad2D (already designed)**
The design document at `documentation/design_smartpad2d.md` sketches a 2D gesture/touch input widget. This would enable interactive selection of (x, y) coordinate pairs directly on the plot.

**Export and serialization**
Save figure state (expressions, parameter values, ranges, styling) to JSON and recreate figures from saved state. This enables sharing, reproducibility, and notebook-independent figure definitions.

**Async rendering pipeline**
For computationally heavy expressions, move numpify compilation and array evaluation to a background thread or process. Use `asyncio` or `concurrent.futures` to keep the UI responsive during long renders.

**Accessibility improvements**
Add ARIA labels to slider widgets, keyboard navigation for plot interaction, and high-contrast color schemes. Jupyter's accessibility story is still developing, but proactive improvements here would benefit all users.

---

## 7. Module Reference

| Module | Lines | Dependencies (internal) | Role | Health |
|--------|------:|------------------------|------|--------|
| `SmartFigure.py` | 3,347 | numpify, PlotlyPane, SmartSlider, ParamRef, ParamEvent, ParameterSnapshot, InputConvert, NumericExpression | Coordinator, layout, managers, render pipeline | Functional but oversized |
| `SmartSlider.py` | 815 | InputConvert | Custom float slider with expression parsing | Good |
| `PlotlyPane.py` | 734 | *(none)* | Responsive Plotly container with anywidget resize | Good |
| `NamedFunction.py` | 601 | *(none)* | Decorator: function/class to SymPy Function | Good |
| `ParamRef.py` | 591 | ParamEvent | Parameter reference protocol + proxy | Good (widget typing could improve) |
| `numpify.py` | 561 | *(none)* | SymPy to NumPy compilation with caching | Good |
| `prelude.py` | 226 | *(none)* | Symbol families, function families, shortcuts | Good |
| `InputConvert.py` | 128 | *(none)* | Numeric parsing with SymPy fallback | Good |
| `NumericExpression.py` | 116 | ParameterSnapshot | Live/dead expression wrappers | Good |
| `SmartParseLaTeX.py` | 75 | *(none)* | LaTeX parser with backend fallback | Good |
| `ParameterSnapshot.py` | 70 | *(none)* | Immutable parameter state mapping | Good |
| `ParamEvent.py` | 53 | *(none)* | Parameter change event dataclass | Good |
| `__init__.py` | 24 | *(all re-exports)* | Public API surface | Minor cleanup needed |
| **Total** | **7,341** | | | |
