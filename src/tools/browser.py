"""Browser interaction tools for agents."""
import logging
import time
from typing import Any

from .base import BaseTool
from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm, get_html_summary
from ..core.log_context import get_logger
from ..core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)

logger = logging.getLogger(__name__)


class NavigateTool(BaseTool):
    """Navigate browser to URL."""

    name = "browser_navigate"
    description = "Navigate the browser to a specified URL and wait for page load."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self, url: str) -> dict[str, Any]:
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            logger.info(f">>> BROWSER NAVIGATING TO: {url}")

            # Log navigation start
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.navigate.start",
                        name="Navigation started",
                    ),
                    message=f"Navigating to {url}",
                    data={"url": url},
                    tags=["browser", "navigate", "start"],
                )

            result = self.session.navigate(url)
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(f">>> BROWSER NAVIGATION COMPLETE: {url}")

            # Log navigation complete
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.navigate.complete",
                        name="Navigation completed",
                    ),
                    message=f"Navigation to {url} completed",
                    data={"url": url, "status": "success"},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "navigate", "success"],
                )

            return {
                "success": True,
                "result": f"Navigated to {url}",
                "details": result
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f">>> BROWSER NAVIGATION FAILED: {e}")

            # Log navigation error
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.navigate.error",
                        name="Navigation failed",
                    ),
                    message=f"Navigation to {url} failed: {e}",
                    data={"url": url, "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "navigate", "error"],
                )

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
        slog = get_logger()
        start_time = time.perf_counter()

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
            truncated = False
            if len(html) > 150000:
                html = html[:150000] + "\n... [TRUNCATED]"
                truncated = True

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log HTML fetch
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.html.fetched",
                        name="HTML fetched",
                    ),
                    message=f"HTML fetched: {original_length} -> {len(html)} bytes",
                    data={
                        "original_size": original_length,
                        "cleaned_size": len(html),
                        "raw": raw,
                        "truncated": truncated,
                    },
                    metrics=LogMetrics(
                        duration_ms=duration_ms,
                        content_size_bytes=len(html),
                    ),
                    tags=["browser", "html", "success"],
                )

            return {
                "success": True,
                "result": html,
                "original_length": original_length,
                "cleaned_length": len(html),
                "raw": raw
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000 if 'start_time' in dir() else 0

            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.html.error",
                        name="HTML fetch failed",
                    ),
                    message=f"Failed to get HTML: {e}",
                    data={"error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "html", "error"],
                )

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
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            result = self.session.click(selector)
            duration_ms = (time.perf_counter() - start_time) * 1000

            if result.get("success"):
                if slog:
                    slog.info(
                        event=LogEvent(
                            category=EventCategory.BROWSER_OPERATION,
                            event_type="browser.click",
                            name="Element clicked",
                        ),
                        message=f"Clicked element: {selector}",
                        data={"selector": selector, "success": True},
                        metrics=LogMetrics(duration_ms=duration_ms),
                        tags=["browser", "click", "success"],
                    )
                return {
                    "success": True,
                    "result": f"Clicked element: {selector}"
                }

            if slog:
                slog.warning(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.click",
                        name="Click failed",
                    ),
                    message=f"Click failed for: {selector}",
                    data={"selector": selector, "error": result.get("error")},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "click", "failure"],
                )
            return {
                "success": False,
                "error": result.get("error", "Click failed")
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000 if 'start_time' in dir() else 0
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.click",
                        name="Click error",
                    ),
                    message=f"Click error for {selector}: {e}",
                    data={"selector": selector, "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "click", "error"],
                )
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
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            elements = self.session.query_selector_all(selector)
            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.debug(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.query",
                        name="DOM query executed",
                    ),
                    message=f"Query '{selector}' returned {len(elements)} elements",
                    data={"selector": selector, "results_count": len(elements)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "query"],
                )

            return {
                "success": True,
                "result": elements,
                "count": len(elements)
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000 if 'start_time' in dir() else 0
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.query",
                        name="DOM query failed",
                    ),
                    message=f"Query '{selector}' failed: {e}",
                    data={"selector": selector, "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "query", "error"],
                )
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
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            if seconds:
                time.sleep(seconds)
                duration_ms = (time.perf_counter() - start_time) * 1000

                if slog:
                    slog.debug(
                        event=LogEvent(
                            category=EventCategory.BROWSER_OPERATION,
                            event_type="browser.wait",
                            name="Wait completed",
                        ),
                        message=f"Waited {seconds} seconds",
                        data={"wait_type": "time", "seconds": seconds},
                        metrics=LogMetrics(duration_ms=duration_ms),
                        tags=["browser", "wait", "time"],
                    )

                return {
                    "success": True,
                    "result": f"Waited {seconds} seconds"
                }
            elif selector:
                found = self.session.wait_for_selector(selector)
                duration_ms = (time.perf_counter() - start_time) * 1000

                if found:
                    if slog:
                        slog.debug(
                            event=LogEvent(
                                category=EventCategory.BROWSER_OPERATION,
                                event_type="browser.wait",
                                name="Wait completed",
                            ),
                            message=f"Found element: {selector}",
                            data={"wait_type": "selector", "selector": selector, "found": True},
                            metrics=LogMetrics(duration_ms=duration_ms),
                            tags=["browser", "wait", "selector", "success"],
                        )
                    return {
                        "success": True,
                        "result": f"Found element: {selector}"
                    }

                if slog:
                    slog.warning(
                        event=LogEvent(
                            category=EventCategory.BROWSER_OPERATION,
                            event_type="browser.wait",
                            name="Wait timeout",
                        ),
                        message=f"Timeout waiting for: {selector}",
                        data={"wait_type": "selector", "selector": selector, "found": False},
                        metrics=LogMetrics(duration_ms=duration_ms),
                        tags=["browser", "wait", "selector", "timeout"],
                    )
                return {
                    "success": False,
                    "error": f"Timeout waiting for: {selector}"
                }
            return {
                "success": False,
                "error": "Must provide selector or seconds"
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000 if 'start_time' in dir() else 0
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.wait",
                        name="Wait error",
                    ),
                    message=f"Wait error: {e}",
                    data={"selector": selector, "seconds": seconds, "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "wait", "error"],
                )
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
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            elements = self.session.query_selector_all("a[href]")
            links = [
                {"text": el["text"], "href": el["href"]}
                for el in elements
                if el.get("href") and not el["href"].startswith("javascript:")
            ]
            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.extract_links",
                        name="Links extracted",
                    ),
                    message=f"Extracted {len(links)} links from page",
                    data={"links_count": len(links)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "links", "extraction"],
                )

            return {
                "success": True,
                "result": links,
                "count": len(links)
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000 if 'start_time' in dir() else 0
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.extract_links",
                        name="Link extraction failed",
                    ),
                    message=f"Failed to extract links: {e}",
                    data={"error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["browser", "links", "error"],
                )
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}
