#!/usr/bin/env python3
"""
Download test script - downloads books to ~/Downloads for manual verification
Tests both search and download functionality for working plugins
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
SEARCH_PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "search"
DOWNLOAD_PLUGIN_DIR = BASE_DIR / "config" / "plugins" / "download"
sys.path.insert(0, str(SEARCH_PLUGIN_DIR))
sys.path.insert(0, str(DOWNLOAD_PLUGIN_DIR))

from annas_archive import AnnasArchiveSearch
from standardebooks import StandardEbooksSearch
from annas_archivedl import AnnasArchiveDownload
import requests

# Get user's Downloads folder
DOWNLOAD_DIR = str(Path.home() / "Downloads" / "book_test_downloads")

def ensure_download_dir():
    """Create download directory if it doesn't exist"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"📁 Download directory: {DOWNLOAD_DIR}\n")

def test_annas_archive():
    """Test Anna's Archive search and download"""
    print("="*80)
    print("🔍 ANNA'S ARCHIVE - Search & Download Test")
    print("="*80)
    
    try:
        # Search
        search_plugin = AnnasArchiveSearch()
        query = "python programming"
        category = search_plugin.getcat()[0]
        
        print(f"Searching for: '{query}'...")
        search_results = search_plugin.search(query, category)
        
        if not search_results:
            print("❌ No search results found")
            return None
        
        print(f"✅ Found {len(search_results)} results\n")
        
        # Show first few results
        print("Top 3 results:")
        for i, result in enumerate(search_results[:3], 1):
            print(f"  {i}. {result.get('title')[:80]}")
        
        # Download first result
        first_result = search_results[0]
        print(f"\n📥 Downloading first result...")
        print(f"Title: {first_result.get('title')}")
        print(f"Link: {first_result.get('link')}")
        
        download_plugin = AnnasArchiveDownload()
        result_path = download_plugin.download(
            url=first_result.get('link'),
            title="Annas_Archive_Test",
            download_dir=DOWNLOAD_DIR,
            cat=category
        )
        
        if result_path == "404":
            print("❌ Download failed")
            return None
        
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"\n✅ SUCCESS!")
            print(f"📦 Downloaded: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
            print(f"📍 Location: {result_path}")
            return result_path
        else:
            print(f"❌ File not found at: {result_path}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_standard_ebooks():
    """Test Standard Ebooks search and download"""
    print("\n" + "="*80)
    print("📚 STANDARD EBOOKS - Search & Download Test")
    print("="*80)
    
    try:
        # Search
        search_plugin = StandardEbooksSearch()
        query = search_plugin.gettestquery()  # "wilde"
        category = search_plugin.getcat()[0]
        
        print(f"Searching for: '{query}'...")
        search_results = search_plugin.search(query, category)
        
        if not search_results:
            print("❌ No search results found")
            return None
        
        print(f"✅ Found {len(search_results)} results\n")
        
        # Show first few results
        print("Top 3 results:")
        for i, result in enumerate(search_results[:3], 1):
            print(f"  {i}. {result.get('book_title')} - {result.get('author')}")
        
        # Download first result
        first_result = search_results[0]
        download_url = first_result.get('link')
        
        print(f"\n📥 Downloading first result...")
        print(f"Title: {first_result.get('book_title')} - {first_result.get('author')}")
        print(f"Download URL: {download_url}")
        
        # Download the file
        response = requests.get(download_url, timeout=30, stream=True)
        if response.status_code != 200:
            print(f"❌ Download failed: HTTP {response.status_code}")
            return None
        
        # Save to Downloads
        filename = f"StandardEbooks_{first_result.get('author')}_{first_result.get('book_title')}.epub"
        # Clean filename
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '_', '-', '.')).strip()
        filepath = os.path.join(DOWNLOAD_DIR, category, "StandardEbooks_Test", filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(filepath)
        print(f"\n✅ SUCCESS!")
        print(f"📦 Downloaded: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
        print(f"📍 Location: {filepath}")
        return filepath
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("\n" + "="*80)
    print("📖 BOOK DOWNLOAD TEST")
    print("="*80)
    print("This script will download actual books to verify download functionality\n")
    
    ensure_download_dir()
    
    downloaded_files = []
    
    # Test Anna's Archive
    annas_file = test_annas_archive()
    if annas_file:
        downloaded_files.append(("Anna's Archive", annas_file))
    
    # Test Standard Ebooks
    standard_file = test_standard_ebooks()
    if standard_file:
        downloaded_files.append(("Standard Ebooks", standard_file))
    
    # Final summary
    print("\n" + "="*80)
    print("📊 DOWNLOAD TEST SUMMARY")
    print("="*80)
    
    if downloaded_files:
        print(f"\n✅ Successfully downloaded {len(downloaded_files)} file(s):\n")
        for source, filepath in downloaded_files:
            file_size = os.path.getsize(filepath)
            print(f"  📚 {source}")
            print(f"     File: {os.path.basename(filepath)}")
            print(f"     Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
            print(f"     Path: {filepath}")
            print()
        
        print(f"📂 All downloads are in: {DOWNLOAD_DIR}")
        print(f"\n💡 Open the files above to verify they are valid ebooks!")
    else:
        print("❌ No files were downloaded successfully")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
