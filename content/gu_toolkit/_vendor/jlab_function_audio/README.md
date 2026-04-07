# jlab-function-audio

`jlab-function-audio` turns a Python callable `f(t)` into buffered background audio inside JupyterLab.

The package is designed for the workflow described in the request that motivated this implementation:

- sound is produced in the browser with the Web Audio API,
- Python owns the transport clock and only renders small chunks ahead of playback,
- the signal callable is installed later via `set_function(...)`,
- the signal is periodic over **100 seconds**,
- playback supports `play`, `stop`, `restart`, and `seek`,
- `set_function(...)` can swap in a new callable while playback is already running,
- a phase-matching algorithm and short crossfade suppress clicks when the signal changes,
- the browser helper stays **non-visual** and is controlled entirely from Python.

## Architecture

The implementation has three layers:

1. **Python transport and buffering**
   - `FunctionAudioPlayer` keeps an unwrapped transport clock.
   - A background thread renders small mono float32 chunks only a short time ahead of the audible position.
   - The transport wraps into the user-visible 100-second period only when sampling the callable.

2. **Phase matching**
   - `phase_match_functions(...)` compares the currently scheduled signal with the replacement callable.
   - The matcher searches for a function time in the replacement callable whose value, slope, and short forward window best match the signal already in flight.
   - A short crossfade on the first replacement chunk guarantees click suppression even when the two callables cannot be matched perfectly.

3. **JupyterLab / browser playback**
   - The package uses `anywidget` so the browser side works naturally inside JupyterLab.
   - The front end receives chunk messages, converts them to `AudioBuffer` objects, and schedules them with the Web Audio API.
   - A master gain node provides a small attack and release for play/stop/seek.
   - The widget renders **no visible UI** and instead auto-arms browser audio from the next ordinary notebook interaction.

## Installation

Open the project directory and install it into the kernel environment:

```bash
pip install -e .
```

The notebook in `notebooks/jlab_function_audio_demo.ipynb` contains a guided walk-through and interactive experiments.

## Quick start

```python
import math
from jlab_function_audio import FunctionAudioPlayer

player = FunctionAudioPlayer()
player.set_function(
    lambda t: 0.3 * math.sin(2 * math.pi * 220.0 * t),
    function_name="220 Hz sine",
)
player.play()
```

## Important practical note

Browsers still commonly require one user gesture before audio can begin.
This release no longer shows a dedicated **Enable audio** button. Instead, the
hidden browser helper listens for the next normal notebook interaction such as a
button click, key press, or slider drag and unlocks audio automatically.

Two browser-side lifecycle boundaries are handled explicitly:

- **Audio activation boundary**: `play()` only arms playback. A new `AudioContext`
  is created or resumed only from a trusted notebook gesture path.
- **Widget transport boundary**: the browser no longer owns a perpetual 250 ms
  stats loop. Browser status is reported only on meaningful transitions, and the
  helper stops sending entirely once its comm or last rendered view goes away.


## Optional bounded autonormalization

`FunctionAudioPlayer` now supports an optional Python-side autonormalization path.
When `auto_normalize=False`, the original clipped render path is preserved.
When `auto_normalize=True`, the player instead:

1. renders raw unclipped samples,
2. crossfades raw chunks on live function swaps,
3. subtracts local DC with a one-pole estimator,
4. computes a bounded forward running peak over a short lookahead window,
5. applies one-sided attenuation with exponential release memory,
6. keeps the final hard clip only as a safety net.

The browser remains a passive scheduler; no AGC or compressor is used in the
front end.

The public configuration fields are:

- `auto_normalize`
- `normalization_dc_time_constant`
- `normalization_attack_lookahead_duration`
- `normalization_release_time_constant`

A guided A/B notebook section is included in
`notebooks/jlab_function_audio_demo.ipynb`.

## Readiness and troubleshooting

Widget rendering is asynchronous. If you call `player.snapshot_state()` in the
same cell that constructs the player, `frontend_ready` will often still be
`False` even when the front end is working normally. Run the snapshot in a later
cell or use the notebook's status refresh helper.

If `snapshot_state()` reports `waiting-for-browser-gesture`, audio is still
locked by the browser. Click any notebook button or move any widget slider once;
there is no separate audio-enable control anymore.

The front end bootstraps from both the AnyWidget `initialize` hook and the
`render` hook so older or partially compatible notebook front ends still attach
reliably.

When the last rendered view disappears, the front end now emits a
`frontend-detached` message, clears browser audio resources, and stops trying to
report status back to Python. This prevents stale hidden helpers from spamming
`Cannot send` errors after a notebook output is removed or a comm is torn down.

## Regression checks

The repo includes focused front-end regression harnesses plus Python
autonormalization tests:

```bash
node tests/frontend_activation_boundary.mjs
node tests/frontend_comm_resilience.mjs
pytest -q tests/test_autonormalization.py
```

## Package contents

- `config.py` - validated public configuration dataclass
- `sampling.py` - periodic time wrapping and chunk rendering helpers
- `matching.py` - phase matching algorithm and result dataclass
- `player.py` - the JupyterLab widget, transport engine, and background pump
- `_frontend.js` / `_frontend.css` - hidden browser playback helper
- `notebooks/jlab_function_audio_demo.ipynb` - interactive demonstration notebook
