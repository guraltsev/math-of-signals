# math-of-signals-autorun

Minimal JupyterLab frontend extension used by this repo's JupyterLite deployment.

It watches for opened notebooks, waits for the kernel session to become ready, and executes code cells whose metadata contains:

```json
{
  "autorun": true
}
```

The generated prebuilt labextension is written to `../../extensions/math-of-signals-autorun` during the GitHub Actions build.
