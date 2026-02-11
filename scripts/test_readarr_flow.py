#!/usr/bin/env python3
"""
Emulate a Readarr -> Newznabarr -> SABnzbd flow for the LibGen plugin.

Steps:
1. Simulate Readarr performing a Newznab `t=search` call (LibGen category 7020).
2. Convert the plugin results to the RSS XML returned by the API.
3. Pick the first item (as Readarr would) and build the NZB payload that Newznabarr
   exposes via `download=nzb`.
4. Simulate SABnzbd's `mode=addfile` handler parsing that NZB and enqueueing the job.
5. Invoke the LibGen download plugin to fetch the payload to a local directory.

Run this script on a host that has network access to LibGen mirrors.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
from newznab import searchresults_to_response  # type: ignore  # noqa: E402


def build_nzb_payload(prefix: str, url: str, size: str, title: str) -> str:
    """Reproduce the `/api?download=nzb` response."""
    nzb = ET.Element('nzb', xmlns="http://www.newzbin.com/DTD/2003/nzb")
    meta = ET.SubElement(nzb, 'meta')
    ET.SubElement(meta, 'prefix').text = prefix
    ET.SubElement(meta, 'url').text = url
    ET.SubElement(meta, 'size').text = size
    ET.SubElement(meta, 'title').text = title
    file_elem = ET.SubElement(nzb, 'file', poster="none", subject="none")
    ET.SubElement(file_elem, 'groups')
    segments = ET.SubElement(file_elem, 'segments')
    ET.SubElement(segments, 'segment', bytes=size, number="1")
    return ET.tostring(nzb, encoding='utf-8', xml_declaration=True).decode()


def parse_nzb_payload(nzb_xml: str):
    """Parse NZB XML the same way SAB's addfile handler does."""
    root = ET.fromstring(nzb_xml)
    namespace = {'nzb': 'http://www.newzbin.com/DTD/2003/nzb'}
    def extract(tag):
        elem = root.find(f'.//nzb:meta/nzb:{tag}', namespace)
        return elem.text if elem is not None else None
    return {
        "prefix": extract("prefix"),
        "url": extract("url"),
        "size": extract("size"),
        "title": extract("title"),
    }


def parse_rss_items(rss_xml: bytes):
    root = ET.fromstring(rss_xml)
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item"):
        link = item.findtext("link")
        title = item.findtext("title")
        size = item.findtext("size")
        items.append({"link": link, "title": title, "size": size})
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a full Readarr -> SAB flow for LibGen.")
    parser.add_argument("query", nargs="?", default="Pride and Prejudice", help="Search query to send.")
    parser.add_argument("--category", default="7020", help="Newznab/Lidarr category to use.")
    parser.add_argument("--download-dir", default=None, help="Directory to place downloads in.")
    args = parser.parse_args()

    search_plugin = LibGenSearch()
    print(f"[1] Searching for '{args.query}' in category {args.category}")
    results = search_plugin.search(args.query, args.category)
    if not results:
        print("No results returned; aborting.")
        return 1

    rss = searchresults_to_response("http://localhost:10000/", results)
    rss_items = parse_rss_items(rss)
    if not rss_items:
        print("RSS payload missing items.")
        return 1

    print(f"[2] RSS contains {len(rss_items)} items; iterating until a download succeeds")
    download_dir = (
        Path(args.download_dir).expanduser()
        if args.download_dir
        else Path(tempfile.mkdtemp(prefix="libgen_readarr_flow_"))
    )
    print(f"[4] Simulating SAB addfile -> download into {download_dir}")

    download_plugin = LibGenDownload()
    for idx, item in enumerate(rss_items, start=1):
        link = item.get("link")
        if not link:
            continue
        parsed_link = urlparse(link)
        params = parse_qs(parsed_link.query)
        prefix = params.get("prefix", [None])[0]
        url = params.get("url", [None])[0]
        size = params.get("size", [item.get("size"), "0"])[0]
        title = params.get("title", [item.get("title", "Untitled")])[0]

        if not all([prefix, url, size, title]):
            continue

        print(f"[3.{idx}] Building NZB for '{title}' (prefix={prefix})")
        nzb_payload = build_nzb_payload(prefix, url, size, title)
        nzb_meta = parse_nzb_payload(nzb_payload)
        try:
            dest = download_plugin.download(
                nzb_meta["url"],
                nzb_meta["title"],
                str(download_dir),
                args.category,
            )
        except Exception as exc:
            print(f"    Download plugin raised exception: {exc}")
            continue

        if dest != "404":
            print(f"[5] Download complete: {dest}")
            return 0
        print(f"    Download plugin reported failure for {nzb_meta['url']}, trying next item...")

    print("All download attempts failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
