import json
import os
import re
import concurrent.futures
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from plugin_search_interface import PluginSearchBase

DEFAULT_MIRROR_ENTRIES = [
    "https://libgen.li/index.php",
    "https://libgen.vg/index.php",
    "https://libgen.la/index.php",
    "https://libgen.gl/index.php",
    "https://libgen.bz/index.php",
]


def _candidate_config_paths():
    paths = []
    config_dir = os.environ.get("CONFIG")
    if config_dir:
        paths.append(os.path.join(config_dir, "config.json"))
    plugin_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    paths.append(os.path.join(plugin_config_dir, "config.json"))
    return paths


def _load_configured_entries():
    for path in _candidate_config_paths():
        try:
            with open(path, "r", encoding="utf-8") as cfg:
                data = json.load(cfg)
            custom_hosts = data.get("libgen_mirrors")
            if isinstance(custom_hosts, list) and custom_hosts:
                return custom_hosts
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as exc:
            print(f"Invalid config while loading LibGen mirrors from {path}: {exc}")
            continue
    return DEFAULT_MIRROR_ENTRIES


def _normalize_entry(entry):
    normalized_entries = []

    params_override = None
    custom_name = None
    url_value = entry

    if isinstance(entry, dict):
        params_override = entry.get("params_type")
        custom_name = entry.get("name")
        url_value = entry.get("url")

    if not url_value:
        return normalized_entries

    url_value = str(url_value).strip()
    if not url_value:
        return normalized_entries

    def build_entry(url, params_type):
        host_name = custom_name or url.split("//", 1)[-1].split("/")[0]
        normalized_entries.append({
            "name": host_name,
            "url": url,
            "params_type": params_type
        })

    if not url_value.startswith(("http://", "https://")):
        url_value = f"http://{url_value.lstrip('/')}"

    lowered = url_value.lower()
    if lowered.endswith("index.php"):
        build_entry(url_value.rstrip("/"), params_override or "index")
    elif lowered.endswith("search.php"):
        build_entry(url_value.rstrip("/"), params_override or "search")
    else:
        base = url_value.rstrip("/")
        build_entry(f"{base}/index.php", params_override or "index")
        build_entry(f"{base}/search.php", params_override or "search")

    return normalized_entries


def get_configured_mirror_entries():
    seen = set()
    entries = []
    for raw in _load_configured_entries():
        for normalized in _normalize_entry(raw):
            key = (normalized["url"], normalized["params_type"])
            if key in seen:
                continue
            seen.add(key)
            entries.append(normalized)
    return entries


def get_configured_mirrors():
    """Return the configured LibGen mirror URLs for tooling/tests."""
    return [entry["url"] for entry in get_configured_mirror_entries()]


LIBGEN_MIRROR_ENTRIES = get_configured_mirror_entries()

def getmyprefix():
    return "libgen"

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
}
NUMBER_DIGITS = {v: k for k, v in NUMBER_WORDS.items()}

def convert_size_to_bytes(size_str):
    normalized = str(size_str).lower()
    try:
        if 'kb' in normalized:
            size_in_bytes = float(normalized.replace('kb', '').strip()) * 1024
        elif 'mb' in normalized:
            size_in_bytes = float(normalized.replace('mb', '').strip()) * 1024 * 1024
        elif 'gb' in normalized:
            size_in_bytes = float(normalized.replace('gb', '').strip()) * 1024 * 1024 * 1024
        else:
            size_in_bytes = float(normalized)
    except ValueError:
        size_in_bytes = 0
    return str(int(size_in_bytes))

def _extract_year(year_value):
    if not year_value:
        return None
    match = re.search(r"\d{4}", str(year_value))
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


def convert_results(books, cat):
    results = []
    for book in books:
        link = book.get("mirror_1")
        if not link:
            continue
        author = (book.get("author") or "Unknown").strip()
        title = (book.get("title") or "Unknown").strip()
        file_format = (book.get("extension") or "").lower()
        size = convert_size_to_bytes(book.get("size", "0"))
        publisher = (book.get("publisher") or "").strip()
        series = (book.get("series") or "").strip()
        constructed_title = f"{series} - {title} - {author}" if series else f"{title} - {author}"
        if file_format:
            constructed_title += f" ({file_format})"
        description_parts = [part for part in [series, title, author, publisher, book.get("year"), book.get("language")] if part]
        if file_format:
            description_parts.append(file_format.upper())
        description = " | ".join(description_parts) or constructed_title

        pub_year = _extract_year(book.get("year"))
        pub_ts = book.get("added_ts")
        age_days = None
        if pub_ts:
            age_days = max(int((datetime.now(timezone.utc) - datetime.fromtimestamp(pub_ts, tz=timezone.utc)).days), 0)
        elif pub_year:
            pub_dt = datetime(pub_year, 1, 1, tzinfo=timezone.utc)
            pub_ts = pub_dt.timestamp()
            age_days = max(int((datetime.now(timezone.utc) - pub_dt).days), 0)

        entry = {
            "link": link,
            "title": constructed_title,
            "description": description or constructed_title,
            "guid": link,
            "comments": link,
            "files": "1",
            "size": size,
            "category": cat,
            "grabs": "100",
            "prefix": getmyprefix(),
            "author": author,
            "book_title": title,
            "publisher": publisher,
            "series": series,
            "year": book.get("year"),
            "language": book.get("language"),
            "format": file_format.upper() if file_format else "",
            "pub_ts": pub_ts,
            "age": age_days,
        }
        results.append(entry)
    return results


def _make_params(ptype, query, limit):
    if ptype == "index":
        return {"req": query, "res": limit, "columns": "def"}
    return {
        "req": query,
        "lg_topic": "libgen",
        "open": 0,
        "view": "detailed",
        "res": limit,
        "phrase": 1,
        "column": "def",
    }


def _parse_table_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    candidate = None
    header_row_index = None
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for idx, row in enumerate(rows):
            # Clean header text: remove non-alphanumeric chars except spaces to handle sort arrows etc
            header_text = " ".join(re.sub(r"[^a-z0-9\s]", "", cell.get_text(strip=True).lower()) for cell in row.find_all(["td", "th"]))
            if "author" in header_text and "title" in header_text:
                candidate = table
                header_row_index = idx
                break
        if candidate:
            break

    if not candidate or header_row_index is None:
        return []

    header_cells = candidate.find_all("tr")[header_row_index].find_all(["td", "th"])
    # Clean individual headers
    headers = [re.sub(r"[^a-z0-9\s]", "", cell.get_text(strip=True).lower()).strip() for cell in header_cells]
    header_map = {name: idx for idx, name in enumerate(headers) if name}
    
    # Updated fallback map based on libgen.li structure
    fallback_map = {
        "id": 0,
        "author": 1,
        "title": 0,
        "publisher": 2,
        "year": 3,
        "pages": 5,
        "language": 4,
        "size": 6,
        "extension": 7,
    }

    data_rows = candidate.find_all("tr")[header_row_index + 1 :]
    results = []
    for row in data_rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        cell_labels = [re.sub(r"[^a-z0-9\s]", "", cell.get("data-title", "").strip().lower()) for cell in cols]

        def get_by_name(name, fallback_key=None):
            target = name.lower()
            # Try to find by data-title first
            for idx, lbl in enumerate(cell_labels):
                if lbl == target:
                    return cols[idx].get_text(strip=True)
            
            # Try header map
            idx = header_map.get(name)
            
            # Try fallback map
            if idx is None and fallback_key:
                idx = fallback_map.get(fallback_key)
                
            if idx is None or idx >= len(cols):
                return ""
            return cols[idx].get_text(strip=True)

        col_text = [c.get_text(strip=True) for c in cols]

        def col(idx):
            return col_text[idx] if idx < len(col_text) else ""

        link = None
        try:
            # Look for the mirror link in the last column or specific mirror columns
            # Usually mirrors are in columns 9, 10, 11 etc.
            # But for libgen.li it seems to be in column 9 (index 9) or similar.
            # Let's try to find any link that looks like a download link
            for cell in cols:
                anchor = cell.find("a")
                if anchor and anchor.has_attr("href"):
                    raw_link = anchor["href"]
                    if "ads.php" in raw_link or "get.php" in raw_link:
                         link = urljoin(base_url, raw_link)
                         break
        except Exception:
            link = None

        author_value = get_by_name("authors", "author") or col(1)
        publisher_value = get_by_name("publisher", "publisher") or col(2)
        year_value = get_by_name("year", "year") or col(3)
        language_value = get_by_name("language", "language") or col(4)
        size_value = get_by_name("size", "size") or col(6)
        extension_value = get_by_name("ext", "extension") or col(7)

        series_hint, title_hint, added_ts, publisher_hint, year_hint, language_hint, format_hint = _extract_series_title(row)
        title_value = title_hint or get_by_name("title", "title")
        series_value = series_hint or get_by_name("series")

        results.append({
            "id": get_by_name("id", "id"),
            "author": author_value,
            "title": title_value,
            "publisher": publisher_hint or publisher_value,
            "series": series_value,
            "year": year_hint or year_value,
            "language": language_hint or language_value,
            "size": size_value,
            "extension": extension_value or format_hint,
            "mirror_1": link,
            "added_ts": added_ts,
        })
    return results


def _extract_series_title(row):
    series_text = ""
    title_text = ""
    format_hint = ""
    publisher = ""
    year_value = ""
    language = ""
    added_ts = None

    def parse_added(meta):
        if not meta:
            return None
        match = re.search(r"Add/Edit\s*:\s*(\d{4}-\d{2}-\d{2})", meta)
        if match:
            dt = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.timestamp()
        return None

    cells = row.find_all("td")
    if len(cells) >= 8:
        # These indices are based on the observed structure of libgen.li
        # 0: Composite (ID/Title/Series), 1: Author, 2: Publisher, 3: Year, 4: Language, 5: Pages, 6: Size, 7: Extension, 8: Mirrors
        format_hint = cells[7].get_text(strip=True)
        publisher = cells[2].get_text(strip=True)
        year_value = cells[3].get_text(strip=True)
        language = cells[4].get_text(strip=True)

    for cell in cells:
        series_tag = cell.find("b")
        if series_tag:
            raw_series = series_tag.get_text(" ", strip=True)
            series_text = re.sub(r"Add/Edit:.*", "", raw_series).strip()
            link = series_tag.find("a")
            if link:
                # Check both data-original-title and title attributes
                meta = link.get("data-original-title") or link.get("title") or ""
                added_ts = added_ts or parse_added(meta)
        
        links = cell.find_all("a", href=lambda h: h and "edition.php" in h)
        for link in links:
            text = link.get_text(strip=True)
            if not text or "Add/Edit" in text:
                continue
            if series_text and text.startswith(series_text):
                continue
            title_text = text
            meta = link.get("data-original-title") or link.get("title") or ""
            added_ts = added_ts or parse_added(meta)
            break
        if series_text or title_text:
            break
    return (
        series_text.strip(),
        title_text.strip(),
        added_ts,
        publisher.strip(),
        year_value.strip(),
        language.strip(),
        format_hint.strip(),
    )


def libgen_search(query, limit=25, try_mirrors=True, timeout=15):
    errors = []
    mirrors_to_try = LIBGEN_MIRROR_ENTRIES if try_mirrors else LIBGEN_MIRROR_ENTRIES[:1]
    
    def query_mirror(mirror):
        url = mirror["url"]
        params = _make_params(mirror.get("params_type", "search"), query, limit)
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            results = _parse_table_from_html(resp.text, url)
            if results:
                print(f"Found {len(results)} results using mirror: {mirror['name']}")
                return results
            else:
                raise Exception("no-results")
        except (Timeout, ConnectionError) as exc:
            raise Exception(f"network-error: {exc}")
        except RequestException as exc:
            raise Exception(f"http-error: {exc}")
        except Exception as exc:
            raise Exception(f"error: {exc}")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_mirror = {executor.submit(query_mirror, m): m for m in mirrors_to_try}
        for future in concurrent.futures.as_completed(future_to_mirror):
            mirror = future_to_mirror[future]
            try:
                results = future.result()
                return results, []
            except Exception as exc:
                errors.append((mirror["name"], str(exc)))

    print("No results returned from any mirror.")
    for name, err in errors:
        print(f" - {name}: {err}")
    return [], errors


def probe_mirror(entry, query, limit=5, timeout=10):
    """Probe a single LibGen mirror and return (status, message)."""
    params = _make_params(entry.get("params_type", "search"), query, limit)
    url = entry["url"]
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
    except (Timeout, ConnectionError) as exc:
        return False, f"network-error: {exc}"
    except RequestException as exc:
        return False, f"http-error: {exc}"

    results = _parse_table_from_html(resp.text, url)
    if results:
        return True, f"Received {len(results)} rows"
    return False, "No recognizable results"


def search_libgen(book):
    last_errors = []
    try:
        print("Searching for " + book)
        non_standard_chars_pattern = r"[^a-zA-Z0-9\s.]"
        cleaned = book.replace("ø", "o")
        cleaned = re.sub(non_standard_chars_pattern, "", cleaned)
        variants = set()

        def add_variant(text):
            text = re.sub(r"\s+", " ", text.strip())
            if text:
                variants.add(text)

        add_variant(cleaned)
        words_to_digits = cleaned
        for word, digit in NUMBER_WORDS.items():
            words_to_digits = re.sub(rf"\b{word}\b", digit, words_to_digits, flags=re.IGNORECASE)
        add_variant(words_to_digits)
        digits_to_words = cleaned
        for digit, word in NUMBER_DIGITS.items():
            digits_to_words = re.sub(rf"\b{digit}\b", word, digits_to_words, flags=re.IGNORECASE)
        add_variant(digits_to_words)

        for candidate in variants:
            results, errors = libgen_search(candidate, try_mirrors=True)
            if results:
                return results, errors
            last_errors = errors
        return [], last_errors
    except Exception as e:
        print(str(e))
        raise Exception("Error Searching libgen: " + str(e))


def reverse_author_name(name):
    # Split the name by the comma (if it's in the "Last, First" format)
    if ',' in name:
        last_name, first_names = name.split(',', 1)
        last_name = last_name.strip().capitalize()  # Capitalize the last name
        first_names = first_names.strip()
        formatted_first_names = " ".join([first.capitalize() for first in first_names.split()])
        return f"{formatted_first_names} {last_name}"
    else:
        # If no comma, it's just a single word name (e.g., "King")
        return name.capitalize()
        
class LibGenSearch(PluginSearchBase):
    def getcat(self):
        return ["7020"]

    def gettestquery(self):
        return "pride and prejudice"

    def getprefix(self):
        return getmyprefix()

    def search(self, query, cat):
        self.last_error = None
        try:
            books, errors = search_libgen(query)
            if not books:
                if errors:
                    details = "; ".join(f"{name}: {err}" for name, err in errors)
                    self.last_error = f"LibGen mirrors failed - {details}"
                else:
                    self.last_error = "LibGen mirrors returned no usable results"
            results = convert_results(books, cat)
            return results
        except Exception as exc:
            self.last_error = str(exc)
            print(f"LibGenSearch error: {exc}")
            return []

    def get_rss_feed(self):
        """Fetch and parse the LibGen RSS feed with fallback to mirrors."""
        # Use configured mirrors
        mirrors = get_configured_mirror_entries()
        
        for mirror in mirrors:
            base_url = mirror["url"]
            # Construct RSS URL. Assuming mirrors follow similar structure.
            # If base is https://libgen.li/index.php, we want https://libgen.li/rss.php
            if "index.php" in base_url:
                rss_url = base_url.replace("index.php", "rss.php")
            elif "search.php" in base_url:
                rss_url = base_url.replace("search.php", "rss.php")
            else:
                rss_url = urljoin(base_url, "rss.php")
                
            print(f"Trying RSS feed at: {rss_url}")
            try:
                resp = requests.get(rss_url, timeout=30)
                resp.raise_for_status()
                results = _parse_rss_feed(resp.content)
                if results:
                    print(f"Successfully fetched RSS from {rss_url}")
                    return results
            except Exception as e:
                print(f"Error fetching LibGen RSS from {rss_url}: {e}")
                continue
                
        print("All LibGen RSS mirrors failed.")
        return []

def _parse_rss_feed(xml_content):
    soup = BeautifulSoup(xml_content, "xml")
    items = soup.find_all("item")
    results = []
    
    for item in items:
        description = item.find("description").text if item.find("description") else ""
        if not description:
            continue
            
        # Parse the HTML description
        meta = _parse_rss_description(description)
        if not meta:
            continue
            
        # Construct result entry
        # Use ID to construct a consistent link
        book_id = meta.get("id")
        if not book_id:
            continue
            
        link = f"https://libgen.li/file.php?id={book_id}"
        
        # Construct title
        series = meta.get("series", "")
        title = meta.get("title", "")
        author = meta.get("author", "Unknown")
        file_format = meta.get("extension", "").upper()
        
        constructed_title = f"{series} - {title} - {author}" if series else f"{title} - {author}"
        if not title and not series:
             constructed_title = f"Unknown Title - {author}"
        
        if file_format:
            constructed_title += f" ({file_format})"
            
        # Size conversion
        size_str = meta.get("size", "0")
        size_bytes = convert_size_to_bytes(size_str)
        
        entry = {
            "link": link,
            "title": constructed_title,
            "description": constructed_title,
            "guid": link,
            "comments": link,
            "files": "1",
            "size": size_bytes,
            "category": "7020", # Books
            "grabs": "0",
            "prefix": getmyprefix(),
            "author": author,
            "book_title": title or series or "Unknown",
            "publisher": meta.get("publisher", ""),
            "series": series,
            "year": meta.get("year", ""),
            "language": meta.get("language", ""),
            "format": file_format,
            "pub_ts": meta.get("added_ts", datetime.now().timestamp()),
            "age": "0", # New items
            "cover_url": meta.get("cover", "")
        }
        results.append(entry)
        
    return results

def _parse_rss_description(html_desc):
    soup = BeautifulSoup(html_desc, "html.parser")
    data = {}
    
    # Extract Cover
    img = soup.find("img")
    if img and img.get("src"):
        data["cover"] = urljoin("https://libgen.li", img["src"])
        
    # Extract Title (often empty in bold tag)
    bold = soup.find("b")
    if bold:
        data["title"] = bold.get_text(strip=True)
        
    # Extract Metadata from rows
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
            
        # Key is usually in a font tag with color grey
        key_cell = cells[0]
        val_cell = cells[1]
        
        # If first cell has rowspan, key might be in second cell (which is effectively first for that row)
        # But in the HTML structure, the rowspan cell is only in the first row.
        # Subsequent rows have 2 cells: Key, Value.
        # The first row has 3 cells: Image(rowspan), Title(colspan=2).
        
        font = key_cell.find("font", color="grey")
        if not font:
            continue
            
        key = font.get_text(strip=True).replace(":", "").lower()
        val = val_cell.get_text(strip=True)
        
        if key == "author":
            data["author"] = val
        elif key == "series":
            data["series"] = val
        elif key == "language":
            data["language"] = val
        elif key == "publisher":
            data["publisher"] = val
        elif key == "year":
            data["year"] = val
        elif key == "id":
            data["id"] = val
        elif key == "size":
            # Format: 1774879 [pdf]
            match = re.match(r"(\d+)\s*\[(.*?)\]", val)
            if match:
                data["size"] = match.group(1)
                data["extension"] = match.group(2)
            else:
                data["size"] = val
        elif key == "date added":
            try:
                dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                data["added_ts"] = dt.timestamp()
            except ValueError:
                pass
                
    return data
