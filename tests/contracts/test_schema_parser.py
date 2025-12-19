"""Tests for schema parser utilities."""

import json

import pytest

from src.contracts.exceptions import SchemaLoadError
from src.contracts.schema_parser import (
    SCHEMAS_BASE_PATH,
    extract_field_paths,
    generate_example_json,
    generate_fields_markdown,
    inject_agent_response_content,
    load_schema,
)


class TestLoadSchema:
    """Tests for load_schema function."""

    def test_load_schema_valid(self, tmp_path):
        """Load a valid JSON schema file."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = tmp_path / "test.schema.json"
        schema_file.write_text(json.dumps(schema))

        result = load_schema(schema_file)

        assert result == schema
        assert result["type"] == "object"

    def test_load_schema_with_string_path(self, tmp_path):
        """Load schema using string path."""
        schema = {"type": "object"}
        schema_file = tmp_path / "test.schema.json"
        schema_file.write_text(json.dumps(schema))

        result = load_schema(str(schema_file))

        assert result == schema

    def test_load_schema_not_found(self):
        """Verify SchemaLoadError raised for missing file."""
        with pytest.raises(SchemaLoadError) as exc_info:
            load_schema("/nonexistent/path/schema.json")

        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.schema_path == "/nonexistent/path/schema.json"

    def test_load_schema_invalid_json(self, tmp_path):
        """Verify SchemaLoadError for malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ invalid json }")

        with pytest.raises(SchemaLoadError) as exc_info:
            load_schema(bad_file)

        assert "invalid json" in str(exc_info.value).lower()

    def test_load_real_discovery_schema(self):
        """Can load real discovery agent schema if it exists."""
        discovery_path = SCHEMAS_BASE_PATH / "discovery_agent" / "output.schema.json"
        if not discovery_path.exists():
            pytest.skip("Discovery schema not found")

        schema = load_schema(discovery_path)

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "article_urls" in schema["properties"]


class TestExtractFieldPaths:
    """Tests for extract_field_paths function."""

    def test_extract_simple_fields(self):
        """Extract paths from flat schema."""
        schema = {"properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}

        paths = extract_field_paths(schema)

        assert "name" in paths
        assert "age" in paths
        assert len(paths) == 2

    def test_extract_nested_fields(self):
        """Extract paths from nested schema with dot notation."""
        schema = {
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "address": {"type": "object", "properties": {"city": {"type": "string"}}},
                    },
                }
            }
        }

        paths = extract_field_paths(schema)

        assert "user" in paths
        assert "user.name" in paths
        assert "user.address" in paths
        assert "user.address.city" in paths

    def test_extract_array_fields(self):
        """Extract paths with array bracket notation."""
        schema = {"properties": {"items": {"type": "array", "items": {"type": "string"}}}}

        paths = extract_field_paths(schema)

        assert "items" in paths or "items[]" in paths

    def test_extract_empty_schema(self):
        """Handle schema with no properties."""
        schema = {"type": "object"}

        paths = extract_field_paths(schema)

        assert paths == []

    def test_extract_with_prefix(self):
        """Extract with custom prefix."""
        schema = {"properties": {"field": {"type": "string"}}}

        paths = extract_field_paths(schema, prefix="root")

        assert "root.field" in paths


class TestGenerateExampleJson:
    """Tests for generate_example_json function."""

    def test_generate_string_field(self):
        """Generate example for string field."""
        schema = {"properties": {"name": {"type": "string"}}}

        example = generate_example_json(schema)

        assert "name" in example
        assert isinstance(example["name"], str)

    def test_generate_integer_field(self):
        """Generate example for integer field."""
        schema = {"properties": {"count": {"type": "integer"}}}

        example = generate_example_json(schema)

        assert "count" in example
        assert isinstance(example["count"], int)

    def test_generate_number_field(self):
        """Generate example for number field."""
        schema = {"properties": {"price": {"type": "number"}}}

        example = generate_example_json(schema)

        assert "price" in example
        assert isinstance(example["price"], (int, float))

    def test_generate_boolean_field(self):
        """Generate example for boolean field."""
        schema = {"properties": {"active": {"type": "boolean"}}}

        example = generate_example_json(schema)

        assert "active" in example
        assert isinstance(example["active"], bool)

    def test_generate_array_field(self):
        """Generate example for array field."""
        schema = {"properties": {"tags": {"type": "array", "items": {"type": "string"}}}}

        example = generate_example_json(schema)

        assert "tags" in example
        assert isinstance(example["tags"], list)

    def test_generate_nested_object(self):
        """Generate example for nested object."""
        schema = {
            "properties": {"user": {"type": "object", "properties": {"name": {"type": "string"}}}}
        }

        example = generate_example_json(schema)

        assert "user" in example
        assert isinstance(example["user"], dict)
        assert "name" in example["user"]

    def test_generate_with_examples(self):
        """Use examples from schema when available."""
        schema = {"properties": {"status": {"type": "string", "examples": ["active", "inactive"]}}}

        example = generate_example_json(schema)

        assert example["status"] == "active"

    def test_generate_empty_schema(self):
        """Handle schema with no properties."""
        schema = {"type": "object"}

        example = generate_example_json(schema)

        assert example == {}


class TestGenerateFieldsMarkdown:
    """Tests for generate_fields_markdown function."""

    def test_generate_required_fields_section(self):
        """Generate markdown with required fields section."""
        schema = {
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "email": {"type": "string", "description": "User email"},
                "age": {"type": "integer", "description": "User age"},
            },
        }

        markdown = generate_fields_markdown(schema)

        assert "## Required Fields" in markdown
        assert "**name**" in markdown
        assert "**email**" in markdown
        assert "User name" in markdown

    def test_generate_optional_fields_section(self):
        """Generate markdown with optional fields section."""
        schema = {
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "nickname": {"type": "string", "description": "Optional nickname"},
            },
        }

        markdown = generate_fields_markdown(schema)

        assert "## Optional Fields" in markdown
        assert "**nickname**" in markdown
        assert "Optional nickname" in markdown

    def test_generate_with_no_description(self):
        """Handle fields without description."""
        schema = {"required": ["name"], "properties": {"name": {"type": "string"}}}

        markdown = generate_fields_markdown(schema)

        assert "**name**" in markdown
        assert "No description" in markdown

    def test_generate_empty_required(self):
        """Handle schema with no required fields."""
        schema = {"properties": {"optional_field": {"type": "string", "description": "Optional"}}}

        markdown = generate_fields_markdown(schema)

        assert "## Required Fields" in markdown
        assert "## Optional Fields" in markdown
        assert "**optional_field**" in markdown


class TestSchemaParserIntegration:
    """Integration tests using real schema files."""

    def test_full_workflow_with_discovery_schema(self):
        """Test full workflow with real discovery agent schema."""
        discovery_path = SCHEMAS_BASE_PATH / "discovery_agent" / "output.schema.json"
        if not discovery_path.exists():
            pytest.skip("Discovery schema not found")

        # Load schema
        schema = load_schema(discovery_path)
        assert schema["type"] == "object"

        # Extract field paths
        paths = extract_field_paths(schema)
        assert len(paths) > 0
        assert any("pagination" in p for p in paths)

        # Generate example
        example = generate_example_json(schema)
        assert "article_urls" in example
        assert "pagination" in example

        # Generate markdown
        markdown = generate_fields_markdown(schema)
        assert "## Required Fields" in markdown
        assert "article_urls" in markdown


class TestInjectAgentResponseContent:
    """Tests for inject_agent_response_content function."""

    def test_injects_field_when_missing(self):
        """Field is added when not present in schema."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        result = inject_agent_response_content(schema)

        assert "agent_response_content" in result["properties"]
        assert result["properties"]["agent_response_content"]["type"] == "string"

    def test_does_not_duplicate_when_present(self):
        """Field is not duplicated if already present."""
        existing_field = {"type": "string", "description": "Custom description"}
        schema = {
            "type": "object",
            "properties": {"agent_response_content": existing_field, "name": {"type": "string"}},
        }

        result = inject_agent_response_content(schema)

        # Should preserve the original field, not overwrite
        assert result["properties"]["agent_response_content"] == existing_field
        assert len(result["properties"]) == 2

    def test_does_not_mutate_original(self):
        """Original schema is not modified."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        original_keys = set(schema["properties"].keys())

        inject_agent_response_content(schema)

        # Original should be unchanged
        assert set(schema["properties"].keys()) == original_keys

    def test_handles_empty_properties(self):
        """Works with schema that has empty or no properties."""
        schema = {"type": "object", "properties": {}}

        result = inject_agent_response_content(schema)

        assert "agent_response_content" in result["properties"]

    def test_handles_missing_properties(self):
        """Works with schema that has no properties key."""
        schema = {"type": "object"}

        result = inject_agent_response_content(schema)

        assert "agent_response_content" in result["properties"]

    def test_field_has_correct_description(self):
        """Injected field has proper description."""
        schema = {"type": "object", "properties": {}}

        result = inject_agent_response_content(schema)

        field = result["properties"]["agent_response_content"]
        assert "description" in field
        assert "summary" in field["description"].lower()


class TestLoadSchemaWithInjection:
    """Tests for load_schema with inject_response_content parameter."""

    def test_load_with_injection_true(self, tmp_path):
        """load_schema injects field when inject_response_content=True."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = tmp_path / "test.schema.json"
        schema_file.write_text(json.dumps(schema))

        result = load_schema(schema_file, inject_response_content=True)

        assert "agent_response_content" in result["properties"]

    def test_load_with_injection_false(self, tmp_path):
        """load_schema does not inject when inject_response_content=False."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = tmp_path / "test.schema.json"
        schema_file.write_text(json.dumps(schema))

        result = load_schema(schema_file, inject_response_content=False)

        assert "agent_response_content" not in result["properties"]

    def test_load_default_no_injection(self, tmp_path):
        """load_schema defaults to not injecting field."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = tmp_path / "test.schema.json"
        schema_file.write_text(json.dumps(schema))

        result = load_schema(schema_file)

        assert "agent_response_content" not in result["properties"]
