"""Main Agent for orchestrating the crawl plan creation workflow.

This module uses the new observability decorators for automatic logging.
The @traced_agent decorator handles all agent instrumentation.
"""
import logging
from pathlib import Path
from typing import TYPE_CHECKING

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
from src.prompts import get_prompt_provider

from .data_prep_agent import DataPrepAgent
from .result import AgentResult
from .selector_agent import SelectorAgent

if TYPE_CHECKING:
    from ..infrastructure import Container
    from ..services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MainAgent(BaseAgent):
    """Main orchestrator agent that coordinates all sub-agents.

    Each sub-agent has an isolated memory service to prevent implicit data
    sharing. Data flows explicitly via AgentResult and context parameters.
    """

    name = "main_agent"
    system_prompt = get_prompt_provider().get_agent_prompt("main")

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        output_dir: Path,
        memory_service: "MemoryService",
        container: "Container | None" = None,
    ):
        """Initialize the main agent.

        Args:
            llm: LLM client for API calls
            browser_session: Browser session for web interactions
            output_dir: Directory for output files
            memory_service: Memory service for this agent
            container: DI container for creating sub-agent services
        """
        self._memory_service = memory_service
        self.browser_session = browser_session
        self.output_dir = output_dir

        # If container provided, use it for sub-agents; otherwise create standalone
        if container:
            self._container = container
        else:
            from ..infrastructure import Container
            self._container = Container.create_inmemory()

        # Create sub-agents with isolated memory services
        self.browser_agent = BrowserAgent(
            llm, browser_session,
            memory_service=self._container.memory_service("browser")
        )
        self.selector_agent = SelectorAgent(
            llm, browser_session,
            memory_service=self._container.memory_service("selector")
        )
        self.accessibility_agent = AccessibilityAgent(
            llm,
            memory_service=self._container.memory_service("accessibility")
        )
        self.data_prep_agent = DataPrepAgent(
            llm, browser_session,
            memory_service=self._container.memory_service("data_prep")
        )

        tools = [
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemoryListTool(memory_service),
            MemorySearchTool(memory_service),
            MemoryDumpTool(memory_service, output_dir),
            # Plan generators (structured output from memory)
            GeneratePlanTool(memory_service),
            GenerateTestPlanTool(memory_service),
            # File tools
            FileCreateTool(output_dir),
            FileReplaceTool(output_dir),
            # Agent orchestration tools
            RunBrowserAgentTool(self.browser_agent),
            RunSelectorAgentTool(self.selector_agent),
            RunAccessibilityAgentTool(self.accessibility_agent),
            RunDataPrepAgentTool(self.data_prep_agent),
        ]

        super().__init__(llm, tools, memory_service=memory_service)

    @traced_agent(name="main_agent.create_crawl_plan")
    def create_crawl_plan(self, url: str) -> AgentResult:
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
