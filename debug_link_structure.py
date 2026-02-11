#!/usr/bin/env python3
"""Debug script to inspect HTML structure of Standard Ebooks link"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from selenium_helper import SeleniumHelper
from bs4 import BeautifulSoup
import re

# Get the page
search_url = "https://standardebooks.org/ebooks?query=wilde"
print(f"Fetching: {search_url}")

html = SeleniumHelper.get_page_source(
    search_url,
    wait_for_selector="a[href*='/ebooks/']",
    wait_time=15
)

soup = BeautifulSoup(html, 'html.parser')

# Find the first specific link
ebook_links = soup.find_all('a', href=re.compile(r'/ebooks/[^/]+/[^/]+$'))
print(f"\nFound {len(ebook_links)} book links")

if ebook_links:
    print("\nFirst link full HTML:")
    link = ebook_links[0]
    print(link.prettify())
    
    print("\n" + "="*80)
    print("Analyzing link structure:")
    print(f"href: {link.get('href')}")
    print(f"text content: '{link.get_text(strip=True)}'")
    
    # Check for img tag with alt text
    img = link.find('img')
    if img:
        print(f"img alt: {img.get('alt')}")
        print(f"img src: {img.get('src')}")
    
    # Check for picture tag
    picture = link.find('picture')
    if picture:
        print(f"Has picture tag: {picture}")
    
    # Parse href to extract author/title
    href = link.get('href')
    if href:
        parts = href.strip('/').split('/')
        print(f"\nHref parts: {parts}")
        if len(parts) >= 3:
            author_slug = parts[1]
            title_slug = parts[2]
            print(f"Author slug: {author_slug}")
            print(f"Title slug: {title_slug}")
            
            # Convert slugs to readable text
            author = author_slug.replace('-', ' ').title()
            title = title_slug.replace('-', ' ').title()
            print(f"Author: {author}")
            print(f"Title: {title}")
