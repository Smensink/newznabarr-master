import mimetypes
import os
from urllib.parse import urlparse

import requests

from plugin_download_interface import PluginDownloadBase

GUTENBERG_SUFFIXES = [
    ".epub3.images",
    ".epub3.noimages",
    ".epub.images",
    ".epub.noimages",
    ".epub",
    ".mobi",
    ".kindle.images",
    ".kindle.noimages",
    ".kindle",
    ".txt.utf-8",
    ".txt",
    ".zip",
    ".htm",
    ".html",
]

CONTENT_TYPE_MAP = {
    "application/epub+zip": ".epub",
    "application/x-mobipocket-ebook": ".mobi",
    "text/plain": ".txt",
    "text/html": ".html",
}

USER_AGENT = "Mozilla/5.0 (compatible; Newznabarr/1.0; +https://github.com/)"  # simple UA


def _derive_extension(response, fallback_url):
    path = urlparse(response.url or fallback_url).path.lower()
    for suffix in GUTENBERG_SUFFIXES:
        if path.endswith(suffix):
            return suffix if suffix.startswith(".") else f".{suffix}"

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type in CONTENT_TYPE_MAP:
        return CONTENT_TYPE_MAP[content_type]

    guessed = mimetypes.guess_extension(content_type)
    if guessed:
        return guessed

    _, ext = os.path.splitext(path)
    if ext:
        return ext

    return ".epub"


class GutendexDownload(PluginDownloadBase):
    """Download handler for Gutendex / Project Gutenberg links."""

    def getprefix(self):
        return ["gutendex"]

    def download(self, url, title, download_dir, cat, progress_callback=None):
        category = cat or "uncategorized"
        destination_dir = os.path.join(download_dir, category, title)
        os.makedirs(destination_dir, exist_ok=True)

        try:
            response = requests.get(
                url,
                stream=True,
                timeout=120,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code != 200:
                print(f"Gutendex download failed with status {response.status_code} for {url}")
                return "404"

            extension = _derive_extension(response, url)
            filename = f"{title}{extension}"
            destination_path = os.path.join(destination_dir, filename)

            total_bytes = 0
            try:
                total_bytes = int(response.headers.get("content-length", 0))
            except Exception:
                total_bytes = 0

            downloaded = 0
            with open(destination_path, "wb") as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes or None)

            return destination_path
        except Exception as exc:
            print(f"Gutendex download error for {url}: {exc}")
            return "404"


def getmyprefix():
    return "gutendex"
