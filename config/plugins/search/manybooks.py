import requests
from bs4 import BeautifulSoup
import re
from plugin_search_interface import PluginSearchBase

class ManyBooksSearch(PluginSearchBase):
    """
    ManyBooks search plugin
    Searches manybooks.net for free ebooks
    """
    
    BASE_URL = "https://manybooks.net"
    
    def getcat(self):
        return ["7020"]  # Books/eBook
    
    def gettestquery(self):
        return "adventure"
    
    def getprefix(self):
        return "manybooks"
    
    def search(self, query, cat):
        """
        Search ManyBooks by using their search functionality
        Uses Selenium for JavaScript rendering
        """
        self.last_error = None
        if not query:
            self.last_error = "Missing query"
            return []
        
        from selenium_helper import SeleniumHelper
        
        search_url = f"{self.BASE_URL}/search-book"
        params = {
            "search": query,
        }
        
        # Build full URL with params
        from urllib.parse import urlencode
        full_url = f"{search_url}?{urlencode(params)}"
        
        try:
            # Try FlareSolverr first to bypass Cloudflare
            try:
                print(f"Attempting ManyBooks search with FlareSolverr...")
                html = SeleniumHelper.get_page_source_flaresolverr(full_url, max_timeout=60000)
                print(f"FlareSolverr succeeded")
            except Exception as flare_error:
                print(f"FlareSolverr failed ({flare_error}), falling back to regular Selenium")
                # Fallback to regular Selenium
                html = SeleniumHelper.get_page_source(
                    full_url,
                    wait_for_selector="a[href^='/titles/']",
                    wait_time=45
                )
            
            books = self._parse_search_results(html)
            results = self._convert_results(books, cat)
            
            print(f"Found {len(results)} results from ManyBooks")
            return results
            
        except Exception as e:
            print(f"ManyBooks error: {e}")
            self.last_error = str(e)
            return []
    
    def _parse_search_results(self, html):
        """
        Parse ManyBooks search results page
        """
        soup = BeautifulSoup(html, 'html.parser')
        books = []
        
        # Find all book title links (they link to /titles/...)
        book_links = soup.find_all('a', href=re.compile(r'^/titles/'))
        
        for link in book_links:
            try:
                book = {}
                
                # Title is the link text
                title = link.get_text(strip=True)
                if not title:
                    continue
                    
                book['title'] = title
                
                # Get book URL
                href = link.get('href', '')
                if href.startswith('/'):
                    book['link'] = f"{self.BASE_URL}{href}"
                else:
                    book['link'] = href
                
                # Author might be in nearby elements - try to find it
                # Look in parent or nearby siblings
                author = "Unknown"
                parent = link.parent
                if parent:
                    # Look for author in nearby text or elements
                    author_elem = parent.find('span', class_='author') or parent.find('div', class_='author')
                    if author_elem:
                        author = author_elem.get_text(strip=True)
                
                book['author'] = author
                
                # Extract format from nearby text if available
                page_text = parent.get_text() if parent else ""
                format_match = re.search(r'\b(EPUB|PDF|MOBI|TXT)\b', page_text, re.I)
                if format_match:
                    book['format'] = format_match.group(1).upper()
                
                books.append(book)
                    
            except Exception as e:
                print(f"Error parsing ManyBooks result: {e}")
                continue
        
        return books
        
        for item in book_items:
            try:
                book = {}
                
                # Get title
                title_elem = item.find('h2') or item.find('h3') or item.find('a', class_='book-title')
                if title_elem:
                    book['title'] = title_elem.get_text(strip=True)
                
                # Get author
                author_elem = item.find('span', class_='author') or item.find('a', class_='author')
                if author_elem:
                    book['author'] = author_elem.get_text(strip=True)
                
                # Get book link
                link_elem = item.find('a', href=True)
                if link_elem:
                    book_path = link_elem.get('href', '')
                    if book_path.startswith('/'):
                        book['link'] = f"{self.BASE_URL}{book_path}"
                    else:
                        book['link'] = book_path
                
                # Extract formats from text if available
                formats_text = item.get_text()
                format_match = re.search(r'\b(EPUB|PDF|MOBI|TXT)\b', formats_text, re.I)
                if format_match:
                    book['format'] = format_match.group(1).upper()
                
                if book.get('title') and book.get('link'):
                    books.append(book)
                    
            except Exception as e:
                print(f"Error parsing ManyBooks result: {e}")
                continue
        
        return books
    
    def _convert_results(self, books, cat):
        """
        Convert parsed books to standardized format
        """
        results = []
        
        for book in books:
            try:
                title = book.get('title', 'Unknown')
                author = book.get('author', 'Unknown')
                book_link = book.get('link', '')
                file_format = book.get('format', 'EPUB')  # Default to EPUB
                
                # Estimate file size based on format
                size_estimates = {
                    "EPUB": "1572864",  # 1.5MB
                    "PDF": "3145728",   # 3MB
                    "MOBI": "2097152",  # 2MB
                    "TXT": "524288",    # 512KB
                }
                estimated_size = size_estimates.get(file_format, "1572864")
                
                # Construct title
                constructed_title = f"{title} - {author} ({file_format})"
                
                # Build description
                description = f"{title} | {author} | {file_format}"
                
                entry = {
                    "link": book_link,
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
                    "pub_ts": None,
                }
                
                results.append(entry)
                
            except Exception as e:
                print(f"Error converting ManyBooks result: {e}")
                continue
        
        if not results:
            self.last_error = "No results returned"
        return results


def getmyprefix():
    return "manybooks"
