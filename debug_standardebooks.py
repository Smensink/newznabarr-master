#!/usr/bin/env python3
"""Debug script for Standard Ebooks plugin"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "search"
sys.path.insert(0, str(PLUGIN_DIR))

from standardebooks import StandardEbooksSearch

# Test the plugin
plugin = StandardEbooksSearch()
query = plugin.gettestquery()
category = plugin.getcat()[0]

print(f"Testing Standard Ebooks with query: {query}")
print(f"Category: {category}")
print("-" * 80)

results = plugin.search(query, category)

print(f"\nFound {len(results)} results")
if results:
    print("\nFirst result:")
    for key, value in results[0].items():
        print(f"  {key}: {value}")
else:
    print("\nNo results found. Testing parser directly...")
    
    # Get the HTML and test parsing
    from selenium_helper import SeleniumHelper
    search_url = f"{plugin.BASE_URL}/ebooks?query={query}"
    print(f"\nFetching URL: {search_url}")
    
    html = SeleniumHelper.get_page_source(
        search_url,
        wait_for_selector="a[href*='/ebooks/']",
        wait_time=15
    )
    
    print(f"\nHTML length: {len(html)}")
    
    # Test parsing
    books = plugin._parse_ebooks_page(html, query.lower())
    print(f"\nParsed {len(books)} books")
    
    if books:
        print("\nFirst book:")
        for key, value in books[0].items():
            print(f"  {key}: {value}")
    else:
        print("\nNo books parsed. Checking HTML structure...")
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Check for ebook links
        ebook_links = soup.find_all('a', href=re.compile(r'/ebooks/'))
        print(f"\nFound {len(ebook_links)} links with /ebooks/ in href")
        
        if ebook_links:
            print("\nFirst 5 ebook link hrefs:")
            for link in ebook_links[:5]:
                print(f"  {link.get('href')}")
                
        # Check the specific pattern the plugin is looking for
        specific_links = soup.find_all('a', href=re.compile(r'/ebooks/[^/]+/[^/]+$'))
        print(f"\nFound {len(specific_links)} links matching pattern /ebooks/[^/]+/[^/]+$")
        
        if specific_links:
            print("\nFirst specific link:")
            link = specific_links[0]
            print(f"  href: {link.get('href')}")
            print(f"  text: {link.get_text(strip=True)[:100]}")
            print(f"  HTML: {str(link)[:200]}")
