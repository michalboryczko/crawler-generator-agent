"""AgentTool - wrapper for sub-agents with contract support.

This module uses the @traced_tool decorator for automatic tool instrumentation.
"""

import json
from typing import TYPE_CHECKING, Any

from ...contracts.schema_parser import generate_example_json, generate_fields_markdown, load_schema
from ...observability.decorators import traced_tool
from ..base import BaseTool

if TYPE_CHECKING:
    from ...agents.base import BaseAgent


class AgentTool(BaseTool):
    """Tool that wraps a sub-agent with contract metadata.

    Provides prompt_attachment() for generating prompt sections that describe
    the agent's input requirements and output contract.

    Example:
        tool = AgentTool(
            agent=discovery_agent,
            output_schema_path="discovery/output.schema.json",
            description="Run discovery agent to find article URLs"
        )

        # Get OpenAI-compatible schema for function calling
        schema = tool.to_openai_schema()

        # Generate prompt section describing the agent
        prompt_section = tool.prompt_attachment()
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

    @property
    def agent(self) -> "BaseAgent":
        """The wrapped sub-agent."""
        return self._agent

    @property
    def output_schema(self) -> dict[str, Any]:
        """The output contract schema."""
        return self._output_schema

    @property
    def input_schema(self) -> dict[str, Any] | None:
        """The input contract schema (if defined)."""
        return self._input_schema

    def get_agent_name(self) -> str:
        """Return the wrapped agent's name."""
        return self._agent.name

    def get_agent_description(self) -> str:
        """Return agent's full description via agent's get_description method."""
        return self._agent.get_description()

    def get_tool_name(self) -> str:
        """Return the tool name (run_{agent.name})."""
        return self.name

    def get_output_contract_schema(self) -> dict[str, Any]:
        """Return the output contract schema dictionary."""
        return self._output_schema

    def get_input_contract_schema(self) -> dict[str, Any] | None:
        """Return the input contract schema dictionary or None."""
        return self._input_schema

    @traced_tool()  # Uses self.name dynamically (run_{agent.name})
    def execute(
        self,
        task: str,
        context: dict | None = None,
        run_identifier: str | None = None,
        expected_outputs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute the wrapped agent.

        Instrumented by @traced_tool - logs tool inputs/outputs.

        Args:
            task: Task description to pass to the agent
            context: Optional context data for the agent
            run_identifier: Optional UUID for validation context tracking
            expected_outputs: Optional list of expected output fields

        Returns:
            Dict with success, data, errors, and iterations
        """
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

        Returns OpenAI-compatible parameter schema with:
        - task (required): Task description string
        - context (optional): Context data object
        - run_identifier (optional): UUID for validation tracking
        - expected_outputs (optional): List of expected output fields
        """
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": f"Task for the {self._agent.name} agent",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context data to pass to agent",
                },
                "run_identifier": {
                    "type": "string",
                    "description": "UUID from generate_uuid for validation tracking",
                },
                "expected_outputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of expected output fields from the agent",
                },
            },
            "required": ["task"],
        }

    def prompt_attachment(self) -> str:
        """Generate prompt section describing this agent and its contracts.

        Returns a markdown-formatted string that can be included in prompts
        to describe the sub-agent's capabilities and expected output format.

        The example JSON uses the wrapped structure with agent_response_content
        at the top level and actual data in a nested 'data' object.

        Returns:
            Markdown string with agent description and contracts
        """
        # Format example JSON with wrapped structure
        example_json = generate_example_json(self._output_schema, wrap_in_data=True)
        example_json_str = json.dumps(example_json, indent=2)

        lines = [
            f"### {self._agent.name}",
            f"**Tool name:** `{self.name}`",
            f"**Description:** {self._description}",
            "",
            "#### Output Contract",
            generate_fields_markdown(self._output_schema),
            "",
            "#### Example Output",
            "```json",
            example_json_str,
            "```",
        ]

        if self._input_schema:
            lines.extend(
                [
                    "",
                    "#### Input Contract",
                    generate_fields_markdown(self._input_schema),
                ]
            )

        return "\n".join(lines)
