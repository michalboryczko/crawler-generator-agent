"""Utility for merging JSON schemas.

This module provides functions to merge multiple JSON schemas into one,
combining properties, required fields, and handling $defs/$ref correctly.
"""

from __future__ import annotations

import copy
from typing import Any


def merge_schemas(*schemas: dict[str, Any] | None) -> dict[str, Any]:
    """Merge multiple JSON schemas into one.

    Combines:
    - properties: Union of all properties (later schemas override earlier)
    - required: Union of all required arrays
    - $defs: Merged definitions
    - type: Takes from first schema that has it
    - Other fields: Later schemas override earlier

    Args:
        *schemas: JSON schema dicts to merge (None values are skipped)

    Returns:
        Merged schema dict
    """
    # Filter out None schemas
    valid_schemas = [s for s in schemas if s is not None]
    if not valid_schemas:
        return {"type": "object", "properties": {}}

    if len(valid_schemas) == 1:
        return copy.deepcopy(valid_schemas[0])

    result: dict[str, Any] = {
        "type": "object",
        "properties": {},
    }

    all_required: set[str] = set()
    all_defs: dict[str, Any] = {}

    for schema in valid_schemas:
        schema = copy.deepcopy(schema)

        # Merge properties
        if "properties" in schema:
            result["properties"].update(schema["properties"])

        # Collect required fields
        if "required" in schema:
            all_required.update(schema["required"])

        # Merge $defs
        if "$defs" in schema:
            all_defs.update(schema["$defs"])

        # Copy other fields (title, description, etc.)
        for key in ["title", "description", "$schema", "$id"]:
            if key in schema:
                result[key] = schema[key]

    # Set merged required array
    if all_required:
        result["required"] = sorted(all_required)

    # Set merged $defs
    if all_defs:
        result["$defs"] = all_defs

    # Don't set additionalProperties: false on merged schema
    # since we're combining multiple schemas

    return result


def merge_agent_tool_schema(
    base_schema: dict[str, Any],
    agent_input_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge base agent tool schema with agent-specific input schema.

    The base schema provides common fields (task, run_identifier, expected_outputs).
    The agent input schema provides agent-specific required fields (target_url, etc.).

    Agent input properties are merged at the top level.

    Args:
        base_schema: Base agent tool schema with task, run_identifier, etc.
        agent_input_schema: Agent-specific input schema with required fields

    Returns:
        Merged schema with all properties at top level
    """
    if agent_input_schema is None:
        return copy.deepcopy(base_schema)

    # Merge schemas
    merged = merge_schemas(base_schema, agent_input_schema)

    # Ensure task is always required (from base)
    if "required" not in merged:
        merged["required"] = ["task"]
    elif "task" not in merged["required"]:
        merged["required"].append("task")
        merged["required"] = sorted(merged["required"])

    return merged
