"""Main Agent for orchestrating the crawl plan creation workflow.

This module uses the new observability decorators for automatic logging.
The @traced_agent decorator handles all agent instrumentation.
"""
import logging
from pathlib import Path
from typing import Any

from ..core.browser import BrowserSession
from ..core.llm import LLMClient
from ..observability.decorators import traced_agent
from ..tools.file import (
    FileCreateTool,
    FileReplaceTool,
)
from ..tools.memory import (
    MemoryDumpTool,
    MemoryListTool,
    MemoryReadTool,
    MemorySearchTool,
    MemoryStore,
    MemoryWriteTool,
)
from ..tools.orchestration import (
    RunAccessibilityAgentTool,
    RunBrowserAgentTool,
    RunDataPrepAgentTool,
    RunSelectorAgentTool,
)
from ..tools.plan_generator import (
    GeneratePlanTool,
    GenerateTestPlanTool,
)
from .accessibility_agent import AccessibilityAgent
from .base import BaseAgent
from .browser_agent import BrowserAgent
from .data_prep_agent import DataPrepAgent
from .prompts import MAIN_AGENT_PROMPT
from .selector_agent import SelectorAgent

logger = logging.getLogger(__name__)


class MainAgent(BaseAgent):
    """Main orchestrator agent that coordinates all sub-agents."""

    name = "main_agent"
    system_prompt = MAIN_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        output_dir: Path,
        memory_store: MemoryStore | None = None
    ):
        self.memory_store = memory_store or MemoryStore()
        self.browser_session = browser_session
        self.output_dir = output_dir

        # Create sub-agents
        self.browser_agent = BrowserAgent(llm, browser_session, self.memory_store)
        self.selector_agent = SelectorAgent(llm, browser_session, self.memory_store)
        self.accessibility_agent = AccessibilityAgent(llm, self.memory_store)
        self.data_prep_agent = DataPrepAgent(llm, browser_session, self.memory_store)

        tools = [
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemoryListTool(self.memory_store),
            MemorySearchTool(self.memory_store),
            MemoryDumpTool(self.memory_store, output_dir),
            # Plan generators (structured output from memory)
            GeneratePlanTool(self.memory_store),
            GenerateTestPlanTool(self.memory_store),
            # File tools
            FileCreateTool(output_dir),
            FileReplaceTool(output_dir),
            # Agent orchestration tools
            RunBrowserAgentTool(self.browser_agent),
            RunSelectorAgentTool(self.selector_agent),
            RunAccessibilityAgentTool(self.accessibility_agent),
            RunDataPrepAgentTool(self.data_prep_agent),
        ]

        super().__init__(llm, tools)

    @traced_agent(name="main_agent.create_crawl_plan")
    def create_crawl_plan(self, url: str) -> dict[str, Any]:
        """High-level method to create a complete crawl plan for a URL.

        Instrumented by @traced_agent - logs workflow lifecycle and results.
        """
        task = f"""Create a complete crawl plan for: {url}

Execute the full workflow:
1. Store '{url}' in memory as 'target_url'
2. Run browser agent to extract article links, pagination info, and max pages
3. Run selector agent to find CSS selectors for listings and detail pages
4. Run accessibility agent to check HTTP accessibility
5. Run data prep agent to create test dataset with 5+ listing pages and 20+ article pages
6. Use generate_plan_md to create comprehensive plan, then file_create for plan.md
7. Use generate_test_md to create test documentation, then file_create for test.md
8. Search for BOTH 'test-data-listing-*' AND 'test-data-article-*' keys
9. Dump ALL test entries to data/test_set.jsonl

Return summary with counts when complete."""

        return self.run(task)
