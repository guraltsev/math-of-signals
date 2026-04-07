"""Widget chrome bridges and backwards-compatible UI helpers.

The toolkit's generic visual system lives in :mod:`gu_toolkit.ui_system`.  This
module keeps the frontend bridge widgets that need browser-side behavior, while
re-exporting the shared layout/button helpers for existing imports.
"""

from __future__ import annotations

from typing import Iterable

import traitlets

from ._widget_stubs import anywidget, widgets
from .ui_system import (
    ButtonVariant,
    IconButtonRole,
    SectionPanel,
    add_widget_classes,
    attach_host_children,
    build_action_bar,
    build_boolean_field,
    build_dialog_header,
    build_form_section,
    build_inline_alert,
    build_modal_overlay,
    build_modal_panel,
    build_readonly_value,
    build_section_panel,
    build_tab_bar,
    build_title_chip,
    configure_action_button,
    configure_control,
    configure_icon_button,
    ensure_fill_layout,
    full_width_layout,
    hbox,
    hosted_modal_dimensions,
    load_ui_css,
    labelled_field,
    responsive_row,
    set_tab_button_selected,
    set_widget_class_state,
    shared_style_widget,
    shared_theme_css,
    style_widget_value,
    vbox,
)


class ModalDialogBridge(anywidget.AnyWidget):
    """Frontend bridge for modal dialog semantics and keyboard handling.
    
    Full API
    --------
    ``ModalDialogBridge(modal_class=traitlets.Unicode('').tag(sync=True), panel_selector=traitlets.Unicode('.gu-modal-panel').tag(sync=True), close_selector=traitlets.Unicode('.gu-icon-close-button').tag(sync=True), title_selector=traitlets.Unicode('.gu-modal-title-text').tag(sync=True), dialog_open=traitlets.Bool(False).tag(sync=True), dialog_label=traitlets.Unicode('Dialog').tag(sync=True), return_focus_selector=traitlets.Unicode('').tag(sync=True), focus_selector=traitlets.Unicode('').tag(sync=True), focus_nonce=traitlets.Int(0).tag(sync=True))``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    modal_class : Any, optional
        Value for ``modal_class`` in this API. Defaults to ``traitlets.Unicode('').tag(sync=True)``.
    
    panel_selector : Any, optional
        Value for ``panel_selector`` in this API. Defaults to ``traitlets.Unicode('.gu-modal-panel').tag(sync=True)``.
    
    close_selector : Any, optional
        Value for ``close_selector`` in this API. Defaults to ``traitlets.Unicode('.gu-icon-close-button').tag(sync=True)``.
    
    title_selector : Any, optional
        Value for ``title_selector`` in this API. Defaults to ``traitlets.Unicode('.gu-modal-title-text').tag(sync=True)``.
    
    dialog_open : Any, optional
        Value for ``dialog_open`` in this API. Defaults to ``traitlets.Bool(False).tag(sync=True)``.
    
    dialog_label : Any, optional
        Value for ``dialog_label`` in this API. Defaults to ``traitlets.Unicode('Dialog').tag(sync=True)``.
    
    return_focus_selector : Any, optional
        Value for ``return_focus_selector`` in this API. Defaults to ``traitlets.Unicode('').tag(sync=True)``.
    
    focus_selector : Any, optional
        Value for ``focus_selector`` in this API. Defaults to ``traitlets.Unicode('').tag(sync=True)``.
    
    focus_nonce : Any, optional
        Value for ``focus_nonce`` in this API. Defaults to ``traitlets.Int(0).tag(sync=True)``.
    
    Returns
    -------
    ModalDialogBridge
        New ``ModalDialogBridge`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``modal_class=traitlets.Unicode('').tag(sync=True)``: Value for ``modal_class`` in this API.
    - ``panel_selector=traitlets.Unicode('.gu-modal-panel').tag(sync=True)``: Value for ``panel_selector`` in this API.
    - ``close_selector=traitlets.Unicode('.gu-icon-close-button').tag(sync=True)``: Value for ``close_selector`` in this API.
    - ``title_selector=traitlets.Unicode('.gu-modal-title-text').tag(sync=True)``: Value for ``title_selector`` in this API.
    - ``dialog_open=traitlets.Bool(False).tag(sync=True)``: Value for ``dialog_open`` in this API.
    - ``dialog_label=traitlets.Unicode('Dialog').tag(sync=True)``: Value for ``dialog_label`` in this API.
    - ``return_focus_selector=traitlets.Unicode('').tag(sync=True)``: Value for ``return_focus_selector`` in this API.
    - ``focus_selector=traitlets.Unicode('').tag(sync=True)``: Value for ``focus_selector`` in this API.
    - ``focus_nonce=traitlets.Int(0).tag(sync=True)``: Value for ``focus_nonce`` in this API.
    
    Architecture note
    -----------------
    ``ModalDialogBridge`` lives in ``gu_toolkit.widget_chrome``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.widget_chrome import ModalDialogBridge
        obj = ModalDialogBridge(...)
    
    Discovery-oriented use::
    
        help(ModalDialogBridge)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(ModalDialogBridge)`` and ``dir(ModalDialogBridge)`` to inspect adjacent members.
    """

    modal_class = traitlets.Unicode("").tag(sync=True)
    panel_selector = traitlets.Unicode(".gu-modal-panel").tag(sync=True)
    close_selector = traitlets.Unicode(".gu-icon-close-button").tag(sync=True)
    title_selector = traitlets.Unicode(".gu-modal-title-text").tag(sync=True)
    dialog_open = traitlets.Bool(False).tag(sync=True)
    dialog_label = traitlets.Unicode("Dialog").tag(sync=True)
    return_focus_selector = traitlets.Unicode("").tag(sync=True)
    focus_selector = traitlets.Unicode("").tag(sync=True)
    focus_nonce = traitlets.Int(0).tag(sync=True)

    _esm = r"""
    function q(node, selector) {
      return node ? node.querySelector(selector) : null;
    }

    function focusables(root) {
      if (!root) return [];
      const selector = [
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "a[href]",
        "[tabindex]:not([tabindex='-1'])",
      ].join(",");
      return Array.from(root.querySelectorAll(selector)).filter((el) => {
        if (!(el instanceof HTMLElement)) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        return !el.hasAttribute("disabled");
      });
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";
        const dialogId = `gu-modal-${Math.random().toString(16).slice(2)}`;
        const titleId = `${dialogId}-title`;
        let returnFocusEl = null;
        let lastFocusNonce = Number(model.get("focus_nonce") || 0);

        function modalEl() {
          const className = model.get("modal_class") || "";
          return className ? document.querySelector(`.${className}`) : null;
        }

        function panelEl() {
          const modal = modalEl();
          if (!modal) return null;
          const selector = model.get("panel_selector") || ".gu-modal-panel";
          return modal.querySelector(selector) || modal.firstElementChild;
        }

        function closeButtonEl() {
          return q(modalEl(), model.get("close_selector") || ".gu-icon-close-button");
        }

        function titleEl() {
          return q(modalEl(), model.get("title_selector") || ".gu-modal-title-text");
        }

        function requestedFocusEl() {
          const panel = panelEl();
          if (!(panel instanceof HTMLElement)) return null;
          const selector = model.get("focus_selector") || "";
          if (!selector) return null;
          return panel.querySelector(selector);
        }

        function sendClose(reason) {
          try {
            model.send({ type: "dialog_request", action: "close", reason: reason || "request" });
          } catch (_error) {}
        }

        function applyState() {
          const modal = modalEl();
          const panel = panelEl();
          const title = titleEl();
          const closeButton = closeButtonEl();
          const isOpen = !!model.get("dialog_open");
          const label = model.get("dialog_label") || "Dialog";

          if (title instanceof HTMLElement) {
            title.id = titleId;
          }

          if (panel instanceof HTMLElement) {
            panel.id = dialogId;
            panel.setAttribute("role", "dialog");
            panel.setAttribute("aria-modal", "true");
            panel.setAttribute("tabindex", "-1");
            panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (title instanceof HTMLElement) {
              panel.setAttribute("aria-labelledby", titleId);
            } else {
              panel.setAttribute("aria-label", label);
            }
          }

          if (modal instanceof HTMLElement) {
            modal.setAttribute("aria-hidden", isOpen ? "false" : "true");
          }

          if (closeButton instanceof HTMLElement) {
            closeButton.setAttribute("aria-controls", dialogId);
          }
        }

        function focusDialog() {
          const panel = panelEl();
          if (!(panel instanceof HTMLElement) || !model.get("dialog_open")) return;
          const requested = requestedFocusEl();
          const items = focusables(panel);
          const target = (requested instanceof HTMLElement ? requested : null) || items[0] || panel;
          try {
            target.focus({ preventScroll: true });
          } catch (_error) {
            try { target.focus(); } catch (_inner) {}
          }
        }

        function restoreFocus() {
          const selector = model.get("return_focus_selector") || "";
          const preferred = selector ? document.querySelector(selector) : null;
          const target = document.documentElement.contains(returnFocusEl)
            ? returnFocusEl
            : (preferred instanceof HTMLElement ? preferred : null);
          if (target instanceof HTMLElement) {
            try {
              target.focus({ preventScroll: true });
            } catch (_error) {
              try { target.focus(); } catch (_inner) {}
            }
            return;
          }
          const panel = panelEl();
          if (panel instanceof HTMLElement) {
            panel.blur();
          }
        }

        function syncFromModel() {
          applyState();
          const isOpen = !!model.get("dialog_open");
          const focusNonce = Number(model.get("focus_nonce") || 0);
          if (isOpen) {
            const active = document.activeElement;
            if (active instanceof HTMLElement) {
              returnFocusEl = active;
            }
            requestAnimationFrame(() => focusDialog());
            lastFocusNonce = focusNonce;
            return;
          }
          restoreFocus();
          lastFocusNonce = focusNonce;
        }

        function onFocusChange() {
          if (!model.get("dialog_open")) return;
          const focusNonce = Number(model.get("focus_nonce") || 0);
          if (focusNonce === lastFocusNonce && !(model.get("focus_selector") || "")) return;
          lastFocusNonce = focusNonce;
          requestAnimationFrame(() => focusDialog());
        }

        function onKeydown(event) {
          if (!model.get("dialog_open")) return;
          const panel = panelEl();
          if (!(panel instanceof HTMLElement)) return;

          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            sendClose("escape");
            return;
          }

          if (event.key !== "Tab") return;

          const items = focusables(panel);
          if (!items.length) {
            event.preventDefault();
            try { panel.focus({ preventScroll: true }); } catch (_error) {}
            return;
          }

          const first = items[0];
          const last = items[items.length - 1];
          const active = document.activeElement;

          if (!panel.contains(active)) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (_error) { try { first.focus(); } catch (_inner) {} }
            return;
          }

          if (event.shiftKey && active === first) {
            event.preventDefault();
            try { last.focus({ preventScroll: true }); } catch (_error) { try { last.focus(); } catch (_inner) {} }
            return;
          }

          if (!event.shiftKey && active === last) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (_error) { try { first.focus(); } catch (_inner) {} }
          }
        }

        function onDocumentClick(event) {
          if (!model.get("dialog_open")) return;
          const modal = modalEl();
          if (!(modal instanceof HTMLElement)) return;
          if (event.target === modal) {
            sendClose("backdrop");
          }
        }

        const onModelChange = () => syncFromModel();
        const onFocusModelChange = () => onFocusChange();
        model.on("change:dialog_open", onModelChange);
        model.on("change:dialog_label", onModelChange);
        model.on("change:modal_class", onModelChange);
        model.on("change:panel_selector", onModelChange);
        model.on("change:close_selector", onModelChange);
        model.on("change:title_selector", onModelChange);
        model.on("change:return_focus_selector", onModelChange);
        model.on("change:focus_selector", onFocusModelChange);
        model.on("change:focus_nonce", onFocusModelChange);
        document.addEventListener("keydown", onKeydown, true);
        document.addEventListener("click", onDocumentClick, true);

        requestAnimationFrame(() => syncFromModel());

        return () => {
          try { model.off("change:dialog_open", onModelChange); } catch (_error) {}
          try { model.off("change:dialog_label", onModelChange); } catch (_error) {}
          try { model.off("change:modal_class", onModelChange); } catch (_error) {}
          try { model.off("change:panel_selector", onModelChange); } catch (_error) {}
          try { model.off("change:close_selector", onModelChange); } catch (_error) {}
          try { model.off("change:title_selector", onModelChange); } catch (_error) {}
          try { model.off("change:return_focus_selector", onModelChange); } catch (_error) {}
          try { model.off("change:focus_selector", onFocusModelChange); } catch (_error) {}
          try { model.off("change:focus_nonce", onFocusModelChange); } catch (_error) {}
          try { document.removeEventListener("keydown", onKeydown, true); } catch (_error) {}
          try { document.removeEventListener("click", onDocumentClick, true); } catch (_error) {}
        };
      },
    };
    """


class TabListBridge(anywidget.AnyWidget):
    """Frontend bridge that adds accessible tab semantics and arrow navigation.
    
    Full API
    --------
    ``TabListBridge(tablist_selector=traitlets.Unicode('.gu-tab-bar').tag(sync=True), tab_selector=traitlets.Unicode('.gu-action-button-tab').tag(sync=True), panel_selector=traitlets.Unicode('.gu-tab-panel').tag(sync=True), selected_index=traitlets.Int(0).tag(sync=True))``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    tablist_selector : Any, optional
        Value for ``tablist_selector`` in this API. Defaults to ``traitlets.Unicode('.gu-tab-bar').tag(sync=True)``.
    
    tab_selector : Any, optional
        Value for ``tab_selector`` in this API. Defaults to ``traitlets.Unicode('.gu-action-button-tab').tag(sync=True)``.
    
    panel_selector : Any, optional
        Value for ``panel_selector`` in this API. Defaults to ``traitlets.Unicode('.gu-tab-panel').tag(sync=True)``.
    
    selected_index : Any, optional
        Value for ``selected_index`` in this API. Defaults to ``traitlets.Int(0).tag(sync=True)``.
    
    Returns
    -------
    TabListBridge
        New ``TabListBridge`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``tablist_selector=traitlets.Unicode('.gu-tab-bar').tag(sync=True)``: Value for ``tablist_selector`` in this API.
    - ``tab_selector=traitlets.Unicode('.gu-action-button-tab').tag(sync=True)``: Value for ``tab_selector`` in this API.
    - ``panel_selector=traitlets.Unicode('.gu-tab-panel').tag(sync=True)``: Value for ``panel_selector`` in this API.
    - ``selected_index=traitlets.Int(0).tag(sync=True)``: Value for ``selected_index`` in this API.
    
    Architecture note
    -----------------
    ``TabListBridge`` lives in ``gu_toolkit.widget_chrome``. Runtime, scheduling, and widget-chrome modules isolate notebook-specific concerns from the core plotting model so the main figure code remains testable. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.widget_chrome import TabListBridge
        obj = TabListBridge(...)
    
    Discovery-oriented use::
    
        help(TabListBridge)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/ui-layout-system.md``.
    - Example notebook: ``examples/layout_debug.ipynb``.
    - Runtime discovery tip: pair ``help(...)`` with ``examples/layout_debug.ipynb`` when debugging widget, CSS, or geometry behavior.
    - In a notebook or REPL, run ``help(TabListBridge)`` and ``dir(TabListBridge)`` to inspect adjacent members.
    """

    tablist_selector = traitlets.Unicode(".gu-tab-bar").tag(sync=True)
    tab_selector = traitlets.Unicode(".gu-action-button-tab").tag(sync=True)
    panel_selector = traitlets.Unicode(".gu-tab-panel").tag(sync=True)
    selected_index = traitlets.Int(0).tag(sync=True)

    _esm = r"""
    function qAll(root, selector) {
      return root ? Array.from(root.querySelectorAll(selector)) : [];
    }

    function ensureId(node, prefix) {
      if (!(node instanceof HTMLElement)) return "";
      if (!node.id) {
        node.id = `${prefix}-${Math.random().toString(16).slice(2)}`;
      }
      return node.id;
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";
        const baseId = `gu-tablist-${Math.random().toString(16).slice(2)}`;

        function tablistEl() {
          const selector = model.get("tablist_selector") || ".gu-tab-bar";
          return document.querySelector(selector);
        }

        function tabs() {
          const list = tablistEl();
          const selector = model.get("tab_selector") || ".gu-action-button-tab";
          return qAll(list, selector).filter((node) => node instanceof HTMLElement);
        }

        function panels() {
          const selector = model.get("panel_selector") || ".gu-tab-panel";
          return qAll(document, selector).filter((node) => node instanceof HTMLElement);
        }

        function syncState() {
          const list = tablistEl();
          const tabNodes = tabs();
          const panelNodes = panels();
          const selectedIndex = Math.max(0, Math.min(Number(model.get("selected_index") || 0), tabNodes.length - 1));

          if (list instanceof HTMLElement) {
            list.setAttribute("role", "tablist");
            list.setAttribute("aria-orientation", "horizontal");
          }

          tabNodes.forEach((tab, index) => {
            const isSelected = index === selectedIndex;
            const tabId = ensureId(tab, `${baseId}-tab-${index}`);
            tab.setAttribute("role", "tab");
            tab.setAttribute("aria-selected", isSelected ? "true" : "false");
            tab.setAttribute("tabindex", isSelected ? "0" : "-1");
            if (panelNodes[index] instanceof HTMLElement) {
              const panel = panelNodes[index];
              const panelId = ensureId(panel, `${baseId}-panel-${index}`);
              tab.setAttribute("aria-controls", panelId);
              panel.setAttribute("role", "tabpanel");
              panel.setAttribute("aria-labelledby", tabId);
              panel.setAttribute("aria-hidden", isSelected ? "false" : "true");
            }
          });
        }

        function commitSelected(index, focusTab) {
          const tabNodes = tabs();
          if (!tabNodes.length) return;
          const next = Math.max(0, Math.min(Number(index) || 0, tabNodes.length - 1));
          if (Number(model.get("selected_index") || 0) !== next) {
            model.set("selected_index", next);
            model.save_changes();
          }
          requestAnimationFrame(() => {
            syncState();
            if (focusTab) {
              const node = tabs()[next];
              if (node instanceof HTMLElement) {
                try { node.focus({ preventScroll: true }); } catch (_error) { try { node.focus(); } catch (_inner) {} }
              }
            }
          });
        }

        function onKeydown(event) {
          const list = tablistEl();
          if (!(list instanceof HTMLElement)) return;
          if (!list.contains(event.target)) return;
          const tabNodes = tabs();
          if (!tabNodes.length) return;
          const current = Math.max(0, Math.min(Number(model.get("selected_index") || 0), tabNodes.length - 1));

          if (event.key === "ArrowRight") {
            event.preventDefault();
            commitSelected((current + 1) % tabNodes.length, true);
            return;
          }
          if (event.key === "ArrowLeft") {
            event.preventDefault();
            commitSelected((current - 1 + tabNodes.length) % tabNodes.length, true);
            return;
          }
          if (event.key === "Home") {
            event.preventDefault();
            commitSelected(0, true);
            return;
          }
          if (event.key === "End") {
            event.preventDefault();
            commitSelected(tabNodes.length - 1, true);
          }
        }

        function onModelChange() {
          requestAnimationFrame(() => syncState());
        }

        model.on("change:selected_index", onModelChange);
        model.on("change:tablist_selector", onModelChange);
        model.on("change:tab_selector", onModelChange);
        model.on("change:panel_selector", onModelChange);
        document.addEventListener("keydown", onKeydown, true);

        requestAnimationFrame(() => syncState());

        return () => {
          try { model.off("change:selected_index", onModelChange); } catch (_error) {}
          try { model.off("change:tablist_selector", onModelChange); } catch (_error) {}
          try { model.off("change:tab_selector", onModelChange); } catch (_error) {}
          try { model.off("change:panel_selector", onModelChange); } catch (_error) {}
          try { document.removeEventListener("keydown", onKeydown, true); } catch (_error) {}
        };
      },
    };
    """


__all__ = [
    "ButtonVariant",
    "IconButtonRole",
    "ModalDialogBridge",
    "SectionPanel",
    "TabListBridge",
    "add_widget_classes",
    "attach_host_children",
    "build_action_bar",
    "build_dialog_header",
    "build_form_section",
    "build_inline_alert",
    "build_modal_overlay",
    "build_modal_panel",
    "build_readonly_value",
    "build_section_panel",
    "build_tab_bar",
    "build_title_chip",
    "configure_action_button",
    "configure_control",
    "configure_icon_button",
    "ensure_fill_layout",
    "full_width_layout",
    "hbox",
    "hosted_modal_dimensions",
    "labelled_field",
    "responsive_row",
    "set_tab_button_selected",
    "set_widget_class_state",
    "shared_style_widget",
    "vbox",
]
