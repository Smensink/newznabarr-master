import requests
from bs4 import BeautifulSoup
import re
from plugin_search_interface import PluginSearchBase

class StandardEbooksSearch(PluginSearchBase):
    """
    Standard Ebooks search plugin
    Searches high-quality public domain ebooks
    """
    
    BASE_URL = "https://standardebooks.org"
    
    def getcat(self):
        return ["7020"]  # Books/eBook
    
    def gettestquery(self):
        return "wilde"
    
    def getprefix(self):
        return "standardebooks"
    
    def search(self, query, cat):
        """
        Search Standard Ebooks by scraping their ebooks page
        Uses Selenium for JavaScript rendering
        """
        if not query:
            return []
        
        from selenium_helper import SeleniumHelper
        
        search_url = f"{self.BASE_URL}/ebooks?query={query}"
        
        try:
            # Use Selenium to get rendered page
            html = SeleniumHelper.get_page_source(
                search_url,
                wait_for_selector="a[href*='/ebooks/']",  # Wait for ebook links
                wait_time=15
            )
            
            books = self._parse_ebooks_page(html, query.lower())
            results = self._convert_results(books, cat)
            
            print(f"Found {len(results)} results from Standard Ebooks")
            return results
            
        except Exception as e:
            print(f"Standard Ebooks error: {e}")
            return []
    
    def _parse_ebooks_page(self, html, query):
        """
        Parse the ebooks index page and filter by query
        """
        soup = BeautifulSoup(html, 'html.parser')
        books = []
        
        # Find all ebook links (they link to /ebooks/author/title)
        ebook_links = soup.find_all('a', href=re.compile(r'/ebooks/[^/]+/[^/]+$'))
        
        for link in ebook_links:
            try:
                # Get book path
                book_path = link.get('href', '')
                if not book_path or not book_path.startswith('/'):
                    continue
                
                # Extract author and title from path
                # Path format: /ebooks/author-slug/title-slug
                parts = book_path.strip('/').split('/')
                if len(parts) < 3:
                    continue
                    
                author_slug = parts[1]
                title_slug = parts[2]
                
                # Convert slugs to readable text
                author = author_slug.replace('-', ' ').title()
                title = title_slug.replace('-', ' ').title()
                
                # Filter by query (case-insensitive)
                if query not in title.lower() and query not in author.lower():
                    continue
                
                # Construct full URL
                book_url = f"{self.BASE_URL}{book_path}"
                
                # Construct download URLs from path
                # Note: Standard Ebooks requires ?source=download parameter to trigger actual download
                book_slug = title_slug
                epub_url = f"{book_url}/downloads/{author_slug}_{book_slug}.epub?source=download"
                
                book = {
                    'title': title,
                    'author': author,
                    'link': book_url,
                    'epub_url': epub_url,
                }
                books.append(book)
                    
            except Exception as e:
                print(f"Error parsing Standard Ebooks entry: {e}")
                continue
        
        return books
    
    def _convert_results(self, books, cat):
        """
        Convert parsed books to standardized format
        """
        results = []
        
        for book in books:
            try:
                title = book['title']
                author = book['author']
                book_link = book['link']
                epub_url = book['epub_url']
                
                # Standard Ebooks typically provides high-quality EPUB3
                file_format = "EPUB3"
                
                # Estimate file size (Standard Ebooks are typically well-formatted)
                estimated_size = "2097152"  # 2MB estimate
                
                # Construct title
                constructed_title = f"{title} - {author} ({file_format})"
                
                # Build description
                description = f"{title} | {author} | {file_format} | Public Domain | High Quality"
                
                entry = {
                    "link": epub_url,
                    "title": constructed_title,
                    "description": description,
                    "guid": book_link,
                    "comments": book_link,
                    "files": "1",
                    "size": estimated_size,
                    "category": cat,
                    "grabs": "100",
                    "prefix": self.getprefix(),
                    "author": author,
                    "book_title": title,
                    "format": file_format,
                    "language": "English",  # Standard Ebooks are all English
                    "pub_ts": None,
                }
                
                results.append(entry)
                
            except Exception as e:
                print(f"Error converting Standard Ebooks result: {e}")
                continue
        
        return results


def getmyprefix():
    return "standardebooks"
