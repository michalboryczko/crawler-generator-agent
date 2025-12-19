"""Tool for validating agent response against schema."""

import json
from typing import Any

import jsonschema

from ...contracts.validation_registry import ValidationRegistry
from ...observability.decorators import traced_tool
from ..base import BaseTool


class ValidateResponseTool(BaseTool):
    """Validate agent response against registered schema.

    Sub-agents use this tool to validate their output JSON before returning
    to the parent agent. The validation context must have been prepared by
    the parent using PrepareAgentOutputValidationTool.

    Example:
        # Sub-agent workflow:
        # 1. Do work and prepare response
        # 2. Validate before returning
        result = tool.execute(
            run_identifier="uuid-from-parent",
            response_json={"article_urls": [...], "pagination_type": "numbered"}
        )
        if result["valid"]:
            # Safe to return
        else:
            # Fix issues based on result["validation_errors"]
    """

    def __init__(self, registry: ValidationRegistry | None = None):
        """Initialize with optional registry.

        Args:
            registry: ValidationRegistry instance (defaults to singleton)
        """
        self._registry = registry or ValidationRegistry.get_instance()

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "validate_response"

    @property
    def description(self) -> str:
        """Description for LLM."""
        return (
            "Validate your response JSON against the expected output contract. "
            "Call this before returning your final output."
        )

    @traced_tool()
    def execute(
        self,
        run_identifier: str,
        response_json: dict[str, Any] | str,
    ) -> dict[str, Any]:
        """Validate response against registered schema.

        Supports both wrapped structure (with data key) and legacy flat structure.

        Wrapped structure:
            {
                "agent_response_content": "summary",
                "data": { ...actual schema properties... }
            }

        Legacy flat structure:
            { ...schema properties... }

        Args:
            run_identifier: UUID linking to validation context
            response_json: The JSON response to validate (dict or JSON string)

        Returns:
            Dict with:
            - success=True, valid=True on successful validation
            - success=True, valid=False with validation_errors on failure
            - success=False with error if no context found or invalid JSON
        """
        # Handle string input (LLM may pass JSON as string)
        if isinstance(response_json, str):
            try:
                response_json = json.loads(response_json)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON string: {e}",
                }

        context = self._registry.get(run_identifier)
        if not context:
            return {
                "success": False,
                "error": f"No validation context for run_identifier: {run_identifier}",
            }

        # Ensure response_json is a dict for further processing
        if not isinstance(response_json, dict):
            return {
                "success": False,
                "error": f"Expected JSON object, got {type(response_json).__name__}",
            }

        # Extract data from wrapper if present
        if "data" in response_json and isinstance(response_json.get("data"), dict):
            validation_data = response_json["data"]
            agent_content = response_json.get("agent_response_content")
            is_wrapped = True
        else:
            # Support legacy flat structure
            validation_data = response_json
            agent_content = response_json.get("agent_response_content")
            is_wrapped = False

        errors: list[dict[str, str]] = []

        # Validate agent_response_content if schema expects it
        schema_requires_content = "agent_response_content" in context.schema.get("required", [])
        if schema_requires_content and not agent_content:
            errors.append(
                {
                    "path": "agent_response_content",
                    "message": "Missing required field: agent_response_content",
                }
            )

        # Validate data against schema (exclude agent_response_content from validation)
        schema_for_data = self._get_data_schema(context.schema)

        try:
            jsonschema.validate(validation_data, schema_for_data)
        except jsonschema.ValidationError as e:
            # Extract path as dot-separated string
            path = ".".join(str(p) for p in e.path) if e.path else ""
            if is_wrapped and path:
                path = f"data.{path}"
            errors.append({"path": path, "message": e.message})

        if errors:
            return {
                "success": True,
                "valid": False,
                "validation_errors": errors,
                "message": f"Validation failed: {errors[0]['message']}",
            }

        return {
            "success": True,
            "valid": True,
            "message": "Response validates against contract",
        }

    def _get_data_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Get schema for data validation, excluding agent_response_content.

        Args:
            schema: Original schema with possible agent_response_content

        Returns:
            Schema for validating data portion only
        """
        # Copy schema to avoid mutations
        data_schema = schema.copy()
        properties = data_schema.get("properties", {}).copy()
        required = list(data_schema.get("required", []))

        # Remove agent_response_content from validation
        if "agent_response_content" in properties:
            del properties["agent_response_content"]
            data_schema["properties"] = properties

        if "agent_response_content" in required:
            required.remove("agent_response_content")
            data_schema["required"] = required

        return data_schema

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "run_identifier": {
                    "type": "string",
                    "description": "UUID linking to validation context from parent",
                },
                "response_json": {
                    "type": "object",
                    "description": "The JSON response to validate",
                },
            },
            "required": ["run_identifier", "response_json"],
        }
