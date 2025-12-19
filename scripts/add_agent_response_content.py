#!/usr/bin/env python3
"""Add agent_response_content field to all output schemas.

This field allows agents to include a natural language summary
alongside their structured JSON output.

Usage:
    python scripts/add_agent_response_content.py
"""

import json
import sys
from pathlib import Path

# Field definition to add to all output schemas
AGENT_RESPONSE_CONTENT_FIELD = {
    "type": "string",
    "description": (
        "Natural language summary of the agent's response, "
        "explaining key findings and decisions in human-readable form"
    ),
}


def update_schema(schema_path: Path) -> bool:
    """Add agent_response_content to schema if not present.

    Args:
        schema_path: Path to output.schema.json file

    Returns:
        True if schema was modified, False if field already existed
    """
    with open(schema_path) as f:
        schema = json.load(f)

    properties = schema.get("properties", {})

    if "agent_response_content" in properties:
        print(f"  [SKIP] {schema_path.name} - field already exists")
        return False

    properties["agent_response_content"] = AGENT_RESPONSE_CONTENT_FIELD
    schema["properties"] = properties

    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")

    print(f"  [UPDATE] {schema_path.name} - added agent_response_content")
    return True


def main():
    """Run migration on all output schemas."""
    # Find contracts directory relative to script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    contracts_dir = project_root / "docs" / "agent_contracts" / "goal" / "contracts"

    if not contracts_dir.exists():
        print(f"Error: Contracts directory not found: {contracts_dir}")
        sys.exit(1)

    output_schemas = list(contracts_dir.glob("**/output.schema.json"))

    print(f"Found {len(output_schemas)} output schemas")
    print()

    modified = 0
    for schema_path in output_schemas:
        agent_name = schema_path.parent.name
        print(f"Processing {agent_name}:")
        if update_schema(schema_path):
            modified += 1

    print()
    print(f"Modified {modified} of {len(output_schemas)} schemas")

    return 0


if __name__ == "__main__":
    sys.exit(main())
