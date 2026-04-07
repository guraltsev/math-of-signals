"""
plotly_pane.py — Responsive Plotly FigureWidget pane for Jupyter via anywidget

This module provides a small, reusable “Plotly pane” that can be embedded into
arbitrary ipywidgets layouts while maintaining reliable Plotly sizing under
dynamic container changes (e.g., JupyterLab sidebars, split panels, flex reflows).

It is designed for the common situation where:

- You have a `plotly.graph_objects.FigureWidget` (or any widget that renders a
  Plotly DOM subtree containing a `.js-plotly-plot` element), and
- You want the Plotly plot to *track the pixel size of its container*, including
  changes that are *not* simple window resizes (sidebar toggles, panel drags),
  and
- You want optional “autorange” behavior after resizing, and
- You may want to defer showing the host until a valid size is available, to
  reduce “flash at wrong size” artifacts.

Public API
----------

Primary classes:

- `PlotlyResizeDriver`
    An `anywidget.AnyWidget` whose frontend JavaScript attaches observers
    (ResizeObserver + MutationObserver) to locate a Plotly element under a host
    container and call Plotly’s resize mechanisms when the host size changes.

    The driver widget itself is hidden (`display: none`); it is intended to be
    placed as a child of (or adjacent to) the Plotly FigureWidget within the
    same container.

- `PlotlyPaneStyle`
    A small frozen dataclass holding visual styling options (padding/border/etc.)
    for the pane wrapper.

- `PlotlyPane`
    A Python-side convenience wrapper that assembles:
      (a) a “host” flex box that owns the pixel height
      (b) the figure widget + `PlotlyResizeDriver`
      (c) an outer wrapper that applies style (padding/border/radius/overflow)

    Exposes `.widget` (the widget to embed in layouts) and `.reflow()` for
    manual, programmatic resizing.

Typical usage
-------------

1) Create a Plotly FigureWidget:

    import plotly.graph_objects as go
    figw = go.FigureWidget(data=[go.Scatter(y=[1, 3, 2])])

2) Wrap it in a PlotlyPane:

    pane = PlotlyPane(
        figw,
        style=PlotlyPaneStyle(padding_px=8, border="1px solid #ddd"),
        autorange_mode="once",   # "none" | "once" | "always"
        defer_reveal=True,
    )

3) Place pane.widget into an ipywidgets layout that provides a real pixel height:

    import ipywidgets as W
    root = W.Box(
        [pane.widget],
        layout=W.Layout(height="70vh", width="100%")
    )
    display(root)

4) If your code performs layout changes that might not trigger observers
   (or you want deterministic recovery), call:

    pane.reflow()

Architecture / design summary
-----------------------------

There are two layers:

(1) Frontend resize logic (JavaScript in `PlotlyResizeDriver._esm`)

    - Determines a “host” element:
        - If `host_selector` is set, uses `document.querySelector(host_selector)`.
        - Otherwise uses `el.parentElement` where `el` is the driver’s DOM node.

    - Locates the Plotly element:
        - Searches under host for `.js-plotly-plot` (Plotly’s standard container).

    - Computes an “effective size”:
        - Uses host bounding box for width/height.
        - Additionally attempts to find the nearest ancestor with non-`visible`
          horizontal overflow (a “clip ancestor”). This is a pragmatic approach
          for JupyterLab-like layouts where the visible width can be constrained
          by a clipping parent even if the host’s nominal layout width is larger.
        - Effective width is `min(host.width, clip.width)`, height is host.height.

    - Applies sizing to the Plotly DOM:
        - Sets plot element and `.plot-container` heights in pixels.
        - Clamps width via `maxWidth` to the effective visible width and enforces
          `min-width: 0` / `width: 100%` to allow shrink in flex layouts.

    - Triggers Plotly resize:
        - Prefer `window.Plotly.Plots.resize(plotEl)` when available.
        - Fallback: dispatch a global `window.resize` event.

    - Optional autorange:
        - If `autorange_mode` is "once" or "always", attempts `Plotly.relayout`
          with `{xaxis*.autorange: true, yaxis*.autorange: true}` for all axes
          in `_fullLayout`. (This relies on Plotly’s runtime layout object and
          is necessarily Plotly-specific.)

    - Observers and scheduling:
        - Uses `ResizeObserver` on the host to react to size changes.
        - Uses `ResizeObserver` on the clip ancestor (if distinct) to react to
          changes in the clipping viewport.
        - Uses `MutationObserver` on the host subtree to detect Plotly DOM
          insertion and trigger an initial resize.
        - Debounces resize work (`debounce_ms`) and performs two follow-up resizes
          (`followup_ms_1`, `followup_ms_2`) to survive animated transitions.

    - Deferred reveal:
        - If `defer_reveal=True`, the host is hidden via `opacity: 0` and
          `pointer-events: none` until the first successful resize.

(2) Python wrapper layer (`PlotlyPane`)

    - Constructs a host container (`self._host`) that:
        - is a flex column
        - has `width="100%"`, `height="100%"`, `min_width="0"`, `min_height="0"`
        - contains `[figw, driver]`
      The outer layout is responsible for giving this a real pixel height.

    - Constructs a wrapper (`self._wrap`) that applies the visual style
      (padding/border/radius/overflow).

Key contract / expectation
--------------------------

For reliable behavior, the pane must ultimately receive a computed pixel height.
In practice, that means some ancestor in the ipywidgets layout should set a
height (e.g. `"70vh"`, `"400px"`, or a flex layout where height is defined).

If the pane has no real height (e.g. all ancestors have `height="auto"`), Plotly
has no stable target size and may collapse or render unpredictably.

Limitations / notes
-------------------

- The driver assumes Plotly renders an element with class `.js-plotly-plot`.
  This is standard for Plotly, but it is still a DOM-level coupling.

- Autorange uses the presence of `plotEl._fullLayout` and `Plotly.relayout`.
  If Plotly changes these internals, autorange behavior may degrade (resize will
  still function via `Plots.resize`/fallback).

- This code uses `ResizeObserver` and `MutationObserver`, which are supported by
  modern browsers. If unavailable, no polyfill is provided here.

- The “clip ancestor” heuristic is intentionally generic; it can be adjusted if
  a target environment has more specific layout structure.

Exports
-------

- `PlotlyResizeDriver`
- `PlotlyPaneStyle`
- `PlotlyPane`
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

import anywidget
import traitlets
import ipywidgets as W


__all__ = ["PlotlyResizeDriver", "PlotlyPaneStyle", "PlotlyPane"]


def _uid(n: int = 8) -> str:
    """
    Return a short random hex identifier.

    Parameters
    ----------
    n:
        Number of hex characters to return. Default is 8.

    Notes
    -----
    This helper is not used by the public API in this file, but is commonly
    useful when you want to generate per-instance CSS classes/selectors for
    complex widget layouts.
    """
    return uuid.uuid4().hex[:n]


class PlotlyResizeDriver(anywidget.AnyWidget):
    """
    Frontend resize driver for a Plotly DOM subtree.

    This widget is meant to be included as a hidden child within (or adjacent to)
    the container that hosts a Plotly-rendered widget (typically a
    `plotly.graph_objects.FigureWidget`).

    The JavaScript frontend:

    - Resolves a host element (by `host_selector` or `parentElement`).
    - Locates the Plotly node `.js-plotly-plot`.
    - Computes an effective size (optionally constrained by a clipping ancestor).
    - Applies pixel height + width clamps to the Plotly DOM.
    - Calls Plotly’s resize API (`Plotly.Plots.resize`) when available.
    - Optionally triggers autorange via `Plotly.relayout`.
    - Observes host and clip-ancestor size changes via `ResizeObserver`.
    - Detects initial Plotly DOM insertion via `MutationObserver`.
    - Supports Python-side manual reflow via a custom message.

    Traitlets (synced to frontend)
    ------------------------------

    host_selector:
        Optional CSS selector. If non-empty, the driver uses
        `document.querySelector(host_selector)` as the host container.
        If empty, the host is `el.parentElement`.

        In most cases (including `PlotlyPane`), leaving this empty is best.

    autorange_mode:
        Controls post-resize autorange behavior:
        - "none": never autorange
        - "once": autorange at most one time after a successful resize
        - "always": autorange after every resize

    defer_reveal:
        If True, hides the host container (opacity 0, pointer-events none) until
        the first successful resize is performed.

    debounce_ms:
        Debounce delay for resize scheduling (milliseconds).

    min_delta_px:
        Minimum pixel change in width or height before a resize is applied once
        the host is already “revealed”. Prevents jitter from tiny oscillations.

    followup_ms_1 / followup_ms_2:
        Extra follow-up resizes scheduled after the debounced resize. These are
        a pragmatic stabilizer for animated transitions in JupyterLab-like UIs.

    debug_js:
        If True, enables console logging from the frontend driver.

    Public methods
    --------------
    reflow():
        Send a custom message to trigger a resize schedule on the frontend.
        This is useful when you programmatically change layout state and want
        deterministic correction.

    Implementation detail
    ---------------------
    The widget’s frontend node is hidden (`display: none`) and serves only as a
    coordination point for trait syncing and custom messages.
    """

    host_selector = traitlets.Unicode("").tag(sync=True)
    autorange_mode = traitlets.Unicode("none").tag(sync=True)  # "none" | "once" | "always"
    defer_reveal = traitlets.Bool(True).tag(sync=True)

    debounce_ms = traitlets.Int(60).tag(sync=True)
    min_delta_px = traitlets.Int(2).tag(sync=True)

    # follow-up resizes to survive JupyterLab sidebar transitions
    followup_ms_1 = traitlets.Int(80).tag(sync=True)
    followup_ms_2 = traitlets.Int(250).tag(sync=True)

    debug_js = traitlets.Bool(False).tag(sync=True)

    # Frontend module: anywidget expects an ES module that default-exports an object
    # with a `render({ model, el })` method. The render method returns an optional
    # cleanup function called on widget disposal.
    _esm = r"""
    function clampInt(x, dflt) {
      let n = Number(x);
      return Number.isFinite(n) ? Math.trunc(n) : dflt;
    }

    function safeLog(enabled, ...args) {
      if (enabled) console.log("[PlotlyResizeDriver]", ...args);
    }

    function pxSizeOf(el) {
      const r = el.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height) };
    }

    function findPlotEl(host) {
      if (!host) return null;
      return host.querySelector(".js-plotly-plot");
    }

    function findClipAncestor(startEl) {
      // Nearest ancestor that can clip horizontally (common in JupyterLab layouts).
      // Generic heuristic: detect via computed overflow-x/overflow.
      let el = startEl;
      while (el && el.parentElement) {
        el = el.parentElement;
        const cs = getComputedStyle(el);
        const ox = cs.overflowX || cs.overflow || "visible";
        // treat anything but 'visible' as potentially clipping / viewport-defining
        if (ox !== "visible") return el;
      }
      return null;
    }

    function effectiveSize(host, clip) {
      const hs = pxSizeOf(host);
      if (!clip) return hs;
      const cs = pxSizeOf(clip);
      // visible width is limited by the clip viewport even if host layout width stays large
      return { w: Math.min(hs.w, cs.w), h: hs.h };
    }

    function setPlotHeights(plotEl, hPx) {
      plotEl.style.height = `${hPx}px`;
      const pc = plotEl.querySelector(".plot-container");
      if (pc) pc.style.height = `${hPx}px`;
    }

    function applyWidthClamp(plotEl, wPx) {
      // Clamp width to effective visible width (important under JupyterLab side panes).
      plotEl.style.width = "100%";
      plotEl.style.minWidth = "0";
      plotEl.style.maxWidth = `${wPx}px`;
      plotEl.style.boxSizing = "border-box";

      const pc = plotEl.querySelector(".plot-container");
      if (pc) {
        pc.style.width = "100%";
        pc.style.minWidth = "0";
        pc.style.maxWidth = `${wPx}px`;
        pc.style.boxSizing = "border-box";
      }
    }

    async function plotlyResize(plotEl) {
      try {
        const P = window.Plotly;
        if (P && P.Plots && typeof P.Plots.resize === "function") {
          return await P.Plots.resize(plotEl);
        }
      } catch (e) {}
      window.dispatchEvent(new Event("resize"));
    }

    function buildAutorangeUpdate(plotEl) {
      const fl = plotEl && plotEl._fullLayout;
      if (!fl) return null;

      const upd = {};
      for (const k of Object.keys(fl)) {
        if (/^xaxis(\d+)?$/.test(k)) upd[`${k}.autorange`] = true;
        if (/^yaxis(\d+)?$/.test(k)) upd[`${k}.autorange`] = true;
      }
      return Object.keys(upd).length ? upd : null;
    }

    async function maybeAutorange(plotEl, mode, alreadyDidOnce, debug) {
      if (mode === "none") return alreadyDidOnce;
      if (mode === "once" && alreadyDidOnce) return alreadyDidOnce;

      const P = window.Plotly;
      if (!P || typeof P.relayout !== "function") {
        safeLog(debug, "autorange requested but window.Plotly.relayout unavailable");
        return alreadyDidOnce;
      }

      const upd = buildAutorangeUpdate(plotEl);
      if (!upd) return alreadyDidOnce;

      try {
        await P.relayout(plotEl, upd);
        return true;
      } catch (e) {
        safeLog(debug, "autorange relayout failed:", e);
        return alreadyDidOnce;
      }
    }

    export default {
      render({ model, el }) {
        // The driver node is an implementation detail: it should not affect layout.
        el.style.display = "none";

        let debug = !!model.get("debug_js");

        function resolveHost() {
          const sel = model.get("host_selector");
          if (sel && typeof sel === "string" && sel.trim()) {
            return document.querySelector(sel.trim());
          }
          return el.parentElement;
        }

        let host = resolveHost();
        if (!host) {
          safeLog(debug, "No host found; driver inactive.");
          return;
        }

        // clip ancestor used for effective visible width under JupyterLab side panes
        let clip = findClipAncestor(host);

        let last = { w: 0, h: 0 };
        let timer = null;
        let follow1 = null;
        let follow2 = null;

        let roHost = null;
        let roClip = null;
        let mo = null;

        let revealed = false;
        let didAutorangeOnce = false;

        function setHostHidden(hidden) {
          if (!model.get("defer_reveal")) return;
          if (hidden) {
            host.style.opacity = "0";
            host.style.pointerEvents = "none";
          } else {
            host.style.opacity = "";
            host.style.pointerEvents = "";
          }
        }

        // Hide host until we can size Plotly at least once (optional).
        setHostHidden(true);

        async function doResize(reason) {
          host = resolveHost();
          if (!host) return false;

          // refresh clip in case DOM reparenting occurred
          clip = findClipAncestor(host);

          const plotEl = findPlotEl(host);
          if (!plotEl) {
            safeLog(debug, "Plot element not found yet:", reason);
            return false;
          }

          const cur = effectiveSize(host, clip);
          if (!(cur.w > 0 && cur.h > 0)) return false;

          const minDelta = clampInt(model.get("min_delta_px"), 2);
          const dw = Math.abs(cur.w - last.w);
          const dh = Math.abs(cur.h - last.h);

          // If already stable/visible, ignore tiny jitter.
          if (revealed && dw < minDelta && dh < minDelta) return true;

          last = cur;

          // Apply size hints directly to Plotly DOM before requesting Plotly resize.
          applyWidthClamp(plotEl, cur.w);
          setPlotHeights(plotEl, cur.h);

          await plotlyResize(plotEl);

          const mode = model.get("autorange_mode") || "none";
          didAutorangeOnce = await maybeAutorange(plotEl, mode, didAutorangeOnce, debug);

          if (!revealed) {
            setHostHidden(false);
            revealed = true;
          }
          return true;
        }

        function clearTimers() {
          if (timer) clearTimeout(timer);
          if (follow1) clearTimeout(follow1);
          if (follow2) clearTimeout(follow2);
          timer = follow1 = follow2 = null;
        }

        function schedule(reason) {
          clearTimers();
          const wait = clampInt(model.get("debounce_ms"), 60);
          const t1 = clampInt(model.get("followup_ms_1"), 80);
          const t2 = clampInt(model.get("followup_ms_2"), 250);

          timer = setTimeout(() => { doResize(reason); }, wait);

          // Per-instance follow-ups: helps with JupyterLab sidebar transitions/animations.
          follow1 = setTimeout(() => { doResize(reason + ":follow1"); }, wait + t1);
          follow2 = setTimeout(() => { doResize(reason + ":follow2"); }, wait + t2);
        }

        // Observe host size changes.
        roHost = new ResizeObserver(() => schedule("ResizeObserver:host"));
        roHost.observe(host);

        // Observe clip viewport too (this is what changes when side panes constrain visible width).
        if (clip && clip !== host) {
          roClip = new ResizeObserver(() => schedule("ResizeObserver:clip"));
          roClip.observe(clip);
        }

        // Wait for Plotly to insert DOM, then resize.
        mo = new MutationObserver(() => {
          if (findPlotEl(resolveHost())) schedule("MutationObserver");
        });
        mo.observe(host, { childList: true, subtree: true });

        // Custom messages (Python-side reflow)
        const onMsg = (msg) => {
          if (msg && msg.type === "reflow") schedule("msg:reflow");
        };
        model.on("msg:custom", onMsg);

        // React to trait changes
        const onAutorangeChange = () => schedule("change:autorange_mode");
        const onRevealChange = () => {
          if (!model.get("defer_reveal")) setHostHidden(false);
          schedule("change:defer_reveal");
        };
        model.on("change:autorange_mode", onAutorangeChange);
        model.on("change:defer_reveal", onRevealChange);

        // Initial sizing attempt.
        schedule("init");

        // Cleanup when widget is disposed.
        return () => {
          try { clearTimers(); } catch (e) {}
          try { if (roHost) roHost.disconnect(); } catch (e) {}
          try { if (roClip) roClip.disconnect(); } catch (e) {}
          try { if (mo) mo.disconnect(); } catch (e) {}
          try { model.off("msg:custom", onMsg); } catch (e) {}
          try { model.off("change:autorange_mode", onAutorangeChange); } catch (e) {}
          try { model.off("change:defer_reveal", onRevealChange); } catch (e) {}
          try { setHostHidden(false); } catch (e) {}
        };
      }
    };
    """

    def reflow(self) -> None:
        """
        Request a resize/reflow from the frontend.

        This sends a custom message handled by the frontend driver, which schedules
        a debounced resize plus follow-up resizes.

        Use this when you programmatically alter layout in ways that may not be
        detected (or where you want deterministic correction), e.g.:

        - Toggling a sidebar or accordion that changes available width
        - Showing/hiding sibling widgets
        - Changing CSS/layout attributes that affect size
        """
        self.send({"type": "reflow"})


@dataclass(frozen=True)
class PlotlyPaneStyle:
    """
    Visual styling options for `PlotlyPane`.

    Parameters
    ----------
    padding_px:
        Inner padding (in pixels) applied around the host container. This is
        applied by the outer wrapper box.

    border:
        CSS border string (e.g. "1px solid #ddd").

    border_radius_px:
        Corner radius in pixels.

    overflow:
        Overflow policy for the wrapper. Default "hidden" is typical for plots.
    """

    padding_px: int = 0
    border: str = "1px solid #ddd"
    border_radius_px: int = 8
    overflow: str = "hidden"


class PlotlyPane:
    """
    Styled, responsive plot area for a Plotly `FigureWidget` (or compatible widget).

    This is a small Python-side wrapper that:

    - creates a “host” container with stable flex sizing rules,
    - inserts the Plotly widget plus a hidden `PlotlyResizeDriver`,
    - applies user-facing styling via an outer wrapper box,
    - exposes the wrapper as `.widget` for embedding in any ipywidgets layout.

    Outer layout contract
    ---------------------

    The pane only works reliably if `pane.widget` is given a real computed pixel
    height (directly or via its ancestors). Common patterns:

    - Put it inside a container with a fixed height: `"400px"`.
    - Put it inside a container with viewport height: `"70vh"`.
    - Put it in a flex layout where an ancestor defines height and this pane
      has `height="100%"`.

    Parameters
    ----------
    figw:
        The widget that renders a Plotly figure. Typically
        `plotly.graph_objects.FigureWidget`, but any widget that creates a Plotly
        DOM element with class `.js-plotly-plot` under this pane’s host may work.

    style:
        `PlotlyPaneStyle` controlling padding/border/radius/overflow of the outer
        wrapper.

    autorange_mode:
        One of:
        - "none": never autorange after resizing
        - "once": autorange at most once after a successful resize
        - "always": autorange after every resize

        Autorange is performed via `Plotly.relayout` in the frontend.

    defer_reveal:
        If True, hides the host (opacity 0) until the driver performs a first
        successful resize. This helps reduce initial “wrong size flash”.

    debounce_ms:
        Debounce delay for resize scheduling (milliseconds).

    min_delta_px:
        Ignore tiny size jitter smaller than this threshold (after reveal).

    debug_js:
        Enable frontend console logs for troubleshooting.

    Attributes
    ----------
    driver:
        The underlying `PlotlyResizeDriver` instance.

    Notes
    -----
    The `PlotlyResizeDriver` is inserted as a hidden sibling of the Plotly widget
    inside the host. By default, it uses its DOM parent as the host; no selector
    is required for the common case.
    """

    def __init__(
        self,
        figw: W.Widget,
        *,
        style: PlotlyPaneStyle = PlotlyPaneStyle(),
        autorange_mode: str = "none",   # "none" | "once" | "always"
        defer_reveal: bool = True,
        debounce_ms: int = 60,
        min_delta_px: int = 2,
        debug_js: bool = False,
    ):
        """Initialize a pane that keeps Plotly sized to its widget container."""
        # Anywidget driver: performs the actual DOM sizing + Plotly resize calls.
        self.driver = PlotlyResizeDriver(
            autorange_mode=autorange_mode,
            defer_reveal=defer_reveal,
            debounce_ms=debounce_ms,
            min_delta_px=min_delta_px,
            debug_js=debug_js,
        )

        # Host container: owns pixel height (via outer layout), keeps Plotly flexible.
        # The driver is a hidden child and does not affect layout.
        self._host = W.Box(
            [figw, self.driver],
            layout=W.Layout(
                width="100%",
                height="100%",
                min_width="0",
                min_height="0",
                display="flex",
                flex_flow="column",
                overflow="hidden",
            ),
        )

        # Wrapper container: applies visual styling (padding/border/radius/overflow).
        self._wrap = W.Box(
            [self._host],
            layout=W.Layout(
                width="100%",
                height="100%",
                min_width="0",
                min_height="0",
                padding=f"{int(style.padding_px)}px",
                border=style.border,
                border_radius=f"{int(style.border_radius_px)}px",
                overflow=style.overflow,
                box_sizing="border-box",
            ),
        )

    @property
    def widget(self) -> W.Widget:
        """
        The widget to embed in your outer ipywidgets layout.

        This is the outer wrapper box that applies `PlotlyPaneStyle`. Ensure that
        some ancestor provides a real pixel height so the driver can size Plotly.
        """
        return self._wrap

    def reflow(self) -> None:
        """
        Trigger a programmatic resize/reflow.

        Calls `PlotlyResizeDriver.reflow()`, which schedules a resize in the
        frontend. Use this after known layout changes initiated by Python code.
        """
        self.driver.reflow()
