"""Contract Data Preparation Agent for creating test datasets.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from typing import TYPE_CHECKING

from ..core.browser import BrowserSession
from ..core.llm import LLMClient
from ..tools.extraction import (
    BatchExtractArticlesTool,
    BatchExtractListingsTool,
    BatchFetchURLsTool,
)
from ..tools.memory import (
    MemoryReadTool,
    MemorySearchTool,
    MemoryWriteTool,
)
from ..tools.random_choice import RandomChoiceTool
from src.prompts import get_prompt_provider

from .base import BaseAgent

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService


class DataPrepAgent(BaseAgent):
    """Agent for preparing contract test datasets."""

    name = "data_prep_agent"
    system_prompt = get_prompt_provider().get_agent_prompt("data_prep")

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_service: "MemoryService",
    ):
        self.browser_session = browser_session

        tools = [
            # Batch fetch (uses browser)
            BatchFetchURLsTool(browser_session, memory_service),
            # Batch extraction (separate LLM contexts)
            BatchExtractListingsTool(llm, memory_service),
            BatchExtractArticlesTool(llm, memory_service),
            # Random selection
            RandomChoiceTool(),
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemorySearchTool(memory_service),
        ]

        super().__init__(llm, tools, memory_service=memory_service)
