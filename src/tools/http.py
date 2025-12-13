"""HTTP request tool for making web requests without browser."""
import logging
import time
from typing import Any

import aiohttp

from .base import BaseTool
from ..core.log_context import get_logger
from ..core.structured_logger import EventCategory, LogEvent

logger = logging.getLogger(__name__)


class HTTPRequestTool(BaseTool):
    """Make HTTP requests to fetch web content."""

    name = "http_request"
    description = """Make an HTTP request to fetch web content without JavaScript rendering.
    Use this to check if a page is accessible via simple HTTP or requires browser rendering."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None
    ) -> dict[str, Any]:
        """Make HTTP request.

        Args:
            url: URL to request
            method: HTTP method (GET, POST, etc.)
            headers: Optional request headers
            body: Optional request body
        """
        import asyncio

        slog = get_logger()
        start_time = time.perf_counter()

        if slog:
            slog.info(
                event=LogEvent(
                    category=EventCategory.BROWSER_OPERATION,
                    event_type="tool.http.request.start",
                    name="HTTP request started",
                ),
                message=f"{method} {url}",
                data={"url": url, "method": method},
                tags=["http", "request", "start"],
            )

        async def _request():
            default_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
            if headers:
                default_headers.update(headers)

            timeout_config = aiohttp.ClientTimeout(total=self.timeout)

            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.request(
                    method,
                    url,
                    headers=default_headers,
                    data=body
                ) as response:
                    content = await response.text()
                    return {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": content,
                        "truncated": False
                    }

        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_request())
            loop.close()

            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="tool.http.request.complete",
                        name="HTTP request completed",
                    ),
                    message=f"{method} {url} -> {result['status_code']}",
                    data={
                        "url": url,
                        "method": method,
                        "status_code": result["status_code"],
                        "body_length": len(result["body"]),
                    },
                    tags=["http", "request", "success"],
                    duration_ms=duration_ms,
                )

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"HTTP request failed: {e}")
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="tool.http.request.error",
                        name="HTTP request failed",
                    ),
                    message=f"{method} {url} failed: {e}",
                    data={"url": url, "method": method, "error": str(e)},
                    tags=["http", "request", "error"],
                    duration_ms=duration_ms,
                )
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to request"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "HEAD"],
                    "description": "HTTP method (default: GET)"
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Optional request headers"
                },
                "body": {
                    "type": "string",
                    "description": "Optional request body"
                }
            },
            "required": ["url"]
        }
