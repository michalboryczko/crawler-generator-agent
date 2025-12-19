"""Contract-driven agent communication system.

This package provides tools for schema-based validation of agent outputs,
enabling structured parent-child communication with validated contracts.

Note: AgentTool and contract tools have been moved to src/tools/agent_tools/
      Template rendering has been moved to src/prompts/template_renderer.py
"""

from .exceptions import ContractValidationError, SchemaLoadError
from .schema_parser import (
    SCHEMAS_BASE_PATH,
    extract_field_paths,
    generate_example_json,
    generate_fields_markdown,
    load_schema,
)
from .validation_registry import ValidationContext, ValidationRegistry

__all__ = [
    # Exceptions
    "ContractValidationError",
    "SchemaLoadError",
    # Schema parser functions
    "load_schema",
    "extract_field_paths",
    "generate_example_json",
    "generate_fields_markdown",
    "SCHEMAS_BASE_PATH",
    # Validation registry
    "ValidationContext",
    "ValidationRegistry",
]
