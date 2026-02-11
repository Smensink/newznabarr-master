import requests
import re
from plugin_search_interface import PluginSearchBase

class GutendexSearch(PluginSearchBase):
    """
    Project Gutenberg search plugin via Gutendex API
    Searches public domain classic literature
    """
    
    API_BASE = "https://gutendex.com/books"
    
    def getcat(self):
        return ["7020"]  # Books/eBook
    
    def gettestquery(self):
        return "shakespeare"
    
    def getprefix(self):
        return "gutendex"
    
    def search(self, query, cat):
        """
        Search Project Gutenberg via Gutendex API
        """
        self.last_error = None
        if not query:
            self.last_error = "Missing query"
            return []
        
        params = {
            "search": query,
        }
        
        try:
            response = requests.get(self.API_BASE, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            books = data.get("results", [])
            
            results = self._convert_results(books, cat)
            print(f"Found {len(results)} results from Project Gutenberg (Gutendex)")
            if not results:
                self.last_error = "No results returned"
            return results
            
        except Exception as e:
            print(f"Gutendex error: {e}")
            self.last_error = str(e)
            return []
    
    def _convert_results(self, books, cat):
        """
        Convert Gutendex API response to standardized format
        """
        results = []
        
        for book in books:
            try:
                title = book.get("title", "Unknown")
                authors_list = book.get("authors", [])
                author = authors_list[0].get("name", "Unknown") if authors_list else "Unknown"
                
                # Get formats
                formats = book.get("formats", {})
                
                # Prefer EPUB, then MOBI, then TXT
                preferred_formats = [
                    ("application/epub+zip", "EPUB"),
                    ("application/x-mobipocket-ebook", "MOBI"),
                    ("text/plain; charset=utf-8", "TXT"),
                ]
                
                download_link = None
                file_format = None
                
                for format_key, format_name in preferred_formats:
                    if format_key in formats:
                        download_link = formats[format_key]
                        file_format = format_name
                        break
                
                if not download_link:
                    # Skip if no suitable format found
                    continue
                
                # Get additional metadata
                languages = book.get("languages", ["en"])
                language = languages[0] if languages else "en"
                download_count = book.get("download_count", 0)
                
                # Estimate file size (Gutendex doesn't provide this)
                size_estimates = {
                    "EPUB": "1048576",  # 1MB
                    "MOBI": "2097152",  # 2MB
                    "TXT": "524288",    # 512KB
                }
                estimated_size = size_estimates.get(file_format, "1048576")
                
                # Construct title
                constructed_title = f"{title} - {author} ({file_format})"
                
                # Build description
                description = f"{title} | {author} | {file_format} | Public Domain"
                
                # Gutenberg Project ID and link
                gutenberg_id = book.get("id", "")
                gutenberg_link = f"https://www.gutenberg.org/ebooks/{gutenberg_id}" if gutenberg_id else download_link
                
                entry = {
                    "link": download_link,
                    "title": constructed_title,
                    "description": description,
                    "guid": gutenberg_link,
                    "comments": gutenberg_link,
                    "files": "1",
                    "size": estimated_size,
                    "category": cat,
                    "grabs": str(download_count) if download_count > 0 else "100",
                    "prefix": self.getprefix(),
                    "author": author,
                    "book_title": title,
                    "language": language,
                    "format": file_format,
                    "pub_ts": None,
                }
                
                results.append(entry)
                
            except Exception as e:
                print(f"Error converting Gutendex result: {e}")
                continue
        
        return results


def getmyprefix():
    return "gutendex"
