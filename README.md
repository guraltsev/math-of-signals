# Cookies Fourier

This repository deploys a JupyterLite site for exploratory Fourier-analysis notebooks.

The site is configured so that every new **Python (Pyodide)** notebook starts with these packages available without a setup cell:

- `numpy`
- `pandas`
- `scipy`
- `sympy`
- `plotly`
- `anywidget`
- `ipywidgets`

`ipywidgets` is bundled because the local `gu_toolkit` helpers import it directly.

Extra packages can still be installed from inside a notebook with `%pip install ...`.

## What changed in this repo

- JupyterLite build settings now live in `jupyter_lite_config.json` and `jupyter-lite.json`.
- GitHub Actions now builds **two things in one deployment**:
  1. the JupyterLite site itself
  2. a modified, self-hosted Pyodide distribution under `dist/pyodide`
- The deployed JupyterLite runtime is patched to point at that bundled Pyodide distribution.
- The custom Pyodide builder now reuses packages already present in the upstream Pyodide lockfile instead of replacing them with redundant downloaded wheels.
- The Fourier notebooks no longer tell users to run `%pip install ...` before getting started.

## Repo layout

- `content/` - notebooks, helpers, and JupyterLite workspaces
- `jupyter_lite_config.json` - build-time JupyterLite settings
- `jupyter-lite.json` - runtime JupyterLite settings, including the default Pyodide package preload list
- `pyodide-extra-requirements.txt` - extra pure-Python wheels that get merged into the deployed Pyodide lockfile
- `scripts/build_custom_pyodide.py` - downloads the official Pyodide release, adds the extra wheels, and writes `dist/pyodide`
- `scripts/patch_runtime_config.py` - rewrites the built runtime config so `pyodideUrl` matches the final GitHub Pages URL
- `.github/workflows/deploy.yml` - builds and deploys the complete site to GitHub Pages

## Deploy on GitHub

1. Create a GitHub repository and upload this repo as-is.
2. Make sure the default branch is `main`.
3. Open **Settings -> Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Push to `main`, or open the **Actions** tab and run **Build and Deploy** manually.
6. Wait for the workflow to finish successfully.
7. Open the deployed site:
   - project site: `https://<owner>.github.io/<repo>/lab/`
   - user or organization site (repo named `<owner>.github.io`): `https://<owner>.github.io/lab/`

Once deployed, the JupyterLab launcher and notebooks will use the bundled Pyodide runtime automatically.

## Open the activities

After deployment, these URLs open the four notebooks in single-document mode:

- `https://<owner>.github.io/<repo>/lab/index.html?workspace=Fourier_01&mode=single-document`
- `https://<owner>.github.io/<repo>/lab/index.html?workspace=Fourier_02&mode=single-document`
- `https://<owner>.github.io/<repo>/lab/index.html?workspace=Fourier_03&mode=single-document`
- `https://<owner>.github.io/<repo>/lab/index.html?workspace=Fourier_04&mode=single-document`

For a user or organization site repository named `<owner>.github.io`, remove `/<repo>` from those URLs.

## Change the default package set

There are two places to edit if you want to change what is ready at notebook startup:

1. `pyodide-extra-requirements.txt`
   - add or remove extra pure-Python wheels that should be bundled into the deployed Pyodide distribution
2. `jupyter-lite.json`
   - update `loadPyodideOptions.packages` so the kernel preloads the packages you want available immediately

If you add packages that are not pure-Python wheels, this repo's current workflow is not enough by itself; those packages usually need a real Pyodide package build.

## Notes

- The deployment workflow uses Python 3.13 because the pinned JupyterLite Pyodide kernel line targets Pyodide 0.29.x.
- The custom Pyodide builder asks `pip download` for `--platform any --implementation py --abi none --python-version 3.13` so packages like `psygnal` resolve to universal `py3-none-any` wheels instead of host-specific Linux wheels.
- The Pyodide assets are created during the GitHub Action run and are **not** committed into git.
- The site remains static and GitHub Pages-friendly: no server process is required.
