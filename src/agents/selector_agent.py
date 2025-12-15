"""Selector Agent for finding and verifying CSS selectors.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from ..core.browser import BrowserSession
from ..core.llm import LLMClient
from ..tools.memory import (
    MemoryReadTool,
    MemorySearchTool,
    MemoryStore,
    MemoryWriteTool,
)
from ..tools.selector_extraction import (
    ArticlePageExtractorTool,
    ListingPageExtractorTool,
    SelectorAggregatorTool,
)
from ..tools.selector_sampling import (
    ArticlePagesGeneratorTool,
    ListingPagesGeneratorTool,
)
from .base import BaseAgent
from .prompts import SELECTOR_AGENT_PROMPT


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
            # Sampling tools (URL generation with LLM for pattern detection)
            ListingPagesGeneratorTool(llm),
            ArticlePagesGeneratorTool(llm),
            # Extraction tools (isolated context per page)
            ListingPageExtractorTool(llm, browser_session),
            ArticlePageExtractorTool(llm, browser_session),
            # Aggregation tool (creates selector chains, not single selectors)
            SelectorAggregatorTool(llm),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
