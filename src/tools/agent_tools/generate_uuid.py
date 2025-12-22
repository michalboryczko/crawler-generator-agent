"""Tool for generating validation tracking UUIDs."""

import uuid
from typing import Any

from ...observability.decorators import traced_tool
from ..base import BaseTool
from ..validation import validated_tool


class GenerateUuidTool(BaseTool):
    """Generate a UUID for validation tracking.

    The generated UUID is used to track validation contexts through the
    parent-child agent workflow. Parent agents call this before invoking
    a sub-agent to get a unique identifier that links the validation
    context they prepare with the response they receive.

    Example:
        # Parent agent workflow:
        uuid_tool = GenerateUuidTool()
        result = uuid_tool.execute()
        run_id = result["run_identifier"]  # Use this in prepare_validation
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "generate_uuid"

    @property
    def description(self) -> str:
        """Description for LLM."""
        return (
            "Generate a unique identifier (UUID) for tracking validation of "
            "sub-agent outputs. Call this before invoking a sub-agent to get "
            "a run_identifier that links your validation context to the response."
        )

    @traced_tool()
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Generate a new UUID4. Instrumented by @traced_tool."""
        run_identifier = str(uuid.uuid4())
        return {"success": True, "run_identifier": run_identifier}
