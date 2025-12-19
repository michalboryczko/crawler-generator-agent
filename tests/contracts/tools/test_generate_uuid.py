"""Tests for GenerateUuidTool."""

import uuid

import pytest

from src.tools.agent_tools.generate_uuid import GenerateUuidTool


class TestGenerateUuidTool:
    """Tests for GenerateUuidTool."""

    @pytest.fixture
    def tool(self):
        """Create a GenerateUuidTool instance."""
        return GenerateUuidTool()

    def test_name_property(self, tool):
        """Tool name is 'generate_uuid'."""
        assert tool.name == "generate_uuid"

    def test_description_property(self, tool):
        """Tool has meaningful description."""
        assert "UUID" in tool.description or "uuid" in tool.description
        assert "tracking" in tool.description.lower() or "identifier" in tool.description.lower()

    def test_execute_returns_success(self, tool):
        """execute() returns success=True."""
        result = tool.execute()
        assert result["success"] is True

    def test_execute_returns_valid_uuid(self, tool):
        """execute() returns a valid UUID string."""
        result = tool.execute()
        assert "run_identifier" in result

        # Verify it's a valid UUID
        parsed = uuid.UUID(result["run_identifier"])
        assert str(parsed) == result["run_identifier"]

    def test_execute_returns_uuid4_format(self, tool):
        """execute() returns UUID4 format."""
        result = tool.execute()
        parsed = uuid.UUID(result["run_identifier"])

        # UUID4 has version 4 and variant 1
        assert parsed.version == 4

    def test_execute_returns_unique_uuids(self, tool):
        """Multiple calls return different UUIDs."""
        results = [tool.execute()["run_identifier"] for _ in range(100)]
        unique_results = set(results)

        # All should be unique
        assert len(unique_results) == 100

    def test_get_parameters_schema(self, tool):
        """get_parameters_schema returns empty schema (no params needed)."""
        schema = tool.get_parameters_schema()

        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema["required"] == []

    def test_to_openai_schema(self, tool):
        """to_openai_schema returns valid OpenAI function schema."""
        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "generate_uuid"
        assert "parameters" in schema["function"]
