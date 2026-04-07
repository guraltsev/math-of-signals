"""Small MathLive-backed widget wrappers used by notebook editors.

Purpose
-------
The toolkit mostly relies on standard ipywidgets, but expression entry benefits
from a real mathematical editor. This module provides :class:`MathLiveField`, a
thin ``anywidget`` wrapper around MathLive's ``<math-field>`` custom element.

Architecture
------------
The widget deliberately keeps the Python surface tiny:

- ``value`` stores the current LaTeX string,
- ``placeholder`` and ``aria_label`` describe the field,
- ``read_only`` controls editability.

Frontend code loads MathLive from the ESM CDN recommended by the official docs
and falls back to a plain ``<textarea>`` if the import is unavailable. That
keeps notebook usage resilient without introducing a JavaScript build step.

Discoverability
---------------
See :mod:`gu_toolkit.figure_plot_editor` for the plot-composer dialog that uses
this widget.
"""

from __future__ import annotations

import traitlets

from ._widget_stubs import anywidget, widgets


class MathLiveField(anywidget.AnyWidget):
    """Editable LaTeX-backed math input widget.
    
    Full API
    --------
    ``MathLiveField(*args: object, **kwargs: object)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    *args : object, optional
        Additional positional arguments forwarded by this API. Optional variadic input.
    
    **kwargs : object, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    MathLiveField
        New ``MathLiveField`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``*args``: Additional positional arguments are passed through when this API supports variadic input.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``MathLiveField`` lives in ``gu_toolkit._mathlive_widget``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit._mathlive_widget import MathLiveField
        obj = MathLiveField(...)
    
    Discovery-oriented use::
    
        help(MathLiveField)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(MathLiveField)`` and ``dir(MathLiveField)`` to inspect adjacent members.
    """

    value = traitlets.Unicode("").tag(sync=True)
    placeholder = traitlets.Unicode("").tag(sync=True)
    aria_label = traitlets.Unicode("Mathematical input").tag(sync=True)
    read_only = traitlets.Bool(False).tag(sync=True)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.layout = widgets.Layout(width="100%", min_width="0", max_width="100%")
        add_class = getattr(self, "add_class", None)
        if callable(add_class):
            add_class("gu-control")
            add_class("gu-control-math")

    _esm = r"""
    let mathliveReady = null;

    function ensureMathLive() {
      if (!mathliveReady) {
        mathliveReady = import("https://esm.run/mathlive");
      }
      return mathliveReady;
    }

    function setCommonState(node, model) {
      if (!node) return;
      const placeholder = model.get("placeholder") || "";
      const ariaLabel = model.get("aria_label") || placeholder || "Mathematical input";
      const readOnly = !!model.get("read_only");
      if (node instanceof HTMLElement) {
        node.setAttribute("aria-label", ariaLabel);
        node.style.display = "block";
        node.style.width = "100%";
        node.style.maxWidth = "100%";
        node.style.boxSizing = "border-box";
        node.style.minWidth = "0";
        node.style.overflow = "hidden";
        if (node.tagName && node.tagName.toLowerCase() === "math-field") {
          node.style.fontSize = "var(--gu-math-font-size, 18px)";
          node.style.lineHeight = "1.05";
        }
        node.dataset.guReadOnly = readOnly ? "true" : "false";
      }
      if ("placeholder" in node) node.placeholder = placeholder;
      if ("readOnly" in node) node.readOnly = readOnly;
      if ("disabled" in node) node.disabled = false;
    }

    function applyValue(node, value) {
      const next = value || "";
      if (!node) return;
      if (node.tagName && node.tagName.toLowerCase() === "math-field") {
        if (node.value !== next) {
          try {
            node.setValue(next, { silenceNotifications: true });
          } catch (_error) {
            node.value = next;
          }
        }
        return;
      }
      if (node.value !== next) node.value = next;
    }

    function bindValueBridge(node, model) {
      const commit = () => {
        const next = typeof node.value === "string" ? node.value : "";
        if (model.get("value") === next) return;
        model.set("value", next);
        model.save_changes();
      };
      node.addEventListener("input", commit);
      node.addEventListener("change", commit);
      return () => {
        node.removeEventListener("input", commit);
        node.removeEventListener("change", commit);
      };
    }

    async function buildMathField() {
      await ensureMathLive();
      const field = document.createElement("math-field");
      field.setAttribute("math-virtual-keyboard-policy", "auto");
      field.setAttribute("virtual-keyboard-mode", "manual");
      field.smartFence = true;
      field.smartMode = true;
      return field;
    }

    function buildTextarea() {
      const field = document.createElement("textarea");
      field.rows = 1;
      field.spellcheck = false;
      field.style.resize = "vertical";
      return field;
    }

    export default {
      async render({ model, el }) {
        el.innerHTML = "";
        el.style.width = "100%";
        el.style.minWidth = "0";
        el.style.maxWidth = "100%";
        el.style.overflow = "hidden";

        let input = null;
        try {
          input = await buildMathField();
        } catch (_error) {
          input = buildTextarea();
        }

        const cleanupBridge = bindValueBridge(input, model);
        const syncFromModel = () => {
          setCommonState(input, model);
          applyValue(input, model.get("value"));
        };
        syncFromModel();

        const onValue = () => applyValue(input, model.get("value"));
        const onPlaceholder = () => setCommonState(input, model);
        const onReadOnly = () => setCommonState(input, model);
        model.on("change:value", onValue);
        model.on("change:placeholder", onPlaceholder);
        model.on("change:aria_label", onPlaceholder);
        model.on("change:read_only", onReadOnly);

        el.appendChild(input);

        return () => {
          cleanupBridge();
          model.off("change:value", onValue);
          model.off("change:placeholder", onPlaceholder);
          model.off("change:aria_label", onPlaceholder);
          model.off("change:read_only", onReadOnly);
        };
      },
    };
    """


__all__ = ["MathLiveField"]
