"""Tests for PrepareAgentOutputValidationTool."""

import json

import pytest

from src.contracts.validation_registry import ValidationRegistry
from src.tools.agent_tools.prepare_validation import PrepareAgentOutputValidationTool


@pytest.fixture
def sample_discovery_schema():
    """Sample discovery agent output schema."""
    return {
        "type": "object",
        "properties": {
            "article_urls": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
                "description": "List of discovered article URLs",
            },
            "pagination_type": {
                "type": "string",
                "enum": ["numbered", "load_more", "infinite_scroll", "none"],
                "description": "Type of pagination detected",
            },
        },
        "required": ["article_urls", "pagination_type"],
    }


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset singleton registry before and after each test."""
    ValidationRegistry.reset_instance()
    yield
    ValidationRegistry.reset_instance()


@pytest.fixture
def tool_with_schema(tmp_path, sample_discovery_schema):
    """Create tool with test schema."""
    schema_path = tmp_path / "discovery" / "output.schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(sample_discovery_schema))

    schema_paths = {
        "discovery_agent": str(schema_path),
    }

    return PrepareAgentOutputValidationTool(schema_paths=schema_paths)


class TestPrepareAgentOutputValidationTool:
    """Tests for PrepareAgentOutputValidationTool."""

    def test_name_property(self, tool_with_schema):
        """Tool name is 'prepare_agent_output_validation'."""
        assert tool_with_schema.name == "prepare_agent_output_validation"

    def test_description_property(self, tool_with_schema):
        """Tool has meaningful description."""
        assert "validation" in tool_with_schema.description.lower()

    def test_execute_registers_context(self, tool_with_schema):
        """execute() registers validation context in registry."""
        result = tool_with_schema.execute(
            run_identifier="test-uuid-123", agent_name="discovery_agent"
        )

        assert result["success"] is True
        assert result["run_identifier"] == "test-uuid-123"
        assert result["agent_name"] == "discovery_agent"

        # Verify context is in registry
        registry = ValidationRegistry.get_instance()
        context = registry.get("test-uuid-123")
        assert context is not None
        assert context.agent_name == "discovery_agent"

    def test_execute_with_custom_outputs(self, tool_with_schema):
        """execute() uses custom expected_outputs when provided."""
        result = tool_with_schema.execute(
            run_identifier="test-uuid-456",
            agent_name="discovery_agent",
            expected_outputs=["article_urls"],  # Only one field
        )

        assert result["success"] is True
        assert result["expected_outputs"] == ["article_urls"]

        # Verify in registry
        registry = ValidationRegistry.get_instance()
        context = registry.get("test-uuid-456")
        assert context.expected_outputs == ["article_urls"]

    def test_execute_defaults_to_required_fields(self, tool_with_schema):
        """execute() defaults expected_outputs to schema required fields."""
        result = tool_with_schema.execute(
            run_identifier="test-uuid-789", agent_name="discovery_agent"
        )

        # Should use schema's required fields
        assert "article_urls" in result["expected_outputs"]
        assert "pagination_type" in result["expected_outputs"]

    def test_execute_unknown_agent(self, tool_with_schema):
        """execute() returns error for unknown agent."""
        result = tool_with_schema.execute(run_identifier="test-uuid", agent_name="unknown_agent")

        assert result["success"] is False
        assert "error" in result
        assert "unknown_agent" in result["error"]

    def test_execute_returns_message(self, tool_with_schema):
        """execute() returns message with instructions."""
        result = tool_with_schema.execute(
            run_identifier="test-uuid-msg", agent_name="discovery_agent"
        )

        assert "message" in result
        assert "validate_response" in result["message"]
        assert "test-uuid-msg" in result["message"]

    def test_get_parameters_schema(self, tool_with_schema):
        """get_parameters_schema returns correct schema."""
        schema = tool_with_schema.get_parameters_schema()

        assert schema["type"] == "object"
        assert "run_identifier" in schema["properties"]
        assert "agent_name" in schema["properties"]
        assert "expected_outputs" in schema["properties"]
        assert "run_identifier" in schema["required"]
        assert "agent_name" in schema["required"]

    def test_to_openai_schema(self, tool_with_schema):
        """to_openai_schema returns valid OpenAI function schema."""
        schema = tool_with_schema.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "prepare_agent_output_validation"


class TestPrepareValidationWithCustomRegistry:
    """Tests with custom registry injection."""

    def test_uses_injected_registry(self, tmp_path, sample_discovery_schema):
        """Tool uses injected registry instead of singleton."""
        schema_path = tmp_path / "discovery" / "output.schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(json.dumps(sample_discovery_schema))

        # Create custom registry
        custom_registry = ValidationRegistry()

        tool = PrepareAgentOutputValidationTool(
            schema_paths={"discovery_agent": str(schema_path)}, registry=custom_registry
        )

        tool.execute(run_identifier="custom-uuid", agent_name="discovery_agent")

        # Should be in custom registry
        assert custom_registry.is_registered("custom-uuid")
