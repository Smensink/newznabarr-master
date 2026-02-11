#!/usr/bin/env python3
"""
Enhanced download test script that uses download plugins where available
"""
import sys
import os
from pathlib import Path
import tempfile

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
SEARCH_PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "search"
DOWNLOAD_PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "download"
sys.path.insert(0, str(SEARCH_PLUGIN_DIR))
sys.path.insert(0, str(DOWNLOAD_PLUGIN_DIR))

from annas_archive import AnnasArchiveSearch
from standardebooks import StandardEbooksSearch
from annas_archivedl import AnnasArchiveDownload

def test_annas_archive():
    """Test Anna's Archive search AND download"""
    print("\n" + "="*80)
    print("TESTING ANNA'S ARCHIVE (Search + Download)")
    print("="*80)
    
    try:
        # Search
        search_plugin = AnnasArchiveSearch()
        query = "python programming"
        category = search_plugin.getcat()[0]
        
        print(f"Searching for: {query}")
        search_results = search_plugin.search(query, category)
        
        if not search_results:
            print("❌ No search results")
            return False
        
        print(f"✅ Found {len(search_results)} results")
        first_result = search_results[0]
        print(f"\nFirst result:")
        print(f"  Title: {first_result.get('title')}")
        print(f"  Link: {first_result.get('link')}")
        
        # Download
        download_plugin = AnnasArchiveDownload()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"\nAttempting download...")
            result = download_plugin.download(
                url=first_result.get('link'),
                title="test_book",
                download_dir=temp_dir,
                cat=category
            )
            
            if result == "404":
                print("❌ Download failed")
                return False
            
            if os.path.exists(result):
                file_size = os.path.getsize(result)
                print(f"✅ Downloaded {file_size} bytes to {result}")
                
                if file_size < 1024:
                    print(f"⚠️  WARNING: File size is very small")
                    return False
                
                return True
            else:
                print(f"❌ File not found: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_standard_ebooks():
    """Test Standard Ebooks search AND download"""
    print("\n" + "="*80)
    print("TESTING STANDARD EBOOKS (Search + Download)")
    print("="*80)
    
    try:
        # Search
        search_plugin = StandardEbooksSearch()
        query = search_plugin.gettestquery()
        category = search_plugin.getcat()[0]
        
        print(f"Searching for: {query}")
        search_results = search_plugin.search(query, category)
        
        if not search_results:
            print("❌ No search results")
            return False
        
        print(f"✅ Found {len(search_results)} results")
        first_result = search_results[0]
        print(f"\nFirst result:")
        print(f"  Title: {first_result.get('title')}")
        print(f"  Download Link: {first_result.get('link')}")
        
        # For Standard Ebooks, the 'link' field IS the download URL
        # So we can download directly with requests
        import requests
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_url = first_result.get('link')
            print(f"\nDownloading from: {download_url}")
            
            response = requests.get(download_url, timeout=30, stream=True)
            if response.status_code != 200:
                print(f"❌ Download failed: status {response.status_code}")
                return False
            
            filepath = os.path.join(temp_dir, "test_book.epub")
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            print(f"✅ Downloaded {file_size} bytes ({file_size / 1024:.2f} KB)")
            
            if file_size < 1024:
                print(f"⚠️  WARNING: File size is very small")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    results = {}
    
    # Test Anna's Archive
    results['annas_archive'] = test_annas_archive()
    
    # Test Standard Ebooks
    results['standardebooks'] = test_standard_ebooks()
    
    # Summary
    print("\n" + "="*80)
    print("DOWNLOAD TEST SUMMARY")
    print("="*80)
    for plugin, success in results.items():
        icon = '✅' if success else '❌'
        status = 'PASSED' if success else 'FAILED'
        print(f"{icon} {plugin}: {status}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
