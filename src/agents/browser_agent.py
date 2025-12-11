"""Browser Interaction Agent for web navigation and extraction."""
import logging
from typing import Any

from .base import BaseAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.browser import (
    NavigateTool,
    GetHTMLTool,
    ClickTool,
    QuerySelectorTool,
    WaitTool,
    ExtractLinksTool,
)
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemorySearchTool,
    MemoryListTool,
)

logger = logging.getLogger(__name__)

BROWSER_AGENT_PROMPT = """You are a Browser Interaction Agent specialized in navigating websites and extracting information.

Your capabilities:
1. Navigate to URLs
2. Get page HTML content
3. Click elements using CSS selectors
4. Query elements to find their text/href
5. Wait for elements or fixed time
6. Extract all links from a page
7. Store findings in shared memory

Your workflow:
1. Navigate to the target URL
2. Wait for page to load (5 seconds recommended for JS-heavy sites)
3. Extract the page HTML for analysis
4. Find and extract article links
5. Store extracted URLs in memory under 'extracted_articles'
6. Look for pagination and store pagination info in memory

Memory keys to use:
- 'target_url': The URL being analyzed
- 'page_html': Current page HTML (truncated)
- 'extracted_articles': List of article URLs found
- 'pagination_info': Info about pagination structure

Always verify your actions worked before proceeding.
When done, provide a summary of what you found."""


class BrowserAgent(BaseAgent):
    """Agent for browser interaction and page analysis."""

    name = "browser_agent"
    system_prompt = BROWSER_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_store: MemoryStore | None = None
    ):
        self.browser_session = browser_session
        self.memory_store = memory_store or MemoryStore()

        tools = [
            # Browser tools
            NavigateTool(browser_session),
            GetHTMLTool(browser_session),
            ClickTool(browser_session),
            QuerySelectorTool(browser_session),
            WaitTool(browser_session),
            ExtractLinksTool(browser_session),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
            MemoryListTool(self.memory_store),
        ]

        super().__init__(llm, tools)
