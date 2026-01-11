"""Tests for ValidateResponseTool."""

import pytest

from src.contracts.validation_registry import ValidationRegistry
from src.tools.agent_tools.validate_response import ValidateResponseTool


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
def registry_with_context(sample_discovery_schema):
    """Create registry with a pre-registered validation context."""
    registry = ValidationRegistry()
    registry.register(
        run_identifier="valid-uuid",
        schema=sample_discovery_schema,
        agent_name="discovery_agent",
        expected_outputs=["article_urls", "pagination_type"],
    )
    return registry


@pytest.fixture
def tool_with_registry(registry_with_context):
    """Create tool with pre-populated registry."""
    return ValidateResponseTool(registry=registry_with_context)


class TestValidateResponseTool:
    """Tests for ValidateResponseTool."""

    def test_name_property(self, tool_with_registry):
        """Tool name is 'validate_response'."""
        assert tool_with_registry.name == "validate_response"

    def test_description_property(self, tool_with_registry):
        """Tool has meaningful description."""
        assert "validate" in tool_with_registry.description.lower()

    def test_execute_valid_response(self, tool_with_registry):
        """execute() returns valid=True for valid JSON."""
        valid_response = {
            "article_urls": ["https://example.com/article1", "https://example.com/article2"],
            "pagination_type": "numbered",
        }

        result = tool_with_registry.execute(
            run_identifier="valid-uuid", response_json=valid_response
        )

        assert result["success"] is True
        assert result["valid"] is True
        assert "message" in result

    def test_execute_invalid_response_missing_required(self, tool_with_registry):
        """execute() returns valid=False for missing required fields."""
        invalid_response = {
            "article_urls": ["https://example.com/article1"]
            # Missing pagination_type
        }

        result = tool_with_registry.execute(
            run_identifier="valid-uuid", response_json=invalid_response
        )

        assert result["success"] is True  # Tool succeeded, but validation failed
        assert result["valid"] is False
        assert "validation_errors" in result
        assert len(result["validation_errors"]) > 0

    def test_execute_invalid_response_wrong_type(self, tool_with_registry):
        """execute() returns valid=False for wrong field types."""
        invalid_response = {
            "article_urls": "not-an-array",  # Should be array
            "pagination_type": "numbered",
        }

        result = tool_with_registry.execute(
            run_identifier="valid-uuid", response_json=invalid_response
        )

        assert result["success"] is True
        assert result["valid"] is False
        assert "validation_errors" in result

    def test_execute_invalid_response_invalid_enum(self, tool_with_registry):
        """execute() returns valid=False for invalid enum value."""
        invalid_response = {
            "article_urls": ["https://example.com/article1"],
            "pagination_type": "invalid_type",  # Not in enum
        }

        result = tool_with_registry.execute(
            run_identifier="valid-uuid", response_json=invalid_response
        )

        assert result["success"] is True
        assert result["valid"] is False
        assert "validation_errors" in result

    def test_execute_validation_error_contains_path(self, tool_with_registry):
        """Validation errors include path information."""
        invalid_response = {
            "article_urls": ["https://example.com/article1"],
            "pagination_type": "invalid",
        }

        result = tool_with_registry.execute(
            run_identifier="valid-uuid", response_json=invalid_response
        )

        errors = result["validation_errors"]
        assert len(errors) > 0
        assert "path" in errors[0]
        assert "message" in errors[0]

    def test_execute_unknown_run_identifier(self, tool_with_registry):
        """execute() returns error for unknown run_identifier."""
        result = tool_with_registry.execute(
            run_identifier="unknown-uuid", response_json={"any": "data"}
        )

        assert result["success"] is False
        assert "error" in result
        assert "unknown-uuid" in result["error"]

    def test_execute_message_on_failure(self, tool_with_registry):
        """execute() returns message describing validation failure."""
        invalid_response = {"article_urls": "wrong"}

        result = tool_with_registry.execute(
            run_identifier="valid-uuid", response_json=invalid_response
        )

        assert "message" in result
        # Message should contain some indication of the failure
        assert result["message"] is not None

    def test_get_parameters_schema(self, tool_with_registry):
        """get_parameters_schema returns correct schema."""
        schema = tool_with_registry.get_parameters_schema()

        assert schema["type"] == "object"
        assert "run_identifier" in schema["properties"]
        assert "response_json" in schema["properties"]
        assert "run_identifier" in schema["required"]
        assert "response_json" in schema["required"]

    def test_to_openai_schema(self, tool_with_registry):
        """to_openai_schema returns valid OpenAI function schema."""
        schema = tool_with_registry.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "validate_response"


class TestValidateResponseToolDefaultRegistry:
    """Tests using default singleton registry."""

    def test_uses_singleton_registry(self, sample_discovery_schema):
        """Tool uses singleton registry when none injected."""
        # Register context in singleton
        registry = ValidationRegistry.get_instance()
        registry.register(
            run_identifier="singleton-uuid",
            schema=sample_discovery_schema,
            agent_name="discovery_agent",
            expected_outputs=[],
        )

        # Create tool without injecting registry
        tool = ValidateResponseTool()

        valid_response = {"article_urls": ["https://example.com/a"], "pagination_type": "none"}

        result = tool.execute(run_identifier="singleton-uuid", response_json=valid_response)

        assert result["success"] is True
        assert result["valid"] is True


class TestValidateResponseToolFlatStructure:
    """Tests for flat structure validation with agent_response_content."""

    @pytest.fixture
    def registry_with_content_schema(self):
        """Create registry with schema that includes agent_response_content."""
        registry = ValidationRegistry()
        registry.register(
            run_identifier="flat-uuid",
            schema={
                "type": "object",
                "properties": {
                    "agent_response_content": {
                        "type": "string",
                        "description": "Summary of findings",
                    },
                    "article_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "pagination_type": {
                        "type": "string",
                        "enum": ["numbered", "load_more", "none"],
                    },
                },
                "required": ["agent_response_content", "article_urls", "pagination_type"],
            },
            agent_name="discovery_agent",
            expected_outputs=["article_urls", "pagination_type"],
        )
        return registry

    def test_flat_structure_valid(self, registry_with_content_schema):
        """Flat structure validates correctly."""
        tool = ValidateResponseTool(registry=registry_with_content_schema)

        response = {
            "agent_response_content": "Found 2 articles with numbered pagination",
            "article_urls": ["https://example.com/a1", "https://example.com/a2"],
            "pagination_type": "numbered",
        }

        result = tool.execute(run_identifier="flat-uuid", response_json=response)

        assert result["success"] is True
        assert result["valid"] is True

    def test_flat_structure_missing_content(self, registry_with_content_schema):
        """Flat structure without agent_response_content fails."""
        tool = ValidateResponseTool(registry=registry_with_content_schema)

        response = {
            "article_urls": ["https://example.com/a1"],
            "pagination_type": "numbered",
        }

        result = tool.execute(run_identifier="flat-uuid", response_json=response)

        assert result["success"] is True
        assert result["valid"] is False
        assert any("agent_response_content" in e["message"] for e in result["validation_errors"])


class TestValidateResponseToolEdgeCases:
    """Edge case tests for ValidateResponseTool."""

    def test_empty_response_against_empty_schema(self):
        """Empty response validates against schema with no required fields."""
        registry = ValidationRegistry()
        registry.register(
            run_identifier="empty-uuid",
            schema={"type": "object", "properties": {}},
            agent_name="empty_agent",
            expected_outputs=[],
        )

        tool = ValidateResponseTool(registry=registry)

        result = tool.execute(run_identifier="empty-uuid", response_json={})

        assert result["success"] is True
        assert result["valid"] is True

    def test_extra_fields_allowed_by_default(self):
        """Extra fields in response are allowed (no additionalProperties: false)."""
        registry = ValidationRegistry()
        registry.register(
            run_identifier="extra-uuid",
            schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            agent_name="test_agent",
            expected_outputs=["name"],
        )

        tool = ValidateResponseTool(registry=registry)

        result = tool.execute(
            run_identifier="extra-uuid",
            response_json={"name": "test", "extra_field": "should be allowed"},
        )

        assert result["success"] is True
        assert result["valid"] is True
