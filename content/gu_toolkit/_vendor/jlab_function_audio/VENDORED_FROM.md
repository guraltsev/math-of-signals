# Vendored from upstream `jlab_function_audio`

- Upstream package: `jlab_function_audio`
- Upstream version: `0.1.5`
- Source archive: `jlab_function_audio_project.zip`
- Source archive SHA256: `4e07c004c8f97b97b78656600b1316c4948dfc69c123e71607ce8fd8a968deac`
- Vendored into: `src/gu_toolkit/_vendor/jlab_function_audio/`
- Vendoring date: `2026-04-07`

## Files deliberately changed after vendoring

1. `player.py`
   - Added the public `FunctionAudioPlayer.mark_embedded()` API so an external
     widget container can attach the hidden helper without letting `play()` call
     `display(self)` later.
   - Added the public `FunctionAudioPlayer.set_auto_normalize(enabled: bool)`
     API so callers can switch between clipped rendering and bounded streaming
     auto-normalization on the same player instance while preserving transport
     state and flushing buffered audio.
   - Added `dataclasses.replace` import to support the configuration update used
     by `set_auto_normalize(...)`.

## Files copied without runtime changes

- `__init__.py`
- `config.py`
- `matching.py`
- `normalization.py`
- `sampling.py`
- `_frontend.js`
- `_frontend.css`
- `py.typed`
- `README.md`
- `LICENSE`

## Notes

The vendored runtime remains GU-agnostic. All GU-specific figure integration,
legend coordination, strict compatibility validation, and plot adaptation live
outside this subtree in `gu_toolkit.figure_sound`.
