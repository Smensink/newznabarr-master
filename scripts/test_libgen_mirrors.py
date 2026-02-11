#!/usr/bin/env python3
"""
Quick connectivity test for LibGen mirrors configured in config/config.json.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(os.environ.get("CONFIG", PROJECT_ROOT / "config"))
SEARCH_PLUGIN_DIR = CONFIG_DIR / "plugins" / "search"

for path in (PROJECT_ROOT, SEARCH_PLUGIN_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import libgen  # type: ignore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate configured LibGen mirrors.")
    parser.add_argument(
        "query",
        nargs="?",
        default="The Hobbit",
        help="Sample query to use for probing the mirrors (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mirrors = [entry for entry in libgen.get_configured_mirror_entries() if entry.get("params_type") == "index"]
    if not mirrors:
        mirrors = libgen.get_configured_mirror_entries()
    if not mirrors:
        print("No mirrors configured. Check config/config.json.")
        return 1

    print(f"Testing {len(mirrors)} LibGen mirrors with query '{args.query}'\n")
    exit_code = 0
    for mirror in mirrors:
        ok, message = libgen.probe_mirror(mirror, args.query)
        status = "ok" if ok else "error"
        line = f"{mirror['url']:<35} [{status.upper()}] ({mirror['params_type']}) {message}"
        print(line)
        if not ok:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
