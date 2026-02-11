"""
Selenium Helper Module
Provides headless browser automation for JavaScript-heavy websites
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time

class SeleniumHelper:
    """
    Helper class for headless browser automation
    Uses Chrome in headless mode for scraping JavaScript-rendered content
    """
    
    @staticmethod
    def get_headless_driver():
        """
        Create and return a headless Chrome driver
        """
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            return driver
        except WebDriverException as e:
            print(f"Error creating Chrome driver: {e}")
            print("Make sure Chrome and chromedriver are installed")
            raise
    
    @staticmethod
    def get_page_source(url, wait_for_selector=None, wait_time=10):
        """
        Get page source with optional wait for specific element
        
        Args:
            url: URL to fetch
            wait_for_selector: CSS selector to wait for before getting page source
            wait_time: Maximum time to wait in seconds
            
        Returns:
            Page HTML source as string
        """
        driver = None
        try:
            driver = SeleniumHelper.get_headless_driver()
            driver.get(url)
            
            # Wait for specific element if requested
            if wait_for_selector:
                try:
                    WebDriverWait(driver, wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                    )
                except TimeoutException:
                    print(f"Timeout waiting for selector: {wait_for_selector}")
            else:
                # Generic wait for page to stabilize
                time.sleep(2)
            
            return driver.page_source
            
        finally:
            if driver:
                driver.quit()
    
    @staticmethod
    def get_elements(url, selector, wait_for_selector=None, wait_time=10):
        """
        Get elements matching a CSS selector
        
        Args:
            url: URL to fetch
            selector: CSS selector for elements to extract
            wait_for_selector: CSS selector to wait for before extracting
            wait_time: Maximum time to wait in seconds
            
        Returns:
            List of WebElements
        """
        driver = None
        try:
            driver = SeleniumHelper.get_headless_driver()
            driver.get(url)
            
            # Wait for specific element if requested
            if wait_for_selector:
                try:
                    WebDriverWait(driver, wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                    )
                except TimeoutException:
                    print(f"Timeout waiting for selector: {wait_for_selector}")
                    return []
            else:
                # Generic wait for page to stabilize  
                time.sleep(2)
            
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            # Extract data before closing driver
            results = []
            for elem in elements:
                results.append({
                    'text': elem.text,
                    'html': elem.get_attribute('innerHTML'),
                    'href': elem.get_attribute('href'),
                })
            
            return results
            
        finally:
            if driver:
                driver.quit()
    
    @staticmethod
    def get_page_source_flaresolverr(url, max_timeout=60000):
        """
        Get page source using FlareSolverr to bypass Cloudflare/DDoS-Guard
        
        Args:
            url: URL to fetch
            max_timeout: Maximum time to wait in milliseconds (default 60000)
            
        Returns:
            Page HTML source as string
        """
        import requests
        
        flaresolverr_url = "http://localhost:8191/v1"
        
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout
        }
        
        try:
            response = requests.post(flaresolverr_url, json=payload, timeout=max_timeout/1000 + 10)
            data = response.json()
            
            if data.get("status") == "ok":
                solution = data.get("solution", {})
                return solution.get("response", "")
            else:
                error_msg = data.get("message", "Unknown error")
                raise Exception(f"FlareSolverr error: {error_msg}")
                
        except requests.exceptions.ConnectionError:
            raise Exception("FlareSolverr is not running. Start it with: docker-compose up -d flaresolverr")
        except requests.exceptions.Timeout:
            raise Exception(f"FlareSolverr request timed out after {max_timeout}ms")
        except Exception as e:
            raise Exception(f"FlareSolverr request failed: {e}")

    @staticmethod
    def get_page_source_and_cookies_flaresolverr(url, max_timeout=60000):
        """
        Get page source, cookies, and user agent using FlareSolverr
        
        Returns:
            Tuple (html, cookies_dict, user_agent)
        """
        import requests
        
        flaresolverr_url = "http://localhost:8191/v1"
        
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout
        }
        
        try:
            response = requests.post(flaresolverr_url, json=payload, timeout=max_timeout/1000 + 10)
            data = response.json()
            
            if data.get("status") == "ok":
                solution = data.get("solution", {})
                html = solution.get("response", "")
                cookies = {c['name']: c['value'] for c in solution.get("cookies", [])}
                user_agent = solution.get("userAgent", "")
                return html, cookies, user_agent
            else:
                error_msg = data.get("message", "Unknown error")
                raise Exception(f"FlareSolverr error: {error_msg}")
                
        except Exception as e:
            raise Exception(f"FlareSolverr request failed: {e}")
