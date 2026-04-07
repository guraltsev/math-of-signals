#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename

PYODIDE_VERSION = "0.29.3"
PYODIDE_URL = (
    f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE_VERSION}/"
    f"pyodide-{PYODIDE_VERSION}.tar.bz2"
)
PYODIDE_SHA256 = "458e8ddbcbb6e21037d3237cd5c5146c451765bc738dfa2249ff34c5140331e4"
PYODIDE_PYTHON_VERSION = "3.13"
DEFAULT_REQUIREMENTS = Path("pyodide-extra-requirements.txt")
REQUIRED_PACKAGES = {
    "numpy",
    "pandas",
    "scipy",
    "sympy",
    "ipywidgets",
    "anywidget",
    "plotly",
}


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)



def ensure_archive(cache_dir: Path) -> Path:
    archive = cache_dir / f"pyodide-{PYODIDE_VERSION}.tar.bz2"
    if archive.exists() and sha256sum(archive) == PYODIDE_SHA256:
        return archive
    if archive.exists():
        archive.unlink()
    print(f"Downloading {PYODIDE_URL} -> {archive}")
    download_file(PYODIDE_URL, archive)
    actual = sha256sum(archive)
    if actual != PYODIDE_SHA256:
        archive.unlink(missing_ok=True)
        raise RuntimeError(
            "Pyodide archive checksum mismatch: "
            f"expected {PYODIDE_SHA256}, got {actual}"
        )
    return archive



def flatten_extracted_tree(output_dir: Path) -> None:
    if (output_dir / "pyodide.js").exists():
        return
    entries = [entry for entry in output_dir.iterdir() if entry.name != ".DS_Store"]
    if len(entries) != 1 or not entries[0].is_dir():
        raise RuntimeError(
            "Could not find pyodide.js after extraction and could not flatten the archive "
            f"layout in {output_dir}"
        )
    inner = entries[0]
    if not (inner / "pyodide.js").exists():
        raise RuntimeError(f"Expected {inner / 'pyodide.js'} to exist after extraction")
    for child in inner.iterdir():
        shutil.move(str(child), output_dir / child.name)
    inner.rmdir()



def extract_archive(archive_path: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {archive_path} -> {output_dir}")
    with tarfile.open(archive_path, mode="r:bz2") as archive:
        try:
            archive.extractall(output_dir, filter="data")
        except TypeError:
            archive.extractall(output_dir)
    flatten_extracted_tree(output_dir)
    for required in ["pyodide.js", "pyodide-lock.json"]:
        if not (output_dir / required).exists():
            raise RuntimeError(f"Missing required Pyodide asset: {required}")



def run_checked(cmd: list[str], cwd: Path | None = None) -> None:
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)



def download_wheels(requirements_file: Path, output_dir: Path) -> list[Path]:
    wheel_dir = output_dir / "wheels"
    if wheel_dir.exists():
        shutil.rmtree(wheel_dir)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(wheel_dir),
        "--only-binary=:all:",
        "--platform",
        "any",
        "--python-version",
        PYODIDE_PYTHON_VERSION,
        "--implementation",
        "py",
        "--abi",
        "none",
        "--requirement",
        str(requirements_file),
    ]
    run_checked(cmd)
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError(f"No wheels were downloaded from {requirements_file}")
    non_portable = [wheel.name for wheel in wheels if not wheel.name.endswith("none-any.whl")]
    if non_portable:
        raise RuntimeError(
            "Only implementation-agnostic, platform-agnostic wheels are supported by "
            "this repo workflow. Unexpected wheels: "
            f"{', '.join(non_portable)}"
        )
    return wheels



def find_pyodide_cli() -> str:
    pyodide_exe = shutil.which("pyodide")
    if not pyodide_exe:
        raise RuntimeError(
            "The 'pyodide' CLI was not found on PATH. Install pyodide-build before running "
            "this script."
        )
    return pyodide_exe



def lockfile_package_names(lockfile: Path) -> set[str]:
    data = json.loads(lockfile.read_text(encoding="utf-8"))
    return {canonicalize_name(name) for name in data.get("packages", {})}



def wheel_distribution_name(path: Path) -> str:
    try:
        name, _, _, _ = parse_wheel_filename(path.name)
    except InvalidWheelFilename:
        stem_parts = path.stem.split("-")
        if not stem_parts:
            raise RuntimeError(f"Could not determine distribution name for wheel {path}")
        name = stem_parts[0]
    return canonicalize_name(name)



def prune_wheels_already_in_lockfile(output_dir: Path, wheels: list[Path]) -> list[Path]:
    """Keep only wheels for packages that are not already bundled in upstream Pyodide.

    The upstream 0.29.3 lockfile already contains many pure-Python packages such as
    IPython, traitlets, prompt_toolkit, packaging, narwhals, and their dependencies.
    Replacing them with freshly downloaded wheels is unnecessary and can create a much
    larger, more fragile lockfile solve.
    """

    existing_packages = lockfile_package_names(output_dir / "pyodide-lock.json")
    kept: list[Path] = []
    reused: list[tuple[str, Path]] = []

    for wheel in wheels:
        distribution_name = wheel_distribution_name(wheel)
        if distribution_name in existing_packages:
            reused.append((distribution_name, wheel))
            continue
        kept.append(wheel)

    if reused:
        reused_names = sorted({name for name, _ in reused})
        print(
            "Reusing packages already present in upstream pyodide-lock.json instead of "
            "replacing them with downloaded wheels: "
            + ", ".join(reused_names)
        )
        for _, wheel in reused:
            wheel.unlink(missing_ok=True)

    if kept:
        print(
            "Additional wheels to merge into the custom Pyodide lockfile: "
            + ", ".join(wheel.name for wheel in kept)
        )
    else:
        print("No extra wheels need to be merged; upstream Pyodide already provides them.")

    return kept



def add_wheels_to_lockfile_via_api(output_dir: Path, wheels: list[Path]) -> None:
    from pyodide_lock import PyodideLockSpec
    from pyodide_lock.utils import add_wheels_to_spec

    input_lock = output_dir / "pyodide-lock.json"
    output_lock = output_dir / "pyodide-lock.updated.json"
    lock_spec = PyodideLockSpec.from_json(input_lock)
    updated_lock_spec = add_wheels_to_spec(lock_spec, wheels, base_path=output_dir)
    updated_lock_spec.to_json(output_lock)
    output_lock.replace(input_lock)



def add_wheels_to_lockfile(output_dir: Path, wheels: list[Path]) -> None:
    if not wheels:
        return
    try:
        add_wheels_to_lockfile_via_api(output_dir, wheels)
        return
    except ImportError:
        print(
            "pyodide_lock Python API is not importable in this environment; falling back "
            "to the pyodide CLI."
        )

    input_lock = output_dir / "pyodide-lock.json"
    output_lock = output_dir / "pyodide-lock.updated.json"
    cmd = [
        find_pyodide_cli(),
        "lockfile",
        "add-wheels",
        "--input",
        str(input_lock),
        "--output",
        str(output_lock),
        "--base-path",
        str(output_dir),
        *[str(wheel) for wheel in wheels],
    ]
    run_checked(cmd)
    output_lock.replace(input_lock)



def validate_lockfile(output_dir: Path) -> None:
    lockfile = output_dir / "pyodide-lock.json"
    data = json.loads(lockfile.read_text(encoding="utf-8"))
    packages = data.get("packages", {})
    missing = sorted(REQUIRED_PACKAGES - set(packages))
    if missing:
        raise RuntimeError(
            "The generated pyodide-lock.json is missing required packages: "
            + ", ".join(missing)
        )
    print("Validated pyodide-lock.json contains:", ", ".join(sorted(REQUIRED_PACKAGES)))



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the official Pyodide distribution, add extra pure-Python wheels to its "
            "lockfile, and write the result into a directory that JupyterLite can serve."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where the modified Pyodide distribution will be written.",
    )
    parser.add_argument(
        "--requirements-file",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
        help="Pinned requirements file for extra wheels to bundle into Pyodide.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache") / "pyodide",
        help="Directory used to cache the downloaded Pyodide archive.",
    )
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    archive = ensure_archive(args.cache_dir)
    extract_archive(archive, args.output_dir)
    wheels = download_wheels(args.requirements_file, args.output_dir)
    wheels = prune_wheels_already_in_lockfile(args.output_dir, wheels)
    add_wheels_to_lockfile(args.output_dir, wheels)
    validate_lockfile(args.output_dir)
    print(f"Custom Pyodide distribution written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
