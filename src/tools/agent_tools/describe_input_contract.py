"""Tool for describing agent input requirements."""

from typing import Any

from ...contracts.schema_parser import generate_fields_markdown, load_schema
from ...observability.decorators import traced_tool
from ..base import BaseTool


class DescribeInputContractTool(BaseTool):
    """Describe the input requirements for a specific agent.

    This tool allows an LLM to query what context data a sub-agent requires
    before invoking it. Returns human-readable field descriptions and the
    list of required input fields.

    Example:
        tool = DescribeInputContractTool(
            schema_paths={
                "discovery_agent": "discovery/input.schema.json",
                "selector_agent": "selector/input.schema.json",
            }
        )
        result = tool.execute(agent_name="discovery_agent")
        # result["fields_markdown"] contains input field descriptions
    """

    def __init__(self, schema_paths: dict[str, str]):
        """Initialize with mapping of agent names to input schema paths.

        Args:
            schema_paths: Dict mapping agent names to their input schema paths
        """
        self._schema_paths = schema_paths

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "describe_input_contract"

    @property
    def description(self) -> str:
        """Description for LLM."""
        return "Get the expected input contract for a sub-agent - what context data it requires."

    @traced_tool()
    def execute(self, agent_name: str) -> dict[str, Any]:
        """Get input contract description for an agent.

        Args:
            agent_name: Name of the agent to describe

        Returns:
            Dict with success, agent_name, fields_markdown, required_fields
            on success, or success=False with error on failure
        """
        if agent_name not in self._schema_paths:
            return {"success": False, "error": f"Unknown agent: {agent_name}"}

        schema = load_schema(self._schema_paths[agent_name])
        return {
            "success": True,
            "agent_name": agent_name,
            "fields_markdown": generate_fields_markdown(schema),
            "required_fields": schema.get("required", []),
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return schema with required agent_name parameter."""
        return {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent whose input contract to describe",
                }
            },
            "required": ["agent_name"],
        }
