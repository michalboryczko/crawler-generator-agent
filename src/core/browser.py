"""Chrome DevTools Protocol client for browser automation."""

import asyncio
import json
import logging
from typing import Any

import websockets

from .config import BrowserConfig

logger = logging.getLogger(__name__)


class CDPClient:
    """Chrome DevTools Protocol client."""

    def __init__(self, config: BrowserConfig):
        self.config = config
        self.ws: Any = None  # Type: websockets connection when connected
        self._message_id = 0
        self._responses: dict[int, Any] = {}

    async def connect(self) -> None:
        """Connect to Chrome DevTools."""
        # Get websocket URL from Chrome's /json endpoint
        import aiohttp

        http_url = f"http://{self.config.host}:{self.config.port}/json"
        logger.debug(f"Fetching targets from {http_url}")

        async with aiohttp.ClientSession() as session, session.get(http_url) as resp:
            targets = await resp.json()

        # Find a page target
        page_target = None
        for target in targets:
            if target.get("type") == "page":
                page_target = target
                break

        if not page_target:
            raise RuntimeError("No page target found in Chrome")

        ws_url = page_target["webSocketDebuggerUrl"]
        logger.info(f"Connecting to Chrome at {ws_url}")
        self.ws = await websockets.connect(ws_url)

    async def disconnect(self) -> None:
        """Disconnect from Chrome."""
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send(self, method: str, params: dict | None = None) -> dict[str, Any]:
        """Send CDP command and wait for response."""
        if not self.ws:
            raise RuntimeError("Not connected to Chrome")

        self._message_id += 1
        msg_id = self._message_id

        message = {"id": msg_id, "method": method, "params": params or {}}

        await self.ws.send(json.dumps(message))
        logger.debug(f"CDP send: {method}")

        # Wait for response with matching id
        while True:
            response = await asyncio.wait_for(self.ws.recv(), timeout=self.config.timeout)
            data = json.loads(response)

            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"CDP error: {data['error']}")
                return data.get("result", {})

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to URL."""
        result = await self.send("Page.navigate", {"url": url})
        # Wait for page load
        await self.send("Page.enable")
        await asyncio.sleep(2)  # Basic wait for load
        return result

    async def get_html(self) -> str:
        """Get current page HTML."""
        result = await self.send(
            "Runtime.evaluate", {"expression": "document.documentElement.outerHTML"}
        )
        return result.get("result", {}).get("value", "")

    async def click(self, selector: str) -> dict[str, Any]:
        """Click element by CSS selector."""
        result = await self.send(
            "Runtime.evaluate",
            {
                "expression": f"""
                (function() {{
                    const el = document.querySelector('{selector}');
                    if (!el) return {{success: false, error: 'Element not found'}};
                    el.click();
                    return {{success: true}};
                }})()
            """,
                "returnByValue": True,
            },
        )
        return result.get("result", {}).get("value", {})

    async def query_selector_all(self, selector: str) -> list[dict[str, Any]]:
        """Get all elements matching selector with their text and href."""
        result = await self.send(
            "Runtime.evaluate",
            {
                "expression": f"""
                (function() {{
                    const els = document.querySelectorAll('{selector}');
                    return Array.from(els).map(el => ({{
                        text: el.textContent?.trim() || '',
                        href: el.href || el.getAttribute('href') || '',
                        tagName: el.tagName.toLowerCase()
                    }}));
                }})()
            """,
                "returnByValue": True,
            },
        )
        return result.get("result", {}).get("value", [])

    async def wait_for_selector(self, selector: str, timeout: int = 10) -> bool:
        """Wait for selector to appear."""
        for _ in range(timeout * 2):
            result = await self.send(
                "Runtime.evaluate",
                {
                    "expression": f"document.querySelector('{selector}') !== null",
                    "returnByValue": True,
                },
            )
            if result.get("result", {}).get("value"):
                return True
            await asyncio.sleep(0.5)
        return False


class BrowserSession:
    """Synchronous wrapper around CDP client for tool use."""

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._client: CDPClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run(self, coro):
        """Run coroutine synchronously."""
        loop = self._get_loop()
        if loop.is_running():
            # If we're in an async context, create a new loop in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)

    def connect(self) -> None:
        """Connect to browser."""
        self._client = CDPClient(self.config)
        self._run(self._client.connect())

    def disconnect(self) -> None:
        """Disconnect from browser."""
        if self._client:
            self._run(self._client.disconnect())
            self._client = None

    def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to URL."""
        if not self._client:
            raise RuntimeError("Not connected")
        return self._run(self._client.navigate(url))

    def get_html(self) -> str:
        """Get page HTML."""
        if not self._client:
            raise RuntimeError("Not connected")
        return self._run(self._client.get_html())

    def click(self, selector: str) -> dict[str, Any]:
        """Click element."""
        if not self._client:
            raise RuntimeError("Not connected")
        return self._run(self._client.click(selector))

    def query_selector_all(self, selector: str) -> list[dict[str, Any]]:
        """Query all elements."""
        if not self._client:
            raise RuntimeError("Not connected")
        return self._run(self._client.query_selector_all(selector))

    def wait_for_selector(self, selector: str, timeout: int = 10) -> bool:
        """Wait for selector."""
        if not self._client:
            raise RuntimeError("Not connected")
        return self._run(self._client.wait_for_selector(selector, timeout))
