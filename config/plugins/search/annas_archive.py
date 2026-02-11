import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
from plugin_search_interface import PluginSearchBase

class AnnasArchiveSearch(PluginSearchBase):
    """
    Anna's Archive search plugin
    Searches annas-archive.org for ebooks
    """
    
    BASE_URL = "https://annas-archive.org"
    
    def getcat(self):
        return ["7020"]  # Books/eBook
    
    def gettestquery(self):
        return "fiction"
    
    def getprefix(self):
        return "annas_archive"
    
    def search(self, query, cat):
        """
        Search Anna's Archive for books matching the query
        Uses Selenium for JavaScript rendering
        """
        self.last_error = None
        if not query:
            self.last_error = "Missing query"
            return []
        
        from selenium_helper import SeleniumHelper
        
        search_url = f"{self.BASE_URL}/search"
        params = {
            "q": query,
        }
        
        # Build full URL with params
        from urllib.parse import urlencode
        full_url = f"{search_url}?{urlencode(params)}"
        
        try:
            # Prefer regular Selenium first so local/test stubs can be used,
            # then fall back to FlareSolverr for anti-bot protected pages.
            try:
                html = SeleniumHelper.get_page_source(
                    full_url,
                    wait_for_selector="a[href]",  # Wait for any links to load
                    wait_time=45
                )
            except Exception as selenium_error:
                print(f"Selenium failed ({selenium_error}), trying FlareSolverr")
                html = SeleniumHelper.get_page_source_flaresolverr(full_url, max_timeout=60000)
            
            books = self._parse_search_results(html)
            results = self._convert_results(books, cat)
            
            print(f"Found {len(results)} results from Anna's Archive")
            if not results:
                self.last_error = "No results returned"
            return results
            
        except Exception as e:
            print(f"Anna's Archive error: {e}")
            self.last_error = str(e)
            return []
    
    def _parse_search_results(self, html):
        """
        Parse the HTML search results page from Anna's Archive
        """
        soup = BeautifulSoup(html, 'html.parser')
        books = []
        
        # Find all links to book detail pages (contain /md5/ in URL)
        md5_links = soup.find_all('a', href=re.compile(r'/md5/[a-f0-9]+'))
        
        # Limit to first 25 unique books
        seen_md5 = set()
        
        for link in md5_links:
            try:
                href = link.get('href', '')
                if not href or '/md5/' not in href:
                    continue
                
                # Extract MD5 from URL
                md5_match = re.search(r'/md5/([a-f0-9]+)', href)
                if not md5_match:
                    continue
                    
                md5 = md5_match.group(1)
                if md5 in seen_md5:
                    continue
                seen_md5.add(md5)
                
                # Use nearest container to extract rich metadata.
                container = link.find_parent(['article', 'li', 'div']) or link.parent
                context_text = container.get_text(" ", strip=True) if container else link.get_text(" ", strip=True)

                # Get title from link text or nearby heading.
                title = link.get_text(strip=True)
                if not title and container:
                    heading = container.find(['h1', 'h2', 'h3', 'strong'])
                    if heading:
                        title = heading.get_text(" ", strip=True)
                if not title and container:
                    title = context_text[:200]  # Last fallback

                if not title or len(title) < 3:
                    continue
                
                book = {
                    'link': f"{self.BASE_URL}{href}" if href.startswith('/') else href,
                    'title': title,
                    'md5': md5,
                }
                
                # Extract metadata from surrounding text.
                author_match = re.search(r'\bby\s+([^|,\n\r]+)', context_text, re.I)
                if author_match:
                    book['author'] = author_match.group(1).strip(" -")

                format_match = re.search(r'\b(epub|pdf|mobi|azw3|djvu|txt)\b', context_text, re.I)
                if format_match:
                    book['extension'] = format_match.group(1).lower()

                size_match = re.search(r'([\d.]+)\s*(MB|KB|GB|B)\b', context_text, re.I)
                if size_match:
                    book['size'] = f"{size_match.group(1)}{size_match.group(2)}"

                lang_match = re.search(
                    r'\b(English|Spanish|French|German|Italian|Portuguese|Dutch|Russian|Japanese|Chinese)\b',
                    context_text,
                    re.I,
                )
                if lang_match:
                    book['language'] = lang_match.group(1)
                
                books.append(book)
                
                if len(books) >= 25:
                    break
                    
            except Exception as e:
                print(f"Error parsing Anna's Archive result: {e}")
                continue
        
        return books
    
    def _convert_results(self, books, cat):
        """
        Convert parsed books to standardized search result format
        """
        results = []
        
        for book in books:
            try:
                link = book.get('link', '')
                title = book.get('title', 'Unknown')
                author = book.get('author', 'Unknown')
                file_format = book.get('extension', '').upper()
                size_str = book.get('size', '0MB')
                language = book.get('language', 'Unknown')
                
                # Convert size to bytes
                size_bytes = self._convert_size_to_bytes(size_str)
                
                # Construct standardized title
                constructed_title = f"{title} - {author}"
                if file_format:
                    constructed_title += f" ({file_format})"
                
                # Build description
                description_parts = [title, author]
                if language:
                    description_parts.append(language)
                if file_format:
                    description_parts.append(file_format)
                description = " | ".join(description_parts)
                
                entry = {
                    "link": link,
                    "title": constructed_title,
                    "description": description,
                    "guid": link,
                    "comments": link,
                    "files": "1",
                    "size": str(size_bytes),
                    "category": cat,
                    "grabs": "100",
                    "prefix": self.getprefix(),
                    "author": author,
                    "book_title": title,
                    "language": language,
                    "format": file_format,
                    "pub_ts": None,
                }
                
                results.append(entry)
                
            except Exception as e:
                print(f"Error converting Anna's Archive result: {e}")
                continue
        
        return results
    
    def _convert_size_to_bytes(self, size_str):
        """
        Convert size string like '2.5MB' to bytes
        """
        if not size_str:
            return "0"
        
        match = re.match(r'([\d.]+)\s*(MB|KB|GB|B)', size_str, re.I)
        if not match:
            return "0"
        
        value = float(match.group(1))
        unit = match.group(2).upper()
        
        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
        }
        
        return str(int(value * multipliers.get(unit, 1)))


def getmyprefix():
    return "annas_archive"
