#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PLUGIN_KEY = "@jupyterlite/pyodide-kernel-extension:kernel"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch jupyter-lite.json in the built site so the Pyodide URL matches the deployed Pages URL."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the built jupyter-lite.json file inside the dist directory.",
    )
    parser.add_argument(
        "--site-url",
        required=True,
        help="Fully-qualified GitHub Pages base URL, ending with a slash.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    site_url = args.site_url.rstrip("/") + "/"
    data = json.loads(args.config.read_text(encoding="utf-8"))
    config = (
        data.setdefault("jupyter-config-data", {})
        .setdefault("litePluginSettings", {})
        .setdefault(PLUGIN_KEY, {})
    )
    config["pyodideUrl"] = site_url + "pyodide/pyodide.js"
    args.config.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Updated {args.config} with pyodideUrl={config['pyodideUrl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
