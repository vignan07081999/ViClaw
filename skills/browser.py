import os
import time
import logging
from skills.manager import BaseSkill

class BrowserSkill(BaseSkill):
    name = "Browser Automation"
    description = "Uses a headless Chromium browser to fetch deeply nested/JS-heavy web content or take screenshots."

    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_fetch",
                    "description": "Loads a given URL in a headless browser, waits for JavaScript to render, and extracts the text content. Use this when standard web fetching returns empty or incomplete data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The exact HTTP/HTTPS URL to open."
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_screenshot",
                    "description": "Takes a visual screenshot of a URL. Returns the absolute file path to the saved image, which can be sent back in a message. Use carefully.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The target URL."
                            },
                            "full_page": {
                                "type": "boolean",
                                "description": "If true, captures the entire scrollable page context.",
                                "default": False
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        ]

    def _ensure_playwright(self):
        """Lazy load and check for Playwright."""
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError:
            raise RuntimeError("Playwright is not installed. To use the Browser skill, run `pip install playwright && playwright install chromium`.")

    def browser_fetch(self, url: str) -> str:
        playwright_cm = self._ensure_playwright()
        try:
            with playwright_cm() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=15000)
                
                # Extract text using innerText which respects layout and visibility
                text = page.evaluate("document.body.innerText")
                browser.close()
                
                if not text or not text.strip():
                    return f"Loaded {url}, but the page appeared empty."
                
                max_chars = 10000
                if len(text) > max_chars:
                    text = text[:max_chars] + "... [TRUNCATED]"
                
                return text
                
        except Exception as e:
            logging.error(f"Browser fetch failed for {url}: {e}")
            return f"Error loading page: {e}"

    def browser_screenshot(self, url: str, full_page: bool = False) -> str:
        playwright_cm = self._ensure_playwright()
        
        base_dir = os.path.dirname(os.path.dirname(__file__))
        save_dir = os.path.join(base_dir, "data", "screenshots")
        os.makedirs(save_dir, exist_ok=True)
        
        filename = f"screenshot_{int(time.time())}.png"
        save_path = os.path.join(save_dir, filename)
        
        try:
            with playwright_cm() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_viewport_size({"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle", timeout=15000)
                
                page.screenshot(path=save_path, full_page=full_page)
                browser.close()
                
                return f"Successfully saved screenshot of {url} to: {save_path}"
                
        except Exception as e:
            logging.error(f"Browser screenshot failed for {url}: {e}")
            return f"Error taking screenshot: {e}"
