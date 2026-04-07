# SmartFigure Developer Guide

## Purpose and scope

SmartFigure is a Jupyter-first plotting toolkit that connects SymPy expressions to Plotly’s interactive `FigureWidget` while layering in UI affordances (parameter sliders, an info panel, and layout controls). The system is designed for *interactive mathematical exploration* rather than batch plotting, with a heavy emphasis on notebook ergonomics and fast re-rendering.【F:SmartFigure.py†L1-L1687】

This guide describes the architecture, design decisions, and the major components that make SmartFigure work. It is aimed at developers who want to extend or maintain the system, or integrate it into a larger codebase.

---

## High-level architecture

SmartFigure is organized around a **composition-based architecture** that separates responsibilities into discrete managers and UI helpers instead of a single monolithic object. The central coordinator is `SmartFigure`, which owns a Plotly figure and delegates to dedicated classes for layout, parameters, and information rendering.【F:SmartFigure.py†L138-L1687】

```
SmartFigure (Coordinator)
├── SmartFigureLayout (View / layout + CSS + widget tree)
├── ParameterManager (Parameter state + sliders + hooks)
├── InfoPanelManager (Info outputs + stateful components)
├── PlotlyPane (Plotly FigureWidget wrapper + resize driver)
└── SmartPlot instances (Math -> trace rendering)
```

**Design goals:**
- Keep UI layout concerns (CSS, widget tree) isolated from math/plotting logic.
- Keep parameter state and change hooks in a dedicated manager using a ref-first parameter API.
- Keep the plot-by-plot rendering logic separate for extensibility.
- Ensure Plotly resizes reliably inside Jupyter layouts (especially flex or sidebar layouts).【F:SmartFigure.py†L138-L1687】【F:PlotlyPane.py†L1-L157】

---

## Module map (core files)

| File | Responsibility | Notes |
| --- | --- | --- |
| `SmartFigure.py` | Main SmartFigure system (layout, parameter manager, info manager, SmartPlot, plot registry, render pipeline). | Defines most architecture components and their collaboration. |【F:SmartFigure.py†L138-L2097】 |
| `PlotlyPane.py` | Plotly resizing pane for reliable layout handling in Jupyter. | Uses `anywidget` + JS observers to resize plots when container size changes. |【F:PlotlyPane.py†L1-L157】 |
| `SmartSlider.py` | Custom slider widget used for parameters. | Provides a single numeric field plus slider and a settings panel. |【F:SmartSlider.py†L1-L200】 |
| `ParamRef.py` | Parameter reference contract + proxy implementation. | Defines `ParamRef` protocol and `ProxyParamRef` wrapper for controls. |【F:ParamRef.py†L1-L100】 |
| `ParamEvent.py` | Normalized parameter change event. | Shared event payload for callbacks and render triggers. |【F:ParamEvent.py†L1-L40】 |
| `numpify.py` | SymPy → NumPy compilation pipeline. | Compiles SymPy expressions into callable NumPy functions, with binding support. |【F:numpify.py†L1-L200】 |
| `InputConvert.py` | User input parsing/conversion. | Converts text or numeric inputs into float/int/complex with SymPy fallback. |【F:InputConvert.py†L1-L119】 |
| `NamedFunction.py` | SymPy function class generator. | Enables custom symbolic functions with numeric implementations. |【F:NamedFunction.py†L1-L200】 |
| `SmartParseLaTeX.py` | LaTeX parsing helper. | Uses SymPy’s parser with lark/ANTLR fallback. |【F:SmartParseLaTeX.py†L1-L29】 |

---

## Core components

### 1. `SmartFigure` (Coordinator)

`SmartFigure` is the user-facing class. It creates the Plotly `FigureWidget`, wraps it in a `PlotlyPane` for resilient resizing, and wires together the layout and managers. It also manages render throttling on pan/zoom events and keeps a registry of plotted curves by ID.【F:SmartFigure.py†L1503-L1687】

Key responsibilities:
- Owns the plotly `FigureWidget` and its base layout style.
- Owns the layout manager (`SmartFigureLayout`).
- Owns the parameter manager (`ParameterManager`).
- Owns the info panel manager (`InfoPanelManager`).
- Provides the public `.plot(...)` API (through `SmartPlot` instances).
- Triggers re-rendering on parameter changes or relayout events.【F:SmartFigure.py†L1503-L1687】

Design notes:
- The class uses `__slots__` to keep memory usage predictable in interactive notebook contexts.【F:SmartFigure.py†L1527-L1546】
- The figure layout is styled to match a lightweight “white + subtle grid” look, and uses Plotly’s `FigureWidget` to allow dynamic updates without re-displaying the entire chart.【F:SmartFigure.py†L1550-L1668】

### 2. `SmartFigureLayout` (View / widget hierarchy)

`SmartFigureLayout` builds the Jupyter widget tree: a title bar, a plot container, and a sidebar that can show parameters and info content. It also contains the “Full width plot” toggle and layout configuration for responsive behavior (sidebar below plot on narrow widths).【F:SmartFigure.py†L367-L620】

Key behaviors:
- Sidebar starts hidden and is shown when parameters or info outputs are added.
- Controls are laid out using nested `VBox`/`HBox` widgets and a flex container (`display: flex`).
- The plot container explicitly defines height (`60vh`) and minimum sizes, which is crucial for Plotly sizing and is used by `PlotlyPane`.【F:SmartFigure.py†L402-L506】

### 3. `ParameterManager` (Parameter state + sliders)

The `ParameterManager` is the “model” for slider state and change hooks. It creates `SmartFloatSlider` instances and stores **parameter references** (`ParamRef`) by SymPy symbol. It also executes hooks when a parameter changes and provides dictionary-like access for compatibility (`fig.params[symbol]`).【F:SmartFigure.py†L637-L940】【F:ParamRef.py†L1-L100】

Key behaviors:
- Uses `SmartFloatSlider`, which combines a slider with a single editable numeric field and a settings panel for min/max/step values.【F:SmartSlider.py†L1-L200】
- Adds and reuses controls based on symbol identity and stores the resulting `ParamRef` objects in `_refs`.
- Supports registering hooks (`add_hook`) that run on change and at registration time to initialize state.
- Routes changes via `ParamRef.observe(...)` into a normalized `ParamEvent`, then triggers the figure render callback with `reason="param_change"`.【F:SmartFigure.py†L697-L833】【F:ParamRef.py†L1-L100】

#### Widgets + ParamRef refactor (ref-first parameter API)

The parameter system was refactored to be **ref-first**, meaning the public parameter API now returns `ParamRef` objects instead of widgets:

- `fig.parameter(symbol)` returns a `ParamRef`, not a widget.
- `fig.params[symbol]` yields a `ParamRef` for compatibility with dict-like access.
- The `ParamRef` exposes `.value`, `.parameter`, and `.widget` (for direct widget access when needed).
- Change handling is normalized via `ParamEvent` objects, so callbacks no longer depend on raw traitlets change dicts.【F:ParamRef.py†L1-L100】【F:ParamEvent.py†L1-L40】

Controls participate in a **control → refs handshake**: each control exposes `make_refs(symbols)` that returns a mapping of `Symbol → ParamRef`. This allows multi-symbol controls to map multiple parameters onto a shared widget while preserving per-symbol references. The default `SmartFloatSlider` only supports one symbol and returns a `ProxyParamRef` that forwards to the slider’s value and range properties.【F:SmartSlider.py†L430-L480】【F:ParamRef.py†L1-L100】

### 4. `InfoPanelManager` (Info outputs + stateful components)

The `InfoPanelManager` controls the “Info” sidebar area. It provides output widgets for rich display (text, plots, etc.) and supports registering “components” that can update when parameters change. This is used for dynamic annotations, supplementary plots, or explanation widgets tied to slider values.【F:SmartFigure.py†L963-L1101】

Key behaviors:
- Lazily creates `ipywidgets.Output` containers and stores them by ID.
- IDs are versioned (`info:1`, `info:2`, ...) to avoid collisions and allow stable re-access.
- Components can be registered by ID for retrieval or coordinated updates.【F:SmartFigure.py†L963-L1101】

### 5. `SmartPlot` (One curve = one trace)

Each plotted expression is represented as a `SmartPlot`. It converts a SymPy expression into a compiled NumPy function via `numpify_cached`, samples the domain, evaluates with the current parameter values, and updates a Plotly trace. This keeps the math/rendering logic scoped to a single curve, rather than mixing it into the figure class itself.【F:SmartFigure.py†L1102-L1460】

Key behaviors:
- Tracks its own variable, expression, parameters, label, and visibility.
- Supports per-plot overrides for `x_domain` and sampling density.
- Supports per-plot line styling (color, thickness, dash), trace opacity, plus additional Plotly trace/line attributes via the plot/update APIs.【F:SmartFigure.py†L1102-L1632】
- Calls `render()` to update its trace based on the latest parameters and ranges.【F:SmartFigure.py†L1102-L1460】
- Plot-style kwargs are explicitly discoverable via `SmartFigure.plot_style_options()` and module-level `plot_style_options()`, which enumerate all supported style shortcuts (`color`, `thickness`, `dash`, `opacity`, `line`, `trace`).【F:SmartFigure.py†L2431-L2443】

### 6. `PlotlyPane` (Resilient Plotly sizing)

Plotly `FigureWidget` sizing can be unreliable in dynamic Jupyter layouts. `PlotlyPane` adds a hidden `anywidget` driver (`PlotlyResizeDriver`) with a front-end JS layer that monitors container size changes and forces Plotly to resize accordingly. This is essential when embedding plots in flex layouts, sidebars, or dynamic panels.【F:PlotlyPane.py†L1-L157】

Key behaviors (frontend):
- Uses `ResizeObserver` and `MutationObserver` to detect size changes and DOM updates.
- Locates Plotly’s `.js-plotly-plot` element and applies explicit width/height styling.
- Optionally autoranges axes on resize.
- Supports deferred reveal to prevent “flash at wrong size” artifacts.【F:PlotlyPane.py†L1-L157】

---

## Render flow and data flow

### 1. User defines plots

When a user calls `fig.plot(x, expr, ...)`, SmartFigure:
1. Creates or updates a `SmartPlot` instance (tracked by ID).
2. Autodetects parameters from the expression (all free symbols excluding the plot variable) unless overridden.
3. Ensures corresponding sliders are created via `ParameterManager`.
4. Triggers initial rendering of the plot trace(s).【F:SmartFigure.py†L1503-L2097】

### 2. Parameter updates

When a slider changes:
1. `ParamRef.observe(...)` normalizes the widget change into a `ParamEvent`.
2. `ParameterManager` receives the event and calls the render callback with `reason="param_change"`.
3. SmartFigure re-renders the relevant plots using the updated parameter values.
3. Plot traces are updated in-place (no need to re-display the figure widget).【F:SmartFigure.py†L637-L1687】

### 3. Pan/zoom updates

SmartFigure listens to `xaxis.range` and `yaxis.range` changes on the Plotly layout. These relayout events are throttled to avoid excessive renders while panning. The updated ranges are used to resample the functions and redraw plots at the new window.【F:SmartFigure.py†L1659-L1687】

---

## Compilation pipeline (SymPy → NumPy)

SmartFigure uses the `numpify` / `numpify_cached` functions to compile SymPy expressions into NumPy-callable functions. This is the core bridge between symbolic math and numeric evaluation required for plotting.

Key capabilities from `numpify.py`:
- Symbol bindings allow parameters to be injected by name, avoiding positional mismatches.
- Custom SymPy functions can provide an `f_numpy` implementation for efficient evaluation.
- Generated function code is inspectable (stored in docstrings), aiding debugging and reproducibility.【F:numpify.py†L1-L200】

This compilation step makes vectorized evaluation possible, which is essential for fast re-rendering while sliders are moved.

---

## Input parsing and user ergonomics

Interactive widgets accept user-entered values (e.g., slider min/max/step or numeric fields). `InputConvert` provides a safe conversion layer:
- Accepts numeric values directly.
- Parses strings into numbers, with SymPy as a fallback parser.
- Supports float/int/complex destinations and controls truncation behavior.【F:InputConvert.py†L1-L119】

This reduces user friction: expressions like `pi/2` or `1+2j` can be typed directly without manual preprocessing.

---

## Extensibility points

### Adding a new plot type

To add a new plot representation (e.g., scatter, parametric curves), you can:
- Extend `SmartPlot` or create a parallel plot class that still adheres to the “render on parameter change” contract.
- Ensure it can be driven by `SmartFigure.render` callbacks and uses the shared parameter values.

### Custom symbolic functions

Use `NamedFunction` to create SymPy `Function` subclasses with a symbolic definition and/or numeric implementation. This allows custom functions to be used inside expressions while still compiling cleanly through `numpify`.

Example workflow:
1. Define a function with `@NamedFunction`.
2. Implement `.numeric` to supply `f_numpy` for fast evaluation.
3. Use the function in SymPy expressions passed to `SmartFigure.plot(...)`.

This keeps user-defined functions compatible with the compilation pipeline.【F:NamedFunction.py†L1-L200】

---

## Layout and UI considerations

### Plot container sizing

Plotly’s `FigureWidget` requires a concrete pixel height to render correctly. `SmartFigureLayout` sets a default `height="60vh"` on the plot container and minimum sizes to ensure a stable layout. If consumers place the widget inside their own layout, they must still provide a real height; otherwise Plotly may collapse or render unpredictably.【F:SmartFigure.py†L402-L506】【F:PlotlyPane.py†L1-L157】

### Sidebar visibility

The right-side controls panel is hidden until it contains content. This helps keep the layout compact for simple plots and is toggled automatically when parameters or info widgets are added.【F:SmartFigure.py†L430-L506】

---

## Logging and debug behavior

SmartFigure uses Python’s standard logging library and installs a `NullHandler` by default. Developers can enable logging globally or by module name to debug renders and range updates. Rate-limiting is implemented to avoid overwhelming notebook output when sliders or panning are active.【F:SmartFigure.py†L98-L120】

---

## Testing and verification

This repository contains test scripts (see `tests/`) that cover individual components such as `NamedFunction`. When making changes to the math compilation or widget system, prefer targeted tests that exercise:
- SymPy → NumPy compilation on common expressions.
- Slider updates and parameter propagation.
- Plotly resizing in a Jupyter environment (manual or notebook-based smoke tests).

---

## Summary

SmartFigure’s architecture is intentionally modular:
- **SmartFigure** orchestrates the system and exposes the public API.
- **SmartFigureLayout** owns the widget tree and layout behavior.
- **ParameterManager** manages slider state and hooks.
- **InfoPanelManager** manages the info sidebar and stateful components.
- **SmartPlot** isolates math → trace rendering.
- **PlotlyPane** solves Plotly sizing issues in dynamic Jupyter layouts.

Together these components provide a flexible, extensible environment for interactive symbolic plotting inside notebooks.【F:SmartFigure.py†L138-L1687】【F:PlotlyPane.py†L1-L157】

---

## Source-level documentation and discoverability index

This section is a maintenance-oriented index to keep all Python source files discoverable. It mirrors the in-code docstring style used across the toolkit and serves as a quick map when navigating internals.

### Package entry points

- `__init__.py` re-exports the high-level API (`SmartFigure`, `Figure`, `plot`, `parameter`, `plot_style_options`, parser/event/ref helpers, numeric-expression wrappers, and the symbolic prelude). Use this as the first discovery stop for notebook users and downstream imports.【F:__init__.py†L1-L24】
- `prelude.py` defines notebook-friendly symbols/functions (`SymbolFamily`, `FunctionFamily`, infix relations) plus convenient imports (`sp`, `np`, `pd`). It is intentionally broad to reduce friction in teaching and exploratory contexts.【F:prelude.py†L1-L223】

### SmartFigure core stack

- `SmartFigure.py`
  - Module-level helpers manage “current figure” stack semantics for `with fig:` usage and global helper functions. Private helpers (`_current_figure`, `_require_current_figure`, `_push_current_figure`, `_pop_current_figure`, `_use_figure`) should remain lightweight and side-effect scoped to stack state.【F:SmartFigure.py†L1-L336】
  - `SmartFigureLayout` owns widget composition and responsive layout behavior (title area, plot container, sidebar/full-width controls).【F:SmartFigure.py†L450-L739】
  - `ParameterManager` owns parameter control registration, change propagation, snapshots, and dictionary-like access for backward compatibility/discoverability (`keys`, `values`, `items`, iteration, `parameter`).【F:SmartFigure.py†L749-L1276】
  - `InfoPanelManager` owns info components and output routing for sidebar content.【F:SmartFigure.py†L1282-L1428】
  - `SmartPlot` encapsulates symbolic expression + numeric core + trace updates. Style update helpers (`_update_line_style`) are intentionally private and local to trace mutation behavior.【F:SmartFigure.py†L1434-L2062】
  - `SmartFigure` orchestrates figure/widget lifecycle, render triggers, pan/zoom throttling, and context-manager behavior for global helper routing.【F:SmartFigure.py†L2065-L3008】
  - `_CurrentParamsProxy` exposes module-level discoverable access (`params[...]`, `params.parameter(...)`) to the active figure’s parameter manager.【F:SmartFigure.py†L3014-L3070】

### Plotly host + parameter controls

- `PlotlyPane.py` provides the anywidget-backed resize driver (`PlotlyResizeDriver`) and wrapper (`PlotlyPane`) to keep Plotly correctly sized in dynamic notebook layouts. `PlotlyPaneStyle` centralizes style knobs for consistent embedding in parent layouts.【F:PlotlyPane.py†L1-L747】
- `SmartSlider.py` defines `SmartFloatSlider`, the canonical parameter control. It encapsulates value synchronization (slider/text), setting edits (min/max/step/default), reset behavior, and modal-host integration for settings UI.【F:SmartSlider.py†L1-L403】

### Numeric compilation and expression wrappers

- `numpify.py` is the SymPy→NumPy compilation bridge (`numpify`, `numpify_cached`) with binding normalization and cache-aware helpers (`_FrozenFNumPy`, `_numpify_cached_impl`). Private helpers are intentionally documented for maintainers due to non-trivial cache-key behavior and function-binding rules.【F:numpify.py†L1-L616】
- `NumericExpression.py` formalizes live vs. detached expression states:
  - `LiveNumericExpression` (widget/live values),
  - `DeadBoundNumericExpression` (frozen values),
  - `DeadUnboundNumericExpression` (core + parameter order only).【F:NumericExpression.py†L1-L115】

### Parameter contracts and events

- `ParamRef.py` defines the `ParamRef` protocol and `ProxyParamRef` adapter. Public API docs describe parameter metadata capabilities (`default_value`, `min`, `max`, `step`), observer behavior, and reset semantics for robust extension points.【F:ParamRef.py†L1-L348】
- `ParamEvent.py` defines `ParamEvent`, the immutable normalized payload emitted to hooks and observers.【F:ParamEvent.py†L1-L50】
- `ParameterSnapshot.py` defines immutable ordered snapshots for deterministic binding and comparisons in parameterized evaluations.【F:ParameterSnapshot.py†L1-L69】

### Parsing and conversion helpers

- `InputConvert.py` centralizes conversion of user-provided numeric values (Python numeric inputs, strings, and SymPy-parsable text) with explicit truncation rules and predictable errors.【F:InputConvert.py†L1-L126】
- `SmartParseLaTeX.py` provides `parse_latex` with backend fallback (`lark` then `antlr`) and structured error context via `LatexParseError`.【F:SmartParseLaTeX.py†L1-L74】

### Symbolic function authoring

- `NamedFunction.py` provides the `@NamedFunction` API for creating SymPy function classes with symbolic definitions and numeric implementations while preserving inspectable signatures and generated docs.【F:NamedFunction.py†L1-L689】

### Documentation maintenance checklist (for contributors)

When adding or modifying code in this toolkit, keep these standards:

1. **Every module has a top-level docstring** describing purpose, design intent, and where it sits in the architecture.
2. **Every public function/class/method includes thorough API docs**:
   - parameter meanings,
   - return values,
   - expected error conditions,
   - examples/doctests (use `# doctest: +SKIP` for notebook/UI-heavy paths),
   - “See Also” links to related APIs where appropriate.
3. **Every private helper gets at least a brief behavior docstring** to reduce maintenance friction and simplify refactors.
4. **Class docs describe role and collaboration boundaries** (what state they own, what they delegate, and what triggers side effects).
5. **Discoverability first**: module docstrings should point to neighboring modules/classes and mention likely extension points.

By keeping source docstrings and this guide in sync, the toolkit remains approachable for both notebook users and maintainers.
