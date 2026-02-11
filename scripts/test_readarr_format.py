#!/usr/bin/env python3
"""
Validate LibGen search output and the generated Newznab RSS item structure.

Usage:
    python scripts/test_readarr_format.py "author or title"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(os.environ.get("CONFIG", PROJECT_ROOT / "config"))
SEARCH_PLUGIN_DIR = CONFIG_DIR / "plugins" / "search"

for path in (PROJECT_ROOT, SEARCH_PLUGIN_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from libgen import LibGenSearch, get_configured_mirror_entries, _make_params  # type: ignore  # noqa: E402
from newznab import searchresults_to_response  # type: ignore  # noqa: E402
from bs4 import BeautifulSoup  # type: ignore
import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect LibGen -> Newznab output.")
    parser.add_argument("query", nargs="?", default="Matthew Reilly", help="Query to run.")
    parser.add_argument("--category", default="7020", help="Category to use.")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to inspect.")
    parser.add_argument("--dump-html", action="store_true", help="Dump raw LibGen table row for debugging.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plugin = LibGenSearch()
    results = plugin.search(args.query, args.category)
    if not results:
        print("No results returned.")
        return 1

    sample = results[: args.limit]
    for idx, entry in enumerate(sample, start=1):
        print(f"\nResult {idx}:")
        for key, value in entry.items():
            print(f"  {key}: {value}")

    rss = searchresults_to_response("http://localhost:10000/", sample)
    root = ET.fromstring(rss)
    item = root.find("./channel/item")
    if item is None:
        print("RSS has no items.")
        return 1

    print("\nFirst RSS item:")
    print(f"  Title: {item.findtext('title')}")
    print(f"  Description: {item.findtext('description')}")
    attrs = item.findall("newznab:attr", {"newznab": "http://www.newznab.com/DTD/2010/feeds/attributes/"})
    for attr in attrs:
        print(f"  Attr {attr.get('name')}: {attr.get('value')}")

    if args.dump_html:
        mirror = get_configured_mirror_entries()[0]
        params = _make_params(mirror.get("params_type", "search"), args.query, args.limit)
        print(f"\nFetching raw HTML from {mirror['url']} with params {params}")
        resp = requests.get(mirror["url"], params=params, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("No table found in HTML.")
        else:
            header = [cell.get_text(strip=True) for cell in table.find_all("tr")[0].find_all(["td", "th"])]
            print("Header columns:", header)
            rows = table.find_all("tr")
            if len(rows) > 1:
                first_row = rows[1]
                row_values = []
                for idx, cell in enumerate(first_row.find_all("td")):
                    label = cell.get("data-title", "")
                    text = cell.get_text(strip=True)
                    row_values.append((idx, label, text))
                print("First row values (index | data-title | text):")
                for idx, label, text in row_values:
                    print(f"  [{idx}] {label} | {text}")
            else:
                print("Table has no data rows.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
