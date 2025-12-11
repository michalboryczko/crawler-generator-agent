"""Selector Agent for finding and verifying CSS selectors."""
import logging
from typing import Any

from .base import BaseAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.browser import NavigateTool, QuerySelectorTool, GetHTMLTool, WaitTool
from ..tools.selector import (
    FindSelectorTool,
    TestSelectorTool,
    VerifySelectorTool,
    CompareSelectorsTool,
)
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemorySearchTool,
)
from ..tools.random_choice import RandomChoiceTool

logger = logging.getLogger(__name__)

SELECTOR_AGENT_PROMPT = """You are a Selector Agent. Find CSS selectors by visiting multiple listing and article pages.

## CRITICAL: ONE TOOL CALL AT A TIME
You MUST call only ONE tool per response. Never batch multiple tool calls.

## Tools
- browser_navigate: Navigate to URL
- browser_wait: Wait (use seconds=5)
- browser_get_html: Get page HTML
- browser_query: Query elements
- find_selector: Find selectors for 'articles' or 'pagination'
- test_selector: Test a selector
- random_choice: Pick random items
- memory_read/write/search: Access memory

## Workflow - PHASE 1: LISTING PAGES (do this FIRST)

### Step 1: Read memory and plan
- Read 'target_url' and 'pagination_max_pages'
- Calculate: visit ~2% of max_pages (minimum 5, maximum 20 listing pages)
- Example: 342 pages → visit pages 1, 50, 100, 200, 300 (5 pages)

### Step 2: Visit listing page 1 (target_url)
- Navigate to target_url
- Wait 5 seconds
- Get HTML
- Find/query selectors for article links
- Store article URLs found on this page
- Note: you have visited 1 listing page

### Step 3: Visit listing page 2
- Navigate to target_url?page=50 (or similar)
- Wait 5 seconds
- Get HTML
- Query articles with selector from step 2
- Add article URLs to your collection
- Note: you have visited 2 listing pages

### Step 4: Visit listing page 3
- Navigate to target_url?page=100 (or similar)
- Wait 5 seconds
- Get HTML
- Query articles, add URLs
- Note: you have visited 3 listing pages

### Step 5: Visit listing page 4
- Navigate to target_url?page=200 (or similar)
- Wait 5 seconds
- Get HTML
- Query articles, add URLs
- Note: you have visited 4 listing pages

### Step 6: Visit listing page 5
- Navigate to target_url?page=300 (or similar)
- Wait 5 seconds
- Get HTML
- Query articles, add URLs
- Note: you have visited 5 listing pages - MINIMUM REACHED

### Step 7: Store listing results
- Store ALL collected article URLs as 'collected_article_urls'
- Store 'listing_selectors' with the verified selector
- Store 'article_selector' with best selector

## Workflow - PHASE 2: ARTICLE PAGES (do this AFTER Phase 1)

### Step 8: Pick articles to verify
- Use random_choice to select 5 URLs from collected_article_urls
- Store the 5 selected URLs for tracking

### Step 9: Visit article page 1
- Navigate to first article URL
- Wait 5 seconds
- Get HTML
- Query selectors: h1.title, .article-header .date, .article-header .author, .article .content
- Note: you have visited 1 article page

### Step 10: Visit article page 2
- Navigate to second article URL
- Wait 5 seconds
- Get HTML
- Query same selectors, verify they work
- Note: you have visited 2 article pages

### Step 11: Visit article page 3
- Navigate to third article URL
- Wait 5 seconds
- Get HTML
- Query same selectors, verify they work
- Note: you have visited 3 article pages

### Step 12: Visit article page 4
- Navigate to fourth article URL
- Wait 5 seconds
- Get HTML
- Query same selectors, verify they work
- Note: you have visited 4 article pages

### Step 13: Visit article page 5
- Navigate to fifth article URL
- Wait 5 seconds
- Get HTML
- Query same selectors, verify they work
- Note: you have visited 5 article pages - MINIMUM REACHED

### Step 14: Store detail selectors (ONLY after visiting all 5 articles)
Store 'detail_selectors' with verified selectors:
{
  "title": {"primary": "h1.title", "fallbacks": [], "confidence": 0.95},
  "date": {"primary": ".article-header .date", "fallbacks": [], "confidence": 0.9},
  "content": {"primary": ".article .content", "fallbacks": [], "confidence": 0.9}
}

### Step 15: Final summary
Store 'selector_analysis': "Analyzed X listing pages, 5 article pages"
Store 'article_selector' and 'article_selector_confidence'

## CRITICAL RULES
- You MUST visit at least 5 DIFFERENT listing pages before moving to articles
- You MUST visit at least 5 DIFFERENT article pages before storing detail_selectors
- Do NOT store detail_selectors until you have visited 5 article pages
- Call ONE tool at a time"""


class SelectorAgent(BaseAgent):
    """Agent for finding and verifying CSS selectors."""

    name = "selector_agent"
    system_prompt = SELECTOR_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_store: MemoryStore | None = None
    ):
        self.browser_session = browser_session
        self.memory_store = memory_store or MemoryStore()

        tools = [
            # Selector tools
            FindSelectorTool(browser_session),
            TestSelectorTool(browser_session),
            VerifySelectorTool(browser_session),
            CompareSelectorsTool(browser_session),
            # Browser tools (including navigation for visiting articles)
            NavigateTool(browser_session),
            WaitTool(browser_session),
            QuerySelectorTool(browser_session),
            GetHTMLTool(browser_session),
            # Random selection for sampling
            RandomChoiceTool(),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
