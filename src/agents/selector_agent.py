"""Selector Agent for finding and verifying CSS selectors.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from typing import TYPE_CHECKING

from src.prompts import get_prompt_provider

from ..core.browser import BrowserSession
from ..core.llm import LLMClient
from ..tools.memory import (
    MemoryReadTool,
    MemorySearchTool,
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

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService


class SelectorAgent(BaseAgent):
    """Agent for finding and verifying CSS selectors."""

    name = "selector_agent"
    system_prompt = get_prompt_provider().get_agent_prompt("selector")

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_service: "MemoryService",
    ):
        self.browser_session = browser_session

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
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemorySearchTool(memory_service),
        ]

        super().__init__(llm, tools, memory_service=memory_service)
