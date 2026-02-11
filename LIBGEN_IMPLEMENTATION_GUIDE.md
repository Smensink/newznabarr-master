# LibGen Search Implementation Guide

## Overview

This guide explains how to implement a LibGen search client that can query multiple mirrors, parse HTML results, and fetch RSS feeds. The implementation uses parallel requests with automatic failover for reliability.

## Architecture

### 1. Mirror Configuration System

LibGen has multiple mirror domains that may have different availability. The system supports:

- **Default mirrors**: Hardcoded list of known mirrors
- **Custom mirrors**: User-configurable via JSON config
- **Mirror types**: Two parameter styles (`index.php` and `search.php`)

```python
DEFAULT_MIRROR_ENTRIES = [
    "https://libgen.li/index.php",
    "https://libgen.vg/index.php",
    "https://libgen.la/index.php",
    "https://libgen.gl/index.php",
    "https://libgen.bz/index.php",
]
```

**Configuration Loading:**

```python
def get_configured_mirror_entries():
    # 1. Load from config.json if available
    # 2. Normalize each entry (handle both index.php and search.php)
    # 3. Return deduplicated list of entries
```

**Key insight:** Each mirror URL is normalized to create TWO entries:

- `base/index.php` (uses simpler query params)
- `base/search.php` (uses detailed query params)

### 2. Query Parameter Construction

LibGen supports two different parameter formats:

```python
def _make_params(ptype, query, limit):
    if ptype == "index":
        return {
            "req": query,
            "res": limit,
            "columns": "def"
        }
    else:  # "search" type
        return {
            "req": query,
            "lg_topic": "libgen",
            "open": 0,
            "view": "detailed",
            "res": limit,
            "phrase": 1,
            "column": "def",
        }
```

### 3. Parallel Mirror Search

**Strategy:** Query all mirrors in parallel using `ThreadPoolExecutor`, return first successful result.

```python
def libgen_search(query, limit=25, try_mirrors=True, timeout=15):
    errors = []
    mirrors_to_try = LIBGEN_MIRROR_ENTRIES if try_mirrors else LIBGEN_MIRROR_ENTRIES[:1]

    def query_mirror(mirror):
        url = mirror["url"]
        params = _make_params(mirror.get("params_type", "search"), query, limit)
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        results = _parse_table_from_html(resp.text, url)
        if results:
            return results
        else:
            raise Exception("no-results")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_mirror = {executor.submit(query_mirror, m): m for m in mirrors_to_try}
        # as_completed() returns futures as they finish
        for future in concurrent.futures.as_completed(future_to_mirror):
            try:
                results = future.result()
                return results, []  # Return immediately on first success
            except Exception as exc:
                errors.append((mirror["name"], str(exc)))

    return [], errors  # All mirrors failed
```

**Key insight:** The loop exits immediately when ANY mirror returns results, providing fast response times.

### 4. HTML Parsing Strategy

LibGen's HTML structure is **not consistent** across mirrors or over time. The parser uses a multi-layered fallback approach:

#### Step 1: Find the Results Table

```python
def _parse_table_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")

    # Find table containing headers "author" AND "title"
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for idx, row in enumerate(rows):
            header_text = " ".join(cell.get_text(strip=True).lower()
                                  for cell in row.find_all(["td", "th"]))
            if "author" in header_text and "title" in header_text:
                candidate = table
                header_row_index = idx
                break
```

#### Step 2: Map Column Headers

```python
# Extract headers and create index map
headers = [cell.get_text(strip=True).lower()
          for cell in candidate.find_all("tr")[header_row_index].find_all(["td", "th"])]
header_map = {name: idx for idx, name in enumerate(headers) if name}

# Fallback positions if headers are unclear
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
```

#### Step 3: Extract Cell Values with Triple Fallback

```python
def get_by_name(name, fallback_key=None):
    # 1. Try data-title attribute (mobile view)
    for idx, cell in enumerate(cols):
        if cell.get("data-title", "").strip().lower() == name:
            return cols[idx].get_text(strip=True)

    # 2. Try header map
    idx = header_map.get(name)
    if idx is not None:
        return cols[idx].get_text(strip=True)

    # 3. Try fallback position
    if fallback_key:
        idx = fallback_map.get(fallback_key)
        if idx is not None and idx < len(cols):
            return cols[idx].get_text(strip=True)

    return ""
```

#### Step 4: Extract Download Links

```python
# Look for mirror links (usually in ads.php or get.php)
for cell in cols:
    anchor = cell.find("a")
    if anchor and anchor.has_attr("href"):
        raw_link = anchor["href"]
        if "ads.php" in raw_link or "get.php" in raw_link:
            link = urljoin(base_url, raw_link)
            break
```

#### Step 5: Extract Series/Title from Nested Structure

```python
def _extract_series_title(row):
    # LibGen often embeds series in <b> tags
    series_tag = cell.find("b")
    if series_tag:
        series_text = series_tag.get_text(" ", strip=True)
        # Check for tooltip with add/edit date
        link = series_tag.find("a")
        if link:
            meta = link.get("data-original-title") or link.get("title") or ""
            added_ts = parse_added(meta)

    # Find edition links
    links = cell.find_all("a", href=lambda h: h and "edition.php" in h)
    for link in links:
        title_text = link.get_text(strip=True)
        # Extract timestamp from tooltip
```

**Critical insight:** LibGen embeds metadata in HTML attributes like `data-original-title` and `title`, which contain dates and other structured information.

### 5. RSS Feed Implementation

LibGen provides an RSS feed at `https://[mirror]/rss.php`.

#### Multi-Mirror RSS Fallback

```python
def get_rss_feed(self):
    mirrors = get_configured_mirror_entries()

    for mirror in mirrors:
        base_url = mirror["url"]
        # Construct RSS URL from any base URL format
        if "index.php" in base_url:
            rss_url = base_url.replace("index.php", "rss.php")
        elif "search.php" in base_url:
            rss_url = base_url.replace("search.php", "rss.php")
        else:
            rss_url = urljoin(base_url, "rss.php")

        try:
            resp = requests.get(rss_url, timeout=30)
            resp.raise_for_status()
            results = _parse_rss_feed(resp.content)
            if results:
                return results
        except Exception as e:
            continue  # Try next mirror

    return []  # All mirrors failed
```

#### RSS Description Parsing

The RSS feed embeds book metadata in HTML within the `<description>` tag:

```python
def _parse_rss_description(html_desc):
    soup = BeautifulSoup(html_desc, "html.parser")
    data = {}

    # Extract cover image
    img = soup.find("img")
    if img and img.get("src"):
        data["cover"] = urljoin("https://libgen.li", img["src"])

    # Extract title from <b> tag
    bold = soup.find("b")
    if bold:
        data["title"] = bold.get_text(strip=True)

    # Extract metadata from table rows
    # Structure: <td><font color="grey">Key:</font></td><td>Value</td>
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        font = cells[0].find("font", color="grey")
        if not font:
            continue

        key = font.get_text(strip=True).replace(":", "").lower()
        val = cells[1].get_text(strip=True)

        # Parse specific fields
        if key == "size":
            # Format: "1774879 [pdf]"
            match = re.match(r"(\d+)\s*\[(.*?)\]", val)
            if match:
                data["size"] = match.group(1)
                data["extension"] = match.group(2)
```

### 6. Query Optimization

**Number Word Normalization:**

```python
# Convert "book one" to "book 1" and vice versa
NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", ...}
NUMBER_DIGITS = {"1": "one", "2": "two", ...}

def search_libgen(book):
    variants = set()

    # Original query
    variants.add(cleaned)

    # Words to digits: "book one" → "book 1"
    words_to_digits = cleaned
    for word, digit in NUMBER_WORDS.items():
        words_to_digits = re.sub(rf"\b{word}\b", digit, words_to_digits, flags=re.IGNORECASE)
    variants.add(words_to_digits)

    # Digits to words: "book 1" → "book one"
    digits_to_words = cleaned
    for digit, word in NUMBER_DIGITS.items():
        digits_to_words = re.sub(rf"\b{digit}\b", word, digits_to_words, flags=re.IGNORECASE)
    variants.add(digits_to_words)

    # Try each variant until one returns results
    for candidate in variants:
        results, errors = libgen_search(candidate, try_mirrors=True)
        if results:
            return results, errors
```

## Implementation Checklist

To replicate this for another project:

1. **Mirror Management**

   - [ ] Create list of mirror URLs
   - [ ] Implement config loading from JSON
   - [ ] Normalize URLs to handle different endpoints
   - [ ] Support user-configurable mirrors

2. **Parallel Search**

   - [ ] Use `ThreadPoolExecutor` for concurrent requests
   - [ ] Return on first successful result using `as_completed()`
   - [ ] Collect errors from all failures
   - [ ] Set appropriate timeouts (10-15 seconds)

3. **HTML Parsing**

   - [ ] Find results table using header keywords
   - [ ] Create column index map from headers
   - [ ] Implement 3-tier fallback: data-title → header map → position
   - [ ] Extract download links from anchor tags
   - [ ] Parse nested metadata from HTML attributes

4. **RSS Support**

   - [ ] Construct RSS URL from base URLs
   - [ ] Implement mirror fallback for RSS
   - [ ] Parse embedded HTML in RSS descriptions
   - [ ] Extract metadata from table structure

5. **Query Optimization**
   - [ ] Normalize special characters
   - [ ] Convert number words to digits and vice versa
   - [ ] Try multiple query variants

## Testing Strategy

```python
# Test mirror availability
def probe_mirror(entry, query="test", limit=5, timeout=10):
    params = _make_params(entry.get("params_type", "search"), query, limit)
    url = entry["url"]
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    results = _parse_table_from_html(resp.text, url)
    return bool(results), f"Received {len(results)} rows"

# Test RSS feed
def test_rss():
    plugin = LibGenSearch()
    results = plugin.get_rss_feed()
    assert len(results) > 0
    assert "title" in results[0]
    assert "link" in results[0]
```

## Common Pitfalls

1. **HTML Structure Changes**: LibGen's HTML changes frequently. Always use flexible selectors and fallback logic.
2. **Encoding Issues**: Some titles contain special characters. Use `encoding='utf-8'` and proper Unicode handling.
3. **Timeout Handling**: Mirrors can be slow. Use generous timeouts (15-30s) but implement parallel requests.
4. **Link Construction**: Always use `urljoin()` to handle relative URLs correctly.
5. **Empty Results**: A 200 OK response doesn't mean results exist. Always check if parsed data is non-empty.

## Performance Considerations

- **Parallel execution**: Typically 5-10 mirrors × ~2-5 seconds = ~2-5 seconds total (fastest mirror wins)
- **Sequential execution**: 5-10 mirrors × 15 seconds timeout = 75-150 seconds (worst case)
- **Memory**: Minimal, results are returned immediately upon first success
- **Network**: Multiple concurrent connections, ensure firewall/rate limiting won't block
