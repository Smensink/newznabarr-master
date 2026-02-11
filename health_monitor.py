"""
Plugin and Mirror Health Monitoring System
Tests all search plugins and LibGen mirrors for functionality
"""

import threading
import time
import tempfile
import shutil
import uuid
from datetime import datetime, timezone
from collections import deque

# Global health status
plugin_health = {}
mirror_health = {}
health_lock = threading.Lock()
activity_log = deque(maxlen=100)
activity_lock = threading.Lock()


def log_activity(message, status="info"):
    entry = {
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    with activity_lock:
        activity_log.appendleft(entry)


def get_activity_log(limit=25):
    with activity_lock:
        return list(activity_log)[:limit]


def verify_download_link(url, prefix, download_plugins):
    """
    Verify if a download link is likely to work.
    Returns: (status, message)
    """
    import requests
    
    # Check if we have a download plugin for this prefix
    dl_plugin = next((p for p in download_plugins if prefix in p.getprefix()), None)
    
    if dl_plugin:
        temp_dir = tempfile.mkdtemp(prefix="newznabarr_health_")
        fake_title = f"healthcheck-{uuid.uuid4().hex[:8]}"
        try:
            result = dl_plugin.download(
                url,
                fake_title,
                temp_dir,
                "health",
                progress_callback=lambda *_: None
            )
            if not result or result == "404":
                return ("error", f"{dl_plugin.__class__.__name__} download failed")
            return ("healthy", f"{dl_plugin.__class__.__name__} download OK")
        except Exception as exc:
            return ("error", f"Plugin error: {str(exc)}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    # If no plugin, it might be a direct link.
    # Check if it's a valid URL
    if not url or not url.startswith(('http://', 'https://')):
         return ("warning", "No download plugin & invalid URL")

    # Try a HEAD request to check connectivity
    try:
        # Use a short timeout
        headers = {"User-Agent": "Newznabarr/1.0"}
        r = requests.head(url, headers=headers, allow_redirects=True, timeout=5)
        if r.status_code == 200:
             return ("healthy", "Direct link reachable")
        elif r.status_code in (401, 403):
             return ("error", f"Access denied ({r.status_code})")
        elif r.status_code == 404:
             return ("error", "File not found (404)")
        elif r.status_code == 405:
             # Method Not Allowed (some servers block HEAD)
             return ("warning", "Method Not Allowed (HEAD)")
        else:
             return ("warning", f"HTTP {r.status_code}")
    except Exception as e:
        return ("error", f"Link unreachable: {str(e)[:30]}")


def check_plugin_health(plugin_instance, download_plugins=None):
    """
    Test a single plugin by running its test query
    Returns: (status, message, response_time, download_status, download_message)
    """
    plugin_name = plugin_instance.__class__.__name__
    if download_plugins is None:
        download_plugins = []

    if not getattr(plugin_instance, 'enabled', True):
        return ("disabled", "Plugin disabled", 0, "disabled", "Plugin disabled")
    test_query = plugin_instance.gettestquery()
    cat = plugin_instance.getcat()[0] if plugin_instance.getcat() else "7020"
    
    try:
        start_time = time.time()
        results = plugin_instance.search(test_query, cat)
        response_time = time.time() - start_time
        
        if results and len(results) > 0:
            # Verify download for the first result
            first_result = results[0]
            dl_status, dl_message = verify_download_link(
                first_result.get("link"), 
                first_result.get("prefix", plugin_instance.getprefix()), 
                download_plugins
            )
            return ("healthy", f"OK - {len(results)} results", response_time, dl_status, dl_message)
        else:
            message = getattr(plugin_instance, "last_error", "No results returned")
            return ("warning", message or "No results returned", response_time, "unknown", message or "No results to test")
            
    except Exception as e:
        plugin_instance.last_error = str(e)
        return ("error", str(e), 0, "unknown", "Search failed")


def check_all_plugins(search_plugins, download_plugins=None):
    """
    Check health of all loaded plugins in parallel
    Updates global plugin_health dictionary
    """
    import concurrent.futures
    
    def check_single_plugin(plugin):
        plugin_name = plugin.__class__.__name__
        status, message, response_time, dl_status, dl_message = check_plugin_health(plugin, download_plugins)
        
        return plugin_name, {
            "status": status,
            "message": message,
            "response_time": round(response_time, 2),
            "download_status": dl_status,
            "download_message": dl_message,
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "prefix": plugin.getprefix(),
            "enabled": getattr(plugin, 'enabled', False)
        }
    
    if not search_plugins:
        return plugin_health

    log_activity("Starting plugin health checks", status="info")

    # Run health checks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(search_plugins)) as executor:
        futures = [executor.submit(check_single_plugin, plugin) for plugin in search_plugins]
        for future in concurrent.futures.as_completed(futures):
            try:
                plugin_name, health_info = future.result()
                with health_lock:
                    plugin_health[plugin_name] = health_info
                log_activity(f"Checked plugin {plugin_name}", status="success")
            except Exception as e:
                log_activity(f"Plugin health check failed: {e}", status="error")
                print(f"Error checking plugin health: {e}")
    
    return plugin_health


def check_libgen_mirror(mirror_url):
    """
    Test a single LibGen mirror
    Returns: (status, message, response_time)
    """
    import requests
    
    try:
        # Simple connectivity test
        start_time = time.time()
        response = requests.get(mirror_url, timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            return ("healthy", "OK", response_time)
        else:
            return ("warning", f"HTTP {response.status_code}", response_time)
            
    except requests.exceptions.Timeout:
        return ("error", "Timeout", 0)
    except Exception as e:
        return ("error", str(e)[:50], 0)


def check_all_mirrors(mirrors):
    """
    Check health of all LibGen mirrors in parallel
    Updates global mirror_health dictionary
    """
    import concurrent.futures
    
    def check_single_mirror(mirror):
        status, message, response_time = check_libgen_mirror(mirror)
        return mirror, {
            "status": status,
            "message": message,
            "response_time": round(response_time, 2),
            "last_checked": datetime.now(timezone.utc).isoformat()
        }
    
    if not mirrors:
        return mirror_health

    log_activity("Checking LibGen mirrors", status="info")

    # Run mirror checks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(mirrors)) as executor:
        futures = [executor.submit(check_single_mirror, mirror) for mirror in mirrors]
        for future in concurrent.futures.as_completed(futures):
            try:
                mirror, health_info = future.result()
                with health_lock:
                    mirror_health[mirror] = health_info
                log_activity(f"Mirror {mirror} status: {health_info['status']}", status="success")
            except Exception as e:
                log_activity(f"Mirror check failed: {e}", status="error")
                print(f"Error checking mirror health: {e}")
    
    return mirror_health


def update_plugin_status(plugin_name, status, message):
    """
    Update plugin status during runtime (e.g., after a search error)
    """
    with health_lock:
        if plugin_name in plugin_health:
            plugin_health[plugin_name]["status"] = status
            plugin_health[plugin_name]["message"] = message
            plugin_health[plugin_name]["last_checked"] = datetime.now(timezone.utc).isoformat()


def update_mirror_status(mirror_url, status, message):
    """
    Update mirror status during runtime (e.g., after a search error)
    """
    with health_lock:
        if mirror_url in mirror_health:
            mirror_health[mirror_url]["status"] = status
            mirror_health[mirror_url]["message"] = message
            mirror_health[mirror_url]["last_checked"] = datetime.now(timezone.utc).isoformat()


def get_health_summary():
    """
    Get summary of all health statuses
    """
    with health_lock:
        total_plugins = len(plugin_health)
        healthy_plugins = sum(1 for p in plugin_health.values() if p["status"] == "healthy")
        warning_plugins = sum(1 for p in plugin_health.values() if p["status"] == "warning")
        error_plugins = sum(1 for p in plugin_health.values() if p["status"] == "error")
        disabled_plugins = sum(1 for p in plugin_health.values() if p["status"] == "disabled")
        
        total_mirrors = len(mirror_health)
        healthy_mirrors = sum(1 for m in mirror_health.values() if m["status"] == "healthy")
        
        return {
            "plugins": {
                "total": total_plugins,
                "healthy": healthy_plugins,
                "warning": warning_plugins,
                "error": error_plugins,
                "disabled": disabled_plugins
            },
            "mirrors": {
                "total": total_mirrors,
                "healthy": healthy_mirrors,
                "warning": sum(1 for m in mirror_health.values() if m["status"] == "warning"),
                "error": sum(1 for m in mirror_health.values() if m["status"] == "error")
            }
        }


def run_startup_health_checks(search_plugins, download_plugins, libgen_mirrors):
    """
    Run all health checks on startup in a background thread
    """
    def health_check_thread():
        log_activity("Running startup health checks...", status="info")
        print("Running startup health checks...")
        check_all_plugins(search_plugins, download_plugins)
        check_all_mirrors(libgen_mirrors)
        log_activity("Health checks complete", status="success")
        print("Health checks complete")
    
    thread = threading.Thread(target=health_check_thread, daemon=True)
    thread.start()
