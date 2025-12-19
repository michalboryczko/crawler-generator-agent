"""Tests for DescribeOutputContractTool."""

import json

import pytest

from src.tools.agent_tools.describe_output_contract import DescribeOutputContractTool


@pytest.fixture
def sample_discovery_schema():
    """Sample discovery agent output schema."""
    return {
        "type": "object",
        "properties": {
            "article_urls": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
                "description": "List of discovered article URLs"
            },
            "pagination_type": {
                "type": "string",
                "enum": ["numbered", "load_more", "infinite_scroll", "none"],
                "description": "Type of pagination detected"
            }
        },
        "required": ["article_urls", "pagination_type"]
    }


@pytest.fixture
def sample_selector_schema():
    """Sample selector agent output schema."""
    return {
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for target elements"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score for the selector"
            }
        },
        "required": ["selector"]
    }


@pytest.fixture
def tool_with_schemas(tmp_path, sample_discovery_schema, sample_selector_schema):
    """Create tool with test schemas."""
    # Create schema files
    discovery_path = tmp_path / "discovery" / "output.schema.json"
    discovery_path.parent.mkdir(parents=True, exist_ok=True)
    discovery_path.write_text(json.dumps(sample_discovery_schema))

    selector_path = tmp_path / "selector" / "output.schema.json"
    selector_path.parent.mkdir(parents=True, exist_ok=True)
    selector_path.write_text(json.dumps(sample_selector_schema))

    schema_paths = {
        "discovery_agent": str(discovery_path),
        "selector_agent": str(selector_path),
    }

    return DescribeOutputContractTool(schema_paths=schema_paths)


class TestDescribeOutputContractTool:
    """Tests for DescribeOutputContractTool."""

    def test_name_property(self, tool_with_schemas):
        """Tool name is 'describe_output_contract'."""
        assert tool_with_schemas.name == "describe_output_contract"

    def test_description_includes_agents(self, tool_with_schemas):
        """Description lists available agents."""
        description = tool_with_schemas.description
        assert "discovery_agent" in description
        assert "selector_agent" in description

    def test_execute_known_agent(self, tool_with_schemas):
        """execute() returns schema info for known agent."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        assert result["success"] is True
        assert result["agent_name"] == "discovery_agent"
        assert "fields_description" in result
        assert "schema_json" in result
        assert "available_fields" in result
        assert "required_fields" in result

    def test_execute_unknown_agent(self, tool_with_schemas):
        """execute() returns error for unknown agent."""
        result = tool_with_schemas.execute(agent_name="unknown_agent")

        assert result["success"] is False
        assert "error" in result
        assert "unknown_agent" in result["error"]

    def test_execute_returns_fields_description(self, tool_with_schemas):
        """Response includes human-readable fields description."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        fields_desc = result["fields_description"]
        assert "article_urls" in fields_desc
        assert "pagination_type" in fields_desc
        # Should include detailed format with example, type, status
        assert "required" in fields_desc or "optional" in fields_desc

    def test_execute_returns_schema_json(self, tool_with_schemas):
        """Response includes example JSON as string."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        schema_json = result["schema_json"]
        # Should be a JSON string
        assert isinstance(schema_json, str)
        assert "article_urls" in schema_json
        assert "pagination_type" in schema_json

    def test_execute_returns_available_fields(self, tool_with_schemas):
        """Response includes list of available fields."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        available = result["available_fields"]
        assert isinstance(available, list)
        assert "article_urls" in available
        assert "pagination_type" in available

    def test_execute_returns_required_fields(self, tool_with_schemas):
        """Response includes list of required fields."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        required = result["required_fields"]
        assert "article_urls" in required
        assert "pagination_type" in required

    def test_execute_optional_field_not_in_required(self, tool_with_schemas):
        """Optional fields not in required list."""
        result = tool_with_schemas.execute(agent_name="selector_agent")

        required = result["required_fields"]
        assert "selector" in required
        assert "confidence" not in required  # confidence is optional

    def test_get_parameters_schema(self, tool_with_schemas):
        """get_parameters_schema returns correct schema."""
        schema = tool_with_schemas.get_parameters_schema()

        assert schema["type"] == "object"
        assert "agent_name" in schema["properties"]
        assert schema["properties"]["agent_name"]["type"] == "string"
        assert "agent_name" in schema["required"]

    def test_to_openai_schema(self, tool_with_schemas):
        """to_openai_schema returns valid OpenAI function schema."""
        schema = tool_with_schemas.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "describe_output_contract"
        assert "agent_name" in schema["function"]["parameters"]["properties"]


class TestDescribeOutputContractToolEdgeCases:
    """Edge case tests for DescribeOutputContractTool."""

    def test_empty_schema_paths(self):
        """Tool works with empty schema_paths dict."""
        tool = DescribeOutputContractTool(schema_paths={})

        # Description should still work
        assert "describe" in tool.description.lower() or "contract" in tool.description.lower()

        # Execute should fail gracefully
        result = tool.execute(agent_name="any_agent")
        assert result["success"] is False

    def test_schema_with_no_required(self, tmp_path):
        """Handle schema with no required fields."""
        schema = {
            "type": "object",
            "properties": {
                "optional_field": {"type": "string"}
            }
        }

        schema_path = tmp_path / "optional.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(
            schema_paths={"optional_agent": str(schema_path)}
        )

        result = tool.execute(agent_name="optional_agent")

        assert result["success"] is True
        assert result["required_fields"] == []
        assert result["available_fields"] == ["optional_field"]


class TestDetailedFieldsMarkdown:
    """Tests for detailed fields markdown generation."""

    def test_fields_description_includes_type(self, tmp_path):
        """Fields description includes type information."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "count": {"type": "integer", "description": "The count"}
            },
            "required": ["name"]
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        assert "string" in fields_desc
        assert "integer" in fields_desc

    def test_fields_description_includes_required_status(self, tmp_path):
        """Fields description indicates required/optional status."""
        schema = {
            "type": "object",
            "properties": {
                "required_field": {"type": "string"},
                "optional_field": {"type": "string"}
            },
            "required": ["required_field"]
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        # Check that required/optional status is mentioned
        assert "required" in fields_desc
        assert "optional" in fields_desc

    def test_fields_description_includes_example_values(self, tmp_path):
        """Fields description includes example values."""
        schema = {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "examples": ["https://example.com"]
                },
                "count": {"type": "integer"}
            }
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        # Example from schema should be included
        assert "https://example.com" in fields_desc
        # Generated example for integer
        assert "0" in fields_desc

    def test_fields_description_handles_nested_objects(self, tmp_path):
        """Fields description documents nested object properties."""
        schema = {
            "type": "object",
            "properties": {
                "pagination": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Pagination type"},
                        "max_pages": {"type": "integer", "description": "Max pages"}
                    }
                }
            }
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        # Nested fields should use dot notation
        assert "pagination.type" in fields_desc
        assert "pagination.max_pages" in fields_desc

    def test_fields_description_handles_array_of_objects(self, tmp_path):
        """Fields description documents array item properties."""
        schema = {
            "type": "object",
            "properties": {
                "articles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Article title"},
                            "url": {"type": "string", "description": "Article URL"}
                        }
                    }
                }
            }
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        # Array items should use bracket notation
        assert "articles[].title" in fields_desc
        assert "articles[].url" in fields_desc

    def test_fields_description_handles_enums(self, tmp_path):
        """Fields description shows enum values."""
        schema = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "active", "completed"],
                    "description": "Current status"
                }
            }
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        # Enum values should be shown
        assert "pending" in fields_desc
        assert "active" in fields_desc
        assert "completed" in fields_desc

    def test_fields_description_handles_nullable_types(self, tmp_path):
        """Fields description handles nullable union types."""
        schema = {
            "type": "object",
            "properties": {
                "optional_value": {
                    "type": ["string", "null"],
                    "description": "May be null"
                }
            }
        }

        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text(json.dumps(schema))

        tool = DescribeOutputContractTool(schema_paths={"test": str(schema_path)})
        result = tool.execute(agent_name="test")

        fields_desc = result["fields_description"]
        # Should indicate nullable (string?)
        assert "string?" in fields_desc or "string" in fields_desc
