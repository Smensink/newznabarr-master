import requests
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/Users/sebastianmensink/Downloads/newznabarr-master")
from selenium_helper import SeleniumHelper

url = "https://manybooks.net/titles/adamsnother06success_creation.html" # Example URL from search results

print(f"Fetching {url} with FlareSolverr...")
try:
    html = SeleniumHelper.get_page_source_flaresolverr(url)
    print("Success!")
    with open("manybooks_detail.html", "w") as f:
        f.write(html)
    print("Saved to manybooks_detail.html")
except Exception as e:
    print(f"Error: {e}")
