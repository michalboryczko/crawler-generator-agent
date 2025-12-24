"""Plan Generator Agent for creating crawl plans from collected information.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.prompts import get_prompt_provider

from ..core.llm import LLMClient, LLMClientFactory
from ..tools.agent_tools import ValidateResponseTool
from ..tools.crawler_config_generator import PrepareCrawlerConfigurationTool
from ..tools.file import FileCreateTool, FileReplaceTool
from ..tools.memory import (
    MemoryListTool,
    MemoryReadTool,
    MemorySearchTool,
    MemoryWriteTool,
)
from ..tools.plan_draft_provider import PlanDraftProviderTool
from ..tools.supervisor import SupervisorTool
from .base import BaseAgent

if TYPE_CHECKING:
    from ..services.context_service import ContextService
    from ..services.memory_service import MemoryService


class PlanGeneratorAgent(BaseAgent):
    """Agent for generating crawl plans from collected sub-agent information.

    This agent uses:
    - PlanDraftProviderTool: Get plan template structure
    - PrepareCrawlerConfigurationTool: Generate crawler config JSON
    - SupervisorTool: Validate output quality using LLM
    - File tools: Create and update plan.md file
    - Memory tools: Read collected information and store results
    """

    name = "plan_generator_agent"
    description = "Generates comprehensive crawl plans from collected sub-agent data"
    system_prompt = get_prompt_provider().get_agent_prompt("plan_generator")

    def __init__(
        self,
        llm: LLMClient | LLMClientFactory,
        output_dir: Path,
        memory_service: "MemoryService",
        context_service: "ContextService | None" = None,
    ):
        """Initialize the Plan Generator Agent.

        Args:
            llm: LLM client or factory for agent operations and supervisor validation
            output_dir: Directory where plan.md will be created
            memory_service: Memory service for reading collected information
            context_service: Optional ContextService for persisting context events
        """
        self.output_dir = output_dir

        # Get LLM client for supervisor tool
        if isinstance(llm, LLMClientFactory):
            supervisor_llm = llm.get_client("supervisor_tool")
        else:
            supervisor_llm = llm

        tools = [
            # Plan generation tools
            PlanDraftProviderTool(),
            PrepareCrawlerConfigurationTool(),
            SupervisorTool(supervisor_llm),
            # File tools
            FileCreateTool(output_dir),
            FileReplaceTool(output_dir),
            # Memory tools
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            MemorySearchTool(memory_service),
            MemoryListTool(memory_service),
            # Contract validation
            ValidateResponseTool(),
        ]

        super().__init__(llm, tools, memory_service=memory_service, context_service=context_service)

    # Template for user prompt with collected information
    user_prompt_template = "plan_generator_user.md.j2"

    def _build_user_prompt(self, task: str, context: dict[str, Any] | None) -> str:
        """Build user prompt with collected information formatted for plan generation.

        Uses specialized template that renders collected_information from each
        sub-agent in a structured, readable markdown format instead of raw JSON.

        Args:
            task: The task description
            context: Context containing target_url, task_name, collected_information

        Returns:
            Formatted user prompt with collected information as markdown
        """
        if not context or "collected_information" not in context:
            # Fall back to default behavior
            return super()._build_user_prompt(task, context)

        from ..prompts.template_renderer import render_agent_template

        return render_agent_template(
            self.user_prompt_template,
            task=task,
            target_url=context.get("target_url", ""),
            task_name=context.get("task_name", "Generate Crawl Plan"),
            collected_information=context.get("collected_information", []),
        )
