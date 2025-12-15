"""Browser Interaction Agent for web navigation and extraction.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
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
    MemoryStore,
    MemoryWriteTool,
)
from .base import BaseAgent
from .prompts import BROWSER_AGENT_PROMPT


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
