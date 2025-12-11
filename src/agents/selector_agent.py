"""Selector Agent for finding and verifying CSS selectors."""
import logging
from typing import Any

from .base import BaseAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.browser import QuerySelectorTool, GetHTMLTool
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

logger = logging.getLogger(__name__)

SELECTOR_AGENT_PROMPT = """You are a Selector Agent specialized in finding CSS selectors for web scraping.

Your goal is to find reliable CSS selectors that will:
1. Match article links on the page
2. Match pagination elements if present

Workflow:
1. Read the target URL and extracted articles from memory
2. Use find_selector to discover potential selectors for articles
3. Test each candidate selector with test_selector
4. Verify the best candidates against known article URLs using verify_selector
5. Compare multiple selectors to find the optimal one
6. Store the final selectors in memory

Memory keys to read:
- 'target_url': The URL being analyzed
- 'extracted_articles': List of article URLs found by browser agent

Memory keys to write:
- 'article_selector': Best CSS selector for articles
- 'article_selector_confidence': Confidence score (0-1)
- 'pagination_selector': CSS selector for pagination (if found)
- 'pagination_type': 'numbered', 'next_button', or 'infinite_scroll'

Selection criteria:
1. Match rate > 80% of expected articles
2. High precision (few false positives)
3. Selector specificity (prefer specific over generic)
4. Stability (class names that look stable, not generated)

When done, summarize the selectors found and their confidence levels."""


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
            # Browser tools (read-only)
            QuerySelectorTool(browser_session),
            GetHTMLTool(browser_session),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
