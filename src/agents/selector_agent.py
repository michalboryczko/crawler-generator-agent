"""Selector Agent for finding and verifying CSS selectors.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""

from typing import TYPE_CHECKING

from src.prompts import get_prompt_provider

from ..core.browser import BrowserSession
from ..tools.agent_tools import ValidateResponseTool
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
    from ..core.llm import LLMClientFactory
    from ..services.context_service import ContextService
    from ..services.memory_service import MemoryService


class SelectorAgent(BaseAgent):
    """Agent for finding and verifying CSS selectors."""

    name = "selector_agent"
    description = "Finds and verifies CSS selectors for listings and article pages"
    system_prompt = get_prompt_provider().get_agent_prompt("selector")

    def __init__(
        self,
        llm_factory: "LLMClientFactory",
        browser_session: BrowserSession,
        memory_service: "MemoryService",
        context_service: "ContextService | None" = None,
    ):
        self.browser_session = browser_session

        tools = [
            # Sampling tools (URL generation with LLM for pattern detection)
            ListingPagesGeneratorTool(llm_factory),
            ArticlePagesGeneratorTool(llm_factory),
            # Extraction tools (isolated context per page)
            ListingPageExtractorTool(llm_factory, browser_session),
            ArticlePageExtractorTool(llm_factory, browser_session),
            # Aggregation tool (creates selector chains, not single selectors)
            SelectorAggregatorTool(llm_factory),
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemorySearchTool(memory_service),
            # Contract validation
            ValidateResponseTool(),
        ]

        super().__init__(
            llm_factory, tools, memory_service=memory_service, context_service=context_service
        )
