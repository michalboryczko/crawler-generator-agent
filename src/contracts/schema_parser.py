"""Schema parsing and introspection utilities."""

import json
from pathlib import Path
from typing import Any

from .exceptions import SchemaLoadError

# Project root for resolving relative schema paths
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Base path for schema files (used by tests)
SCHEMAS_BASE_PATH = PROJECT_ROOT / "src" / "contracts" / "schemas"

# Standard field injected into all output schemas
AGENT_RESPONSE_CONTENT_FIELD = {
    "agent_response_content": {
        "type": "string",
        "description": (
            "Natural language summary of the agent's response, "
            "explaining key findings and decisions in human-readable form"
        ),
    }
}


def inject_agent_response_content(schema: dict[str, Any]) -> dict[str, Any]:
    """Inject agent_response_content field into schema if not present.

    Args:
        schema: The original schema dict

    Returns:
        Schema with agent_response_content injected
    """
    # Create a copy to avoid mutating original
    schema = schema.copy()
    properties = schema.get("properties", {}).copy()

    if "agent_response_content" not in properties:
        properties["agent_response_content"] = AGENT_RESPONSE_CONTENT_FIELD[
            "agent_response_content"
        ]
        schema["properties"] = properties

    return schema


def load_schema(schema_path: str | Path, inject_response_content: bool = False) -> dict[str, Any]:
    """Load JSON schema from file path.

    Args:
        schema_path: Absolute path or relative to project root
        inject_response_content: If True, injects agent_response_content field

    Returns:
        Parsed JSON schema as dictionary

    Raises:
        SchemaLoadError: If file not found or invalid JSON
    """
    path = Path(schema_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        raise SchemaLoadError(str(schema_path), "File not found")

    try:
        schema = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SchemaLoadError(str(schema_path), f"Invalid JSON: {e}") from e

    if inject_response_content:
        schema = inject_agent_response_content(schema)

    return schema


def extract_field_paths(schema: dict[str, Any], prefix: str = "") -> list[str]:
    """Extract all field paths from schema.

    Uses dot notation for nested fields (e.g., 'pagination.type')
    and bracket notation for arrays (e.g., 'article_urls[]').

    Args:
        schema: JSON schema dictionary
        prefix: Prefix for nested paths

    Returns:
        List of field paths
    """
    paths: list[str] = []
    properties = schema.get("properties", {})

    for name, prop in properties.items():
        full_path = f"{prefix}.{name}" if prefix else name
        prop_type = prop.get("type")

        if prop_type == "array":
            paths.append(f"{full_path}[]")
            # If array items are objects, recurse into them
            items = prop.get("items", {})
            if items.get("type") == "object":
                paths.extend(extract_field_paths(items, f"{full_path}[]"))
        else:
            paths.append(full_path)

        # Recurse into nested objects
        if prop_type == "object":
            paths.extend(extract_field_paths(prop, full_path))

    return paths


def _generate_example_value(prop: dict[str, Any]) -> Any:
    """Generate example value for a single property.

    Args:
        prop: Property definition from schema

    Returns:
        Example value of appropriate type
    """
    prop_type = prop.get("type")

    # Check for examples in schema
    examples = prop.get("examples")
    if examples and isinstance(examples, list) and len(examples) > 0:
        return examples[0]

    # Generate based on type
    if prop_type == "string":
        return "<string>"
    elif prop_type == "integer":
        return 0
    elif prop_type == "number":
        return 0.0
    elif prop_type == "boolean":
        return True
    elif prop_type == "array":
        return []
    elif prop_type == "object":
        return generate_example_json(prop, wrap_in_data=False)
    else:
        # Handle union types like ["string", "null"]
        if isinstance(prop_type, list):
            type_defaults = {
                "string": "<string>",
                "integer": 0,
                "number": 0.0,
                "boolean": True,
            }
            for t in prop_type:
                if t in type_defaults:
                    return type_defaults[t]
            return None
        return None


def generate_example_json(schema: dict[str, Any], wrap_in_data: bool = False) -> dict[str, Any]:
    """Generate example JSON structure from schema.

    Args:
        schema: JSON schema dictionary
        wrap_in_data: If True, wrap properties in 'data' object with
                     agent_response_content at top level

    Returns:
        Example dictionary matching expected response structure
    """
    properties = schema.get("properties", {})

    if wrap_in_data:
        # Build data fields (excluding agent_response_content)
        data_fields: dict[str, Any] = {}
        for name, prop in properties.items():
            if name == "agent_response_content":
                continue  # Handle separately at top level
            data_fields[name] = _generate_example_value(prop)

        return {
            "agent_response_content": "<summary of findings>",
            "data": data_fields,
        }

    # Flat structure (original behavior)
    result: dict[str, Any] = {}
    for name, prop in properties.items():
        result[name] = _generate_example_value(prop)

    return result


def generate_fields_markdown(schema: dict[str, Any]) -> str:
    """Generate markdown documentation of schema fields.

    Args:
        schema: JSON schema dictionary

    Returns:
        Markdown string with required and optional fields sections
    """
    lines: list[str] = ["## Required Fields"]
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # Required fields
    for field in required:
        prop = properties.get(field, {})
        desc = prop.get("description", "No description")
        lines.append(f"- **{field}**: {desc}")

    # Optional fields
    lines.append("\n## Optional Fields")
    for field, prop in properties.items():
        if field not in required:
            desc = prop.get("description", "No description")
            lines.append(f"- **{field}**: {desc}")

    return "\n".join(lines)
