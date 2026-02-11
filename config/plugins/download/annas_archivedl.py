import os
import re
import requests
from bs4 import BeautifulSoup
from plugin_download_interface import PluginDownloadBase
from selenium_helper import SeleniumHelper

class AnnasArchiveDownload(PluginDownloadBase):
    """
    Download plugin for Anna's Archive
    Handles downloading ebooks from Anna's Archive detail pages
    """
    
    BASE_URL = "https://annas-archive.org"
    
    def getprefix(self):
        return ["annas_archive"]
    
    def download(self, url, title, download_dir, cat, progress_callback=None):
        """
        Download a book from Anna's Archive
        
        Args:
            url: URL to the book detail page (e.g., https://annas-archive.org/md5/...)
            title: Title of the book
            download_dir: Directory to save the file
            cat: Category
            
        Returns:
            Path to downloaded file or "404" on error
        """
        # Create download directory
        full_download_dir = os.path.join(download_dir, cat, title)
        os.makedirs(full_download_dir, exist_ok=True)
        
        try:
            # Extract MD5 from detail page URL
            md5_match = re.search(r'/md5/([a-f0-9]+)', url)
            if not md5_match:
                print(f"Could not extract MD5 from URL: {url}")
                return "404"
            
            md5 = md5_match.group(1)
            
            # Get the detail page to find download links
            # Get the detail page to find download links
            # Get the detail page to find download links
            # Try FlareSolverr first to bypass DDoS-Guard
            print(f"Fetching detail page: {url}")
            cookies = {}
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            
            try:
                print(f"Attempting with FlareSolverr...")
                html, cookies, user_agent = SeleniumHelper.get_page_source_and_cookies_flaresolverr(url, max_timeout=60000)
                print(f"FlareSolverr succeeded, got {len(cookies)} cookies and UA: {user_agent[:30]}...")
            except Exception as flare_error:
                print(f"FlareSolverr failed ({flare_error}), trying direct request")
                # Fallback to direct request
                response = requests.get(url, timeout=30)
                if response.status_code != 200:
                    print(f"Failed to fetch detail page: {response.status_code}")
                    return "404"
                html = response.text
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for download links
            # Prioritize slow downloads as they are more likely to work for free users/automation
            download_link = None
            
            # Check slow downloads first
            slow_download_links = soup.find_all('a', href=re.compile(rf'/slow_download/{md5}/'))
            if slow_download_links:
                # Use the first slow download link
                download_link = slow_download_links[0].get('href')
                print(f"Found slow download link: {download_link}")
            
            # If no slow download, try fast download
            if not download_link:
                fast_download_links = soup.find_all('a', href=re.compile(rf'/fast_download/{md5}/'))
                if fast_download_links:
                    download_link = fast_download_links[0].get('href')
                    print(f"Found fast download link: {download_link}")
            
            if not download_link:
                print(f"No download links found on page")
                return "404"
            
            # Construct absolute URL
            if download_link.startswith('/'):
                download_url = f"{self.BASE_URL}{download_link}"
            else:
                download_url = download_link
            
            print(f"Downloading from: {download_url}")
            
            # Download the file using cookies and UA from FlareSolverr
            headers = {
                'User-Agent': user_agent
            }
            dl_response = requests.get(
                download_url, 
                cookies=cookies, 
                headers=headers,
                timeout=120, 
                stream=True, 
                allow_redirects=True
            )
            
            if dl_response.status_code != 200:
                print(f"Download failed: {dl_response.status_code}")
                # Try one more time with FlareSolverr for the download URL itself if direct fails
                try:
                    print("Direct download failed, trying to get download URL via FlareSolverr...")
                    # Note: FlareSolverr returns text, so this only works if we can get the final URL or cookies
                    # But we can try to refresh cookies
                    _, new_cookies, _ = SeleniumHelper.get_page_source_and_cookies_flaresolverr(download_url, max_timeout=60000)
                    cookies.update(new_cookies)
                    dl_response = requests.get(
                        download_url, 
                        cookies=cookies, 
                        headers=headers,
                        timeout=120, 
                        stream=True, 
                        allow_redirects=True
                    )
                except:
                    pass
            
            if dl_response.status_code != 200:
                print(f"Download failed after retry: {dl_response.status_code}")
                return "404"
            
            # Determine file extension
            extension = self._get_extension(dl_response, download_url)
            if not extension:
                extension = '.epub'  # Default fallback
            
            # Save the file
            filename = f"{title}{extension}"
            full_filename = os.path.join(full_download_dir, filename)
            
            total_bytes = 0
            try:
                total_bytes = int(dl_response.headers.get('content-length', 0))
            except Exception:
                total_bytes = 0
            downloaded = 0
            with open(full_filename, 'wb') as f:
                for chunk in dl_response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes or None)
            
            file_size = os.path.getsize(full_filename)
            print(f"Downloaded {file_size} bytes to {full_filename}")
            
            return full_filename
            
        except Exception as e:
            print(f"Error downloading from Anna's Archive: {e}")
            import traceback
            traceback.print_exc()
            return "404"
    
    def _get_extension(self, response, url):
        """Extract file extension from response headers or URL"""
        # Check Content-Disposition header
        content_disposition = response.headers.get('content-disposition', '')
        if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"; ')
            ext = os.path.splitext(filename)[1]
            if ext:
                return ext.lower()
        
        # Check URL path
        from urllib.parse import urlparse
        parsed = urlparse(response.url or url)
        ext = os.path.splitext(parsed.path)[1]
        if ext:
            return ext.lower()
        
        # Check Content-Type
        content_type = response.headers.get('content-type', '').lower()
        content_type_map = {
            'application/epub+zip': '.epub',
            'application/pdf': '.pdf',
            'application/x-mobipocket-ebook': '.mobi',
            'application/vnd.amazon.ebook': '.azw3',
        }
        
        for ct, extension in content_type_map.items():
            if ct in content_type:
                return extension
        
        return None


def getmyprefix():
    return "annas_archive"
