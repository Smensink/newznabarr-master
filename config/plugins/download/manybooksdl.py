import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from plugin_download_interface import PluginDownloadBase
from selenium_helper import SeleniumHelper

VALID_SUFFIXES = [".epub", ".pdf", ".mobi", ".azw3", ".txt", ".zip"]

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _extract_preferred_format(title):
    """Try to infer preferred format from the title suffix (e.g., '(... (EPUB))')."""
    if not title:
        return None
    match = re.search(r"\((EPUB|PDF|MOBI|AZW3|TXT)\)\s*$", title, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def _guess_download_link(html, base_url, preferred_format=None):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    if not anchors:
        return None

    def score(anchor):
        href = anchor["href"].lower()
        text = anchor.get_text(strip=True).lower()
        points = 0
        if "download" in href or "download" in text:
            points += 5
        for suffix in VALID_SUFFIXES:
            if href.endswith(suffix):
                points += 4
                break
        if preferred_format and preferred_format in href:
            points += 3
        if preferred_format and preferred_format in text:
            points += 3
        if anchor.has_attr("data-format") and preferred_format:
            if anchor["data-format"].lower() == preferred_format:
                points += 3
        return points

    best_anchor = max(anchors, key=score)
    if score(best_anchor) == 0:
        return None

    href = best_anchor["href"]
    return urljoin(base_url, href)


class ManyBooksDownload(PluginDownloadBase):
    """Download handler for ManyBooks results."""

    def getprefix(self):
        return ["manybooks"]

    def download(self, url, title, download_dir, cat, progress_callback=None):
        category = cat or "uncategorized"
        dest_dir = os.path.join(download_dir, category, title)
        os.makedirs(dest_dir, exist_ok=True)

        preferred_format = _extract_preferred_format(title)
        html = None
        cookies = {}
        user_agent = DEFAULT_UA

        try:
            html, cookies, user_agent = SeleniumHelper.get_page_source_and_cookies_flaresolverr(
                url, max_timeout=60000
            )
        except Exception as flare_error:
            print(f"ManyBooks FlareSolverr fetch failed: {flare_error}")
            try:
                html = SeleniumHelper.get_page_source(url, wait_for_selector="a[href]", wait_time=45)
            except Exception as selenium_error:
                print(f"ManyBooks Selenium fetch failed: {selenium_error}")
                return "404"

        download_link = _guess_download_link(html, url, preferred_format)
        if not download_link:
            print(f"ManyBooks download link not found on page: {url}")
            return "404"

        headers = {"User-Agent": user_agent or DEFAULT_UA}

        try:
            response = requests.get(
                download_link,
                stream=True,
                timeout=120,
                allow_redirects=True,
                headers=headers,
                cookies=cookies,
            )
        except Exception as exc:
            print(f"ManyBooks download request failed: {exc}")
            return "404"

        if response.status_code != 200:
            print(f"ManyBooks download failed with status {response.status_code} for {download_link}")
            return "404"

        # Try to determine file extension from URL or headers
        extension = ".epub"
        lower_url = download_link.lower()
        for suffix in VALID_SUFFIXES:
            if lower_url.endswith(suffix):
                extension = suffix
                break
        else:
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if "pdf" in content_type:
                extension = ".pdf"
            elif "mobi" in content_type:
                extension = ".mobi"
            elif "plain" in content_type or "text" in content_type:
                extension = ".txt"

        filename = f"{title}{extension}"
        destination = os.path.join(dest_dir, filename)

        total_bytes = 0
        try:
            total_bytes = int(response.headers.get("content-length", 0))
        except Exception:
            total_bytes = 0

        downloaded = 0
        try:
            with open(destination, "wb") as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes or None)
        except Exception as exc:
            print(f"ManyBooks file write failed: {exc}")
            return "404"

        return destination


def getmyprefix():
    return "manybooks"
