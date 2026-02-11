import requests
import re
from datetime import datetime, timezone
from plugin_search_interface import PluginSearchBase

class OpenLibrarySearch(PluginSearchBase):
    """
    Open Library / Internet Archive search plugin
    Uses the official Open Library Search API
    """
    
    API_BASE = "https://openlibrary.org/search.json"
    DOWNLOAD_BASE = "https://archive.org/download"
    
    def getcat(self):
        return ["7020"]  # Books/eBook
    
    def gettestquery(self):
        return "sherlock holmes"
    
    def getprefix(self):
        return "openlibrary"
    
    def search(self, query, cat):
        """
        Search Open Library using their official JSON API
        """
        if not query:
            return []
        
        params = {
            "q": query,
            "limit": 25,
            "fields": "key,title,author_name,first_publish_year,language,publisher,isbn,oclc,lccn,ia,has_fulltext,public_scan_b",
        }
        
        try:
            headers = {
                "User-Agent": "Newznabarr/1.0 (Book search aggregator; contact@example.com)"
            }
            response = requests.get(self.API_BASE, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            books = data.get("docs", [])
            
            results = self._convert_results(books, cat)
            print(f"Found {len(results)} results from Open Library")
            return results
            
        except Exception as e:
            print(f"Open Library error: {e}")
            return []
    
    def _convert_results(self, books, cat):
        """
        Convert Open Library API response to standardized format
        """
        results = []
        
        for book in books:
            try:
                # Only include books that have full text available on Internet Archive AND are public scans
                ia_identifiers = book.get("ia", [])
                has_fulltext = book.get("has_fulltext", False)
                public_scan = book.get("public_scan_b", False)
                
                if not ia_identifiers or not isinstance(ia_identifiers, list) or not has_fulltext or not public_scan:
                    continue
                
                # Use first Internet Archive identifier
                ia_id = ia_identifiers[0]
                
                # Build metadata
                title = book.get("title", "Unknown")
                authors = book.get("author_name", ["Unknown"])
                author = authors[0] if authors else "Unknown"
                year = book.get("first_publish_year", "")
                language_codes = book.get("language", [])
                language = language_codes[0] if language_codes else "Unknown"
                publishers = book.get("publisher", [])
                publisher = publishers[0] if publishers else ""
                
                # Internet Archive download link (PDF format)
                download_link = f"{self.DOWNLOAD_BASE}/{ia_id}/{ia_id}.pdf"
                
                # Open Library link for metadata
                ol_key = book.get("key", "")
                ol_link = f"https://openlibrary.org{ol_key}" if ol_key else download_link
                
                # Estimate file size (Open Library doesn't provide this in search API)
                # We'll use a default estimate
                estimated_size = "5242880"  # 5MB default
                
                # Construct title with metadata
                constructed_title = f"{title} - {author}"
                if year:
                    constructed_title += f" ({year})"
                constructed_title += " (PDF)"
                
                # Build description
                description_parts = [title, author]
                if year:
                    description_parts.append(str(year))
                if publisher:
                    description_parts.append(publisher)
                description_parts.append("PDF")
                description = " | ".join(description_parts)
                
                # Get ISBNs if available
                isbns = book.get("isbn", [])
                isbn = isbns[0] if isbns else ""
                
                entry = {
                    "link": download_link,
                    "title": constructed_title,
                    "description": description,
                    "guid": ol_link,
                    "comments": ol_link,
                    "files": "1",
                    "size": estimated_size,
                    "category": cat,
                    "grabs": "100",
                    "prefix": self.getprefix(),
                    "author": author,
                    "book_title": title,
                    "publisher": publisher,
                    "year": str(year) if year else "",
                    "language": language,
                    "format": "PDF",
                    "pub_ts": None,
                }
                
                results.append(entry)
                
            except Exception as e:
                print(f"Error converting Open Library result: {e}")
                continue
        
        return results


def getmyprefix():
    return "openlibrary"
