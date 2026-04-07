"""Custom slider widget used by Figure parameters.

Provides a synchronized slider/text control with advanced settings (min/max/
step/default) and helper APIs for parameter-reference integration.
"""

import html
import re
import uuid
from collections.abc import Sequence
from typing import Any, cast

from ._widget_stubs import anywidget, widgets
import traitlets

from .InputConvert import InputConvert
from .animation import DEFAULT_ANIMATION_TIME, AnimationController
from .widget_chrome import (
    attach_host_children,
    build_action_bar,
    build_boolean_field,
    build_dialog_header,
    build_form_section,
    build_modal_overlay,
    build_modal_panel,
    configure_action_button,
    configure_control,
    configure_icon_button,
    labelled_field,
    load_ui_css,
    responsive_row,
    shared_style_widget,
    style_widget_value,
)


_ANIMATION_MODE_BUTTON_CLASSES = {
    ">": "mod-mode-once",
    ">>": "mod-mode-loop",
    "<>": "mod-mode-bounce",
}
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

_SLIDER_LOCAL_CSS = load_ui_css("slider.css")


def _derive_accessibility_label(description: str, *, fallback: str = "parameter") -> str:
    """Return a plain-text label suitable for ARIA metadata.

    ``FloatSlider`` descriptions are often rich-text or LaTeX snippets. Screen
    readers need a compact plain-text fallback that stays meaningful even when
    the visible label is rendered via HTML/MathJax.
    """

    raw = html.unescape(str(description or ""))
    raw = _HTML_TAG_RE.sub(" ", raw)
    raw = raw.replace("$", " ")
    raw = raw.replace("\\", " ")
    raw = raw.replace("{", " ").replace("}", " ")
    raw = _WHITESPACE_RE.sub(" ", raw).strip(" :")
    return raw or fallback


def _normalize_title_subject(description: str) -> str:
    """Return a compact visible subject for the settings-dialog title.

    The inline slider description often ends with a trailing colon because it
    sits beside the control row. The dialog title reads more naturally without
    that punctuation while still preserving MathJax-compatible text supplied by
    the caller.
    """

    text = str(description or "").strip()
    if text.endswith(":"):
        text = text[:-1].rstrip()
    return text


class _SliderModalAccessibilityBridge(anywidget.AnyWidget):
    """Frontend bridge that adds dialog semantics and keyboard handling."""

    slider_root_class = traitlets.Unicode("").tag(sync=True)
    modal_class = traitlets.Unicode("").tag(sync=True)
    dialog_open = traitlets.Bool(False).tag(sync=True)
    dialog_label = traitlets.Unicode("Parameter settings").tag(sync=True)
    control_label = traitlets.Unicode("parameter").tag(sync=True)

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

    export default {
      render({ model, el }) {
        el.style.display = "none";

        const dialogId = `smart-slider-dialog-${Math.random().toString(16).slice(2)}`;
        const titleId = `${dialogId}-title`;
        let returnFocusEl = null;

        function rootEl() {
          const className = model.get("slider_root_class") || "";
          return className ? document.querySelector(`.${className}`) : null;
        }

        function modalEl() {
          const className = model.get("modal_class") || "";
          return className ? document.querySelector(`.${className}`) : null;
        }

        function panelEl() {
          return q(modalEl(), ".smart-slider-settings-panel");
        }

        function settingsButtonEl() {
          return qButton(q(rootEl(), ".smart-slider-settings-button"));
        }

        function closeButtonEl() {
          return qButton(q(modalEl(), ".smart-slider-close-button"));
        }

        function sliderInputEl() {
          return qInput(q(rootEl(), ".smart-slider-track"));
        }

        function valueInputEl() {
          return qInput(q(rootEl(), ".smart-slider-value-input"));
        }

        function minInputEl() {
          const limits = rootEl() ? rootEl().querySelectorAll(".smart-slider-limit") : [];
          return qInput(limits && limits.length > 0 ? limits[0] : null);
        }

        function maxInputEl() {
          const limits = rootEl() ? rootEl().querySelectorAll(".smart-slider-limit") : [];
          return qInput(limits && limits.length > 1 ? limits[1] : null);
        }

        function stepInputEl() {
          return qInput(q(modalEl(), ".smart-slider-settings-step-input"));
        }

        function animationTimeInputEl() {
          return qInput(q(modalEl(), ".smart-slider-settings-period-input"));
        }

        function animationModeInputEl() {
          return qInput(q(modalEl(), ".smart-slider-settings-mode-input"));
        }

        function titleEl() {
          return q(modalEl(), ".smart-slider-settings-title-text");
        }

        function sendClose(reason) {
          try {
            model.send({ type: "dialog_request", action: "close", reason: reason || "request" });
          } catch (e) {}
        }

        function applyLabels() {
          const controlLabel = model.get("control_label") || "parameter";
          const dialogLabel = model.get("dialog_label") || "Parameter settings";
          const modal = modalEl();
          const panel = panelEl();
          const settingsButton = settingsButtonEl();
          const closeButton = closeButtonEl();
          const sliderInput = sliderInputEl();
          const valueInput = valueInputEl();
          const minInput = minInputEl();
          const maxInput = maxInputEl();
          const stepInput = stepInputEl();
          const animationTimeInput = animationTimeInputEl();
          const animationModeInput = animationModeInputEl();
          const title = titleEl();
          const isOpen = !!model.get("dialog_open");

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

          if (settingsButton) {
            settingsButton.setAttribute("aria-haspopup", "dialog");
            settingsButton.setAttribute("aria-controls", dialogId);
            settingsButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
          }

          if (closeButton) {
            closeButton.setAttribute("aria-controls", dialogId);
          }

          if (sliderInput) {
            sliderInput.setAttribute("aria-label", `${controlLabel} slider`);
          }

          if (valueInput) {
            valueInput.setAttribute("aria-label", `${controlLabel} value`);
            valueInput.setAttribute("inputmode", "decimal");
          }

          if (minInput) {
            minInput.setAttribute("aria-label", `${controlLabel} minimum`);
            minInput.setAttribute("inputmode", "decimal");
          }

          if (maxInput) {
            maxInput.setAttribute("aria-label", `${controlLabel} maximum`);
            maxInput.setAttribute("inputmode", "decimal");
          }

          if (stepInput) {
            stepInput.setAttribute("aria-label", `${controlLabel} step size`);
            stepInput.setAttribute("inputmode", "decimal");
          }

          if (animationTimeInput) {
            animationTimeInput.setAttribute(
              "aria-label",
              `${controlLabel} animation period in seconds`,
            );
            animationTimeInput.setAttribute("inputmode", "decimal");
          }

          if (animationModeInput) {
            animationModeInput.setAttribute("aria-label", `${controlLabel} animation mode`);
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
          applyLabels();
          const isOpen = !!model.get("dialog_open");
          const panel = panelEl();
          const settingsButton = settingsButtonEl();
          if (isOpen) {
            const active = document.activeElement;
            if (active instanceof HTMLElement) {
              returnFocusEl = active;
            } else if (settingsButton instanceof HTMLElement) {
              returnFocusEl = settingsButton;
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
          } else if (settingsButton instanceof HTMLElement) {
            try {
              settingsButton.focus({ preventScroll: true });
            } catch (e) {
              try { settingsButton.focus(); } catch (err) {}
            }
          }

          if (panel instanceof HTMLElement) {
            panel.blur();
          }
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
          if (!model.get("dialog_open")) return;
          const modal = modalEl();
          if (!modal) return;
          if (event.target === modal) {
            sendClose("backdrop");
          }
        }

        const onOpenChange = () => syncFromModel();
        const onLabelChange = () => applyLabels();

        model.on("change:dialog_open", onOpenChange);
        model.on("change:dialog_label", onLabelChange);
        model.on("change:control_label", onLabelChange);
        model.on("change:slider_root_class", onLabelChange);
        model.on("change:modal_class", onLabelChange);
        document.addEventListener("keydown", onKeydown, true);
        document.addEventListener("click", onDocumentClick, true);

        requestAnimationFrame(() => syncFromModel());

        return () => {
          try { model.off("change:dialog_open", onOpenChange); } catch (e) {}
          try { model.off("change:dialog_label", onLabelChange); } catch (e) {}
          try { model.off("change:control_label", onLabelChange); } catch (e) {}
          try { model.off("change:slider_root_class", onLabelChange); } catch (e) {}
          try { model.off("change:modal_class", onLabelChange); } catch (e) {}
          try { document.removeEventListener("keydown", onKeydown, true); } catch (e) {}
          try { document.removeEventListener("click", onDocumentClick, true); } catch (e) {}
        };
      },
    };
    """


class FloatSlider(widgets.VBox):
    """A FloatSlider with:
    
    Full API
    --------
    ``FloatSlider(value: float=0.0, min: float=0.0, max: float=1.0, step: float=0.1, description: str='Value:', **kwargs: Any)``
    
    Public members exposed from this class: ``open_settings``, ``close_settings``, ``default_value``, ``min``, ``max``, ``step``,
        ``reset``, ``animation_time``, ``animation_mode``, ``animation_running``,
        ``start_animation``, ``stop_animation``, ``toggle_animation``, ``make_refs``,
        ``set_modal_host``
    
    Parameters
    ----------
    value : float, optional
        New or current value for the relevant property, control, or calculation. Defaults to ``0.0``.
    
    min : float, optional
        Lower bound used by sliders, domains, or range validators. Defaults to ``0.0``.
    
    max : float, optional
        Upper bound used by sliders, domains, or range validators. Defaults to ``1.0``.
    
    step : float, optional
        Increment or resolution used for stepping through numeric values. Defaults to ``0.1``.
    
    description : str, optional
        Value for ``description`` in this API. Defaults to ``'Value:'``.
    
    **kwargs : Any, optional
        Additional keyword arguments forwarded by this API. Optional variadic input.
    
    Returns
    -------
    FloatSlider
        New ``FloatSlider`` instance configured according to the constructor arguments.
    
    Optional arguments
    ------------------
    - ``value=0.0``: New or current value for the relevant property, control, or calculation.
    - ``min=0.0``: Lower bound used by sliders, domains, or range validators.
    - ``max=1.0``: Upper bound used by sliders, domains, or range validators.
    - ``step=0.1``: Increment or resolution used for stepping through numeric values.
    - ``description='Value:'``: Value for ``description`` in this API.
    - ``**kwargs``: Additional keyword arguments are forwarded to the underlying implementation. Use the guides and runtime-discovery tips below to see which names matter.
    
    Architecture note
    -----------------
    ``FloatSlider`` lives in ``gu_toolkit.Slider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use the class as the stable owner for this slice of state rather than reaching into collaborators directly.
    
    Examples
    --------
    Construction::
    
        from gu_toolkit.Slider import FloatSlider
        obj = FloatSlider(...)
    
    Discovery-oriented use::
    
        help(FloatSlider)
        dir(obj)
    
    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
    - Guide: ``docs/guides/parameter-key-semantics.md``.
    - Guide: ``docs/guides/parameter-animation.md``.
    - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
    - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
    """

    value = traitlets.Float(0.0)

    def __init__(
        self,
        value: float = 0.0,
        min: float = 0.0,
        max: float = 1.0,
        step: float = 0.1,
        description: str = "Value:",
        **kwargs: Any,
    ) -> None:
        """Create a slider with a single editable numeric field, animation button, and settings panel.

        Parameters
        ----------
        value : float, optional
            Initial value for the slider and numeric text field.
        min : float, optional
            Lower bound for the slider.
        max : float, optional
            Upper bound for the slider.
        step : float, optional
            Increment for the slider and step control.
        description : str, optional
            Label displayed to the left of the control.
        **kwargs : Any
            Additional keyword arguments forwarded to ``widgets.VBox``.

        Returns
        -------
        None
            This constructor initializes the widget in place.

        Examples
        --------
        Create a slider and read its value::

            >>> slider = FloatSlider(value=0.25, min=0.0, max=1.0, step=0.05)
            >>> float(slider.value)
            0.25

        Notes
        -----
        Use :meth:`make_refs` to bind the slider to a SymPy symbol when working
        with :class:`Figure` or :class:`ParameterManager`.
        """
        # Remember defaults for reset
        self._defaults = {"value": value, "min": min, "max": max, "step": step}

        # Internal guards to prevent circular updates.
        self._syncing = False
        self._syncing_animation_settings = False
        self._settings_open = False

        accessibility_label = str(kwargs.pop("accessibility_label", "")).strip()
        self._accessible_label = accessibility_label or _derive_accessibility_label(
            description
        )
        self._slider_root_class = f"smart-slider-instance-{uuid.uuid4().hex[:8]}"
        self._settings_modal_class = f"{self._slider_root_class}-modal"

        root_layout = kwargs.pop("layout", None)
        if root_layout is None:
            root_layout = widgets.Layout(width="100%", min_width="0")

        # --- Main controls ----------------------------------------------------
        self.slider = widgets.FloatSlider(
            value=value,
            min=min,
            max=max,
            step=step,
            description="",
            continuous_update=True,
            readout=False,  # IMPORTANT: no built-in numeric field
            style={"description_width": "initial"},
            layout=widgets.Layout(flex="1 1 auto", width="auto", min_width="0"),
        )
        self.slider.add_class("smart-slider-track")

        self.description_label = widgets.HTMLMath(
            value=description,
            layout=widgets.Layout(width="auto", min_width="0", margin="0 1px 0 0"),
        )
        self.description_label.add_class("smart-slider-label")

        self._theme_style = shared_style_widget()
        self._limit_style = shared_style_widget(_SLIDER_LOCAL_CSS, include_base=False)
        # The *only* numeric field (editable; accepts expressions)
        self.number = widgets.Text(
            value=str(value),
            continuous_update=False,  # commit on Enter (and typically blur)
            layout=widgets.Layout(width="64px", min_width="0"),
        )
        self.number.add_class("smart-slider-value-input")

        self.btn_animate = widgets.Button(
            description="Start animation",
            tooltip="Start animation",
        )
        configure_icon_button(self.btn_animate, role="animate", size_px=24)
        self.btn_reset = widgets.Button(
            description="Reset parameter",
            tooltip="Reset parameter",
        )
        configure_icon_button(self.btn_reset, role="reset", size_px=24)
        self.btn_settings = widgets.Button(
            description="Open parameter settings",
            tooltip="Open parameter settings",
        )
        configure_icon_button(self.btn_settings, role="settings", size_px=24)

        # --- Settings panel ---------------------------------------------------
        style_args = {
            "layout": widgets.Layout(width="100%", min_width="0"),
        }
        self.set_min = widgets.Text(
            value=f"{min:.4g}",
            continuous_update=False,
            layout=widgets.Layout(width="38px", min_width="0", height="16px", margin="0px"),
        )
        self.set_min.add_class("smart-slider-limit")
        self.set_max = widgets.Text(
            value=f"{max:.4g}",
            continuous_update=False,
            layout=widgets.Layout(width="38px", min_width="0", height="16px", margin="0px"),
        )
        self.set_max.add_class("smart-slider-limit")
        for field, placeholder in (
            (self.number, "value"),
            (self.set_min, "min"),
            (self.set_max, "max"),
        ):
            if hasattr(field, "placeholder"):
                setattr(field, "placeholder", placeholder)
        self.set_step = widgets.FloatText(value=step, description="", **style_args)
        configure_control(self.set_step, family="numeric")
        self.set_step.add_class("smart-slider-settings-step-input")
        self.set_live = widgets.Checkbox(
            value=True,
            description="Live Update",
            indent=False,
            layout=widgets.Layout(width="auto", min_width="0"),
        )
        configure_control(self.set_live, family="checkbox")
        self.set_animation_time = widgets.BoundedFloatText(
            value=DEFAULT_ANIMATION_TIME,
            min=0.001,
            step=0.1,
            description="",
            tooltip="Animation period in seconds for one pass across the current range.",
            **style_args,
        )
        configure_control(self.set_animation_time, family="numeric")
        self.set_animation_time.add_class("smart-slider-settings-period-input")
        self.set_animation_mode = widgets.Dropdown(
            options=(("Loop (>>)", ">>"), ("Once (>)", ">"), ("Bounce (<>)", "<>")),
            value=">>",
            description="",
            tooltip="Animation mode for this parameter.",
            **style_args,
        )
        configure_control(self.set_animation_mode, family="dropdown")
        self.set_animation_mode.add_class("smart-slider-settings-mode-input")

        self.btn_close_settings = widgets.Button(
            description="Close parameter settings",
            tooltip="Close parameter settings",
        )
        configure_icon_button(self.btn_close_settings, role="close", size_px=24)
        self.settings_title_text = widgets.HTML(
            "Parameter settings",
            layout=widgets.Layout(margin="0px", min_width="0"),
        )
        self.settings_title_text.add_class("gu-modal-title-text")
        self.settings_title_text.add_class("smart-slider-settings-title-text")
        settings_subject_value = _normalize_title_subject(description)
        self.settings_subject = widgets.HTMLMath(
            settings_subject_value,
            layout=widgets.Layout(
                display=("block" if settings_subject_value else "none"),
                width="auto",
                min_width="0",
                margin="0px",
            ),
        )
        self.settings_subject.add_class("smart-slider-settings-subject")
        settings_header = build_dialog_header(
            self.settings_title_text,
            self.btn_close_settings,
            chip_widget=self.settings_subject,
        )

        self.btn_done_settings = widgets.Button(
            description="Done",
            tooltip="Close parameter settings",
        )
        configure_action_button(self.btn_done_settings, variant="primary", min_width_px=84)
        self.btn_done_settings.on_click(lambda _button: self.close_settings())

        self._settings_step_field = labelled_field(
            "Step",
            self.set_step,
            flex="1 1 180px",
            max_width="220px",
            extra_classes=("smart-slider-settings-field", "smart-slider-settings-step-field"),
        )
        self._settings_step_row = responsive_row(
            [self._settings_step_field],
            gap="12px",
            extra_classes=("smart-slider-settings-row", "smart-slider-settings-step-row"),
        )
        self._settings_live_field = build_boolean_field(
            self.set_live,
            width="auto",
            max_width="100%",
            extra_classes=("smart-slider-settings-live-field",),
        )
        self._settings_live_row = responsive_row(
            [self._settings_live_field],
            gap="12px",
            extra_classes=("smart-slider-settings-row", "smart-slider-settings-live-row"),
        )
        self._settings_animation_time_field = labelled_field(
            "Period (s)",
            self.set_animation_time,
            flex="1 1 180px",
            max_width="220px",
            extra_classes=(
                "smart-slider-settings-field",
                "smart-slider-settings-period-field",
            ),
        )
        self._settings_animation_mode_field = labelled_field(
            "Mode",
            self.set_animation_mode,
            flex="1 1 200px",
            max_width="260px",
            extra_classes=(
                "smart-slider-settings-field",
                "smart-slider-settings-mode-field",
            ),
        )
        self._settings_animation_row = responsive_row(
            [self._settings_animation_time_field, self._settings_animation_mode_field],
            gap="12px",
            extra_classes=("smart-slider-settings-row", "smart-slider-settings-animation-row"),
        )
        self._settings_animation_section = build_form_section(
            "Animation",
            [self._settings_animation_row],
            extra_classes=("smart-slider-settings-animation-section",),
        )

        self._settings_accessibility = _SliderModalAccessibilityBridge(
            slider_root_class=self._slider_root_class,
            modal_class=self._settings_modal_class,
            dialog_open=False,
            dialog_label=f"Parameter settings for {self._accessible_label}",
            control_label=self._accessible_label,
            layout=widgets.Layout(width="0px", height="0px", margin="0px"),
        )
        self._settings_accessibility.on_msg(self._handle_settings_accessibility_message)

        settings_actions = build_action_bar([self.btn_done_settings])
        self.settings_panel = build_modal_panel(
            [
                settings_header,
                self._settings_step_row,
                self._settings_live_row,
                self._settings_animation_section,
                settings_actions,
            ],
            width="min(460px, calc(100vw - 32px))",
            min_width="min(320px, calc(100vw - 32px))",
            max_width="calc(100vw - 32px)",
            display="none",
            extra_classes=(),
        )
        self.settings_modal = build_modal_overlay(
            self.settings_panel,
            hosted=False,
            z_index="1000",
            background_color="rgba(15, 23, 42, 0.12)",
        )
        self.settings_modal.add_class(self._settings_modal_class)
        self._top_row: widgets.HBox | None = None
        self._modal_host: widgets.Box | None = None

        # --- Layout -----------------------------------------------------------
        top_row = widgets.HBox(
            [
                self._theme_style,
                self._limit_style,
                self.description_label,
                self.set_min,
                self.slider,
                self.set_max,
                self.number,
                self.btn_animate,
                self.btn_reset,
                self.btn_settings,
            ],
            layout=widgets.Layout(width="100%", min_width="0", align_items="center"),
        )
        top_row.add_class("smart-slider-top-row")
        self._top_row = top_row
        super().__init__(
            [top_row, self._settings_accessibility, self.settings_modal],
            layout=root_layout,
            **kwargs,
        )
        self.add_class("smart-slider-root")
        self.add_class(self._slider_root_class)

        # --- Wiring -----------------------------------------------------------
        # Keep self.value and slider.value in sync
        traitlets.link((self, "value"), (self.slider, "value"))

        # Slider -> Text (display)
        self.slider.observe(self._sync_number_from_slider, names="value")
        self.slider.observe(self._sync_limit_texts, names=["min", "max"])
        # Text -> Slider (parse + clamp)
        self.number.observe(self._commit_text_value, names="value")
        self.set_min.observe(self._commit_min_value, names="value")
        self.set_max.observe(self._commit_max_value, names="value")

        # Buttons
        self.btn_animate.on_click(self._toggle_animation)
        self.btn_reset.on_click(self._reset)
        self.btn_settings.on_click(self._toggle_settings)
        self.btn_close_settings.on_click(self._close_settings)

        # Settings -> slider traits
        widgets.link((self.set_step, "value"), (self.slider, "step"))
        widgets.link((self.set_live, "value"), (self.slider, "continuous_update"))

        # Initialize trait (and normalize displayed text)
        self.value = value
        self._sync_number_text(self.value)
        self._sync_limit_texts(None)

        self._animation = AnimationController(
            self,
            animation_time=float(self.set_animation_time.value),
            animation_mode=str(self.set_animation_mode.value),
            state_change_callback=self._sync_animation_button,
        )
        self.observe(self._handle_animation_value_change, names="value")
        self.slider.observe(
            self._handle_animation_domain_change,
            names=["min", "max", "step"],
        )
        self.set_animation_time.observe(self._commit_animation_time, names="value")
        self.set_animation_mode.observe(self._commit_animation_mode, names="value")
        self._sync_animation_button(self._animation.running)

    # --- Helpers --------------------------------------------------------------

    @staticmethod
    def _set_class_state(widget: Any, class_name: str, enabled: bool) -> None:
        """Add or remove a CSS class when the widget supports class helpers."""
        add_class = getattr(widget, "add_class", None)
        remove_class = getattr(widget, "remove_class", None)
        if enabled:
            if callable(add_class):
                add_class(class_name)
            return
        if callable(remove_class):
            remove_class(class_name)

    def _handle_settings_accessibility_message(
        self, _widget: Any, content: Any, _buffers: Any
    ) -> None:
        """Handle frontend accessibility requests such as Escape-to-close."""

        if not isinstance(content, dict):
            return
        if content.get("type") != "dialog_request":
            return
        if content.get("action") != "close":
            return
        self.close_settings()

    def _set_settings_open(self, is_open: bool) -> None:
        """Apply settings-dialog visibility and synchronized button state."""

        self._settings_open = bool(is_open)
        self.settings_modal.layout.display = "flex" if self._settings_open else "none"
        self.settings_panel.layout.display = "flex" if self._settings_open else "none"
        self._settings_accessibility.dialog_open = self._settings_open
        next_description = (
            "Close parameter settings"
            if self._settings_open
            else "Open parameter settings"
        )
        self.btn_settings.description = next_description
        self.btn_settings.tooltip = next_description

    def open_settings(self) -> None:
        """Open the parameter settings dialog.
        
        Full API
        --------
        ``obj.open_settings() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.open_settings(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """

        self._set_settings_open(True)

    def close_settings(self) -> None:
        """Close the parameter settings dialog.
        
        Full API
        --------
        ``obj.close_settings() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.close_settings(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """

        self._set_settings_open(False)

    def _sync_number_text(self, val: float) -> None:
        """Set the text field from a numeric value without triggering parse logic.

        Parameters
        ----------
        val : float
            The numeric value to format and display in the text field.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._syncing = True
        try:
            self.number.value = f"{val:.4g}"
        finally:
            self._syncing = False

    def _sync_number_from_slider(self, change: Any) -> None:
        """Update the numeric field when the slider moves.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object that contains the new slider value.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        if self._syncing:
            return
        self._sync_number_text(change.new)

    def _sync_limit_texts(self, change: Any) -> None:
        """Refresh min/max limit text fields from the slider limits.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch or None
            Traitlets change object (unused) or ``None`` when called manually.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        if self._syncing:
            return
        self._syncing = True
        try:
            self.set_min.value = f"{self.slider.min:.4g}"
            self.set_max.value = f"{self.slider.max:.4g}"
        finally:
            self._syncing = False

    def _commit_limit_value(self, change: Any, *, limit: str) -> None:
        """Parse and apply min/max limits from text inputs.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.
        limit : {"min", "max"}
            Selects which limit to update.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        if self._syncing:
            return
        raw = (change.new or "").strip()
        old_min = float(self.slider.min)
        old_max = float(self.slider.max)

        try:
            new_val = float(InputConvert(raw, dest_type=float, truncate=True))
            if limit == "min":
                new_min = min(new_val, old_max)
                self.slider.min = new_min
            else:
                new_max = max(new_val, old_min)
                self.slider.max = new_max
            self._sync_limit_texts(None)
        except (ValueError, TypeError, SyntaxError):
            self._syncing = True
            try:
                self.set_min.value = f"{old_min:.4g}"
                self.set_max.value = f"{old_max:.4g}"
            finally:
                self._syncing = False

    def _commit_min_value(self, change: Any) -> None:
        """Commit the minimum limit from the min text field.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._commit_limit_value(change, limit="min")

    def _commit_max_value(self, change: Any) -> None:
        """Commit the maximum limit from the max text field.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._commit_limit_value(change, limit="max")

    def _commit_text_value(self, change: Any) -> None:
        """
        Commit text input to the slider when the user finishes editing.

        When the user commits text (Enter / blur):
          - parse via InputConvert,
          - clamp to [min, max],
          - update self.value,
          - normalize the displayed text.

        On any error, revert to the value *before* this edit.

        Parameters
        ----------
        change : traitlets.utils.bunch.Bunch
            Traitlets change object carrying the new text value.

        Returns
        -------
        None
            This method updates widget state in place.

        Examples
        --------
        Update the value by simulating a commit::

            >>> slider = FloatSlider(value=0.0, min=0.0, max=1.0)
            >>> slider.number.value = "0.5"
            >>> float(slider.value)
            0.5
        """
        if self._syncing:
            return

        raw = (change.new or "").strip()
        old_val = float(self.value)

        try:
            new_val = InputConvert(raw, dest_type=float, truncate=True)
            new_val = max(self.slider.min, min(float(new_val), self.slider.max))
            self.value = new_val
            self._sync_number_text(self.value)  # normalize formatting
        except (ValueError, TypeError, SyntaxError):
            # Revert to the value before the edit
            self._sync_number_text(old_val)

    # --- Button handlers ------------------------------------------------------

    def _reset(self, _: Any) -> None:
        """Reset the slider value to its initial default.

        Parameters
        ----------
        _ : object
            Click event payload (unused).

        Returns
        -------
        None
            This method updates the value in place (limits are unchanged).

        Notes
        -----
        Public callers should prefer :meth:`reset`.
        """
        self.value = self._defaults[
            "value"
        ]  # slider sync + slider observer updates text

    def _toggle_animation(self, _: Any) -> None:
        """Toggle animation from the small play/pause button."""
        self.toggle_animation()

    def _sync_animation_mode_button_classes(self) -> None:
        """Apply the idle-mode glyph class used by the animation button."""
        current_mode = str(self._animation.animation_mode)
        for mode, class_name in _ANIMATION_MODE_BUTTON_CLASSES.items():
            self._set_class_state(self.btn_animate, class_name, mode == current_mode)

    def _sync_animation_button(self, running: bool) -> None:
        """Refresh the animation button state from the controller."""
        self.btn_animate.description = (
            "Pause animation" if running else "Start animation"
        )
        self.btn_animate.tooltip = (
            "Pause animation" if running else "Start animation"
        )
        self.btn_animate.button_style = ""
        self._sync_animation_mode_button_classes()
        self._set_class_state(self.btn_animate, "mod-running", running)

    def _handle_animation_value_change(self, change: Any) -> None:
        """Forward external value changes to the animation controller."""
        self._animation.handle_value_change(float(change.new))

    def _handle_animation_domain_change(self, change: Any) -> None:
        """Forward range/step edits to the animation controller."""
        self._animation.handle_domain_change()

    def _commit_animation_time(self, change: Any) -> None:
        """Commit the animation duration from the settings panel."""
        if self._syncing_animation_settings:
            return
        self._animation.animation_time = float(change.new)

    def _commit_animation_mode(self, change: Any) -> None:
        """Commit the animation mode from the settings panel."""
        if self._syncing_animation_settings:
            return
        self._animation.animation_mode = str(change.new)
        self._sync_animation_button(self._animation.running)

    @property
    def default_value(self) -> float:
        """Return the stored default value used by reset.
        
        Full API
        --------
        ``obj.default_value -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.default_value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return float(self._defaults["value"])

    @default_value.setter
    def default_value(self, value: float) -> None:
        """Set the stored default value used by reset.
        
        Full API
        --------
        ``obj.default_value = value``
        
        Parameters
        ----------
        value : float
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.default_value = value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        self._defaults["value"] = float(value)

    @property
    def min(self) -> float:
        """Return the current minimum slider limit.
        
        Full API
        --------
        ``obj.min -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.min
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return float(self.slider.min)

    @min.setter
    def min(self, value: float) -> None:
        """Set the minimum slider limit.
        
        Full API
        --------
        ``obj.min = value``
        
        Parameters
        ----------
        value : float
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.min = value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        new_min = float(value)
        if new_min > float(self.slider.max):
            self.slider.max = new_min
        self.slider.min = new_min
        self._sync_limit_texts(None)

    @property
    def max(self) -> float:
        """Return the current maximum slider limit.
        
        Full API
        --------
        ``obj.max -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.max
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return float(self.slider.max)

    @max.setter
    def max(self, value: float) -> None:
        """Set the maximum slider limit.
        
        Full API
        --------
        ``obj.max = value``
        
        Parameters
        ----------
        value : float
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.max = value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        new_max = float(value)
        if new_max < float(self.slider.min):
            self.slider.min = new_max
        self.slider.max = new_max
        self._sync_limit_texts(None)

    @property
    def step(self) -> float:
        """Return the current slider step.
        
        Full API
        --------
        ``obj.step -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.step
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return float(self.slider.step)

    @step.setter
    def step(self, value: float) -> None:
        """Set the slider step size.
        
        Full API
        --------
        ``obj.step = value``
        
        Parameters
        ----------
        value : float
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.step = value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        self.slider.step = float(value)

    def reset(self) -> None:
        """Reset the slider value to its initial default.
        
        Full API
        --------
        ``obj.reset() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.reset(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        self._reset(None)

    @property
    def animation_time(self) -> float:
        """Seconds needed to traverse the current numeric range once.
        
        Full API
        --------
        ``obj.animation_time -> float``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        float
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.animation_time
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return float(self._animation.animation_time)

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Work with animation time on ``FloatSlider``.
        
        Full API
        --------
        ``obj.animation_time = value``
        
        Parameters
        ----------
        value : float
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.animation_time = value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """

        self._animation.animation_time = float(value)
        self._syncing_animation_settings = True
        try:
            self.set_animation_time.value = float(self._animation.animation_time)
        finally:
            self._syncing_animation_settings = False

    @property
    def animation_mode(self) -> str:
        """Animation mode token for this slider.
        
        Full API
        --------
        ``obj.animation_mode -> str``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        str
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.animation_mode
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return str(self._animation.animation_mode)

    @animation_mode.setter
    def animation_mode(self, value: str) -> None:
        """Work with animation mode on ``FloatSlider``.
        
        Full API
        --------
        ``obj.animation_mode = value``
        
        Parameters
        ----------
        value : str
            New or current value for the relevant property, control, or calculation. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.animation_mode = value
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """

        self._animation.animation_mode = str(value)
        self._syncing_animation_settings = True
        try:
            self.set_animation_mode.value = str(self._animation.animation_mode)
        finally:
            self._syncing_animation_settings = False
        self._sync_animation_button(self._animation.running)

    @property
    def animation_running(self) -> bool:
        """Whether the slider is currently animating.
        
        Full API
        --------
        ``obj.animation_running -> bool``
        
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
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            current = obj.animation_running
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        return bool(self._animation.running)

    def start_animation(self) -> None:
        """Start animating the slider value.
        
        Full API
        --------
        ``obj.start_animation() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.start_animation(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        self._animation.start()

    def stop_animation(self) -> None:
        """Stop animating the slider value.
        
        Full API
        --------
        ``obj.stop_animation() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.stop_animation(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        self._animation.stop()

    def toggle_animation(self) -> None:
        """Toggle the slider animation state.
        
        Full API
        --------
        ``obj.toggle_animation() -> None``
        
        Parameters
        ----------
        None. This API does not declare user-supplied parameters beyond implicit object context.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.toggle_animation(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        self._animation.toggle()

    def make_refs(self, symbols: Sequence[Any]) -> dict[Any, Any]:
        """Create ParamRef mappings for provided symbols.
        
        Full API
        --------
        ``obj.make_refs(symbols: Sequence[Any]) -> dict[Any, Any]``
        
        Parameters
        ----------
        symbols : Sequence[Any]
            Parameter symbols, names, or other accepted parameter keys. Required.
        
        Returns
        -------
        dict[Any, Any]
            Result produced by this API.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            result = obj.make_refs(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        if len(symbols) != 1:
            raise ValueError("FloatSlider only supports a single symbol.")
        from .ParamRef import ProxyParamRef

        symbol = symbols[0]
        return {symbol: ProxyParamRef(symbol, self)}

    def set_modal_host(self, host: widgets.Box | None) -> None:
        """Attach the settings modal to a host container.
        
        Full API
        --------
        ``obj.set_modal_host(host: widgets.Box | None) -> None``
        
        Parameters
        ----------
        host : widgets.Box | None
            Value for ``host`` in this API. Required.
        
        Returns
        -------
        None
            This call is used for side effects and does not return a value.
        
        Optional arguments
        ------------------
        This API does not declare optional arguments in its Python signature.
        
        Architecture note
        -----------------
        This member belongs to ``FloatSlider``. Parameter behavior is name-authoritative and flows through ParamRef/ParameterManager abstractions so widgets, hooks, and animation all stay synchronized. Use it through the owning object rather than bypassing the surrounding figure/runtime machinery.
        
        Examples
        --------
        Basic use::
        
            obj = FloatSlider(...)
            obj.set_modal_host(...)
        
        Discovery-oriented use::
        
            help(FloatSlider)
            # then follow the guide/test links listed below
        
        Learn more / explore
        --------------------
        - Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
        - Guide: ``docs/guides/parameter-key-semantics.md``.
        - Guide: ``docs/guides/parameter-animation.md``.
        - Runtime discovery tip: inspect ``fig.parameters``, ``ParamRef.capabilities``, and the slider/animation helpers together to understand the live parameter model.
        - In a notebook or REPL, run ``help(FloatSlider)`` and ``dir(FloatSlider)`` to inspect adjacent members.
        """
        if host is self._modal_host:
            return

        if self._modal_host is not None:
            self._modal_host.children = tuple(
                child
                for child in self._modal_host.children
                if child is not self.settings_modal
            )

        modal_add_class = getattr(self.settings_modal, "add_class", None)
        modal_remove_class = getattr(self.settings_modal, "remove_class", None)

        top_row = cast(widgets.HBox, self._top_row)

        if host is None:
            current_children = cast(tuple[Any, ...], self.children)
            if self.settings_modal not in current_children:
                cast(Any, self).children = (
                    top_row,
                    self._settings_accessibility,
                    self.settings_modal,
                )
            if callable(modal_remove_class):
                modal_remove_class("smart-slider-settings-modal-hosted")
                modal_remove_class("gu-modal-overlay-hosted")
            if callable(modal_add_class):
                modal_add_class("smart-slider-settings-modal-global")
                modal_add_class("gu-modal-overlay-global")
        else:
            cast(Any, self).children = (top_row, self._settings_accessibility)
            attach_host_children(host, self.settings_modal)
            if callable(modal_remove_class):
                modal_remove_class("smart-slider-settings-modal-global")
                modal_remove_class("gu-modal-overlay-global")
            if callable(modal_add_class):
                modal_add_class("smart-slider-settings-modal-hosted")
                modal_add_class("gu-modal-overlay-hosted")

        self._sync_theme_style_widget(host)
        self._modal_host = host

    @staticmethod
    def _widget_has_class(widget: widgets.Widget | None, class_name: str) -> bool:
        classes = getattr(widget, "_dom_classes", ()) or ()
        return class_name in classes

    def _sync_theme_style_widget(self, host: widgets.Box | None) -> None:
        include_base = host is None or not self._widget_has_class(host, "gu-theme-root")
        self._theme_style.value = style_widget_value(include_base=include_base)

    def _close_settings(self, _: Any) -> None:
        """Close the settings dialog from explicit UI actions."""

        self.close_settings()

    def _toggle_settings(self, _: Any) -> None:
        """Toggle visibility of the settings panel.

        Parameters
        ----------
        _ : object
            Click event payload (unused).

        Returns
        -------
        None
            This method updates widget state in place.
        """
        self._set_settings_open(not self._settings_open)
