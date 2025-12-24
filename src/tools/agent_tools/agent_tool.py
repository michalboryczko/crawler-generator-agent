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
        """Human-readable description for LLM, including input requirements."""
        desc = self._description

        # Add input contract info if available
        if self._input_schema:
            required = self._input_schema.get("required", [])
            if required:
                desc += f"\n\nREQUIRED INPUT (pass via 'context' parameter): {', '.join(required)}"

        return desc

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

    def _validate_input(self, context: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate context against input schema.

        Returns error dict if validation fails, None if valid.
        Error dict is designed to help calling agent retry with correct input.

        Args:
            context: Context dict to validate against input schema

        Returns:
            None if valid, error dict with helpful hints if invalid
        """
        if not self._input_schema:
            return None  # No schema, no validation

        from jsonschema import ValidationError, validate

        if context is None:
            context = {}

        try:
            validate(instance=context, schema=self._input_schema)
            return None  # Valid
        except ValidationError as e:
            required = self._input_schema.get("required", [])
            missing = [f for f in required if f not in context]

            return {
                "success": False,
                "error": "Input contract validation failed",
                "validation_message": e.message,
                "path": list(e.path),
                "required_fields": required,
                "missing_fields": missing,
                "provided_fields": list(context.keys()) if context else [],
                "hint": f"Please provide all required fields: {', '.join(missing)}"
                if missing
                else e.message,
            }

    @traced_tool()  # Uses self.name dynamically (run_{agent.name})
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the wrapped agent with merged context.

        Extra kwargs beyond reserved keys (task, context, run_identifier,
        expected_outputs, output_contract_schema) are automatically merged
        into the context dict. This allows parent agents to pass data like
        target_url, collected_information at the same level as task.

        Input validation is performed before calling the agent. If validation
        fails, returns an error dict with helpful hints for the calling agent
        to retry with correct input (similar to output validation retry flow).

        Instrumented by @traced_tool.
        """
        # Extract reserved keys
        task = kwargs.pop("task")
        run_identifier = kwargs.pop("run_identifier", None)
        expected_outputs = kwargs.pop("expected_outputs", None)
        output_contract_schema_override = kwargs.pop("output_contract_schema", None)
        explicit_context = kwargs.pop("context", None)

        # Merge remaining kwargs into context
        # This allows parent agent to pass target_url, collected_information, etc.
        # at the same level as task, and have them merged into context
        context = explicit_context.copy() if explicit_context else {}
        context.update(kwargs)  # target_url, collected_information, etc.

        # Validate input contract BEFORE calling agent
        # Returns actionable error so calling agent can retry with correct input
        validation_error = self._validate_input(context if context else None)
        if validation_error:
            return validation_error

        result = self._agent.run(
            task,
            context=context if context else None,
            expected_outputs=expected_outputs,
            run_identifier=run_identifier,
            output_contract_schema=output_contract_schema_override or self._output_schema,
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
