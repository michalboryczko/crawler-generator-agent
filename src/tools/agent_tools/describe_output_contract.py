"""Tool for describing agent output contracts."""

import json
from typing import Any

from ...contracts.schema_parser import generate_example_json, load_schema
from ...observability.decorators import traced_tool
from ..base import BaseTool


class DescribeOutputContractTool(BaseTool):
    """Describe the output contract for a specific agent.

    This tool allows an LLM to query the expected output format for any
    sub-agent before invoking it. Returns human-readable field descriptions,
    example JSON, and the list of required fields.

    Example:
        tool = DescribeOutputContractTool(
            schema_paths={
                "discovery_agent": "discovery/output.schema.json",
                "selector_agent": "selector/output.schema.json",
            }
        )
        result = tool.execute(agent_name="discovery_agent")
        # result["fields_description"] contains detailed field descriptions
        # result["schema_json"] contains example JSON string
        # result["available_fields"] lists all fields
    """

    def __init__(self, schema_paths: dict[str, str]):
        """Initialize with mapping of agent names to schema paths.

        Args:
            schema_paths: Dict mapping agent names to their output schema paths
        """
        self._schema_paths = schema_paths

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "describe_output_contract"

    @property
    def description(self) -> str:
        """Description listing available agents."""
        if self._schema_paths:
            agents = ", ".join(self._schema_paths.keys())
            return (
                f"Get the expected output contract (JSON schema) for a sub-agent. "
                f"Available agents: {agents}"
            )
        return "Get the expected output contract (JSON schema) for a sub-agent."

    @traced_tool()
    def execute(self, agent_name: str) -> dict[str, Any]:
        """Get output contract description for an agent.

        Args:
            agent_name: Name of the agent to describe

        Returns:
            Dict with success, agent_name, schema_json, fields_description,
            available_fields, required_fields on success, or success=False
            with error on failure
        """
        if agent_name not in self._schema_paths:
            available = list(self._schema_paths.keys())
            return {
                "success": False,
                "error": f"Unknown agent: {agent_name}. Available: {available}",
            }

        schema = load_schema(self._schema_paths[agent_name])
        example_json = generate_example_json(schema)

        return {
            "success": True,
            "agent_name": agent_name,
            "schema_json": json.dumps(example_json, indent=2),
            "fields_description": self._generate_detailed_fields_markdown(schema),
            "available_fields": list(schema.get("properties", {}).keys()),
            "required_fields": schema.get("required", []),
        }

    def _generate_detailed_fields_markdown(self, schema: dict[str, Any], prefix: str = "") -> str:
        """Generate detailed markdown with field path, example, type, status, description.

        Args:
            schema: JSON schema dictionary
            prefix: Prefix for nested field paths

        Returns:
            Markdown string with detailed field documentation
        """
        lines: list[str] = []
        if not prefix:
            lines.append("### Fields:")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        for field, prop in properties.items():
            full_path = f"{prefix}.{field}" if prefix else field
            req_status = "required" if field in required else "optional"
            field_type = self._get_type_string(prop)
            desc = prop.get("description", "No description")
            example = self._get_example_value(prop)

            lines.append(f"- **{full_path}** - `{example}` - {field_type} is {req_status} - {desc}")

            # Handle nested objects
            if prop.get("type") == "object" and "properties" in prop:
                nested_md = self._generate_detailed_fields_markdown(prop, full_path)
                # Remove header from nested (already has one at top)
                nested_lines = nested_md.split("\n")
                lines.extend([f"  {line}" for line in nested_lines if not line.startswith("###")])

            # Handle arrays of objects
            if prop.get("type") == "array":
                items = prop.get("items", {})
                if items.get("type") == "object" and "properties" in items:
                    nested_md = self._generate_detailed_fields_markdown(items, f"{full_path}[]")
                    nested_lines = nested_md.split("\n")
                    lines.extend(
                        [f"  {line}" for line in nested_lines if not line.startswith("###")]
                    )

        return "\n".join(lines)

    def _get_type_string(self, prop: dict[str, Any]) -> str:
        """Get human-readable type string for a property.

        Args:
            prop: Property definition from schema

        Returns:
            Type string (e.g., "string", "array<string>", "object")
        """
        prop_type = prop.get("type", "any")

        # Handle union types like ["string", "null"]
        if isinstance(prop_type, list):
            non_null = [t for t in prop_type if t != "null"]
            if non_null:
                prop_type = non_null[0]
                if "null" in prop.get("type", []):
                    return f"{prop_type}?"  # nullable
            else:
                prop_type = "null"

        # Handle arrays with item types
        if prop_type == "array":
            items = prop.get("items", {})
            item_type = items.get("type", "any")
            if item_type == "object":
                return "array<object>"
            return f"array<{item_type}>"

        # Handle enums
        if "enum" in prop:
            return f"enum({', '.join(str(v) for v in prop['enum'])})"

        return str(prop_type)

    def _get_example_value(self, prop: dict[str, Any]) -> str:
        """Get example value for a property.

        Args:
            prop: Property definition from schema

        Returns:
            String representation of example value
        """
        # Check for examples in schema
        examples = prop.get("examples")
        if examples and isinstance(examples, list) and len(examples) > 0:
            example = examples[0]
            if isinstance(example, str):
                return f'"{example}"'
            return str(example)

        # Generate based on type
        prop_type = prop.get("type")

        # Handle union types
        if isinstance(prop_type, list):
            prop_type = next((t for t in prop_type if t != "null"), "any")

        if prop_type == "string":
            if "enum" in prop:
                return f'"{prop["enum"][0]}"'
            return '"<string>"'
        elif prop_type == "integer":
            return "0"
        elif prop_type == "number":
            return "0.0"
        elif prop_type == "boolean":
            return "true"
        elif prop_type == "array":
            return "[]"
        elif prop_type == "object":
            return "{...}"
        else:
            return "null"

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return schema with required agent_name parameter."""
        return {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent whose output contract to describe",
                }
            },
            "required": ["agent_name"],
        }
