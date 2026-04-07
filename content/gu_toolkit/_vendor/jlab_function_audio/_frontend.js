/**
 * Hidden front-end helper for jlab-function-audio.
 *
 * Python owns transport and chunk generation. The browser owns the actual sound
 * output. The widget intentionally renders nothing visible. Instead it installs
 * document-level gesture listeners so the first ordinary notebook interaction
 * (for example clicking Play or dragging a slider) can unlock browser audio
 * without a dedicated enable button.
 */

/**
 * Convert a potentially invalid numeric value into a finite number.
 *
 * @param {number} value - Candidate numeric value.
 * @param {number} fallback - Value returned when `value` is not finite.
 * @returns {number} Safe finite number.
 */
function safeNumber(value, fallback = 0) {
  return Number.isFinite(value) ? Number(value) : Number(fallback);
}

/**
 * Convert an arbitrary error-like object into a readable string.
 *
 * @param {unknown} error - Browser-side exception value.
 * @returns {string} Human-readable message.
 */
function stringifyError(error) {
  if (error instanceof Error) {
    return `${error.name}: ${error.message}`;
  }
  return String(error);
}

/**
 * Create the shared model-level state object.
 *
 * @param {import("@jupyter-widgets/base").DOMWidgetModel} model - Widget model.
 * @returns {object} Mutable shared state for all views of the widget model.
 */
function createState(model) {
  return {
    model,
    ctx: null,
    masterGain: null,
    desiredGain: safeNumber(model.get("gain"), 0.18),
    scheduledUntil: 0,
    nodes: [],
    playing: false,
    unlocked: false,
    views: new Set(),
    bindingsReady: false,
    bootMode: "unknown",
    onCustomMessage: null,
    onRelevantTraitChange: null,
    unlockListenersInstalled: false,
    unlockListener: null,
    unlockAttemptInFlight: false,
    commOpen: true,
    modelDestroyed: false,
    detachMessageSent: false,
    lastStatsSentAtMs: 0,
    lastStatsSignature: "",
    onCommClose: null,
    onModelDestroy: null,
    onCommLiveUpdate: null,
  };
}

/**
 * Return the shared state object, creating it lazily when required.
 *
 * @param {import("@jupyter-widgets/base").DOMWidgetModel} model - Widget model.
 * @returns {object} Shared mutable state used by both lifecycle hooks.
 */
function ensureState(model) {
  if (!model._jfa_state) {
    model._jfa_state = createState(model);
    return model._jfa_state;
  }

  const state = model._jfa_state;
  state.model = model;
  if (!(state.views instanceof Set)) {
    state.views = new Set();
  }
  if (!Array.isArray(state.nodes)) {
    state.nodes = [];
  }
  if (!("ctx" in state)) {
    state.ctx = null;
  }
  if (!("masterGain" in state)) {
    state.masterGain = null;
  }
  if (!("desiredGain" in state)) {
    state.desiredGain = safeNumber(model.get("gain"), 0.18);
  }
  if (!("scheduledUntil" in state)) {
    state.scheduledUntil = 0;
  }
  if (!("playing" in state)) {
    state.playing = false;
  }
  if (!("unlocked" in state)) {
    state.unlocked = false;
  }
  if (!("bindingsReady" in state)) {
    state.bindingsReady = false;
  }
  if (!("bootMode" in state)) {
    state.bootMode = "unknown";
  }
  if (!("onCustomMessage" in state)) {
    state.onCustomMessage = null;
  }
  if (!("onRelevantTraitChange" in state)) {
    state.onRelevantTraitChange = null;
  }
  if (!("unlockListenersInstalled" in state)) {
    state.unlockListenersInstalled = false;
  }
  if (!("unlockListener" in state)) {
    state.unlockListener = null;
  }
  if (!("unlockAttemptInFlight" in state)) {
    state.unlockAttemptInFlight = false;
  }
  if (!("commOpen" in state)) {
    state.commOpen = true;
  }
  if (!("modelDestroyed" in state)) {
    state.modelDestroyed = false;
  }
  if (!("detachMessageSent" in state)) {
    state.detachMessageSent = false;
  }
  if (!("lastStatsSentAtMs" in state)) {
    state.lastStatsSentAtMs = 0;
  }
  if (!("lastStatsSignature" in state)) {
    state.lastStatsSignature = "";
  }
  if (!("onCommClose" in state)) {
    state.onCommClose = null;
  }
  if (!("onModelDestroy" in state)) {
    state.onModelDestroy = null;
  }
  if (!("onCommLiveUpdate" in state)) {
    state.onCommLiveUpdate = null;
  }
  return state;
}

/**
 * Update the hidden DOM nodes with the latest state for debugging purposes.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function updateViews(state) {
  const browserState = state.unlocked ? "audio-enabled" : "waiting-for-browser-gesture";
  const audioContextState = state.ctx ? state.ctx.state : "not-created";

  for (const view of state.views) {
    if (!view || !view.root) {
      continue;
    }
    view.root.dataset.playbackState = String(state.model.get("playback_state") || "");
    view.root.dataset.browserState = browserState;
    view.root.dataset.currentFunction = String(state.model.get("current_function_name") || "");
    view.root.dataset.audioContextState = audioContextState;
  }
}

/**
 * Return whether the widget currently has at least one rendered view.
 *
 * @param {object} state - Shared widget state.
 * @returns {boolean} Whether at least one view is attached.
 */
function hasActiveViews(state) {
  return state.views instanceof Set && state.views.size > 0;
}

/**
 * Return whether the shared AudioContext is still usable.
 *
 * @param {object} state - Shared widget state.
 * @returns {boolean} Whether the current graph can schedule audio.
 */
function hasUsableAudioGraph(state) {
  return Boolean(state.ctx && state.masterGain && state.ctx.state !== "closed");
}

/**
 * Return whether the page currently has transient user activation.
 *
 * @returns {boolean} Whether autoplay-sensitive work may run now.
 */
function hasTransientUserActivation() {
  try {
    return Boolean(globalThis.navigator?.userActivation?.isActive);
  } catch (error) {
    void error;
    return false;
  }
}

/**
 * Return a monotonic-ish timestamp in milliseconds.
 *
 * @returns {number} Current time in milliseconds.
 */
function nowMs() {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }
  return Date.now();
}

/**
 * Best-effort check for whether the widget model may still send custom messages.
 *
 * @param {object} state - Shared widget state.
 * @returns {boolean} Whether outbound comm traffic should be attempted.
 */
function canSendToPython(state) {
  if (state.modelDestroyed || !state.commOpen) {
    return false;
  }

  const model = state.model;
  if (!model || typeof model.send !== "function") {
    return false;
  }

  if ("comm" in model && model.comm === undefined) {
    return false;
  }
  if ("comm_live" in model && model.comm_live === false) {
    return false;
  }
  if ("_closed" in model && model._closed === true) {
    return false;
  }

  return true;
}

/**
 * Remember that outbound comm traffic is no longer available and stop active runtime work.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function markCommUnavailable(state) {
  state.commOpen = false;
  state.detachMessageSent = true;
  state.playing = false;
  state.unlocked = false;
  state.unlockAttemptInFlight = false;
  state.lastStatsSentAtMs = 0;
  state.lastStatsSignature = "";
  removeAutoUnlockListeners(state);
  cleanupAudioResources(state);
  updateViews(state);
}

/**
 * Safely send a custom message to Python without letting comm shutdown leak into the console.
 *
 * @param {object} state - Shared widget state.
 * @param {object} content - JSON payload.
 * @returns {boolean} Whether the message was accepted for sending.
 */
function safeModelSend(state, content) {
  if (!canSendToPython(state)) {
    return false;
  }

  try {
    state.model.send(content);
    return true;
  } catch (error) {
    void error;
    markCommUnavailable(state);
    return false;
  }
}

/**
 * Attach a best-effort model lifecycle listener when the host provides one.
 *
 * @param {object} model - Widget model.
 * @param {string} eventName - Event name to subscribe to.
 * @param {Function | null} callback - Event callback.
 * @returns {void}
 */
function bindOptionalModelEvent(model, eventName, callback) {
  if (!callback || !model || typeof model.on !== "function") {
    return;
  }
  try {
    model.on(eventName, callback);
  } catch (error) {
    void error;
  }
}

/**
 * Remove a best-effort model lifecycle listener.
 *
 * @param {object} model - Widget model.
 * @param {string} eventName - Event name to unsubscribe from.
 * @param {Function | null} callback - Event callback.
 * @returns {void}
 */
function unbindOptionalModelEvent(model, eventName, callback) {
  if (!callback || !model || typeof model.off !== "function") {
    return;
  }
  try {
    model.off(eventName, callback);
  } catch (error) {
    void error;
  }
}

/**
 * Remove global auto-unlock listeners when they are no longer needed.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function removeAutoUnlockListeners(state) {
  if (!state.unlockListenersInstalled || !state.unlockListener) {
    return;
  }

  for (const eventName of ["pointerdown", "mousedown", "touchstart", "keydown"]) {
    document.removeEventListener(eventName, state.unlockListener, true);
  }

  state.unlockListenersInstalled = false;
  state.unlockListener = null;
}

/**
 * Mark the browser audio context as unlocked and notify Python once.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function markAudioUnlocked(state) {
  const firstUnlock = !state.unlocked;
  state.unlocked = true;
  removeAutoUnlockListeners(state);

  if (firstUnlock) {
    safeModelSend(state, { type: "audio-unlocked" });
  }

  if (state.playing && state.ctx) {
    state.scheduledUntil = Math.max(state.scheduledUntil, state.ctx.currentTime + 0.02);
    rampMasterGain(
      state,
      state.desiredGain,
      safeNumber(state.model.get("attack_duration"), 0.01),
    );
  }

  updateViews(state);
  sendStats(state, { force: true });
}

/**
 * Ensure that the shared AudioContext and GainNode exist.
 *
 * @param {object} state - Shared widget state.
 * @returns {object} The same state object for convenience.
 * @throws {Error} Raised when the browser does not support the Web Audio API.
 */
function ensureAudioGraph(state) {
  if (state.ctx && state.ctx.state === "closed") {
    state.ctx = null;
    state.masterGain = null;
    state.nodes = [];
    state.scheduledUntil = 0;
  }

  if (state.ctx && state.masterGain) {
    state.desiredGain = safeNumber(state.model.get("gain"), state.desiredGain);
    return state;
  }

  if (state.ctx || state.masterGain) {
    state.ctx = null;
    state.masterGain = null;
    state.nodes = [];
    state.scheduledUntil = 0;
  }

  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor) {
    throw new Error("Web Audio API is not available in this browser.");
  }

  state.ctx = new AudioContextCtor();
  state.masterGain = state.ctx.createGain();
  state.masterGain.gain.value = 0.0;
  state.masterGain.connect(state.ctx.destination);
  state.scheduledUntil = state.ctx.currentTime;
  state.desiredGain = safeNumber(state.model.get("gain"), state.desiredGain);

  state.ctx.onstatechange = () => {
    if (!state.ctx) {
      return;
    }
    if (state.ctx.state === "running") {
      markAudioUnlocked(state);
    } else {
      updateViews(state);
      sendStats(state, { force: true });
    }
  };

  if (state.ctx.state === "running") {
    markAudioUnlocked(state);
  }

  return state;
}

/**
 * Try to transition browser audio into the running state.
 *
 * Browser autoplay policy treats AudioContext creation and the first resume as
 * privileged operations. This helper therefore keeps new-context creation on
 * the user-gesture side of the activation boundary instead of touching the Web
 * Audio graph eagerly from ordinary widget message handling.
 *
 * @param {object} state - Shared widget state.
 * @param {{ fromGesture?: boolean }} [options] - Metadata about the unlock attempt.
 * @returns {Promise<boolean>} Whether the context ended up running.
 */
async function tryUnlockAudio(state, options = {}) {
  if (!hasActiveViews(state)) {
    return false;
  }

  const activationNow = Boolean(options.fromGesture) || hasTransientUserActivation();
  const mayCreateAudioGraph = activationNow;
  const mayResumeExistingContext = state.unlocked || activationNow;

  if (!hasUsableAudioGraph(state)) {
    if (!mayCreateAudioGraph) {
      updateViews(state);
      sendStats(state, { force: true });
      return false;
    }

    try {
      ensureAudioGraph(state);
    } catch (error) {
      safeModelSend(state, {
        type: "frontend-error",
        message: stringifyError(error),
      });
      return false;
    }
  }

  if (!state.ctx) {
    return false;
  }

  if (state.ctx.state === "running") {
    markAudioUnlocked(state);
    return true;
  }

  if (!mayResumeExistingContext) {
    updateViews(state);
    sendStats(state, { force: true });
    return false;
  }

  if (state.unlockAttemptInFlight) {
    return false;
  }

  state.unlockAttemptInFlight = true;
  try {
    await state.ctx.resume();
  } catch (error) {
    void error;
  } finally {
    state.unlockAttemptInFlight = false;
  }

  if (state.ctx && state.ctx.state === "running") {
    markAudioUnlocked(state);
    return true;
  }

  updateViews(state);
  sendStats(state, { force: true });
  return false;
}

/**
 * Install document-level gesture listeners that opportunistically unlock audio.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function ensureAutoUnlockListeners(state) {
  if (state.unlocked || state.unlockListenersInstalled || !hasActiveViews(state)) {
    return;
  }

  state.unlockListener = (event) => {
    if (event && "isTrusted" in event && !event.isTrusted) {
      return;
    }
    void tryUnlockAudio(state, { fromGesture: true });
  };

  for (const eventName of ["pointerdown", "mousedown", "touchstart", "keydown"]) {
    document.addEventListener(eventName, state.unlockListener, true);
  }

  state.unlockListenersInstalled = true;
}

/**
 * Stop queued audio and release browser-side resources.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function cleanupAudioResources(state) {
  try {
    if (state.ctx) {
      flushScheduled(state);
      state.ctx.onstatechange = null;
      state.masterGain?.disconnect();
      state.ctx.close().catch(() => {});
    }
  } catch (error) {
    void error;
  } finally {
    state.ctx = null;
    state.masterGain = null;
    state.nodes = [];
    state.scheduledUntil = 0;
  }
}

/**
 * Remove model-level listeners and timers if they were previously installed.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function teardownModelBindings(state) {
  if (!state.bindingsReady) {
    return;
  }

  const model = state.model;
  if (state.onCustomMessage) {
    model.off("msg:custom", state.onCustomMessage);
  }
  if (state.onRelevantTraitChange) {
    model.off("change:gain", state.onRelevantTraitChange);
    model.off("change:playback_state", state.onRelevantTraitChange);
    model.off("change:position_seconds", state.onRelevantTraitChange);
    model.off("change:buffered_seconds", state.onRelevantTraitChange);
    model.off("change:current_function_name", state.onRelevantTraitChange);
    model.off("change:last_phase_summary", state.onRelevantTraitChange);
    model.off("change:last_error", state.onRelevantTraitChange);
  }

  unbindOptionalModelEvent(model, "comm:close", state.onCommClose);
  unbindOptionalModelEvent(model, "destroy", state.onModelDestroy);
  unbindOptionalModelEvent(model, "comm_live_update", state.onCommLiveUpdate);

  removeAutoUnlockListeners(state);
  state.bindingsReady = false;
  state.onCustomMessage = null;
  state.onRelevantTraitChange = null;
  state.onCommClose = null;
  state.onModelDestroy = null;
  state.onCommLiveUpdate = null;
  state.detachMessageSent = true;
  state.playing = false;
  state.unlocked = false;
  state.unlockAttemptInFlight = false;
  state.lastStatsSentAtMs = 0;
  state.lastStatsSignature = "";
  cleanupAudioResources(state);
  updateViews(state);
}

/**
 * Ensure that model-level event handlers are installed exactly once.
 *
 * @param {object} state - Shared widget state.
 * @param {string} bootMode - Description of the lifecycle path that reached this function.
 * @returns {object} The same state object for convenience.
 */
function ensureModelBindings(state, bootMode) {
  if (state.bindingsReady) {
    if (state.bootMode === "unknown" && bootMode) {
      state.bootMode = bootMode;
    }
    if (hasActiveViews(state)) {
      ensureAutoUnlockListeners(state);
    }
    return state;
  }

  const model = state.model;
  state.bootMode = bootMode || "unknown";

  state.onCustomMessage = (msg, buffers) => {
    try {
      if (msg && msg.type === "audio-chunk") {
        handleAudioChunk(state, msg, buffers);
      } else {
        handleControlMessage(state, msg || {});
      }
    } catch (error) {
      safeModelSend(state, {
        type: "frontend-error",
        message: stringifyError(error),
      });
    }
  };

  state.onRelevantTraitChange = () => {
    state.desiredGain = safeNumber(model.get("gain"), state.desiredGain);
    if (state.playing && state.unlocked && state.ctx) {
      rampMasterGain(state, state.desiredGain, 0.01);
    }
    updateViews(state);
    sendStats(state);
  };

  state.onCommClose = () => {
    markCommUnavailable(state);
  };
  state.onModelDestroy = () => {
    state.modelDestroyed = true;
    markCommUnavailable(state);
  };
  state.onCommLiveUpdate = () => {
    if ("comm_live" in model && model.comm_live === false) {
      markCommUnavailable(state);
    }
  };

  model.on("msg:custom", state.onCustomMessage);
  model.on("change:gain", state.onRelevantTraitChange);
  model.on("change:playback_state", state.onRelevantTraitChange);
  model.on("change:position_seconds", state.onRelevantTraitChange);
  model.on("change:buffered_seconds", state.onRelevantTraitChange);
  model.on("change:current_function_name", state.onRelevantTraitChange);
  model.on("change:last_phase_summary", state.onRelevantTraitChange);
  model.on("change:last_error", state.onRelevantTraitChange);
  bindOptionalModelEvent(model, "comm:close", state.onCommClose);
  bindOptionalModelEvent(model, "destroy", state.onModelDestroy);
  bindOptionalModelEvent(model, "comm_live_update", state.onCommLiveUpdate);

  state.bindingsReady = true;
  if (hasActiveViews(state)) {
    ensureAutoUnlockListeners(state);
  }
  return state;
}

/**
 * Drop references to nodes whose end time is already in the past.
 *
 * @param {object} state - Shared widget state.
 * @returns {void}
 */
function pruneNodes(state) {
  if (!state.ctx) {
    state.nodes = [];
    return;
  }
  const now = state.ctx.currentTime;
  state.nodes = state.nodes.filter((item) => item.endTime > now - 0.001);
}

/**
 * Convert the first binary custom-message buffer into a Float32Array.
 *
 * @param {(ArrayBuffer | ArrayBufferView)[] | undefined} buffers - Binary buffers attached to a custom message.
 * @returns {Float32Array} Decoded float32 PCM samples.
 */
function buffersToFloat32(buffers) {
  if (!buffers || buffers.length === 0) {
    return new Float32Array(0);
  }

  const raw = buffers[0];
  if (raw instanceof Float32Array) {
    return new Float32Array(raw);
  }

  if (raw instanceof ArrayBuffer) {
    return new Float32Array(raw.slice(0));
  }

  if (ArrayBuffer.isView(raw)) {
    const byteOffset = raw.byteOffset || 0;
    const byteLength = raw.byteLength || 0;
    const frameCount = Math.floor(byteLength / Float32Array.BYTES_PER_ELEMENT);
    return new Float32Array(new Float32Array(raw.buffer, byteOffset, frameCount));
  }

  return new Float32Array(0);
}

/**
 * Apply a smooth linear ramp to the master gain.
 *
 * @param {object} state - Shared widget state.
 * @param {number} target - Target gain value.
 * @param {number} duration - Ramp duration in seconds.
 * @param {number | null} startTime - Optional explicit start time.
 * @returns {void}
 */
function rampMasterGain(state, target, duration, startTime = null) {
  if (!state.ctx || !state.masterGain) {
    return;
  }

  const now = startTime ?? state.ctx.currentTime;
  const safeDuration = Math.max(0.0, safeNumber(duration, 0.0));
  const safeTarget = Math.max(0.0, safeNumber(target, 0.0));

  state.masterGain.gain.cancelScheduledValues(now);
  state.masterGain.gain.setValueAtTime(state.masterGain.gain.value, now);
  if (safeDuration === 0) {
    state.masterGain.gain.setValueAtTime(safeTarget, now);
  } else {
    state.masterGain.gain.linearRampToValueAtTime(safeTarget, now + safeDuration);
  }
}

/**
 * Stop queued nodes and reset queue bookkeeping.
 *
 * @param {object} state - Shared widget state.
 * @param {number | null} stopTime - Optional AudioContext time at which nodes should stop.
 * @returns {void}
 */
function flushScheduled(state, stopTime = null) {
  if (!state.ctx) {
    state.nodes = [];
    state.scheduledUntil = 0;
    return;
  }

  const when = stopTime ?? state.ctx.currentTime;
  for (const item of state.nodes) {
    try {
      item.source.stop(when);
    } catch (error) {
      void error;
    }
  }
  state.nodes = [];
  state.scheduledUntil = when;
}

/**
 * Send throttled browser statistics back to Python.
 *
 * The browser no longer owns a perpetual polling loop. Instead, statistics are
 * reported on meaningful front-end transitions and opportunistically throttled.
 * This ties kernel traffic to real widget activity rather than to timer cleanup
 * races around comm shutdown.
 *
 * @param {object} state - Shared widget state.
 * @param {{ force?: boolean }} [options] - Override normal throttling.
 * @returns {boolean} Whether a message was attempted successfully.
 */
function sendStats(state, options = {}) {
  if (!hasActiveViews(state)) {
    return false;
  }

  let queuedSeconds = 0.0;
  let contextState = "not-created";
  if (state.ctx) {
    pruneNodes(state);
    contextState = state.ctx.state;
    queuedSeconds = Math.max(0.0, state.scheduledUntil - state.ctx.currentTime);
    if (state.ctx.state === "running" && !state.unlocked) {
      markAudioUnlocked(state);
      return true;
    }
  }

  const queuedBucket = (Math.round(queuedSeconds * 10) / 10).toFixed(1);
  const signature = `${contextState}|${queuedBucket}|${state.playing ? "playing" : "stopped"}|${state.unlocked ? "unlocked" : "locked"}`;
  const now = nowMs();

  if (!options.force) {
    if (signature === state.lastStatsSignature && now - state.lastStatsSentAtMs < 400) {
      return false;
    }
  }

  const sent = safeModelSend(state, {
    type: "frontend-stats",
    queuedSeconds,
    contextState,
  });
  if (sent) {
    state.lastStatsSignature = signature;
    state.lastStatsSentAtMs = now;
  }
  return sent;
}

/**
 * Schedule one PCM chunk received from Python.
 *
 * @param {object} state - Shared widget state.
 * @param {object} msg - JSON custom message payload.
 * @param {(ArrayBuffer | ArrayBufferView)[] | undefined} buffers - Binary buffers attached to the message.
 * @returns {void}
 */
function handleAudioChunk(state, msg, buffers) {
  if (!state.playing || !state.unlocked) {
    return;
  }

  if (!hasUsableAudioGraph(state)) {
    return;
  }

  if (state.ctx.state !== "running") {
    void tryUnlockAudio(state);
    return;
  }

  const pcm = buffersToFloat32(buffers);
  if (pcm.length === 0) {
    return;
  }

  const sampleRate = safeNumber(msg.sampleRate, state.model.get("sample_rate"));
  const audioBuffer = state.ctx.createBuffer(1, pcm.length, sampleRate);
  audioBuffer.copyToChannel(pcm, 0);

  const source = state.ctx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(state.masterGain);

  pruneNodes(state);

  const minLead = 0.02;
  const startTime = Math.max(state.scheduledUntil, state.ctx.currentTime + minLead);
  source.start(startTime);

  state.nodes.push({
    source,
    startTime,
    endTime: startTime + audioBuffer.duration,
  });
  state.scheduledUntil = startTime + audioBuffer.duration;
  updateViews(state);
  sendStats(state);
}

/**
 * Handle small JSON control messages from Python.
 *
 * @param {object} state - Shared widget state.
 * @param {object} msg - JSON custom message payload.
 * @returns {void}
 */
function handleControlMessage(state, msg) {
  const type = msg.type;

  if (type === "play") {
    state.playing = true;
    ensureAutoUnlockListeners(state);
    void tryUnlockAudio(state);
    updateViews(state);
    sendStats(state, { force: true });
    return;
  }

  if (type === "stop") {
    state.playing = false;
    if (state.ctx) {
      const release = safeNumber(state.model.get("release_duration"), 0.02);
      const now = state.ctx.currentTime;
      rampMasterGain(state, 0.0, release, now);
      flushScheduled(state, now + release + 0.005);
    }
    updateViews(state);
    sendStats(state, { force: true });
    return;
  }

  if (type === "reset-queue") {
    if (state.ctx) {
      const now = state.ctx.currentTime;
      const fade = 0.005;
      rampMasterGain(state, 0.0, fade, now);
      flushScheduled(state, now + fade + 0.001);
      state.scheduledUntil = now + 0.02;
      if (state.playing && state.unlocked) {
        const attack = safeNumber(state.model.get("attack_duration"), 0.01);
        rampMasterGain(state, state.desiredGain, attack, now + fade + 0.001);
      }
    }
    updateViews(state);
    sendStats(state, { force: true });
  }
}

/**
 * Build one hidden notebook view and attach it to the shared state.
 *
 * @param {object} state - Shared widget state.
 * @param {HTMLElement} el - Notebook output element for this view.
 * @returns {object} View descriptor.
 */
function createView(state, el) {
  void state;
  el.classList.add("jfa-root");
  el.setAttribute("aria-hidden", "true");
  el.style.display = "none";
  el.style.width = "0";
  el.style.height = "0";
  el.style.overflow = "hidden";
  el.textContent = "";
  return { root: el };
}

/**
 * Notify Python when widget bootstrapping fails while keeping the helper hidden.
 *
 * @param {import("@jupyter-widgets/base").DOMWidgetModel} model - Widget model.
 * @param {HTMLElement} el - Output element for the failed view.
 * @param {unknown} error - Exception that aborted rendering.
 * @returns {void}
 */
function renderFatalError(model, el, error) {
  const message = `Front-end initialization failed: ${stringifyError(error)}`;
  el.classList.add("jfa-root");
  el.setAttribute("aria-hidden", "true");
  el.style.display = "none";
  el.style.width = "0";
  el.style.height = "0";
  el.style.overflow = "hidden";
  el.textContent = "";

  try {
    const state = model && model._jfa_state ? ensureState(model) : null;
    if (state) {
      safeModelSend(state, {
        type: "frontend-error",
        message,
      });
    } else {
      model.send({
        type: "frontend-error",
        message,
      });
    }
  } catch (sendError) {
    void sendError;
  }
}

/**
 * Initialize the shared model-level behavior for the widget.
 *
 * @param {{ model: import("@jupyter-widgets/base").DOMWidgetModel }} context - AnyWidget initialize context.
 * @returns {() => void} Cleanup callback.
 */
function initialize({ model }) {
  const state = ensureState(model);
  ensureModelBindings(state, "initialize");

  return () => {
    teardownModelBindings(state);
  };
}

/**
 * Render one hidden notebook view and notify Python that the front end is ready.
 *
 * @param {{ model: import("@jupyter-widgets/base").DOMWidgetModel, el: HTMLElement }} context - AnyWidget render context.
 * @returns {() => void} Cleanup callback for this specific view.
 */
function render({ model, el }) {
  try {
    const state = ensureState(model);
    ensureModelBindings(state, state.bindingsReady ? state.bootMode : "render-fallback");
    const view = createView(state, el);
    state.views.add(view);
    ensureAutoUnlockListeners(state);
    state.detachMessageSent = false;
    state.lastStatsSentAtMs = 0;
    state.lastStatsSignature = "";
    updateViews(state);

    safeModelSend(state, { type: "frontend-ready" });
    sendStats(state, { force: true });

    return () => {
      state.views.delete(view);
      updateViews(state);
      if (!hasActiveViews(state)) {
        state.detachMessageSent = true;
        safeModelSend(state, { type: "frontend-detached" });
        state.playing = false;
        state.unlocked = false;
        state.unlockAttemptInFlight = false;
        state.lastStatsSentAtMs = 0;
        state.lastStatsSignature = "";
        removeAutoUnlockListeners(state);
        cleanupAudioResources(state);
        updateViews(state);
      }
    };
  } catch (error) {
    renderFatalError(model, el, error);
    return () => {};
  }
}

export default { initialize, render };
