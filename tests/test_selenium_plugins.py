import sys
import types
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "search"
sys.path.insert(0, str(PLUGIN_DIR))


def _ensure_selenium_available():
    """Provide lightweight selenium modules so tests can import helpers."""
    try:
        import selenium  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    selenium_pkg = types.ModuleType("selenium")

    # webdriver stubs
    webdriver_mod = types.ModuleType("selenium.webdriver")

    class DummyChrome:
        def __init__(self, *args, **kwargs):
            pass

        def set_page_load_timeout(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            pass

        def quit(self):
            pass

        def find_elements(self, *args, **kwargs):
            return []

    webdriver_mod.Chrome = DummyChrome

    # chrome modules
    chrome_pkg = types.ModuleType("selenium.webdriver.chrome")
    chrome_options_mod = types.ModuleType("selenium.webdriver.chrome.options")

    class Options:
        def __init__(self):
            self.arguments = []

        def add_argument(self, arg):
            self.arguments.append(arg)

    chrome_options_mod.Options = Options

    chrome_service_mod = types.ModuleType("selenium.webdriver.chrome.service")

    class Service:
        def __init__(self, *args, **kwargs):
            pass

    chrome_service_mod.Service = Service

    chrome_pkg.options = chrome_options_mod
    chrome_pkg.service = chrome_service_mod

    # common/by modules
    common_pkg = types.ModuleType("selenium.webdriver.common")
    by_mod = types.ModuleType("selenium.webdriver.common.by")

    class By:
        CSS_SELECTOR = "css selector"

    by_mod.By = By
    common_pkg.by = by_mod

    # support modules
    support_pkg = types.ModuleType("selenium.webdriver.support")
    support_ui_mod = types.ModuleType("selenium.webdriver.support.ui")

    class WebDriverWait:
        def __init__(self, *args, **kwargs):
            pass

        def until(self, *args, **kwargs):
            pass

    support_ui_mod.WebDriverWait = WebDriverWait

    expected_conditions_mod = types.ModuleType("selenium.webdriver.support.expected_conditions")

    def presence_of_element_located(*args, **kwargs):  # pragma: no cover - stub
        return None

    expected_conditions_mod.presence_of_element_located = presence_of_element_located
    support_pkg.expected_conditions = expected_conditions_mod

    # exceptions module
    common_top_pkg = types.ModuleType("selenium.common")
    exceptions_mod = types.ModuleType("selenium.common.exceptions")

    class TimeoutException(Exception):
        pass

    class WebDriverException(Exception):
        pass

    exceptions_mod.TimeoutException = TimeoutException
    exceptions_mod.WebDriverException = WebDriverException
    common_top_pkg.exceptions = exceptions_mod

    # Register modules
    selenium_pkg.webdriver = webdriver_mod
    selenium_pkg.common = common_top_pkg

    sys.modules["selenium"] = selenium_pkg
    sys.modules["selenium.webdriver"] = webdriver_mod
    sys.modules["selenium.webdriver.chrome"] = chrome_pkg
    sys.modules["selenium.webdriver.chrome.options"] = chrome_options_mod
    sys.modules["selenium.webdriver.chrome.service"] = chrome_service_mod
    sys.modules["selenium.webdriver.common"] = common_pkg
    sys.modules["selenium.webdriver.common.by"] = by_mod
    sys.modules["selenium.webdriver.support"] = support_pkg
    sys.modules["selenium.webdriver.support.ui"] = support_ui_mod
    sys.modules["selenium.webdriver.support.expected_conditions"] = expected_conditions_mod
    sys.modules["selenium.common"] = common_top_pkg
    sys.modules["selenium.common.exceptions"] = exceptions_mod

    # Ensure webdriver module exposes chrome/common/support namespaces
    webdriver_mod.chrome = chrome_pkg
    webdriver_mod.common = common_pkg
    webdriver_mod.support = support_pkg


_ensure_selenium_available()

import selenium_helper

from annas_archive import AnnasArchiveSearch  # noqa: E402
from manybooks import ManyBooksSearch  # noqa: E402
from standardebooks import StandardEbooksSearch  # noqa: E402


def _stub_page_source(monkeypatch, html):
    """Replace Selenium page retrieval with deterministic HTML."""

    def fake_page_source(url, wait_for_selector=None, wait_time=10):
        return html

    monkeypatch.setattr(
        selenium_helper.SeleniumHelper,
        "get_page_source",
        staticmethod(fake_page_source),
    )


def test_annas_archive_parses_metadata(monkeypatch):
    html = """
    <html>
      <body>
        <div class="h-[125]">
          <a href="/md5/abc123"></a>
          <h3>Pride and Prejudice</h3>
          <div class="line-clamp-[2]">English EPUB 1.5 MB</div>
          <div>By Jane Austen</div>
        </div>
      </body>
    </html>
    """
    _stub_page_source(monkeypatch, html)

    plugin = AnnasArchiveSearch()
    results = plugin.search("pride", "7020")

    assert len(results) == 1
    result = results[0]
    assert result["category"] == "7020"
    assert result["prefix"] == plugin.getprefix()
    assert result["author"] == "Jane Austen"
    assert result["format"] == "EPUB"
    assert result["language"] == "English"
    assert result["size"] == str(int(1.5 * 1024 * 1024))


def test_manybooks_returns_estimated_size(monkeypatch):
    html = """
    <div class="book-info">
      <h2>The Time Machine</h2>
      <span class="author">H. G. Wells</span>
      <a href="/book/time-machine">Details</a>
      <div>Available formats: EPUB | PDF</div>
    </div>
    """
    _stub_page_source(monkeypatch, html)

    plugin = ManyBooksSearch()
    results = plugin.search("time machine", "7020")

    assert len(results) == 1
    result = results[0]
    assert result["category"] == "7020"
    assert result["prefix"] == plugin.getprefix()
    assert result["format"] == "EPUB"
    assert result["size"] == "1572864"
    assert result["link"] == "https://manybooks.net/book/time-machine"


def test_standardebooks_filters_by_query(monkeypatch):
    html = """
    <ul>
      <li class="ebook">
        <a href="/ebooks/oscar-wilde_the-picture-of-dorian-gray">
          <span itemprop="name">The Picture of Dorian Gray</span>
          <span itemprop="author">Oscar Wilde</span>
        </a>
      </li>
      <li class="ebook">
        <a href="/ebooks/mary-shelley_frankenstein">
          <span itemprop="name">Frankenstein</span>
          <span itemprop="author">Mary Shelley</span>
        </a>
      </li>
    </ul>
    """
    _stub_page_source(monkeypatch, html)

    plugin = StandardEbooksSearch()
    results = plugin.search("wilde", "7020")

    assert len(results) == 1
    result = results[0]
    assert result["category"] == "7020"
    assert result["prefix"] == plugin.getprefix()
    assert result["book_title"] == "The Picture of Dorian Gray"
    assert result["link"].endswith(".epub")
    assert result["guid"].startswith("https://standardebooks.org/ebooks/oscar-wilde")
