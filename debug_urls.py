#!/usr/bin/env python3
"""Quick debug script to see what URLs are being generated"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
SEARCH_PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "search"
sys.path.insert(0, str(SEARCH_PLUGIN_DIR))

from standardebooks import StandardEbooksSearch

plugin = StandardEbooksSearch()
results = plugin.search("wilde", plugin.getcat()[0])

if results:
    first = results[0]
    print("First result:")
    print(f"title: {first['title']}")
    print(f"book_title: {first['book_title']}")
    print(f"author: {first['author']}")
    print(f"link (download URL): {first['link']}")
    print(f"guid: {first['guid']}")
    print(f"comments: {first['comments']}")
    
    print(f"\nExpected download URL per browser investigation:")
    print(f"https://standardebooks.org/ebooks/oscar-wilde/a-woman-of-no-importance/downloads/oscar-wilde_a-woman-of-no-importance.epub")
