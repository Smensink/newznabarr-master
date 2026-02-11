import mimetypes
import os
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from plugin_download_interface import PluginDownloadBase

VALID_EXTENSIONS = [".pdf", ".epub", ".mobi", ".azw", ".djvu", ".azw3"]
CONTENT_TYPE_MAPPING = {
    "application/pdf": ".pdf",
    "application/epub+zip": ".epub",
    "application/x-mobipocket-ebook": ".mobi",
    "application/octet-stream": ".epub",  # best effort
}


def _extract_extension(resp, fallback_url):
    content_disposition = resp.headers.get("content-disposition", "")
    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[1].strip('"; ')
        ext = os.path.splitext(filename)[1]
        if ext:
            return ext.lower()

    parsed = urlparse(resp.url or fallback_url)
    ext = os.path.splitext(parsed.path)[1]
    if ext:
        return ext.lower()

    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type in CONTENT_TYPE_MAPPING:
        return CONTENT_TYPE_MAPPING[content_type]

    guessed = mimetypes.guess_extension(content_type)
    if guessed:
        return guessed.lower()

    return ""


class LibGenDownload(PluginDownloadBase):
    def getprefix(self):
        return ["libgen"]

    def download(self, url, title, download_dir, cat, progress_callback=None):
        full_download_dir = os.path.join(download_dir, cat, title)
        os.makedirs(full_download_dir, exist_ok=True)
        print(full_download_dir)
        full_filename = os.path.join(full_download_dir, title)

        response = requests.get(url, timeout=120)
        if response.status_code != 200:
            return "404"

        soup = BeautifulSoup(response.text, "html.parser")
        link_url = None
        download_div = soup.find("div", id="download")
        if download_div:
            candidate_link = download_div.find("a")
            if candidate_link and candidate_link.has_attr("href"):
                link_url = candidate_link["href"]

        if not link_url:
            anchors = soup.find_all("a", href=True)
            for anchor in anchors:
                href = anchor["href"]
                if "get.php" in href and "md5" in href:
                    link_url = href
                    break

        if not link_url:
            elements_with_get = soup.find_all(string=lambda text: "GET" in text.upper())
            for element_text in elements_with_get:
                parent_element = element_text.parent
                anchor = parent_element.find("a") if parent_element else None
                if anchor and anchor.has_attr("href"):
                    link_url = anchor["href"]
                    break

        if not link_url:
            return "404"

        absolute_link = urljoin(url, link_url)
        dl_resp = requests.get(absolute_link, stream=True)
        if dl_resp.status_code != 200:
            return "404"

        extension = _extract_extension(dl_resp, absolute_link)
        if extension not in VALID_EXTENSIONS:
            return "404"

        total_bytes = 0
        try:
            total_bytes = int(dl_resp.headers.get("content-length", 0))
        except Exception:
            total_bytes = 0

        full_filename += extension
        downloaded = 0
        with open(full_filename, "wb") as f:
            for chunk in dl_resp.iter_content(chunk_size=1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_bytes or None)
        return full_filename
