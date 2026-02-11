import os
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "search"
sys.path.insert(0, str(PLUGIN_DIR))

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SELENIUM_LIVE") != "1",
    reason="set RUN_SELENIUM_LIVE=1 to hit real sites via Selenium",
)

from annas_archive import AnnasArchiveSearch  # noqa: E402
from manybooks import ManyBooksSearch  # noqa: E402
from standardebooks import StandardEbooksSearch  # noqa: E402


def _assert_minimal_structure(result):
    required = ["link", "title", "guid", "category", "prefix"]
    for field in required:
        assert field in result, f"missing {field}"
        assert result[field], f"{field} empty"


def _run_live_search(plugin_cls):
    plugin = plugin_cls()
    category = plugin.getcat()[0]
    query = plugin.gettestquery()
    results = plugin.search(query, category)
    assert isinstance(results, list)
    assert results, "expected live search results"
    _assert_minimal_structure(results[0])
    return results


@pytest.mark.integration
def test_annas_archive_live():
    _run_live_search(AnnasArchiveSearch)


@pytest.mark.integration
def test_manybooks_live():
    _run_live_search(ManyBooksSearch)


@pytest.mark.integration
def test_standardebooks_live():
    _run_live_search(StandardEbooksSearch)
