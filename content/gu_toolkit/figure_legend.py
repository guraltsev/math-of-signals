"""Legend sidebar runtime and interaction glue.

Purpose
-------
This module owns the toolkit-managed legend sidebar: visible rows for plots in
the active view, per-row visibility toggles, the line-style dialog, and the
toolbar/edit triggers that now launch the plot-composer modal.

Architecture
------------
The legend intentionally stays a *row manager* rather than becoming a full plot
editor. It owns row widgets, active-view filtering, and browser-only context
menu/dialog affordances, while delegating new-plot/edit-plot form logic to
``figure_plot_editor.py`` through a tiny callback bridge.

Discoverability
---------------
See :mod:`gu_toolkit.figure_plot_editor` for the modal form and
:mod:`gu_toolkit.Figure` for the coordinator that wires both subsystems
together.
"""

from __future__ import annotations

import base64
import html
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import traitlets

from ._widget_stubs import anywidget, widgets
from .figure_color import color_for_trace_index, color_to_picker_hex
from .widget_chrome import (
    add_widget_classes,
    attach_host_children,
    build_action_bar,
    build_boolean_field,
    build_dialog_header,
    build_form_section,
    build_modal_overlay,
    build_modal_panel,
    build_title_chip,
    configure_action_button,
    configure_control,
    configure_icon_button,
    hosted_modal_dimensions,
    labelled_field,
    load_ui_css,
    shared_style_widget,
)


_DASH_STYLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Solid", "solid"),
    ("Dot", "dot"),
    ("Dash", "dash"),
    ("Dash-dot", "dashdot"),
    ("Long dash", "longdash"),
    ("Long dash-dot", "longdashdot"),
)
_DASH_STYLE_VALUES = frozenset(value for _, value in _DASH_STYLE_OPTIONS)

_LEGEND_LOCAL_CSS = load_ui_css("legend.css")


class _LegendInteractionBridge(anywidget.AnyWidget):
    """Frontend bridge for legend context menus and dialog UX.

    The legend still uses Python widgets for the visible rows and style editor,
    but browser-side glue is needed for two interactions Python cannot observe
    directly:

    - custom right-click handling inside the legend area,
    - modal affordances such as Escape-to-close, backdrop clicks, and focus
      restoration.
    """

    root_class = traitlets.Unicode("").tag(sync=True)
    modal_class = traitlets.Unicode("").tag(sync=True)
    dialog_open = traitlets.Bool(False).tag(sync=True)
    dialog_label = traitlets.Unicode("Legend style settings").tag(sync=True)
    plot_label = traitlets.Unicode("plot").tag(sync=True)
    sound_enabled = traitlets.Bool(False).tag(sync=True)

    _esm = r"""
    function q(node, selector) {
      return node ? node.querySelector(selector) : null;
    }

    function qInput(node) {
      return q(node, "input, textarea, select") || node;
    }

    function qButton(node) {
      return q(node, "button, .widget-button, .jupyter-button") || node;
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

    function parsePlotIdFromClasses(node) {
      if (!(node instanceof HTMLElement)) return "";
      for (const cls of Array.from(node.classList || [])) {
        if (cls.startsWith("gu-legend-plot-id-")) {
          return cls.slice("gu-legend-plot-id-".length);
        }
      }
      return "";
    }

    export default {
      render({ model, el }) {
        el.style.display = "none";

        const dialogId = `gu-legend-style-dialog-${Math.random().toString(16).slice(2)}`;
        const titleId = `${dialogId}-title`;
        const menuId = `gu-legend-context-menu-${Math.random().toString(16).slice(2)}`;
        let returnFocusEl = null;
        let menuPlotId = "";

        function rootEl() {
          const rootClass = model.get("root_class") || "";
          return rootClass ? document.querySelector(`.${rootClass}`) : null;
        }

        function modalEl() {
          const modalClass = model.get("modal_class") || "";
          return modalClass ? document.querySelector(`.${modalClass}`) : null;
        }

        function panelEl() {
          return q(modalEl(), ".gu-legend-style-dialog-panel");
        }

        function titleEl() {
          return q(panelEl(), ".gu-legend-style-dialog-title-text");
        }

        function closeButtonEl() {
          return qButton(q(panelEl(), ".smart-slider-close-button"));
        }

        function cancelButtonEl() {
          return qButton(q(panelEl(), ".gu-legend-style-dialog-cancel-button"));
        }

        function okButtonEl() {
          return qButton(q(panelEl(), ".gu-legend-style-dialog-ok-button"));
        }

        function colorInputEl() {
          return qInput(q(panelEl(), ".gu-legend-style-dialog-color"));
        }

        function widthInputEl() {
          return qInput(q(panelEl(), ".gu-legend-style-dialog-width"));
        }

        function opacityInputEl() {
          return qInput(q(panelEl(), ".gu-legend-style-dialog-opacity"));
        }

        function dashInputEl() {
          return qInput(q(panelEl(), ".gu-legend-style-dialog-dash"));
        }

        function autonormalizationInputEl() {
          return qInput(q(panelEl(), ".gu-legend-style-dialog-autonormalization"));
        }

        function sendRequest(action, payload) {
          try {
            model.send({
              type: "legend_context_request",
              action,
              ...(payload || {}),
            });
          } catch (e) {}
        }

        function ensureContextMenu() {
          if (el.__guLegendContextMenu instanceof HTMLElement) {
            return el.__guLegendContextMenu;
          }

          const menu = document.createElement("div");
          menu.id = menuId;
          menu.className = "gu-legend-context-menu";
          menu.setAttribute("role", "menu");
          menu.style.display = "none";

          const checkboxLabel = document.createElement("label");
          checkboxLabel.className = "gu-legend-context-menu-item gu-legend-context-menu-checkbox";
          checkboxLabel.setAttribute("role", "menuitemcheckbox");

          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.className = "gu-legend-context-menu-sound-checkbox";

          const checkboxText = document.createElement("span");
          checkboxText.textContent = "Sound generation";

          checkboxLabel.appendChild(checkbox);
          checkboxLabel.appendChild(checkboxText);

          menu.appendChild(checkboxLabel);
          document.body.appendChild(menu);

          checkbox.addEventListener("change", () => {
            sendRequest("set_sound_enabled", { enabled: !!checkbox.checked });
          });
          menu.addEventListener("contextmenu", (event) => {
            event.preventDefault();
            event.stopPropagation();
          });

          el.__guLegendContextMenu = menu;
          el.__guLegendContextMenuCheckbox = checkbox;
          return menu;
        }

        function contextMenuEl() {
          return ensureContextMenu();
        }

        function menuCheckboxEl() {
          return el.__guLegendContextMenuCheckbox || ensureContextMenu().querySelector("input");
        }

        function contextMenuVisible() {
          const menu = contextMenuEl();
          return menu instanceof HTMLElement && menu.style.display !== "none";
        }

        function syncContextMenu() {
          const checkbox = menuCheckboxEl();
          if (checkbox) {
            checkbox.checked = !!model.get("sound_enabled");
          }
        }

        function hideContextMenu() {
          const menu = contextMenuEl();
          if (!(menu instanceof HTMLElement)) return;
          menu.style.display = "none";
          menu.setAttribute("aria-hidden", "true");
          menuPlotId = "";
        }

        function showContextMenu(clientX, clientY) {
          const menu = contextMenuEl();
          if (!(menu instanceof HTMLElement)) return;
          syncContextMenu();
          menu.style.display = "flex";
          menu.setAttribute("aria-hidden", "false");
          menu.style.left = `${Math.max(8, Number(clientX) || 0)}px`;
          menu.style.top = `${Math.max(8, Number(clientY) || 0)}px`;
          requestAnimationFrame(() => {
            const rect = menu.getBoundingClientRect();
            const maxLeft = Math.max(8, window.innerWidth - rect.width - 8);
            const maxTop = Math.max(8, window.innerHeight - rect.height - 8);
            menu.style.left = `${Math.min(Math.max(8, Number(clientX) || 0), maxLeft)}px`;
            menu.style.top = `${Math.min(Math.max(8, Number(clientY) || 0), maxTop)}px`;
          });
        }

        function legendTargetOf(target) {
          if (!(target instanceof HTMLElement)) return null;
          return target.closest(
            ".gu-figure-legend-area, .gu-legend-row, .gu-legend-toggle, .gu-legend-sound-toggle"
          );
        }

        function applyDialogLabels() {
          const dialogLabel = model.get("dialog_label") || "Legend style settings";
          const plotLabel = model.get("plot_label") || "plot";
          const isOpen = !!model.get("dialog_open");
          const modal = modalEl();
          const panel = panelEl();
          const title = titleEl();
          const closeButton = closeButtonEl();
          const cancelButton = cancelButtonEl();
          const okButton = okButtonEl();
          const colorInput = colorInputEl();
          const widthInput = widthInputEl();
          const opacityInput = opacityInputEl();
          const dashInput = dashInputEl();
          const autonormalizationInput = autonormalizationInputEl();

          if (title) {
            title.id = titleId;
          }

          if (panel) {
            panel.id = dialogId;
            panel.setAttribute("role", "dialog");
            panel.setAttribute("aria-modal", "true");
            panel.setAttribute("tabindex", "-1");
            panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
            if (title) {
              panel.setAttribute("aria-labelledby", titleId);
            } else {
              panel.setAttribute("aria-label", dialogLabel);
            }
          }

          if (modal) {
            modal.setAttribute("aria-hidden", isOpen ? "false" : "true");
          }

          if (closeButton) {
            closeButton.setAttribute("aria-controls", dialogId);
          }

          if (cancelButton) {
            cancelButton.setAttribute("aria-controls", dialogId);
          }

          if (okButton) {
            okButton.setAttribute("aria-controls", dialogId);
          }

          if (colorInput) {
            colorInput.setAttribute("aria-label", `${plotLabel} color`);
          }

          if (widthInput) {
            widthInput.setAttribute("aria-label", `${plotLabel} line width`);
            widthInput.setAttribute("inputmode", "decimal");
          }

          if (opacityInput) {
            opacityInput.setAttribute("aria-label", `${plotLabel} opacity`);
            opacityInput.setAttribute("inputmode", "decimal");
          }

          if (dashInput) {
            dashInput.setAttribute("aria-label", `${plotLabel} line style`);
          }

          if (autonormalizationInput) {
            autonormalizationInput.setAttribute(
              "aria-label",
              `${plotLabel} sound auto-normalization`,
            );
          }
        }

        function focusDialog() {
          const panel = panelEl();
          if (!panel || !model.get("dialog_open")) return;
          const items = focusables(panel);
          const target = items[0] || panel;
          try {
            target.focus({ preventScroll: true });
          } catch (e) {
            try { target.focus(); } catch (err) {}
          }
        }

        function syncFromModel() {
          applyDialogLabels();
          syncContextMenu();
          const isOpen = !!model.get("dialog_open");
          const panel = panelEl();
          if (isOpen) {
            if (!(returnFocusEl instanceof HTMLElement)) {
              const active = document.activeElement;
              if (active instanceof HTMLElement) {
                returnFocusEl = active;
              }
            }
            requestAnimationFrame(() => focusDialog());
            return;
          }

          if (returnFocusEl instanceof HTMLElement && document.documentElement.contains(returnFocusEl)) {
            try {
              returnFocusEl.focus({ preventScroll: true });
            } catch (e) {
              try { returnFocusEl.focus(); } catch (err) {}
            }
          }

          if (panel instanceof HTMLElement) {
            panel.blur();
          }

          returnFocusEl = null;
        }

        function detachContext() {
          const oldRoot = el.__guLegendRoot;
          const oldHandler = el.__guLegendContextHandler;
          if (oldRoot && oldHandler) {
            oldRoot.removeEventListener("contextmenu", oldHandler, true);
          }
          el.__guLegendRoot = null;
          el.__guLegendContextHandler = null;
        }

        function attachContext() {
          const root = rootEl();
          if (!(root instanceof HTMLElement)) {
            detachContext();
            return;
          }
          if (el.__guLegendRoot === root) return;
          detachContext();
          const handler = (event) => {
            const target = event.target;
            const legendTarget = legendTargetOf(target);
            if (!(legendTarget instanceof HTMLElement)) return;
            event.preventDefault();
            event.stopPropagation();
            const owner = target instanceof HTMLElement
              ? target.closest(".gu-legend-row, .gu-legend-toggle, .gu-legend-sound-toggle")
              : null;
            const plotId = parsePlotIdFromClasses(owner || legendTarget || target);
            const marker = target instanceof HTMLElement ? target.closest(".gu-legend-toggle") : null;
            returnFocusEl = qButton(marker || owner || legendTarget) || owner || legendTarget;
            menuPlotId = plotId || "";
            showContextMenu(event.clientX, event.clientY);
          };
          root.addEventListener("contextmenu", handler, true);
          el.__guLegendRoot = root;
          el.__guLegendContextHandler = handler;
        }

        function onKeydown(event) {
          if (event.key === "Escape" && contextMenuVisible()) {
            event.preventDefault();
            event.stopPropagation();
            hideContextMenu();
            return;
          }

          if (!model.get("dialog_open")) return;
          const panel = panelEl();
          if (!(panel instanceof HTMLElement)) return;

          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            sendRequest("close_style_dialog", { reason: "escape" });
            return;
          }

          if (event.key !== "Tab") return;

          const items = focusables(panel);
          if (!items.length) {
            event.preventDefault();
            try { panel.focus({ preventScroll: true }); } catch (e) {}
            return;
          }

          const first = items[0];
          const last = items[items.length - 1];
          const active = document.activeElement;

          if (!panel.contains(active)) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (e) { try { first.focus(); } catch (err) {} }
            return;
          }

          if (event.shiftKey && active === first) {
            event.preventDefault();
            try { last.focus({ preventScroll: true }); } catch (e) { try { last.focus(); } catch (err) {} }
            return;
          }

          if (!event.shiftKey && active === last) {
            event.preventDefault();
            try { first.focus({ preventScroll: true }); } catch (e) { try { first.focus(); } catch (err) {} }
          }
        }

        function onDocumentClick(event) {
          const target = event.target;
          const menu = contextMenuEl();
          if (contextMenuVisible() && menu instanceof HTMLElement) {
            if (!(target instanceof HTMLElement) || !menu.contains(target)) {
              hideContextMenu();
            }
          }

          if (!model.get("dialog_open")) return;
          const modal = modalEl();
          if (!modal) return;
          if (target === modal) {
            sendRequest("close_style_dialog", { reason: "backdrop" });
          }
        }

        const onRootChange = () => {
          attachContext();
          applyDialogLabels();
          syncContextMenu();
        };
        const onDialogOpenChange = () => syncFromModel();
        const onLabelChange = () => applyDialogLabels();
        const onSoundEnabledChange = () => syncContextMenu();

        model.on("change:root_class", onRootChange);
        model.on("change:modal_class", onRootChange);
        model.on("change:dialog_open", onDialogOpenChange);
        model.on("change:dialog_label", onLabelChange);
        model.on("change:plot_label", onLabelChange);
        model.on("change:sound_enabled", onSoundEnabledChange);
        ensureContextMenu();
        attachContext();
        document.addEventListener("keydown", onKeydown, true);
        document.addEventListener("click", onDocumentClick, true);
        requestAnimationFrame(() => syncFromModel());

        return () => {
          try { model.off("change:root_class", onRootChange); } catch (e) {}
          try { model.off("change:modal_class", onRootChange); } catch (e) {}
          try { model.off("change:dialog_open", onDialogOpenChange); } catch (e) {}
          try { model.off("change:dialog_label", onLabelChange); } catch (e) {}
          try { model.off("change:plot_label", onLabelChange); } catch (e) {}
          try { model.off("change:sound_enabled", onSoundEnabledChange); } catch (e) {}
          try { document.removeEventListener("keydown", onKeydown, true); } catch (e) {}
          try { document.removeEventListener("click", onDocumentClick, true); } catch (e) {}
          try {
            const menu = el.__guLegendContextMenu;
            if (menu instanceof HTMLElement && menu.parentElement) {
              menu.parentElement.removeChild(menu);
            }
          } catch (e) {}
          detachContext();
        };
      },
    };
    """

@dataclass
class LegendRowModel:
    """Widget and state bundle for one legend row bound to a plot id.
    
    Full API
    --------
    ``LegendRowModel(plot_id: str, container: widgets.HBox, toggle: widgets.ToggleButton, label_widget: widgets.HTMLMath, sound_button: widgets.Button, style_widget: widgets.HTML, css_plot_id: str, edit_button: widgets.Button | None=None, is_visible_for_active_view: bool=False)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    plot_id : str
        Stable plot identifier used for lookup or update. Required.
    
    container : widgets.HBox
        Value for ``container`` in this API. Required.
    
    toggle : widgets.ToggleButton
        Value for ``toggle`` in this API. Required.
    
    label_widget : widgets.HTMLMath
        Value for ``label_widget`` in this API. Required.
    
    sound_button : widgets.Button
        Value for ``sound_button`` in this API. Required.
    
    style_widget : widgets.HTML
        Value for ``style_widget`` in this API. Required.
    
    css_plot_id : str
        Value for ``css_plot_id`` in this API. Required.
    
    edit_button : widgets.Button | None, optional
        Value for ``edit_button`` in this API. Defaults to ``None``.
    
    is_visible_for_active_view : bool, optional
        Boolean flag or query related to visible for active view. Defaults to ``False``.
    
    Returns
    -------
    LegendRowModel
        New ``LegendRowModel`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``edit_button=None``: Value for ``edit_button`` in this API.
    - ``is_visible_for_active_view=False``: Boolean flag or query related to visible for active view.
    
    Architecture note
    -----------------
    ``LegendRowModel`` lives in ``gu_toolkit.figure_legend``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_legend import LegendRowModel
        obj = LegendRowModel(...)
    
    Discovery-oriented use::
    
        help(LegendRowModel)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(LegendRowModel)`` and ``dir(LegendRowModel)`` to inspect adjacent members.
    """

    plot_id: str
    container: widgets.HBox
    toggle: widgets.ToggleButton
    label_widget: widgets.HTMLMath
    sound_button: widgets.Button
    style_widget: widgets.HTML
    css_plot_id: str
    edit_button: widgets.Button | None = None
    is_visible_for_active_view: bool = False


@dataclass(frozen=True)
class LegendStyleDialogState:
    """Snapshot of the dialog controls loaded from a plot.
    
    Full API
    --------
    ``LegendStyleDialogState(picker_color: str, width: float, opacity: float, dash: str, autonormalization: bool)``
    
    Public members exposed from this class: No additional public methods are declared directly on this class.
    
    Parameters
    ----------
    picker_color : str
        Value for ``picker_color`` in this API. Required.
    
    width : float
        Value for ``width`` in this API. Required.
    
    opacity : float
        Opacity value applied to the rendered output. Required.
    
    dash : str
        Dash pattern used for contour or curve rendering. Required.
    
    autonormalization : bool
        Value for ``autonormalization`` in this API. Required.
    
    Returns
    -------
    LegendStyleDialogState
        New ``LegendStyleDialogState`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    This API does not declare optional arguments in its Python signature.
    
    Architecture note
    -----------------
    ``LegendStyleDialogState`` lives in ``gu_toolkit.figure_legend``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_legend import LegendStyleDialogState
        obj = LegendStyleDialogState(...)
    
    Discovery-oriented use::
    
        help(LegendStyleDialogState)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(LegendStyleDialogState)`` and ``dir(LegendStyleDialogState)`` to inspect adjacent members.
    """

    picker_color: str
    width: float
    opacity: float
    dash: str
    autonormalization: bool


class LegendPanelManager:
    """Manage legend sidebar rows and synchronize them with plot lifecycle events.
    
    Full API
    --------
    ``LegendPanelManager(layout_box: widgets.Box, modal_host: widgets.Box | None=None, root_widget: widgets.Box | None=None, header_toolbar: widgets.Box | None=None, enable_plot_editor: bool=False)``
    
    Public members exposed from this class: ``has_legend``, ``panel_visible``, ``bind_plot_editor_handler``,
        ``bind_sound_enabled_handler``, ``set_sound_generation_enabled``,
        ``set_sound_playing_plot``, ``on_plot_added``, ``on_plot_updated``,
        ``on_plot_removed``, ``set_active_view``, ``refresh``
    
    Parameters
    ----------
    layout_box : widgets.Box
        Value for ``layout_box`` in this API. Required.
    
    modal_host : widgets.Box | None, optional
        Value for ``modal_host`` in this API. Defaults to ``None``.
    
    root_widget : widgets.Box | None, optional
        Value for ``root_widget`` in this API. Defaults to ``None``.
    
    header_toolbar : widgets.Box | None, optional
        Value for ``header_toolbar`` in this API. Defaults to ``None``.
    
    enable_plot_editor : bool, optional
        Value for ``enable_plot_editor`` in this API. Defaults to ``False``.
    
    Returns
    -------
    LegendPanelManager
        New ``LegendPanelManager`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``modal_host=None``: Value for ``modal_host`` in this API.
    - ``root_widget=None``: Value for ``root_widget`` in this API.
    - ``header_toolbar=None``: Value for ``header_toolbar`` in this API.
    - ``enable_plot_editor=False``: Value for ``enable_plot_editor`` in this API.
    
    Architecture note
    -----------------
    ``LegendPanelManager`` lives in ``gu_toolkit.figure_legend``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.figure_legend import LegendPanelManager
        obj = LegendPanelManager(...)
    
    Discovery-oriented use::
    
        help(LegendPanelManager)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/develop_guide.md``.
    - Example notebook: ``examples/Toolkit_overview.ipynb``.
    - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
    - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
    """

    def __init__(
        self,
        layout_box: widgets.Box,
        *,
        modal_host: widgets.Box | None = None,
        root_widget: widgets.Box | None = None,
        header_toolbar: widgets.Box | None = None,
        enable_plot_editor: bool = False,
    ) -> None:
        """Initialize a legend manager bound to the provided layout box."""
        self._layout_box = layout_box
        self._modal_host = modal_host
        self._header_toolbar = header_toolbar
        self._enable_plot_editor = bool(enable_plot_editor)
        self._plot_editor_handler: Callable[[str | None], None] | None = None
        self._rows: dict[str, LegendRowModel] = {}
        self._plots: dict[str, Any] = {}
        self._ordered_plot_ids: list[str] = []
        self._active_view_id: str | None = None
        self._suspended_plot_ids: set[str] = set()
        self._sound_generation_enabled = False
        self._sound_playing_plot_id: str | None = None
        self._sound_enabled_handler: Any = None
        self._settings_open = False
        self._settings_plot_id: str | None = None
        self._dialog_loaded_style: LegendStyleDialogState | None = None

        self._root_css_class = f"gu-figure-context-root-{uuid.uuid4().hex[:8]}"
        self._dialog_modal_class = f"{self._root_css_class}-legend-style-modal"
        add_layout_class = getattr(self._layout_box, "add_class", None)
        if callable(add_layout_class):
            add_layout_class("gu-figure-legend-area")
        if root_widget is not None:
            add_class = getattr(root_widget, "add_class", None)
            if callable(add_class):
                add_class(self._root_css_class)
                add_class("gu-figure-context-governed")
        self._context_bridge = _LegendInteractionBridge(
            root_class=self._root_css_class,
            modal_class=self._dialog_modal_class,
            dialog_open=False,
            dialog_label="Legend style settings",
            plot_label="plot",
            sound_enabled=False,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._context_bridge.on_msg(self._handle_context_bridge_message)

        self._style_widget = shared_style_widget(_LEGEND_LOCAL_CSS, include_base=False)
        self._row_style_widget = self._style_widget
        self._refresh_row_style_widget()
        self._dialog_color = widgets.ColorPicker(
            value="#636efa",
            description="",
            concise=True,
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        configure_control(
            self._dialog_color,
            family="color",
            extra_classes=("gu-legend-style-dialog-color",),
        )
        self._dialog_width = widgets.BoundedFloatText(
            value=2.0,
            min=0.0,
            description="",
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        configure_control(
            self._dialog_width,
            family="numeric",
            extra_classes=("gu-legend-style-dialog-width",),
        )
        self._dialog_opacity = widgets.BoundedFloatText(
            value=1.0,
            min=0.0,
            max=1.0,
            description="",
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        configure_control(
            self._dialog_opacity,
            family="numeric",
            extra_classes=("gu-legend-style-dialog-opacity",),
        )
        self._dialog_dash = widgets.Dropdown(
            options=_DASH_STYLE_OPTIONS,
            value="solid",
            description="",
            layout=widgets.Layout(width="100%", min_width="0"),
        )
        configure_control(
            self._dialog_dash,
            family="dropdown",
            extra_classes=("gu-legend-style-dialog-dash",),
        )
        self._dialog_autonormalization = widgets.Checkbox(
            value=False,
            description="Auto-normalize sound",
            indent=False,
            tooltip="Automatically scale louder sound chunks into [-1, 1]",
            layout=widgets.Layout(width="auto", min_width="0"),
        )
        configure_control(
            self._dialog_autonormalization,
            family="checkbox",
            extra_classes=("gu-legend-style-dialog-autonormalization",),
        )
        self._dialog_close_button = widgets.Button(
            description="Close legend style dialog",
            tooltip="Close legend style dialog",
        )
        configure_icon_button(
            self._dialog_close_button,
            role="close",
            size_px=24,
            extra_classes=("gu-legend-style-dialog-close-button",),
        )
        self._dialog_close_button.on_click(self._dismiss_style_dialog)
        self._dialog_title_text = widgets.HTML(
            "Legend style",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self._dialog_title_text.add_class("gu-modal-title-text")
        self._dialog_title_text.add_class("gu-legend-style-dialog-title-text")
        self._dialog_subject = build_title_chip("")
        self._dialog_cancel_button = widgets.Button(
            description="Cancel",
            tooltip="Discard legend style changes",
        )
        configure_action_button(
            self._dialog_cancel_button,
            variant="secondary",
            min_width_px=72,
            extra_classes=("gu-legend-style-dialog-cancel-button",),
        )
        self._dialog_cancel_button.on_click(self._dismiss_style_dialog)
        self._dialog_ok_button = widgets.Button(
            description="Apply",
            tooltip="Apply legend style changes",
        )
        configure_action_button(
            self._dialog_ok_button,
            variant="primary",
            min_width_px=72,
            extra_classes=("gu-legend-style-dialog-ok-button",),
        )
        self._dialog_ok_button.on_click(self._apply_style_dialog)
        dialog_header = build_dialog_header(
            self._dialog_title_text,
            self._dialog_close_button,
            chip_widget=self._dialog_subject,
        )
        dialog_actions = build_action_bar(
            [self._dialog_cancel_button, self._dialog_ok_button],
            extra_classes=("gu-legend-style-dialog-actions",),
        )
        dialog_fields = build_form_section(
            "Style",
            [
                labelled_field("Color", self._dialog_color),
                labelled_field("Width", self._dialog_width),
                labelled_field("Opacity", self._dialog_opacity),
                labelled_field("Dash", self._dialog_dash),
            ],
            extra_classes=("gu-legend-style-dialog-section",),
        )
        dialog_sound = build_form_section(
            "Sound",
            [build_boolean_field(self._dialog_autonormalization)],
            extra_classes=("gu-legend-style-dialog-section",),
        )
        dialog_width, dialog_min_width, dialog_max_width = hosted_modal_dimensions(
            preferred_width_px=440,
            minimum_width_px=320,
        )
        self._dialog_panel = build_modal_panel(
            [
                dialog_header,
                dialog_fields,
                dialog_sound,
                dialog_actions,
            ],
            width=dialog_width,
            min_width=dialog_min_width,
            max_width=dialog_max_width,
            display="none",
            extra_classes=("gu-legend-style-dialog-panel",),
        )
        self._dialog_modal = build_modal_overlay(
            self._dialog_panel,
            hosted=True,
            z_index="1000",
            background_color="rgba(15, 23, 42, 0.12)",
            modal_class=self._dialog_modal_class,
        )

        attach_host_children(
            self._modal_host,
            self._style_widget,
            self._dialog_modal,
            self._context_bridge,
        )

        self._plot_add_button: widgets.Button | None = None
        self._plot_toolbar: widgets.HBox | None = None
        self._empty_state: widgets.HTML | None = None
        if self._enable_plot_editor:
            self._plot_add_button = widgets.Button(
                description="Create plot from expression",
                tooltip="Create plot from expression",
                disabled=True,
            )
            configure_icon_button(
                self._plot_add_button,
                role="plus",
                size_px=28,
                extra_classes=("gu-legend-add-plot-button", "gu-legend-inline-button"),
            )
            self._plot_add_button.on_click(lambda _button: self._request_plot_edit(None))
            if self._header_toolbar is not None:
                self._header_toolbar.children = (self._plot_add_button,)
            else:
                self._plot_toolbar = widgets.HBox(
                    [self._plot_add_button],
                    layout=widgets.Layout(
                        width="100%",
                        align_items="center",
                        justify_content="flex-end",
                        gap="8px",
                        margin="0 0 4px 0",
                    ),
                )
                self._plot_toolbar.add_class("gu-legend-plot-toolbar")
            self._empty_state = widgets.HTML(
                value="No plots in this view yet. Use the + button to add one.",
                layout=widgets.Layout(margin="0", width="100%"),
            )
            self._empty_state.add_class("gu-legend-empty-state")

    @property
    def has_legend(self) -> bool:
        """Return ``True`` when at least one row is visible for the active view.
        
        Full API
        --------
        ``obj.has_legend -> bool``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            current = obj.has_legend
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        return any(row.is_visible_for_active_view for row in self._rows.values())

    @property
    def panel_visible(self) -> bool:
        """Return whether the legend panel should occupy sidebar space.
        
        Full API
        --------
        ``obj.panel_visible -> bool``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        bool
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            current = obj.panel_visible
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """

        return self._enable_plot_editor or self.has_legend

    def bind_plot_editor_handler(
        self, callback: Callable[[str | None], None] | None
    ) -> None:
        """Bind the callback used by add/edit plot controls.
        
        Full API
        --------
        ``obj.bind_plot_editor_handler(callback: Callable[[str | None], None] | None) -> None``
        
        Parameters
        ----------
        callback : Callable[[str | None], None] | None
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.bind_plot_editor_handler(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """

        self._plot_editor_handler = callback
        if self._plot_add_button is not None:
            self._plot_add_button.disabled = callback is None
        for row in self._rows.values():
            if row.edit_button is not None:
                row.edit_button.disabled = callback is None

    def bind_sound_enabled_handler(self, callback: Any) -> None:
        """Bind the figure-level sound enable/disable handler.
        
        Full API
        --------
        ``obj.bind_sound_enabled_handler(callback: Any) -> None``
        
        Parameters
        ----------
        callback : Any
            Callable that is invoked when the relevant event fires. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.bind_sound_enabled_handler(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        self._sound_enabled_handler = callback

    def set_sound_generation_enabled(self, enabled: bool) -> None:
        """Show or hide per-row sound controls.
        
        Full API
        --------
        ``obj.set_sound_generation_enabled(enabled: bool) -> None``
        
        Parameters
        ----------
        enabled : bool
            Boolean flag that turns a feature on or off. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.set_sound_generation_enabled(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        self._sound_generation_enabled = bool(enabled)
        self._context_bridge.sound_enabled = self._sound_generation_enabled
        self.refresh(reason="sound_generation_toggled")

    def set_sound_playing_plot(self, plot_id: str | None) -> None:
        """Mark the row whose sound button should show the playing state.
        
        Full API
        --------
        ``obj.set_sound_playing_plot(plot_id: str | None) -> None``
        
        Parameters
        ----------
        plot_id : str | None
            Stable plot identifier used for lookup or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.set_sound_playing_plot(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        self._sound_playing_plot_id = None if plot_id is None else str(plot_id)
        self.refresh(reason="sound_playback_state_changed")

    def on_plot_added(self, plot: Any) -> None:
        """Register a plot and create a row if needed.
        
        Full API
        --------
        ``obj.on_plot_added(plot: Any) -> None``
        
        Parameters
        ----------
        plot : Any
            Value for ``plot`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.on_plot_added(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        plot_id = self._normalize_plot_id(getattr(plot, "id", None), fallback_prefix="plot")
        self._plots[plot_id] = plot
        if plot_id not in self._ordered_plot_ids:
            self._ordered_plot_ids.append(plot_id)
        if plot_id not in self._rows:
            self._rows[plot_id] = self._create_row(plot_id)
        self.refresh(reason="plot_added")

    def on_plot_updated(self, plot: Any) -> None:
        """Refresh row contents for an existing plot or lazily add it.
        
        Full API
        --------
        ``obj.on_plot_updated(plot: Any) -> None``
        
        Parameters
        ----------
        plot : Any
            Value for ``plot`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.on_plot_updated(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        plot_id = self._normalize_plot_id(getattr(plot, "id", None), fallback_prefix="plot")
        if plot_id not in self._rows:
            self.on_plot_added(plot)
            return
        self._plots[plot_id] = plot
        self.refresh(reason="plot_updated")

    def on_plot_removed(self, plot_id: str) -> None:
        """Unregister a plot and remove its row from the layout.
        
        Full API
        --------
        ``obj.on_plot_removed(plot_id: str) -> None``
        
        Parameters
        ----------
        plot_id : str
            Stable plot identifier used for lookup or update. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.on_plot_removed(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        key = self._normalize_plot_id(plot_id, fallback_prefix="plot")
        self._plots.pop(key, None)
        self._ordered_plot_ids = [pid for pid in self._ordered_plot_ids if pid != key]
        removed = self._rows.pop(key, None)
        if removed is not None:
            removed.toggle.unobserve_all()
        if self._sound_playing_plot_id == key:
            self._sound_playing_plot_id = None
        if self._settings_plot_id == key:
            self._set_style_dialog_open(False)
            self._dialog_loaded_style = None
            self._settings_plot_id = None
        self.refresh(reason="plot_removed")

    def set_active_view(self, view_id: str) -> None:
        """Set the active view used for row filtering.
        
        Full API
        --------
        ``obj.set_active_view(view_id: str) -> None``
        
        Parameters
        ----------
        view_id : str
            Identifier for the relevant view inside a figure. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.set_active_view(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        self._active_view_id = str(view_id)
        self.refresh(reason="active_view_changed")

    def refresh(self, reason: str = "") -> None:
        """Synchronize row widgets with latest plot state and active-view filtering.
        
        Full API
        --------
        ``obj.refresh(reason: str='') -> None``
        
        Parameters
        ----------
        reason : str, optional
            Short machine/human-readable reason recorded for scheduling or rendering. Defaults to ``''``.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        - ``reason=''``: Short machine/human-readable reason recorded for scheduling or rendering.
        
        Architecture note
        -----------------
        This member belongs to ``LegendPanelManager``. The figure layer is coordinator-driven: Figure owns orchestration, while view/layout/info/parameter collaborators own their specific state. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = LegendPanelManager(...)
            obj.refresh(...)
        
        Discovery-oriented use::
        
            help(LegendPanelManager)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/develop_guide.md``.
        - Example notebook: ``examples/Toolkit_overview.ipynb``.
        - Runtime discovery tip: use ``with fig:`` or ``with fig.views["id"]:`` and inspect ``help(Figure)`` for the class-based and current-figure surfaces.
        - In a notebook or REPL, run ``help(LegendPanelManager)`` and ``dir(LegendPanelManager)`` to inspect adjacent members.
        """
        visible_rows: list[widgets.Widget] = []
        for plot_id in self._ordered_plot_ids:
            plot = self._plots.get(plot_id)
            row = self._rows.get(plot_id)
            if plot is None or row is None:
                continue
            visible = self._plot_in_active_view(plot)
            row.is_visible_for_active_view = visible
            self._sync_row_widgets(row=row, plot=plot)
            if visible:
                visible_rows.append(row.container)

        desired_widgets: list[widgets.Widget] = []
        if self._enable_plot_editor:
            if self._plot_toolbar is not None:
                desired_widgets.append(self._plot_toolbar)
            if not visible_rows and self._empty_state is not None:
                desired_widgets.append(self._empty_state)
        desired_widgets.extend(visible_rows)
        desired_children = tuple(desired_widgets)
        if self._layout_box.children != desired_children:
            self._layout_box.children = desired_children
        if not self._settings_open:
            self._sync_dialog_from_plot_state()

    def _plot_in_active_view(self, plot: Any) -> bool:
        """Return whether ``plot`` belongs to the current active view."""
        if self._active_view_id is None:
            return True
        plot_views = getattr(plot, "views", ())
        return self._active_view_id in tuple(str(view_id) for view_id in plot_views)

    def _create_row(self, plot_id: str) -> LegendRowModel:
        """Create a legend row widget bundle with toggle and label controls."""
        css_plot_id = self._css_safe_plot_id(plot_id)
        toggle = widgets.ToggleButton(
            value=False,
            description="Toggle plot visibility",
            tooltip="Toggle plot visibility",
            layout=widgets.Layout(
                width="30px",
                min_width="30px",
                height="30px",
                margin="0",
                padding="0",
            )
        )
        add_widget_classes(
            toggle,
            "gu-legend-toggle",
            f"gu-legend-plot-id-{css_plot_id}",
        )

        label_widget = widgets.HTMLMath(
            value="",
            layout=widgets.Layout(margin="0", width="100%", flex="1 1 auto", min_width="0"),
        )

        edit_button: widgets.Button | None = None
        if self._enable_plot_editor:
            edit_button = widgets.Button(
                description="Edit plot",
                tooltip="Edit plot",
                disabled=self._plot_editor_handler is None,
            )
            configure_icon_button(
                edit_button,
                role="edit",
                size_px=28,
                extra_classes=("gu-legend-edit-button", "gu-legend-inline-button", f"gu-legend-plot-id-{css_plot_id}"),
            )

        sound_button = widgets.Button(
            description="Play sound",
            tooltip="Play sound",
            layout=widgets.Layout(
                width="28px",
                min_width="28px",
                height="28px",
                margin="0",
                padding="0",
                display="none",
            ),
        )
        configure_icon_button(
            sound_button,
            size_px=28,
            extra_classes=("gu-legend-sound-toggle", "gu-legend-inline-button", f"gu-legend-plot-id-{css_plot_id}"),
        )
        children: list[widgets.Widget] = [toggle, label_widget]
        if edit_button is not None:
            children.append(edit_button)
        children.append(sound_button)

        container = widgets.HBox(
            children,
            layout=widgets.Layout(width="100%", align_items="center", margin="0", gap="6px"),
        )
        container.add_class("gu-legend-row")
        container.add_class("gu-figure-context-governed")
        container.add_class(f"gu-legend-plot-id-{css_plot_id}")
        toggle.observe(lambda change, pid=plot_id: self._on_toggle_changed(pid, change), names="value")
        if edit_button is not None:
            edit_button.on_click(lambda _button, pid=plot_id: self._request_plot_edit(pid))
        sound_button.on_click(lambda _button, pid=plot_id: self._on_sound_button_clicked(pid))
        row_model = LegendRowModel(
            plot_id=plot_id,
            container=container,
            toggle=toggle,
            label_widget=label_widget,
            sound_button=sound_button,
            style_widget=self._row_style_widget,
            css_plot_id=css_plot_id,
            edit_button=edit_button,
        )
        self._refresh_row_style_widget()
        return row_model

    def _refresh_row_style_widget(self) -> None:
        """Append per-row marker colors so legend dots stay synchronized to plots."""

        rules: list[str] = []
        for plot_id in self._ordered_plot_ids:
            row = self._rows.get(plot_id)
            plot = self._plots.get(plot_id)
            if row is None or plot is None:
                continue
            marker_color = self._resolve_plot_color(plot).strip() or "#6c757d"
            css_plot_id = row.css_plot_id
            rules.append(
                "\n".join(
                    (
                        f".gu-legend-plot-id-{css_plot_id}.gu-legend-toggle,",
                        f".gu-legend-plot-id-{css_plot_id}.gu-legend-toggle :is(button, .widget-button, .jupyter-button) {{",
                        f"  --gu-legend-marker-color: {marker_color} !important;",
                        "}",
                    )
                )
            )
        css = _LEGEND_LOCAL_CSS
        if rules:
            css = f"{css}\n\n/* Legend row marker colors */\n" + "\n".join(rules)
        self._style_widget.value = f"<style>{css}</style>"

    def _sync_row_widgets(self, *, row: LegendRowModel, plot: Any) -> None:
        """Incrementally update label/toggle to mirror current plot state."""
        label = self._format_label_value(plot=plot, default_plot_id=row.plot_id)
        if row.label_widget.value != label:
            row.label_widget.value = label

        target_value = self._coerce_visible_to_bool(getattr(plot, "visible", True))
        marker_color = self._resolve_plot_color(plot)
        self._refresh_row_style_widget()
        plot_label = self._accessible_plot_label(plot, row.plot_id)
        self._sync_toggle_accessibility(
            toggle=row.toggle,
            plot_label=plot_label,
            is_visible=target_value,
        )
        if row.edit_button is not None:
            self._sync_edit_button_accessibility(
                button=row.edit_button,
                plot_label=plot_label,
            )
            row.edit_button.disabled = self._plot_editor_handler is None
        self._style_toggle_marker(toggle=row.toggle, is_visible=target_value, marker_color=marker_color)
        supports_sound = callable(getattr(plot, "sound", None))
        sound_enabled = self._sound_generation_enabled and supports_sound
        self._sync_sound_button_accessibility(
            button=row.sound_button,
            plot_label=plot_label,
            is_enabled=sound_enabled,
            is_playing=sound_enabled and self._sound_playing_plot_id == row.plot_id,
        )
        self._style_sound_button(
            button=row.sound_button,
            is_enabled=sound_enabled,
            is_playing=sound_enabled and self._sound_playing_plot_id == row.plot_id,
        )
        if row.toggle.value != target_value:
            self._suspended_plot_ids.add(row.plot_id)
            try:
                row.toggle.value = target_value
            finally:
                self._suspended_plot_ids.discard(row.plot_id)

    def _on_sound_button_clicked(self, plot_id: str) -> None:
        """Toggle streaming sound playback for the requested plot."""
        if not self._sound_generation_enabled:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            return
        sound_method = getattr(plot, "sound", None)
        if not callable(sound_method):
            return
        sound_method(run=self._sound_playing_plot_id != plot_id)

    @staticmethod
    def _style_sound_button(*, button: widgets.Button, is_enabled: bool, is_playing: bool) -> None:
        """Render the sound control as a muted or playing speaker icon."""
        button.icon = ""
        button.button_style = ""
        button.style.button_color = "transparent"
        button.layout.border = "none"
        button.layout.display = "inline-flex" if is_enabled else "none"
        button.layout.opacity = "1" if is_playing else "0.8"
        add_class = getattr(button, "add_class", None)
        remove_class = getattr(button, "remove_class", None)
        if callable(remove_class):
            remove_class("mod-muted")
            remove_class("mod-playing")
        if callable(add_class):
            add_class("mod-playing" if is_playing else "mod-muted")

    @staticmethod
    def _sync_sound_button_accessibility(
        *,
        button: widgets.Button,
        plot_label: str,
        is_enabled: bool,
        is_playing: bool,
    ) -> None:
        """Provide descriptive accessible copy for the sound button."""
        label = plot_label.strip() or "plot"
        if not is_enabled:
            description = f"Sound generation disabled for plot {label}"
        else:
            action = "Stop" if is_playing else "Play"
            description = f"{action} sound for plot {label}"
        button.description = description
        button.tooltip = description

    @staticmethod
    def _sync_edit_button_accessibility(
        *,
        button: widgets.Button,
        plot_label: str,
    ) -> None:
        """Provide descriptive accessible copy for the edit button."""

        label = plot_label.strip() or "plot"
        description = f"Edit plot {label}"
        button.description = description
        button.tooltip = description

    def _request_plot_edit(self, plot_id: str | None) -> None:
        """Forward add/edit plot requests to the bound figure callback."""

        if callable(self._plot_editor_handler):
            self._plot_editor_handler(plot_id)

    def _on_toggle_changed(self, plot_id: str, change: dict[str, Any]) -> None:
        """Propagate user checkbox toggles to bound plot visibility."""
        if change.get("name") != "value":
            return
        if plot_id in self._suspended_plot_ids:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            return
        plot.visible = bool(change.get("new"))
        row = self._rows.get(plot_id)
        if row is None:
            return
        marker_color = self._resolve_plot_color(plot)
        self._refresh_row_style_widget()
        self._style_toggle_marker(
            toggle=row.toggle,
            is_visible=plot.visible is True,
            marker_color=marker_color,
        )
        self._sync_toggle_accessibility(
            toggle=row.toggle,
            plot_label=self._accessible_plot_label(plot, plot_id),
            is_visible=plot.visible is True,
        )

    @staticmethod
    def _style_toggle_marker(*, toggle: widgets.ToggleButton, is_visible: bool, marker_color: str) -> None:
        """Render the toggle marker as a color-coded circular legend control."""
        toggle.icon = ""
        toggle.button_style = ""
        toggle.style.text_color = marker_color
        toggle.style.button_color = "transparent"
        toggle.layout.border = "none"
        toggle.layout.opacity = "1" if is_visible else "0.6"
        add_class = getattr(toggle, "add_class", None)
        remove_class = getattr(toggle, "remove_class", None)
        if callable(remove_class):
            remove_class("mod-visible")
            remove_class("mod-hidden")
        if is_visible:
            if callable(add_class):
                add_class("mod-visible")
        elif callable(add_class):
            add_class("mod-hidden")

    @staticmethod
    def _sync_toggle_accessibility(*, toggle: widgets.ToggleButton, plot_label: str, is_visible: bool) -> None:
        """Provide a descriptive, stateful accessible name for the toggle."""
        action = "Hide" if is_visible else "Show"
        label = plot_label.strip() or "plot"
        description = f"{action} plot {label}"
        toggle.description = description
        toggle.tooltip = description

    @classmethod
    def _accessible_plot_label(cls, plot: Any, default_plot_id: str) -> str:
        raw_label = cls._safe_attr_str(plot, "label").strip()
        if raw_label:
            return raw_label
        raw_plot_id = cls._safe_attr_str(plot, "id").strip()
        if raw_plot_id:
            return raw_plot_id
        return default_plot_id

    @classmethod
    def _resolve_plot_color(cls, plot: Any) -> str:
        raw_color = cls._safe_attr_str(plot, "color").strip()
        if raw_color:
            return raw_color
        trace_handle = cls._resolve_reference_trace_handle(plot)
        if trace_handle is not None:
            trace_color = cls._resolve_trace_handle_color(trace_handle)
            if trace_color:
                return trace_color
            inferred = cls._resolve_default_color_from_parent_figure(trace_handle)
            if inferred:
                return inferred
        return "#6c757d"

    @staticmethod
    def _resolve_reference_trace_handle(plot: Any) -> Any:
        getter = getattr(plot, "_reference_trace_handle", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    @classmethod
    def _resolve_trace_handle_color(cls, trace_handle: Any) -> str:
        line_obj = getattr(trace_handle, "line", None)
        line_color = cls._safe_attr_str(line_obj, "color").strip()
        if line_color:
            return line_color
        marker_obj = getattr(trace_handle, "marker", None)
        marker_color = cls._safe_attr_str(marker_obj, "color").strip()
        if marker_color:
            return marker_color
        return ""

    @classmethod
    def _resolve_default_color_from_parent_figure(cls, trace_handle: Any) -> str:
        parent = getattr(trace_handle, "_parent", None)
        traces = tuple(getattr(parent, "data", ())) if parent is not None else ()
        if not traces:
            return ""
        try:
            trace_index = traces.index(trace_handle)
        except ValueError:
            return ""
        return color_for_trace_index(parent, trace_index, fallback="")

    @staticmethod
    def _coerce_visible_to_bool(value: Any) -> bool:
        return value is True

    @staticmethod
    def _normalize_plot_id(raw_plot_id: Any, *, fallback_prefix: str) -> str:
        try:
            value = "" if raw_plot_id is None else str(raw_plot_id)
        except Exception:
            value = ""
        value = value.strip()
        if value:
            return value
        return f"{fallback_prefix}-{id(raw_plot_id)}"

    @classmethod
    def _format_label_value(cls, *, plot: Any, default_plot_id: str) -> str:
        raw_label = cls._safe_attr_str(plot, "label")
        if raw_label.strip() != "":
            return html.escape(raw_label)
        raw_plot_id = cls._safe_attr_str(plot, "id")
        if raw_plot_id.strip() != "":
            return html.escape(raw_plot_id)
        return html.escape(default_plot_id)

    @staticmethod
    def _safe_attr_str(plot: Any, attr_name: str) -> str:
        try:
            value = getattr(plot, attr_name, "")
        except Exception:
            return ""
        try:
            return "" if value is None else str(value)
        except Exception:
            return ""

    @staticmethod
    def _css_safe_plot_id(plot_id: str) -> str:
        payload = base64.urlsafe_b64encode(str(plot_id).encode("utf-8")).decode("ascii")
        return f"b64-{payload.rstrip('=')}"

    @staticmethod
    def _decode_css_plot_id(css_plot_id: str) -> str:
        text = str(css_plot_id or "")
        prefix = "b64-"
        if not text.startswith(prefix):
            return text
        payload = text[len(prefix):]
        if not payload:
            return ""
        padding = "=" * (-len(payload) % 4)
        try:
            return base64.urlsafe_b64decode((payload + padding).encode("ascii")).decode("utf-8")
        except Exception:
            return text

    def _handle_context_bridge_message(self, _widget: Any, content: Any, _buffers: Any) -> None:
        if not isinstance(content, dict):
            return
        if content.get("type") != "legend_context_request":
            return
        action = content.get("action")
        if action == "close_style_dialog":
            self._dismiss_style_dialog(None)
            return
        if action == "set_sound_enabled":
            enabled = bool(content.get("enabled"))
            if callable(self._sound_enabled_handler):
                self._sound_enabled_handler(enabled)
            else:
                self.set_sound_generation_enabled(enabled)
            return
        if action != "open_style_dialog":
            return
        raw_plot_id = content.get("plot_id")
        if not isinstance(raw_plot_id, str):
            return
        plot_id = self._decode_css_plot_id(raw_plot_id)
        plot = self._plots.get(plot_id)
        if plot is None or not getattr(plot, "supports_style_dialog", True):
            return
        self._open_style_dialog(plot_id)

    def _open_style_dialog(self, plot_id: str) -> None:
        plot = self._plots.get(plot_id)
        if plot is None or not getattr(plot, "supports_style_dialog", True):
            return
        self._settings_plot_id = plot_id
        self._load_style_dialog_from_plot(plot, plot_id=plot_id)
        self._set_style_dialog_open(True)

    def _dismiss_style_dialog(self, _event: Any) -> None:
        """Close the dialog without applying its pending edits."""
        self._dialog_loaded_style = None
        self._set_style_dialog_open(False)
        self._settings_plot_id = None

    def _apply_style_dialog(self, _event: Any) -> None:
        """Apply the pending dialog edits to the active plot and close."""
        plot_id = self._settings_plot_id
        loaded = self._dialog_loaded_style
        if plot_id is None or loaded is None:
            self._dismiss_style_dialog(None)
            return

        plot = self._plots.get(plot_id)
        if plot is None:
            self._dismiss_style_dialog(None)
            return

        has_changes = False

        next_picker_color = str(self._dialog_color.value or "").strip() or loaded.picker_color
        if next_picker_color != loaded.picker_color:
            plot.color = next_picker_color
            has_changes = True

        next_width = float(self._dialog_width.value)
        if next_width != loaded.width:
            plot.thickness = next_width
            has_changes = True

        next_opacity = float(self._dialog_opacity.value)
        if next_opacity != loaded.opacity:
            plot.opacity = next_opacity
            has_changes = True

        next_dash = str(self._dialog_dash.value or "solid")
        if next_dash != loaded.dash:
            plot.dash = next_dash
            has_changes = True

        next_autonormalization = bool(self._dialog_autonormalization.value)
        if next_autonormalization != loaded.autonormalization:
            self._set_plot_autonormalization(plot, next_autonormalization)
            has_changes = True

        if has_changes:
            self.on_plot_updated(plot)
        self._dismiss_style_dialog(None)

    def _set_style_dialog_open(self, is_open: bool) -> None:
        self._settings_open = bool(is_open)
        self._dialog_panel.layout.display = "flex" if self._settings_open else "none"
        self._dialog_modal.layout.display = "flex" if self._settings_open else "none"
        self._context_bridge.dialog_open = self._settings_open
        if not self._settings_open:
            self._dialog_subject.layout.display = "none"
            self._context_bridge.dialog_label = "Legend style settings"
            self._context_bridge.plot_label = "plot"

    def _sync_dialog_from_plot_state(self, *, force: bool = False) -> None:
        plot_id = self._settings_plot_id
        if plot_id is None:
            return
        plot = self._plots.get(plot_id)
        if plot is None:
            self._dialog_loaded_style = None
            self._set_style_dialog_open(False)
            self._settings_plot_id = None
            return
        if self._settings_open and not force:
            return
        self._load_style_dialog_from_plot(plot, plot_id=plot_id)

    def _load_style_dialog_from_plot(self, plot: Any, *, plot_id: str) -> None:
        """Populate dialog controls from ``plot`` and capture their baseline."""
        state = self._style_dialog_state_for_plot(plot)
        self._dialog_loaded_style = state
        plot_label = self._accessible_plot_label(plot, plot_id).strip() or plot_id
        self._dialog_subject.value = html.escape(plot_label)
        self._dialog_subject.layout.display = "flex"
        self._dialog_color.value = state.picker_color
        self._dialog_width.value = state.width
        self._dialog_opacity.value = state.opacity
        self._dialog_dash.value = state.dash
        self._dialog_autonormalization.value = state.autonormalization

        self._context_bridge.plot_label = plot_label
        self._context_bridge.dialog_label = f"Legend style settings for {plot_label}"

    def _style_dialog_state_for_plot(self, plot: Any) -> LegendStyleDialogState:
        """Return the normalized style values shown in the dialog for ``plot``."""
        current_color = self._resolve_plot_color(plot)
        current_width = self._safe_float(getattr(plot, "thickness", None), default=2.0)
        current_opacity = self._safe_float(getattr(plot, "opacity", None), default=1.0)
        current_dash = self._safe_attr_str(plot, "dash").strip() or "solid"
        return LegendStyleDialogState(
            picker_color=color_to_picker_hex(current_color, fallback="#6c757d"),
            width=current_width,
            opacity=current_opacity,
            dash=current_dash if current_dash in _DASH_STYLE_VALUES else "solid",
            autonormalization=self._plot_autonormalization_enabled(plot),
        )

    @staticmethod
    def _plot_autonormalization_enabled(plot: Any) -> bool:
        handler = getattr(plot, "autonormalization", None)
        if callable(handler):
            try:
                return bool(handler())
            except Exception:
                return False
        return bool(getattr(plot, "_sound_autonormalization", False))

    @classmethod
    def _set_plot_autonormalization(cls, plot: Any, enabled: bool) -> None:
        handler = getattr(plot, "autonormalization", None)
        if callable(handler):
            handler(enabled)
            return
        setattr(plot, "_sound_autonormalization", bool(enabled))

    @staticmethod
    def _safe_float(value: Any, *, default: float) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except Exception:
            return float(default)
