"""Browser interaction tools for agents.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.
"""

import time
from typing import Any

from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm, get_html_summary
from ..observability.decorators import traced_tool
from .base import BaseTool
from .validation import validated_tool


class NavigateTool(BaseTool):
    """Navigate browser to URL."""

    name = "browser_navigate"
    description = "Navigate the browser to a specified URL and wait for page load."

    def __init__(self, session: BrowserSession):
        self.session = session

    @traced_tool(name="browser_navigate")
    @validated_tool
    def execute(self, url: str) -> dict[str, Any]:
        """Navigate to URL. Instrumented by @traced_tool."""
        result = self.session.navigate(url)
        return {"success": True, "result": f"Navigated to {url}", "details": result}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The URL to navigate to"}},
            "required": ["url"],
        }


class GetHTMLTool(BaseTool):
    """Get current page HTML."""

    name = "browser_get_html"
    description = """Get the HTML content of the current page.
    By default returns cleaned HTML (body only, no scripts/styles/base64).
    Set raw=true to get unprocessed HTML."""

    def __init__(self, session: BrowserSession):
        self.session = session

    @traced_tool(name="browser_get_html")
    @validated_tool
    def execute(self, raw: bool = False) -> dict[str, Any]:
        """Get page HTML. Instrumented by @traced_tool."""
        html = self.session.get_html()
        original_length = len(html)

        if not raw:
            html = clean_html_for_llm(html)
            get_html_summary(html)  # For internal stats

        # Truncate if still too large
        truncated = False
        if len(html) > 150000:
            html = html[:150000] + "\n... [TRUNCATED]"
            truncated = True

        return {
            "success": True,
            "result": html,
            "original_length": original_length,
            "cleaned_length": len(html),
            "raw": raw,
            "truncated": truncated,
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "raw": {
                    "type": "boolean",
                    "description": "If true, return raw HTML without cleaning. Default: false",
                }
            },
        }


class ClickTool(BaseTool):
    """Click element on page."""

    name = "browser_click"
    description = "Click an element on the page using a CSS selector."

    def __init__(self, session: BrowserSession):
        self.session = session

    @traced_tool(name="browser_click")
    @validated_tool
    def execute(self, selector: str) -> dict[str, Any]:
        """Click element. Instrumented by @traced_tool."""
        result = self.session.click(selector)

        if result.get("success"):
            return {"success": True, "result": f"Clicked element: {selector}"}

        return {"success": False, "error": result.get("error", "Click failed")}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for element to click"}
            },
            "required": ["selector"],
        }


class QuerySelectorTool(BaseTool):
    """Query elements by selector."""

    name = "browser_query"
    description = "Find all elements matching a CSS selector and return their text/href."

    def __init__(self, session: BrowserSession):
        self.session = session

    @traced_tool(name="browser_query")
    @validated_tool
    def execute(self, selector: str) -> dict[str, Any]:
        """Query DOM elements. Instrumented by @traced_tool."""
        elements = self.session.query_selector_all(selector)
        return {"success": True, "result": elements, "count": len(elements)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"selector": {"type": "string", "description": "CSS selector to query"}},
            "required": ["selector"],
        }


class WaitTool(BaseTool):
    """Wait for element or time."""

    name = "browser_wait"
    description = "Wait for a selector to appear or for specified seconds."

    def __init__(self, session: BrowserSession):
        self.session = session

    @traced_tool(name="browser_wait")
    @validated_tool
    def execute(self, selector: str | None = None, seconds: int | None = None) -> dict[str, Any]:
        """Wait for selector or time. Instrumented by @traced_tool."""
        if seconds:
            time.sleep(seconds)
            return {"success": True, "result": f"Waited {seconds} seconds"}
        elif selector:
            found = self.session.wait_for_selector(selector)
            if found:
                return {"success": True, "result": f"Found element: {selector}"}
            return {"success": False, "error": f"Timeout waiting for: {selector}"}

        return {"success": False, "error": "Must provide selector or seconds"}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector to wait for"},
                "seconds": {"type": "integer", "description": "Number of seconds to wait"},
            },
        }


class ExtractLinksTool(BaseTool):
    """Extract all links from page."""

    name = "browser_extract_links"
    description = "Extract all links (<a> tags) from the current page with their text and URLs."

    def __init__(self, session: BrowserSession):
        self.session = session

    @traced_tool(name="browser_extract_links")
    @validated_tool
    def execute(self) -> dict[str, Any]:
        """Extract links from page. Instrumented by @traced_tool."""
        elements = self.session.query_selector_all("a[href]")
        links = [
            {"text": el["text"], "href": el["href"]}
            for el in elements
            if el.get("href") and not el["href"].startswith("javascript:")
        ]

        return {"success": True, "result": links, "count": len(links)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}
