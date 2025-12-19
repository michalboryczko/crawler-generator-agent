"""Tool parameter validation decorator.

This module provides the @validated_tool decorator that validates tool arguments
against the tool's parameter schema before execution. This ensures:

1. Agents get helpful error messages when arguments are missing/invalid
2. Tools have consistent execute(**kwargs) signatures (solving mypy override issues)
3. Runtime validation matches the JSON schema provided to the LLM
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import jsonschema

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., dict[str, Any]])


def validated_tool(func: F) -> F:
    """Decorator that validates tool arguments against parameter schema.

    Wraps the execute method to:
    1. Accept **kwargs (consistent signature across all tools)
    2. Validate against get_parameters_schema() before execution
    3. Return structured error if validation fails (agent can retry)
    4. Call original execute with validated kwargs if valid

    Example:
        class MyTool(BaseTool):
            @traced_tool()
            @validated_tool
            def execute(self, required_arg: str, optional_arg: str = "") -> dict[str, Any]:
                ...

    If agent calls without required_arg:
        {"success": False, "error": "Missing required argument: required_arg", ...}

    Returns:
        Wrapped function with validation
    """

    @functools.wraps(func)
    def wrapper(self: Any, **kwargs: Any) -> dict[str, Any]:
        # Get the tool's parameter schema
        schema = self.get_parameters_schema()

        # Validate kwargs against schema
        validation_error = _validate_arguments(kwargs, schema)
        if validation_error:
            tool_name = getattr(self, "name", func.__name__)
            logger.warning(f"Tool {tool_name} validation failed: {validation_error}")
            return {
                "success": False,
                "error": validation_error,
                "provided_arguments": list(kwargs.keys()),
                "hint": "Check required arguments and their types",
            }

        # Call original execute with validated kwargs
        return func(self, **kwargs)

    return wrapper


def _validate_arguments(kwargs: dict[str, Any], schema: dict[str, Any]) -> str | None:
    """Validate arguments against JSON schema.

    Args:
        kwargs: Arguments provided to tool
        schema: JSON schema from get_parameters_schema()

    Returns:
        Error message string if validation fails, None if valid
    """
    # Check required arguments first (clearer error message)
    required = schema.get("required", [])
    missing = [arg for arg in required if arg not in kwargs]
    if missing:
        if len(missing) == 1:
            return f"Missing required argument: {missing[0]}"
        return f"Missing required arguments: {', '.join(missing)}"

    # Full schema validation for type checking
    try:
        jsonschema.validate(kwargs, schema)
    except jsonschema.ValidationError as e:
        # Extract the most useful error message
        if e.path:
            path = ".".join(str(p) for p in e.path)
            return f"Invalid argument '{path}': {e.message}"
        return f"Validation error: {e.message}"

    return None
