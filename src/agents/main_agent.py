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
from ..core.llm import LLMClient, LLMClientFactory
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
from ..tools.plan_generator import GenerateTestPlanTool
from .accessibility_agent import AccessibilityAgent
from .base import BaseAgent
from .data_prep_agent import DataPrepAgent
from .discovery_agent import DiscoveryAgent
from .plan_generator_agent import PlanGeneratorAgent
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
        llm: LLMClient | LLMClientFactory,
        browser_session: BrowserSession,
        output_dir: Path,
        memory_service: "MemoryService",
        container: "Container | None" = None,
        agents_config: AgentsConfig | None = None,
    ):
        """Initialize the main agent.

        Args:
            llm: LLM client or factory for API calls
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
        self.plan_generator_agent = PlanGeneratorAgent(
            llm,
            output_dir=output_dir,
            memory_service=self._container.memory_service("plan_generator"),
        )

        # Mapping from internal agent name to config key
        agent_to_config = {
            "discovery_agent": "discovery",
            "selector_agent": "selector",
            "accessibility_agent": "accessibility",
            "data_prep_agent": "data_prep",
            "plan_generator_agent": "plan_generator",
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
        plan_generator_paths = agents_config.get_schema_paths("plan_generator")

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
            AgentTool(
                agent=self.plan_generator_agent,
                output_schema_path=plan_generator_paths.output_contract_schema_path,
                input_schema_path=plan_generator_paths.input_contract_schema_path,
                description="Generate comprehensive crawl plan from collected sub-agent information",
            ),
        ]

        # Unified tools list - AgentTools are auto-detected by BaseAgent
        tools = [
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemoryListTool(memory_service),
            # Plan generators (structured output from memory)
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
        from ..prompts.template_renderer import render_agent_template

        task = render_agent_template("crawl_plan_task.md.j2", url=url)
        return self.run(task)
