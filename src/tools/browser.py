"""Browser interaction tools for agents."""
import logging
import time
from typing import Any

from .base import BaseTool
from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm, get_html_summary

logger = logging.getLogger(__name__)


class NavigateTool(BaseTool):
    """Navigate browser to URL."""

    name = "browser_navigate"
    description = "Navigate the browser to a specified URL and wait for page load."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self, url: str) -> dict[str, Any]:
        try:
            logger.info(f">>> BROWSER NAVIGATING TO: {url}")
            result = self.session.navigate(url)
            logger.info(f">>> BROWSER NAVIGATION COMPLETE: {url}")
            return {
                "success": True,
                "result": f"Navigated to {url}",
                "details": result
            }
        except Exception as e:
            logger.error(f">>> BROWSER NAVIGATION FAILED: {e}")
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to"
                }
            },
            "required": ["url"]
        }


class GetHTMLTool(BaseTool):
    """Get current page HTML."""

    name = "browser_get_html"
    description = """Get the HTML content of the current page.
    By default returns cleaned HTML (body only, no scripts/styles/base64).
    Set raw=true to get unprocessed HTML."""

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self, raw: bool = False) -> dict[str, Any]:
        try:
            html = self.session.get_html()
            original_length = len(html)

            if not raw:
                # Clean HTML for LLM consumption
                html = clean_html_for_llm(html)
                summary = get_html_summary(html)
                logger.info(
                    f"HTML cleaned: {original_length} -> {len(html)} bytes "
                    f"({summary['reduction_percent']}% reduction)"
                )

            # Truncate if still too large
            if len(html) > 150000:
                html = html[:150000] + "\n... [TRUNCATED]"

            return {
                "success": True,
                "result": html,
                "original_length": original_length,
                "cleaned_length": len(html),
                "raw": raw
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "raw": {
                    "type": "boolean",
                    "description": "If true, return raw HTML without cleaning. Default: false"
                }
            }
        }


class ClickTool(BaseTool):
    """Click element on page."""

    name = "browser_click"
    description = "Click an element on the page using a CSS selector."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self, selector: str) -> dict[str, Any]:
        try:
            result = self.session.click(selector)
            if result.get("success"):
                return {
                    "success": True,
                    "result": f"Clicked element: {selector}"
                }
            return {
                "success": False,
                "error": result.get("error", "Click failed")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for element to click"
                }
            },
            "required": ["selector"]
        }


class QuerySelectorTool(BaseTool):
    """Query elements by selector."""

    name = "browser_query"
    description = "Find all elements matching a CSS selector and return their text/href."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self, selector: str) -> dict[str, Any]:
        try:
            elements = self.session.query_selector_all(selector)
            return {
                "success": True,
                "result": elements,
                "count": len(elements)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to query"
                }
            },
            "required": ["selector"]
        }


class WaitTool(BaseTool):
    """Wait for element or time."""

    name = "browser_wait"
    description = "Wait for a selector to appear or for specified seconds."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(
        self,
        selector: str | None = None,
        seconds: int | None = None
    ) -> dict[str, Any]:
        try:
            if seconds:
                time.sleep(seconds)
                return {
                    "success": True,
                    "result": f"Waited {seconds} seconds"
                }
            elif selector:
                found = self.session.wait_for_selector(selector)
                if found:
                    return {
                        "success": True,
                        "result": f"Found element: {selector}"
                    }
                return {
                    "success": False,
                    "error": f"Timeout waiting for: {selector}"
                }
            return {
                "success": False,
                "error": "Must provide selector or seconds"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to wait for"
                },
                "seconds": {
                    "type": "integer",
                    "description": "Number of seconds to wait"
                }
            }
        }


class ExtractLinksTool(BaseTool):
    """Extract all links from page."""

    name = "browser_extract_links"
    description = "Extract all links (<a> tags) from the current page with their text and URLs."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self) -> dict[str, Any]:
        try:
            elements = self.session.query_selector_all("a[href]")
            links = [
                {"text": el["text"], "href": el["href"]}
                for el in elements
                if el.get("href") and not el["href"].startswith("javascript:")
            ]
            return {
                "success": True,
                "result": links,
                "count": len(links)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}
