"""Tool for preparing validation context."""

from typing import Any

from ...contracts.schema_parser import load_schema
from ...contracts.validation_registry import ValidationRegistry
from ...observability.decorators import traced_tool
from ..base import BaseTool


class PrepareAgentOutputValidationTool(BaseTool):
    """Prepare validation context for a sub-agent's output.

    Parent agents use this tool to register what output schema they expect
    from a sub-agent. The sub-agent can then use ValidateResponseTool to
    validate its output before returning.

    Example:
        # Parent agent workflow:
        # 1. Generate UUID
        # 2. Prepare validation context
        tool.execute(
            run_identifier="uuid-123",
            agent_name="discovery_agent"
        )
        # 3. Call sub-agent with run_identifier
        # 4. Sub-agent validates and returns
    """

    def __init__(
        self,
        schema_paths: dict[str, str],
        registry: ValidationRegistry | None = None,
    ):
        """Initialize with schema paths and optional registry.

        Args:
            schema_paths: Dict mapping agent names to output schema paths
            registry: ValidationRegistry instance (defaults to singleton)
        """
        self._schema_paths = schema_paths
        self._registry = registry or ValidationRegistry.get_instance()

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "prepare_agent_output_validation"

    @property
    def description(self) -> str:
        """Description for LLM."""
        return (
            "Register a validation context before calling a sub-agent. "
            "The sub-agent will use this to validate its output before returning."
        )

    @traced_tool()
    def execute(
        self,
        run_identifier: str,
        agent_name: str,
        expected_outputs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register validation context for a sub-agent call.

        Args:
            run_identifier: UUID from generate_uuid tool
            agent_name: Name of the agent to validate
            expected_outputs: Optional specific fields to validate
                             (defaults to schema's required fields)

        Returns:
            Dict with success and context details, or error
        """
        if agent_name not in self._schema_paths:
            return {"success": False, "error": f"Unknown agent: {agent_name}"}

        schema = load_schema(self._schema_paths[agent_name])
        available_fields = set(schema.get("properties", {}).keys())

        # If expected_outputs provided, validate they exist in schema
        if expected_outputs:
            invalid_fields = [f for f in expected_outputs if f not in available_fields]
            if invalid_fields:
                return {
                    "success": False,
                    "error": f"Invalid fields: {invalid_fields}. Available: {sorted(available_fields)}",
                    "available_fields": sorted(available_fields),
                }
            outputs = expected_outputs
        else:
            outputs = schema.get("required", [])

        context = self._registry.register(
            run_identifier=run_identifier,
            schema=schema,
            agent_name=agent_name,
            expected_outputs=outputs,
        )

        return {
            "success": True,
            "run_identifier": run_identifier,
            "agent_name": agent_name,
            "expected_outputs": context.expected_outputs,
            "available_fields": sorted(available_fields),
            "message": (
                f"Validation prepared. Sub-agent should call validate_response "
                f"with run_identifier '{run_identifier}'"
            ),
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "run_identifier": {
                    "type": "string",
                    "description": "UUID from generate_uuid tool",
                },
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent to validate",
                },
                "expected_outputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional specific fields to validate",
                },
            },
            "required": ["run_identifier", "agent_name"],
        }
