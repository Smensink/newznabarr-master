"""
Test script to verify all search plugins are working correctly
Tests each plugin individually and validates response format
"""

import pytest

pytestmark = pytest.mark.skip("manual plugin health check script")

import sys
import os

sys.path.append(os.getcwd())

# Import required modules
from health_monitor import check_plugin_health, check_all_plugins
import importlib

def test_individual_plugin(plugin_path):
    """Load and test a single plugin"""
    print(f"\n{'='*80}")
    print(f"Testing: {plugin_path}")
    print('='*80)
    
    try:
        # Load the plugin module
        plugin_name = os.path.basename(plugin_path).replace('.py', '')
        sys.path.insert(0, os.path.dirname(plugin_path))
        module = importlib.import_module(plugin_name)
        
        # Find the plugin class
        from plugin_search_interface import PluginSearchBase
        plugin_instance = None
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, PluginSearchBase) and obj is not PluginSearchBase:
                plugin_instance = obj()
                break
        
        if not plugin_instance:
            print(f"❌ ERROR: No plugin class found in {plugin_name}")
            return False
        
        print(f"✓ Plugin loaded: {plugin_instance.__class__.__name__}")
        print(f"  Prefix: {plugin_instance.getprefix()}")
        print(f"  Categories: {plugin_instance.getcat()}")
        print(f"  Test query: {plugin_instance.gettestquery()}")
        
        # Run health check
        status, message, response_time = check_plugin_health(plugin_instance)
        
        print(f"\n  Status: {status}")
        print(f"  Response Time: {response_time:.2f}s")
        print(f"  Message: {message}")
        
        if status == "healthy":
            # Get actual results to inspect
            test_query = plugin_instance.gettestquery()
            cat = plugin_instance.getcat()[0]
            results = plugin_instance.search(test_query, cat)
            
            if results and len(results) > 0:
                print(f"\n  ✓ Returned {len(results)} results")
                
                # Inspect first result
                first_result = results[0]
                print(f"\n  First Result Structure:")
                required_fields = ['link', 'title', 'description', 'guid', 'size', 'category', 'prefix']
                
                for field in required_fields:
                    value = first_result.get(field, 'MISSING')
                    icon = "✓" if value != 'MISSING' else "✗"
                    print(f"    {icon} {field}: {str(value)[:100]}")
                
                # Check optional metadata fields
                print(f"\n  Optional Metadata:")
                optional_fields = ['author', 'book_title', 'publisher', 'year', 'language', 'format']
                for field in optional_fields:
                    value = first_result.get(field)
                    if value:
                        print(f"    ✓ {field}: {str(value)[:100]}")
                
                return True
            else:
                print(f"  ⚠️  Search returned but no results")
                return False
        else:
            print(f"  ❌ Plugin health check failed")
            return False
            
    except Exception as e:
        print(f"❌ ERROR testing {plugin_path}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.dirname(plugin_path) in sys.path:
            sys.path.remove(os.path.dirname(plugin_path))


if __name__ == "__main__":
    print("="*80)
    print("PLUGIN HEALTH CHECK TEST")
    print("="*80)
    
    plugin_dir = "config/plugins/search"
    plugins_to_test = [
        "libgen.py",
        "annas_archive.py",
        "openlibrary.py",
        "gutendex.py",
        "standardebooks.py",
        "manybooks.py"
    ]
    
    results = {}
    
    for plugin_file in plugins_to_test:
        plugin_path = os.path.join(plugin_dir, plugin_file)
        if os.path.exists(plugin_path):
            results[plugin_file] = test_individual_plugin(plugin_path)
        else:
            print(f"\n⚠️  Plugin not found: {plugin_path}")
            results[plugin_file] = False
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed
    
    for plugin, status in results.items():
        icon = "✓" if status else "✗"
        print(f"  {icon} {plugin}")
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
    
    if failed > 0:
        print(f"\n⚠️  {failed} plugin(s) failed. Check output above for details.")
    else:
        print(f"\n✓ All plugins passed!")
