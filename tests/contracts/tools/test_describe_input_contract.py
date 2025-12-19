"""Tests for DescribeInputContractTool."""

import json

import pytest

from src.tools.agent_tools.describe_input_contract import DescribeInputContractTool


@pytest.fixture
def sample_discovery_input_schema():
    """Sample discovery agent input schema."""
    return {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "format": "uri",
                "description": "Target URL to analyze"
            },
            "page_html": {
                "type": "string",
                "description": "HTML content of the page"
            }
        },
        "required": ["url", "page_html"]
    }


@pytest.fixture
def sample_selector_input_schema():
    """Sample selector agent input schema."""
    return {
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "HTML content to analyze"
            },
            "target_description": {
                "type": "string",
                "description": "Description of elements to find"
            }
        },
        "required": ["html"]
    }


@pytest.fixture
def tool_with_schemas(tmp_path, sample_discovery_input_schema, sample_selector_input_schema):
    """Create tool with test schemas."""
    discovery_path = tmp_path / "discovery" / "input.schema.json"
    discovery_path.parent.mkdir(parents=True, exist_ok=True)
    discovery_path.write_text(json.dumps(sample_discovery_input_schema))

    selector_path = tmp_path / "selector" / "input.schema.json"
    selector_path.parent.mkdir(parents=True, exist_ok=True)
    selector_path.write_text(json.dumps(sample_selector_input_schema))

    schema_paths = {
        "discovery_agent": str(discovery_path),
        "selector_agent": str(selector_path),
    }

    return DescribeInputContractTool(schema_paths=schema_paths)


class TestDescribeInputContractTool:
    """Tests for DescribeInputContractTool."""

    def test_name_property(self, tool_with_schemas):
        """Tool name is 'describe_input_contract'."""
        assert tool_with_schemas.name == "describe_input_contract"

    def test_description_property(self, tool_with_schemas):
        """Tool has meaningful description."""
        assert "input" in tool_with_schemas.description.lower()

    def test_execute_known_agent(self, tool_with_schemas):
        """execute() returns input requirements for known agent."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        assert result["success"] is True
        assert result["agent_name"] == "discovery_agent"
        assert "fields_markdown" in result
        assert "required_fields" in result

    def test_execute_unknown_agent(self, tool_with_schemas):
        """execute() returns error for unknown agent."""
        result = tool_with_schemas.execute(agent_name="unknown_agent")

        assert result["success"] is False
        assert "error" in result
        assert "unknown_agent" in result["error"]

    def test_execute_returns_fields_markdown(self, tool_with_schemas):
        """Response includes human-readable fields markdown."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        fields_md = result["fields_markdown"]
        assert "url" in fields_md
        assert "page_html" in fields_md

    def test_execute_returns_required_fields(self, tool_with_schemas):
        """Response includes list of required fields."""
        result = tool_with_schemas.execute(agent_name="discovery_agent")

        required = result["required_fields"]
        assert "url" in required
        assert "page_html" in required

    def test_execute_optional_field_not_in_required(self, tool_with_schemas):
        """Optional fields not in required list."""
        result = tool_with_schemas.execute(agent_name="selector_agent")

        required = result["required_fields"]
        assert "html" in required
        assert "target_description" not in required  # optional

    def test_get_parameters_schema(self, tool_with_schemas):
        """get_parameters_schema returns correct schema."""
        schema = tool_with_schemas.get_parameters_schema()

        assert schema["type"] == "object"
        assert "agent_name" in schema["properties"]
        assert "agent_name" in schema["required"]

    def test_to_openai_schema(self, tool_with_schemas):
        """to_openai_schema returns valid OpenAI function schema."""
        schema = tool_with_schemas.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "describe_input_contract"
