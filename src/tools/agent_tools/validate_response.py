"""Tool for validating agent response against schema."""

from typing import Any

import jsonschema

from ...contracts.validation_registry import ValidationRegistry
from ...core.json_parser import extract_json
from ...observability.decorators import traced_tool
from ..base import BaseTool
from ..validation import validated_tool


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
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Validate response against registered schema. Instrumented by @traced_tool."""
        run_identifier = kwargs["run_identifier"]
        response_json = kwargs.get("response_json")

        # Handle string input - use extract_json to handle both pure JSON and embedded JSON
        if isinstance(response_json, str):
            response_json = extract_json(response_json)
            if response_json is None:
                return {
                    "success": False,
                    "extraction_failed": True,
                    "error": "Could not extract valid JSON from response",
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

        # Validate against schema (agent_response_content is auto-injected)
        try:
            jsonschema.validate(response_json, context.schema)
        except jsonschema.ValidationError as e:
            path = ".".join(str(p) for p in e.path) if e.path else ""
            return {
                "success": True,
                "valid": False,
                "validation_errors": [{"path": path, "message": e.message}],
                "message": f"Validation failed: {e.message}",
            }

        return {
            "success": True,
            "valid": True,
            "message": "Response validates against contract",
        }
