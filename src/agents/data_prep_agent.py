"""Contract Data Preparation Agent for creating test datasets.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
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
    MemoryStore,
    MemoryWriteTool,
)
from ..tools.random_choice import RandomChoiceTool
from .base import BaseAgent
from .prompts import DATA_PREP_AGENT_PROMPT


class DataPrepAgent(BaseAgent):
    """Agent for preparing contract test datasets."""

    name = "data_prep_agent"
    system_prompt = DATA_PREP_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_store: MemoryStore | None = None
    ):
        self.browser_session = browser_session
        self.memory_store = memory_store or MemoryStore()

        tools = [
            # Batch fetch (uses browser)
            BatchFetchURLsTool(browser_session, self.memory_store),
            # Batch extraction (separate LLM contexts)
            BatchExtractListingsTool(llm, self.memory_store),
            BatchExtractArticlesTool(llm, self.memory_store),
            # Random selection
            RandomChoiceTool(),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
