"""Custom slider widget used by SmartFigure parameters.

Provides a synchronized slider/text control with advanced settings (min/max/
step/default) and helper APIs for parameter-reference integration.
"""

import ipywidgets as widgets
import traitlets

from .InputConvert import InputConvert


class SmartFloatSlider(widgets.VBox):
    """
    A FloatSlider with:
      - a *single editable numeric field* (Text) that accepts expressions via InputConvert,
      - reset + settings buttons,
      - a small settings panel (min/max/step + live update toggle).

    Design notes
    ------------
    - The slider's built-in readout is disabled, so there is only one number field.
    - The Text field commits on Enter (continuous_update=False). This avoids fighting the
      user while they type partial expressions like "pi/2".
    - If parsing fails, the Text field reverts to the previous committed value.

    Notes
    -----
    The slider exposes ``default_value``, ``min``, ``max``, and ``step`` so it
    can be wrapped by :class:`ParamRef` implementations and used with
    :class:`SmartFigure` parameter management.

    Examples
    --------
    >>> slider = SmartFloatSlider(value=1.0, min=-2.0, max=2.0, step=0.1)  # doctest: +SKIP
    >>> slider.value  # doctest: +SKIP
    1.0
    """

    value = traitlets.Float(0.0)

    def __init__(
        self,
        value=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        description="Value:",
        **kwargs,
    ):
        """Create a slider with a single editable numeric field and settings panel.

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

            >>> slider = SmartFloatSlider(value=0.25, min=0.0, max=1.0, step=0.05)
            >>> float(slider.value)
            0.25

        Notes
        -----
        Use :meth:`make_refs` to bind the slider to a SymPy symbol when working
        with :class:`SmartFigure` or :class:`ParameterManager`.
        """
        # Remember defaults for reset
        self._defaults = {"value": value, "min": min, "max": max, "step": step}

        # Internal guard to prevent circular updates (slider -> text -> slider -> ...)
        self._syncing = False

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
            layout=widgets.Layout(width="50%"),
        )

        self.description_label = widgets.HTMLMath(
            value=description,
            layout=widgets.Layout(width="60px"),
        )

        #self._limit_style = widgets.HTML(
        #    "<style>"
        #    ".smart-slider-limit input{"
        #    "font-size:10px;"
        #    "color:#666;"
        #    "height:18px;"
        #    "border:none;"
        #    "box-shadow:none;"
        #    "background:transparent;"
        #    "padding:0px;"
        #   "text-align:center;"
        #    "}"
        #    "</style>"
        #)

        self._limit_style = widgets.HTML(r"""
<style>
/* ============================================================
   Min/Max look like small non-editable text until focus,
   but remain fully editable on click.
   Works without relying on a specific wrapper DOM.
   ============================================================ */

/* Shrink any wrapper(s) JupyterLab/ipywidgets might impose. */
.smart-slider-limit,
.smart-slider-limit * {
  min-height: 0 !important;
}

/* The actual editable element(s): handle both input + textarea. */
.smart-slider-limit :is(input, textarea) {
  /* Make it small */
  font-size: 10px !important;
  line-height: 1.1 !important;

  /* Force compact geometry despite JupyterLab theme defaults */
  height: 16px !important;
  min-height: 0 !important;
  padding: 0 2px !important;
  margin: 0 !important;

  /* Make it look like static text */
  background: transparent !important;
  border: 1px solid transparent !important;
  box-shadow: none !important;
  border-radius: 3px !important;

  color: var(--jp-ui-font-color2, #666) !important;
  text-align: center !important;
  box-sizing: border-box !important;
}

/* Optional: subtle “this is clickable” affordance on hover */
.smart-slider-limit :is(input, textarea):hover {
  border-bottom-color: rgba(0,0,0,0.20) !important;
}

/* On focus: show edit chrome so users realize they can type */
.smart-slider-limit :is(input, textarea):focus {
  outline: none !important;
  border-color: rgba(0,0,0,0.28) !important;
  background: rgba(0,0,0,0.04) !important;
}

/* Modal overlay and panel styling */
.smart-slider-settings-modal {
  z-index: 99999 !important;
}

.smart-slider-settings-modal-hosted {
  position: absolute !important;
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
}

.smart-slider-settings-modal-global {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
}

.smart-slider-modal-host {
  position: relative !important;
}

.smart-slider-settings-panel {
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.32) !important;
  border-radius: 10px !important;
  opacity: 1 !important;
  background: #ffffff !important;
}
</style>
""")
        # The *only* numeric field (editable; accepts expressions)
        self.number = widgets.Text(
            value=str(value),
            continuous_update=False,  # commit on Enter (and typically blur)
            layout=widgets.Layout(width="70px"),
        )

        self.btn_reset = widgets.Button(
            description="↺",
            tooltip="Reset",
            layout=widgets.Layout(width="22px", height="22px", padding="0px"),
        )
        self.btn_settings = widgets.Button(
            description="⚙",
            tooltip="Settings",
            layout=widgets.Layout(width="22px", height="22px", padding="0px"),
        )

        # --- Settings panel ---------------------------------------------------
        style_args = {
            "style": {"description_width": "36px"},
            "layout": widgets.Layout(width="170px"),
        }
        self.set_min = widgets.Text(
    value=f"{min:.4g}",
    continuous_update=False,
    layout=widgets.Layout(width="40px", height="16px"),
)
        self.set_min.add_class("smart-slider-limit")
        self.set_max = widgets.Text(
    value=f"{max:.4g}",
    continuous_update=False,
    layout=widgets.Layout(width="40px", height="16px"),
)
        self.set_max.add_class("smart-slider-limit")
        self.set_step = widgets.FloatText(value=step, description="Step:", **style_args)
        self.set_live = widgets.Checkbox(
            value=True,
            description="Live Update",
            indent=False,
            layout=widgets.Layout(width="120px"),
        )

        self.btn_close_settings = widgets.Button(
            description="✕",
            tooltip="Close settings",
            layout=widgets.Layout(width="24px", height="24px", padding="0px"),
        )
        self.settings_title = widgets.HBox(
            [
                widgets.HTML("<b>Slider settings:</b>"),
                widgets.HTMLMath(value=description),
            ],
            layout=widgets.Layout(align_items="center", gap="4px"),
        )
        settings_header = widgets.HBox(
            [self.settings_title, self.btn_close_settings],
            layout=widgets.Layout(justify_content="space-between", align_items="center"),
        )

        self.settings_panel = widgets.VBox(
            [settings_header, widgets.HBox([self.set_step]), widgets.HBox([self.set_live])],
            layout=widgets.Layout(
                width="230px",
                display="none",
                border="1px solid #ddd",
                padding="8px",
                gap="6px",
                background_color="white",
                opacity="1",
                box_shadow="0 10px 28px rgba(15, 23, 42, 0.28)",
            ),
        )
        self.settings_modal = widgets.Box(
            [self.settings_panel],
            layout=widgets.Layout(
                display="none",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                align_items="center",
                justify_content="center",
                background_color="transparent",
                z_index="1000",
            ),
        )
        self.settings_panel.add_class("smart-slider-settings-panel")
        self.settings_modal.add_class("smart-slider-settings-modal")
        self.settings_modal.add_class("smart-slider-settings-modal-global")
        self._top_row = None
        self._modal_host = None

        # --- Layout -----------------------------------------------------------
        top_row = widgets.HBox(
            [
                self._limit_style,
                self.description_label,
                self.set_min,
                self.slider,
                self.set_max,
                self.number,
                self.btn_reset,
                self.btn_settings,
            ],
            layout=widgets.Layout(align_items="center", gap="4px"),
        )
        self._top_row = top_row
        super().__init__([top_row, self.settings_modal], **kwargs)

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
        self.btn_reset.on_click(self._reset)
        self.btn_settings.on_click(self._toggle_settings)
        self.btn_close_settings.on_click(self._toggle_settings)

        # Settings -> slider traits
        widgets.link((self.set_step, "value"), (self.slider, "step"))
        widgets.link((self.set_live, "value"), (self.slider, "continuous_update"))

        # Initialize trait (and normalize displayed text)
        self.value = value
        self._sync_number_text(self.value)
        self._sync_limit_texts(None)

    # --- Helpers --------------------------------------------------------------

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

    def _sync_number_from_slider(self, change) -> None:
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

    def _sync_limit_texts(self, change) -> None:
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

    def _commit_limit_value(self, change, *, limit: str) -> None:
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

    def _commit_min_value(self, change) -> None:
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

    def _commit_max_value(self, change) -> None:
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

    def _commit_text_value(self, change) -> None:
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

            >>> slider = SmartFloatSlider(value=0.0, min=0.0, max=1.0)
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

    def _reset(self, _) -> None:
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
        self.value = self._defaults["value"]  # slider sync + slider observer updates text

    @property
    def default_value(self) -> float:
        """Return the stored default value used by reset.

        Returns
        -------
        float
            Default value for the slider reset.

        Notes
        -----
        Setting ``default_value`` does not change the current slider value.
        """
        return float(self._defaults["value"])

    @default_value.setter
    def default_value(self, value: float) -> None:
        """Set the stored default value used by reset.

        Parameters
        ----------
        value : float
            New default value (does not change the current value).

        Returns
        -------
        None

        See Also
        --------
        reset : Apply the stored default value to the slider.
        """
        self._defaults["value"] = float(value)

    @property
    def min(self) -> float:
        """Return the current minimum slider limit.

        Returns
        -------
        float
            Minimum slider value.

        Examples
        --------
        >>> slider = SmartFloatSlider(min=-1.0, max=1.0)  # doctest: +SKIP
        >>> slider.min  # doctest: +SKIP
        -1.0

        Notes
        -----
        Updating the minimum may clamp the current value if it falls below the
        new bound.
        """
        return float(self.slider.min)

    @min.setter
    def min(self, value: float) -> None:
        """Set the minimum slider limit.

        Parameters
        ----------
        value : float
            New minimum value.

        Returns
        -------
        None

        See Also
        --------
        max : Update the upper bound.
        """
        new_min = float(value)
        if new_min > float(self.slider.max):
            self.slider.max = new_min
        self.slider.min = new_min
        self._sync_limit_texts(None)

    @property
    def max(self) -> float:
        """Return the current maximum slider limit.

        Returns
        -------
        float
            Maximum slider value.

        Examples
        --------
        >>> slider = SmartFloatSlider(min=-1.0, max=1.0)  # doctest: +SKIP
        >>> slider.max  # doctest: +SKIP
        1.0

        Notes
        -----
        Updating the maximum may clamp the current value if it exceeds the
        new bound.
        """
        return float(self.slider.max)

    @max.setter
    def max(self, value: float) -> None:
        """Set the maximum slider limit.

        Parameters
        ----------
        value : float
            New maximum value.

        Returns
        -------
        None

        See Also
        --------
        min : Update the lower bound.
        """
        new_max = float(value)
        if new_max < float(self.slider.min):
            self.slider.min = new_max
        self.slider.max = new_max
        self._sync_limit_texts(None)

    @property
    def step(self) -> float:
        """Return the current slider step.

        Returns
        -------
        float
            Step size for the slider.

        Examples
        --------
        >>> slider = SmartFloatSlider(step=0.25)  # doctest: +SKIP
        >>> slider.step  # doctest: +SKIP
        0.25

        Notes
        -----
        The step size affects both the slider and the settings panel control.
        """
        return float(self.slider.step)

    @step.setter
    def step(self, value: float) -> None:
        """Set the slider step size.

        Parameters
        ----------
        value : float
            New step size.

        Returns
        -------
        None

        See Also
        --------
        default_value : Set the reset target without changing the current value.
        """
        self.slider.step = float(value)

    def reset(self) -> None:
        """Reset the slider value to its initial default.

        Returns
        -------
        None

        Examples
        --------
        >>> slider = SmartFloatSlider(value=2.0)  # doctest: +SKIP
        >>> slider.reset()  # doctest: +SKIP

        Notes
        -----
        This uses the stored ``default_value``.
        """
        self._reset(None)

    def make_refs(self, symbols):
        """Create ParamRef mappings for provided symbols.

        Parameters
        ----------
        symbols : sequence[sympy.Symbol]
            Symbols to bind to this control (must contain exactly one symbol).

        Returns
        -------
        dict
            Mapping of the symbol to a ``ProxyParamRef``.

        Raises
        ------
        ValueError
            If more than one symbol is provided.

        Examples
        --------
        >>> slider = SmartFloatSlider()  # doctest: +SKIP
        >>> import sympy as sp  # doctest: +SKIP
        >>> a = sp.symbols("a")  # doctest: +SKIP
        >>> slider.make_refs([a])  # doctest: +SKIP

        Notes
        -----
        This method exists to integrate with :class:`ParameterManager` and
        :class:`SmartFigure` parameter creation.
        """
        if len(symbols) != 1:
            raise ValueError("SmartFloatSlider only supports a single symbol.")
        from .ParamRef import ProxyParamRef
        symbol = symbols[0]
        return {symbol: ProxyParamRef(symbol, self)}

    def set_modal_host(self, host) -> None:
        """Attach the settings modal to a host container.

        Parameters
        ----------
        host : ipywidgets.Box or None
            Host container to overlay. If ``None``, the modal stays local to the slider.

        Returns
        -------
        None
            Updates widget parenting/layout in place.
        """
        if host is self._modal_host:
            return

        if self._modal_host is not None:
            self._modal_host.children = tuple(
                child for child in self._modal_host.children if child is not self.settings_modal
            )

        modal_add_class = getattr(self.settings_modal, "add_class", None)
        modal_remove_class = getattr(self.settings_modal, "remove_class", None)

        if host is None:
            if self.settings_modal not in self.children:
                self.children = (self._top_row, self.settings_modal)
            if callable(modal_remove_class):
                modal_remove_class("smart-slider-settings-modal-hosted")
            if callable(modal_add_class):
                modal_add_class("smart-slider-settings-modal-global")
        else:
            self.children = (self._top_row,)
            add_class = getattr(host, "add_class", None)
            if callable(add_class):
                add_class("smart-slider-modal-host")
            if self.settings_modal not in host.children:
                host.children += (self.settings_modal,)
            if callable(modal_remove_class):
                modal_remove_class("smart-slider-settings-modal-global")
            if callable(modal_add_class):
                modal_add_class("smart-slider-settings-modal-hosted")

        self._modal_host = host

    def _toggle_settings(self, _) -> None:
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
        is_open = self.settings_modal.layout.display == "flex"
        self.settings_modal.layout.display = "none" if is_open else "flex"
        self.settings_panel.layout.display = "none" if is_open else "flex"
