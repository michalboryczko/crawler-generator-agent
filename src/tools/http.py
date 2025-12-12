"""HTTP request tool for making web requests without browser."""
import logging
from typing import Any

import aiohttp

from .base import BaseTool

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

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
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
