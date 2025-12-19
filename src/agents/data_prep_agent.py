"""Contract Data Preparation Agent for creating test datasets.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from pathlib import Path
from typing import TYPE_CHECKING

from src.prompts import get_prompt_provider

from ..core.browser import BrowserSession
from ..core.llm import LLMClient
from ..tools.agent_tools import ValidateResponseTool
from ..tools.extraction import (
    BatchExtractArticlesTool,
    BatchExtractListingsTool,
    BatchFetchURLsTool,
)
from ..tools.memory import (
    MemoryDumpTool,
    MemoryReadTool,
    MemorySearchTool,
    MemoryWriteTool,
)
from ..tools.random_choice import RandomChoiceTool
from .base import BaseAgent

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService


class DataPrepAgent(BaseAgent):
    """Agent for preparing contract test datasets."""

    name = "data_prep_agent"
    description = "Prepares test datasets with sample pages for validation"
    system_prompt = get_prompt_provider().get_agent_prompt("data_prep")

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_service: "MemoryService",
        output_dir: Path | None = None,
    ):
        self.browser_session = browser_session
        self.output_dir = output_dir

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
            # Contract validation
            ValidateResponseTool(),
        ]

        # Add dump tool if output_dir provided
        if output_dir:
            tools.append(MemoryDumpTool(memory_service, output_dir))

        super().__init__(llm, tools, memory_service=memory_service)
