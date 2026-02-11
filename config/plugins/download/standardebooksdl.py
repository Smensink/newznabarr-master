import os

import requests

from plugin_download_interface import PluginDownloadBase

USER_AGENT = "Mozilla/5.0 (compatible; Newznabarr/1.0; +https://github.com/)"


class StandardEbooksDownload(PluginDownloadBase):
    """Download handler for StandardEbooks search results."""

    def getprefix(self):
        return ["standardebooks"]

    def download(self, url, title, download_dir, cat, progress_callback=None):
        category = cat or "uncategorized"
        target_dir = os.path.join(download_dir, category, title)
        os.makedirs(target_dir, exist_ok=True)

        try:
            response = requests.get(
                url,
                stream=True,
                timeout=120,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code != 200:
                print(f"StandardEbooks download failed with status {response.status_code} for {url}")
                return "404"

            filename = f"{title}.epub"
            destination = os.path.join(target_dir, filename)

            total_bytes = 0
            try:
                total_bytes = int(response.headers.get("content-length", 0))
            except Exception:
                total_bytes = 0

            downloaded = 0
            with open(destination, "wb") as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes or None)

            return destination
        except Exception as exc:
            print(f"StandardEbooks download error for {url}: {exc}")
            return "404"


def getmyprefix():
    return "standardebooks"
