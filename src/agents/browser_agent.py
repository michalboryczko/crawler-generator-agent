"""Browser Interaction Agent for web navigation and extraction.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
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
4. Find and extract article links (look for article previews, blog posts, news items)
5. Store extracted URLs in memory under 'extracted_articles'
6. Analyze pagination structure:
   - Find pagination links/buttons
   - Determine pagination type (numbered, next_button, infinite_scroll, url_parameter)
   - Find max page number if available (look for "last" link or highest page number)
   - Store all pagination info in memory

Memory keys to write:
- 'extracted_articles': List of {text, href} objects for article links found
- 'pagination_type': One of 'numbered', 'next_button', 'infinite_scroll', 'url_parameter', or 'none'
- 'pagination_selector': CSS selector for pagination elements
- 'pagination_max_pages': Maximum page number if determinable (e.g., 342)
- 'pagination_links': List of actual pagination URLs found (e.g., ["/page/2", "?page=3", "?offset=20"])
  This helps detect the pagination URL pattern (page vs offset, etc.)

For pagination_max_pages:
- Look for "last" page links that show the final page number
- Or extract highest numbered page link visible
- Store as integer if found, otherwise omit

Always verify your actions worked before proceeding.
When done, provide a summary of articles found and pagination info."""


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
