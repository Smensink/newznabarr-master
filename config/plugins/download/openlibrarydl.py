import mimetypes
import os
from urllib.parse import urlparse

import requests

from plugin_download_interface import PluginDownloadBase


def _guess_extension(response, fallback_url):
    content_disposition = response.headers.get("content-disposition", "")
    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[1].strip('"; ')
        ext = os.path.splitext(filename)[1]
        if ext:
            return ext.lower()

    parsed = urlparse(response.url or fallback_url)
    ext = os.path.splitext(parsed.path)[1]
    if ext:
        return ext.lower()

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type:
        guessed = mimetypes.guess_extension(content_type)
        if guessed:
            return guessed.lower()

    return ".bin"


class OpenLibraryDownload(PluginDownloadBase):
    """Download plugin that handles Open Library / archive.org links."""

    def getprefix(self):
        return ["openlibrary"]

    def download(self, url, title, download_dir, cat, progress_callback=None):
        category = cat or "uncategorized"
        dest_dir = os.path.join(download_dir, category, title)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            response = requests.get(url, stream=True, timeout=120)
            if response.status_code != 200:
                print(f"OpenLibrary download failed with status {response.status_code} for {url}")
                return "404"

            extension = _guess_extension(response, url)
            filename = f"{title}{extension}"
            full_path = os.path.join(dest_dir, filename)

            total_bytes = 0
            try:
                total_bytes = int(response.headers.get("content-length", 0))
            except Exception:
                total_bytes = 0

            downloaded = 0
            with open(full_path, "wb") as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes or None)

            return full_path
        except Exception as exc:
            print(f"OpenLibrary download error for {url}: {exc}")
            return "404"


def getmyprefix():
    return "openlibrary"
