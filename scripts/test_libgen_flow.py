#!/usr/bin/env python3
"""
Emulate a full Newznabarr LibGen flow: search via indexer plugin, pick a result,
and run the download plugin to fetch the file.

This is best run on a host with network access to LibGen mirrors.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(os.environ.get("CONFIG", PROJECT_ROOT / "config"))
SEARCH_PLUGIN_DIR = CONFIG_DIR / "plugins" / "search"
DOWNLOAD_PLUGIN_DIR = CONFIG_DIR / "plugins" / "download"

for path in (PROJECT_ROOT, SEARCH_PLUGIN_DIR, DOWNLOAD_PLUGIN_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from libgen import LibGenSearch  # type: ignore  # noqa: E402
from libgendl import LibGenDownload  # type: ignore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a LibGen query and download the first successful hit."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Pride and Prejudice",
        help="Search query to send to the LibGen indexer (default: %(default)s)",
    )
    parser.add_argument(
        "--category",
        default="7020",
        help="Category ID to pass to the search plugin (default: %(default)s)",
    )
    parser.add_argument(
        "--download-dir",
        default=None,
        help="Directory to write downloads to (default: create a temp dir)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    search_plugin = LibGenSearch()
    download_plugin = LibGenDownload()
    download_dir = (
        Path(args.download_dir).expanduser()
        if args.download_dir
        else Path(tempfile.mkdtemp(prefix="libgen_flow_"))
    )

    print(f"Searching LibGen for '{args.query}' (category {args.category})")
    results = search_plugin.search(args.query, args.category)
    if not results:
        print("No results returned; cannot continue to download step.")
        return 1

    print(f"Received {len(results)} results, attempting first compatible link.")
    for entry in results:
        prefix = entry.get("prefix")
        link = entry.get("link")
        title = entry.get("title", "Untitled")
        if prefix != "libgen" or not link:
            continue
        print(f"Trying to download '{title}' from {link}")
        dest = download_plugin.download(link, title, str(download_dir), args.category)
        if dest != "404":
            print(f"Download completed: {dest}")
            return 0
        print("Download plugin reported failure, trying next result...")

    print("All download attempts failed. Check network access or mirrors.")
    print(f"Artifacts directory: {download_dir}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
