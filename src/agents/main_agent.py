"""Main Agent for orchestrating the crawl plan creation workflow.

This module uses the new observability decorators for automatic logging.
The @traced_agent decorator handles all agent instrumentation.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.prompts import get_prompt_provider

from ..core.browser import BrowserSession
from ..core.config import AgentsConfig
from ..core.llm import LLMClient
from ..observability.decorators import traced_agent
from ..tools.agent_tools import AgentTool, GenerateUuidTool, PrepareAgentOutputValidationTool
from ..tools.file import (
    FileCreateTool,
    FileReplaceTool,
)
from ..tools.memory import (
    MemoryListTool,
    MemoryReadTool,
    MemoryWriteTool,
)
from ..tools.plan_generator import (
    GeneratePlanTool,
    GenerateTestPlanTool,
)
from .accessibility_agent import AccessibilityAgent
from .base import BaseAgent
from .data_prep_agent import DataPrepAgent
from .discovery_agent import DiscoveryAgent
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
        agents_config: AgentsConfig | None = None,
    ):
        """Initialize the main agent.

        Args:
            llm: LLM client for API calls
            browser_session: Browser session for web interactions
            output_dir: Directory for output files
            memory_service: Memory service for this agent
            container: DI container for creating sub-agent services
            agents_config: Configuration for agent schema paths. If None,
                          loads from default config/agents.yaml.
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

        # Load agents config if not provided
        if agents_config is None:
            agents_config = AgentsConfig.from_yaml()
        self._agents_config = agents_config

        # Create sub-agents with isolated memory services
        self.discovery_agent = DiscoveryAgent(
            llm, browser_session, memory_service=self._container.memory_service("discovery")
        )
        self.selector_agent = SelectorAgent(
            llm, browser_session, memory_service=self._container.memory_service("selector")
        )
        self.accessibility_agent = AccessibilityAgent(
            llm, memory_service=self._container.memory_service("accessibility")
        )
        self.data_prep_agent = DataPrepAgent(
            llm,
            browser_session,
            memory_service=self._container.memory_service("data_prep"),
            output_dir=output_dir,
        )

        # Mapping from internal agent name to config key
        agent_to_config = {
            "discovery_agent": "discovery",
            "selector_agent": "selector",
            "accessibility_agent": "accessibility",
            "data_prep_agent": "data_prep",
        }

        # Build schema paths from config for PrepareAgentOutputValidationTool
        schema_paths = {}
        for agent_name, config_key in agent_to_config.items():
            paths = agents_config.get_schema_paths(config_key)
            schema_paths[agent_name] = paths.output_contract_schema_path

        # Get schema paths from config for AgentTools
        discovery_paths = agents_config.get_schema_paths("discovery")
        selector_paths = agents_config.get_schema_paths("selector")
        accessibility_paths = agents_config.get_schema_paths("accessibility")
        data_prep_paths = agents_config.get_schema_paths("data_prep")

        # Create AgentTools for sub-agents with contract schemas from config
        agent_tools = [
            AgentTool(
                agent=self.discovery_agent,
                output_schema_path=discovery_paths.output_contract_schema_path,
                input_schema_path=discovery_paths.input_contract_schema_path,
                description="Discover site structure, article URLs, pagination, and content fields",
            ),
            AgentTool(
                agent=self.selector_agent,
                output_schema_path=selector_paths.output_contract_schema_path,
                input_schema_path=selector_paths.input_contract_schema_path,
                description="Find and verify CSS selectors for listings and article pages",
            ),
            AgentTool(
                agent=self.accessibility_agent,
                output_schema_path=accessibility_paths.output_contract_schema_path,
                input_schema_path=accessibility_paths.input_contract_schema_path,
                description="Check if site content is accessible via HTTP without JavaScript",
            ),
            AgentTool(
                agent=self.data_prep_agent,
                output_schema_path=data_prep_paths.output_contract_schema_path,
                input_schema_path=data_prep_paths.input_contract_schema_path,
                description="Prepare test datasets with sample pages for validation",
            ),
        ]

        # Unified tools list - AgentTools are auto-detected by BaseAgent
        tools = [
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemoryListTool(memory_service),
            # Plan generators (structured output from memory)
            GeneratePlanTool(memory_service),
            GenerateTestPlanTool(memory_service),
            # File tools
            FileCreateTool(output_dir),
            FileReplaceTool(output_dir),
            # Contract orchestration tools
            GenerateUuidTool(),
            PrepareAgentOutputValidationTool(schema_paths),
            # Agent tools (auto-detected by BaseAgent.agent_tools property)
            *agent_tools,
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
   (The data prep agent will also dump test data to data/test_set.jsonl)
6. Use generate_plan_md to create comprehensive plan, then file_create for plan.md
7. Use generate_test_md to create test documentation, then file_create for test.md

Return summary with counts when complete."""

        return self.run(task)
