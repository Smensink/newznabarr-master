#!/usr/bin/env python3
import sys
import os
import json
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add config to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def test_sabnzbd_api():
    print("\n" + "="*60)
    print("🚀 SABNZBD API COMPATIBILITY TEST")
    print("="*60)
    
    try:
        import app
        
        # Mock initialization
        app.CONFIG_DIR = str(BASE_DIR / "config")
        app.sabqueue = []
        app.sabsavequeue = MagicMock()
        app.ensure_download_worker = MagicMock()
        app.log_event = MagicMock()
        
        # Test Case 1: mode=addurl with valid parameters
        print("\n1. Testing mode=addurl (Valid)...")
        
        # Construct a fake NZB URL like Readarr sends
        real_url = "https://example.com/download.epub"
        prefix = "test_plugin"
        title = "Test Book"
        
        nzb_params = {
            "download": "nzb",
            "prefix": prefix,
            "url": real_url,
            "title": title,
            "size": "1024"
        }
        nzb_url = f"http://localhost:10000/api?{urllib.parse.urlencode(nzb_params)}"
        
        params = {
            "mode": "addurl",
            "name": nzb_url,
            "cat": "books",
            "priority": "-100",
            "apikey": "abcde"
        }
        
        # Use test_request_context properly
        with app.app.test_request_context('/api', query_string=params):
            # Call the API
            response_obj = app.api()
            
            # Handle Flask return values (Response object or Tuple)
            if isinstance(response_obj, tuple):
                response, status_code = response_obj
            else:
                response = response_obj
                status_code = response.status_code

            # Verify response
            if status_code != 200:
                print(f"❌ API returned status {status_code}")
                if hasattr(response, 'get_json'):
                        print(f"Response: {response.get_json()}")
                else:
                        print(f"Response: {response}")
                sys.exit(1)
            
            data = response.get_json()
            if not data.get("status"):
                print(f"❌ API returned status: False. Error: {data.get('error')}")
                sys.exit(1)
                
            if not data.get("nzo_ids"):
                print("❌ API did not return nzo_ids")
                sys.exit(1)
                
            print(f"✅ Success! Returned nzo_ids: {data['nzo_ids']}")
            
            # Verify queue
            if len(app.sabqueue) != 1:
                print(f"❌ Queue length incorrect: {len(app.sabqueue)}")
                sys.exit(1)
                
            item = app.sabqueue[0]
            if item["url"] != real_url:
                print(f"❌ Queue item URL mismatch: {item['url']}")
                sys.exit(1)
            if item["title"] != title:
                print(f"❌ Queue item title mismatch: {item['title']}")
                sys.exit(1)
                
            print("✅ Queue item verified correctly")

        # Test Case 2: mode=addurl with invalid NZB URL
        print("\n2. Testing mode=addurl (Invalid URL)...")
        params["name"] = "http://invalid-url.com/nothing"
        
        with app.app.test_request_context('/api', query_string=params):
            response_obj = app.api()
            
            if isinstance(response_obj, tuple):
                response, status_code = response_obj
            else:
                response = response_obj
                status_code = response.status_code
            
            if status_code == 200:
                    data = response.get_json()
                    if data.get("status"):
                        print("❌ Should have failed but succeeded")
                        sys.exit(1)
                    print("✅ Correctly returned status: False")
            elif status_code == 400:
                print("✅ Correctly returned 400 Bad Request")
            else:
                print(f"❌ Unexpected status code: {status_code}")
                sys.exit(1)

        print("\n🎉 SABnzbd API compatibility verified!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_sabnzbd_api()
