"""Browser Interaction Agent for web navigation and extraction.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from typing import TYPE_CHECKING

from src.prompts import get_prompt_provider

from ..core.browser import BrowserSession
from ..core.llm import LLMClient
from ..tools.browser import (
    ClickTool,
    ExtractLinksTool,
    GetHTMLTool,
    NavigateTool,
    QuerySelectorTool,
    WaitTool,
)
from ..tools.memory import (
    MemoryListTool,
    MemoryReadTool,
    MemorySearchTool,
    MemoryWriteTool,
)
from .base import BaseAgent

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService


class BrowserAgent(BaseAgent):
    """Agent for browser interaction and page analysis."""

    name = "browser_agent"
    system_prompt = get_prompt_provider().get_agent_prompt("browser")

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_service: "MemoryService",
    ):
        self.browser_session = browser_session

        tools = [
            # Browser tools
            NavigateTool(browser_session),
            GetHTMLTool(browser_session),
            ClickTool(browser_session),
            QuerySelectorTool(browser_session),
            WaitTool(browser_session),
            ExtractLinksTool(browser_session),
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemorySearchTool(memory_service),
            MemoryListTool(memory_service),
        ]

        super().__init__(llm, tools, memory_service=memory_service)
