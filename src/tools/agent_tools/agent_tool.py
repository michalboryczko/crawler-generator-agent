"""AgentTool - wrapper for sub-agents with contract support.

This module uses the @traced_tool decorator for automatic tool instrumentation.
"""

import copy
from typing import TYPE_CHECKING, Any

from ...contracts.schema_parser import TOOL_SCHEMAS_PATH, load_schema
from ...observability.decorators import traced_tool
from ..base import BaseTool
from ..validation import validated_tool

if TYPE_CHECKING:
    from ...agents.base import BaseAgent


class AgentTool(BaseTool):
    """Tool that wraps a sub-agent with contract metadata.

    Example:
        tool = AgentTool(
            agent=discovery_agent,
            output_schema_path="discovery/output.schema.json",
            description="Run discovery agent to find article URLs"
        )

        # Get OpenAI-compatible schema for function calling
        schema = tool.to_openai_schema()
    """

    def __init__(
        self,
        agent: "BaseAgent",
        output_schema_path: str,
        input_schema_path: str | None = None,
        description: str | None = None,
    ):
        """Initialize AgentTool.

        Args:
            agent: The sub-agent to wrap
            output_schema_path: Path to the output JSON schema
            input_schema_path: Optional path to input JSON schema
            description: Custom description (defaults to "Run {agent.name} agent")
        """
        self._agent = agent
        self._output_schema_path = output_schema_path
        self._input_schema_path = input_schema_path
        self._description = description or f"Run {agent.name} agent"

        # Load and cache schemas
        # Output schema gets agent_response_content field injected automatically
        self._output_schema = load_schema(output_schema_path, inject_response_content=True)
        self._input_schema = load_schema(input_schema_path) if input_schema_path else None

    @property
    def name(self) -> str:
        """Tool identifier: run_{agent.name}."""
        return f"run_{self._agent.name}"

    @property
    def description(self) -> str:
        """Human-readable description for LLM."""
        return self._description

    # --- Template-accessed methods (used in sub_agents_section.md.j2) ---

    def get_agent_name(self) -> str:
        """Return the wrapped agent's name.

        Note: Called from Jinja2 template sub_agents_section.md.j2
        """
        return self._agent.name

    def get_agent_description(self) -> str:
        """Return agent's full description via agent's get_description method.

        Note: Called from Jinja2 template sub_agents_section.md.j2
        """
        return self._agent.get_description()

    def get_tool_name(self) -> str:
        """Return the tool name (run_{agent.name}).

        Note: Called from Jinja2 template sub_agents_section.md.j2
        """
        return self.name

    @traced_tool()  # Uses self.name dynamically (run_{agent.name})
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the wrapped agent. Instrumented by @traced_tool."""
        task = kwargs["task"]
        context = kwargs.get("context")
        run_identifier = kwargs.get("run_identifier")
        expected_outputs = kwargs.get("expected_outputs")

        result = self._agent.run(
            task,
            context=context,
            expected_outputs=expected_outputs,
            run_identifier=run_identifier,
            output_contract_schema=self._output_schema,
        )
        return {
            "success": result.success,
            "data": result.data,
            "errors": result.errors,
            "iterations": result.iterations,
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return JSON schema for tool parameters.

        Loads base schema from file and customizes task description with agent name.
        Returns OpenAI-compatible parameter schema with:
        - task (required): Task description string
        - context (optional): Context data object
        - run_identifier (optional): UUID for validation tracking
        - expected_outputs (optional): List of expected output fields
        """
        schema_path = TOOL_SCHEMAS_PATH / "agent_tool.schema.json"
        base_schema = load_schema(str(schema_path))
        # Create copy to avoid modifying cached schema
        schema = copy.deepcopy(base_schema)
        # Customize task description with agent name
        schema["properties"]["task"]["description"] = f"Task for the {self._agent.name} agent"
        return schema
