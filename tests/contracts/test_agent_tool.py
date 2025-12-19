"""Tests for AgentTool class with prompt attachment."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.tools.agent_tools import AgentTool


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str = "test_agent"):
        self.name = name
        self.description = "Test agent for unit tests"
        self._run_calls = []

    def get_description(self) -> str:
        """Return formatted agent description."""
        return f"{self.name} - {self.description}"

    def run(
        self,
        task: str,
        context: dict | None = None,
        expected_outputs: list[str] | None = None,
        run_identifier: str | None = None,
        output_contract_schema: dict | None = None,
    ):
        """Mock run method that records calls."""
        self._run_calls.append({
            "task": task,
            "context": context,
            "expected_outputs": expected_outputs,
            "run_identifier": run_identifier,
            "output_contract_schema": output_contract_schema,
        })
        result = MagicMock()
        result.success = True
        result.data = {"result": "mock_result"}
        result.errors = []
        result.iterations = 1
        return result


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    return MockAgent(name="discovery_agent")


@pytest.fixture
def sample_schema():
    """Simple test schema."""
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
def sample_input_schema():
    """Simple input schema."""
    return {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "format": "uri",
                "description": "Target URL to analyze"
            }
        },
        "required": ["url"]
    }


class TestAgentToolCreation:
    """Tests for AgentTool initialization."""

    def test_create_with_mock_agent(self, mock_agent, sample_schema, tmp_path):
        """Create AgentTool with mock agent and schema."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(schema_path)
        )

        assert tool.agent is mock_agent
        # Original fields should be present
        assert "article_urls" in tool.output_schema["properties"]
        assert "pagination_type" in tool.output_schema["properties"]
        # agent_response_content should be injected
        assert "agent_response_content" in tool.output_schema["properties"]

    def test_create_with_custom_description(self, mock_agent, sample_schema, tmp_path):
        """Create AgentTool with custom description."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(schema_path),
            description="Custom description for discovery"
        )

        assert tool.description == "Custom description for discovery"

    def test_create_with_input_schema(
        self, mock_agent, sample_schema, sample_input_schema, tmp_path
    ):
        """Create AgentTool with both input and output schemas."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(sample_input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path)
        )

        # Input schema is not modified
        assert tool.input_schema == sample_input_schema
        # Output schema has agent_response_content injected
        assert "agent_response_content" in tool.output_schema["properties"]
        assert "article_urls" in tool.output_schema["properties"]


class TestAgentToolProperties:
    """Tests for AgentTool properties."""

    def test_name_property(self, mock_agent, sample_schema, tmp_path):
        """Tool name is 'run_{agent.name}'."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.name == "run_discovery_agent"

    def test_default_description(self, mock_agent, sample_schema, tmp_path):
        """Default description uses agent name."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert "discovery_agent" in tool.description

    def test_output_schema_property(self, mock_agent, sample_schema, tmp_path):
        """output_schema returns the loaded schema."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.output_schema["type"] == "object"
        assert "article_urls" in tool.output_schema["properties"]

    def test_input_schema_none_when_not_provided(self, mock_agent, sample_schema, tmp_path):
        """input_schema is None when not provided."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.input_schema is None


class TestAgentToolExecute:
    """Tests for AgentTool.execute()."""

    def test_execute_delegates_to_agent(self, mock_agent, sample_schema, tmp_path):
        """execute() calls agent.run() with task."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        result = tool.execute(task="Find all article URLs on the page")

        assert len(mock_agent._run_calls) == 1
        assert mock_agent._run_calls[0]["task"] == "Find all article URLs on the page"

    def test_execute_passes_context(self, mock_agent, sample_schema, tmp_path):
        """execute() passes context to agent.run()."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))
        context = {"url": "https://example.com", "page_html": "<html>...</html>"}

        tool.execute(task="Analyze page", context=context)

        assert mock_agent._run_calls[0]["context"] == context

    def test_execute_returns_result_dict(self, mock_agent, sample_schema, tmp_path):
        """execute() returns dict with success, data, errors, iterations."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        result = tool.execute(task="Test task")

        assert "success" in result
        assert "data" in result
        assert "errors" in result
        assert "iterations" in result
        assert result["success"] is True


class TestAgentToolParametersSchema:
    """Tests for get_parameters_schema()."""

    def test_get_parameters_schema(self, mock_agent, sample_schema, tmp_path):
        """get_parameters_schema returns OpenAI-compatible schema."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        schema = tool.get_parameters_schema()

        assert schema["type"] == "object"
        assert "task" in schema["properties"]
        assert schema["properties"]["task"]["type"] == "string"
        assert "task" in schema["required"]

    def test_parameters_schema_includes_context(self, mock_agent, sample_schema, tmp_path):
        """Parameters schema includes optional context parameter."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        schema = tool.get_parameters_schema()

        assert "context" in schema["properties"]
        assert schema["properties"]["context"]["type"] == "object"
        # context is optional - not in required
        assert "context" not in schema["required"]


class TestAgentToolPromptAttachment:
    """Tests for prompt_attachment()."""

    def test_prompt_attachment_contains_agent_name(self, mock_agent, sample_schema, tmp_path):
        """prompt_attachment contains agent name."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        attachment = tool.prompt_attachment()

        assert "discovery_agent" in attachment

    def test_prompt_attachment_contains_tool_name(self, mock_agent, sample_schema, tmp_path):
        """prompt_attachment contains tool name."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        attachment = tool.prompt_attachment()

        assert "run_discovery_agent" in attachment

    def test_prompt_attachment_contains_output_contract(
        self, mock_agent, sample_schema, tmp_path
    ):
        """prompt_attachment contains output contract section."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        attachment = tool.prompt_attachment()

        assert "Output Contract" in attachment
        assert "article_urls" in attachment
        assert "pagination_type" in attachment

    def test_prompt_attachment_contains_example_json(
        self, mock_agent, sample_schema, tmp_path
    ):
        """prompt_attachment contains example JSON."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        attachment = tool.prompt_attachment()

        assert "Example Output" in attachment
        assert "```json" in attachment

    def test_prompt_attachment_example_uses_wrapped_structure(
        self, mock_agent, sample_schema, tmp_path
    ):
        """prompt_attachment example JSON uses wrapped structure with data key."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        attachment = tool.prompt_attachment()

        # Extract JSON from attachment (between ```json and ```)
        json_start = attachment.find("```json") + len("```json")
        json_end = attachment.find("```", json_start)
        json_str = attachment[json_start:json_end].strip()
        example = json.loads(json_str)

        # Verify wrapped structure
        assert "agent_response_content" in example
        assert "data" in example
        # Data fields should be inside 'data' key
        assert "article_urls" in example["data"]
        assert "pagination_type" in example["data"]
        # Data fields should NOT be at top level (except agent_response_content)
        assert "article_urls" not in example
        assert "pagination_type" not in example

    def test_prompt_attachment_with_input_schema(
        self, mock_agent, sample_schema, sample_input_schema, tmp_path
    ):
        """prompt_attachment includes input contract when provided."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(sample_input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path)
        )

        attachment = tool.prompt_attachment()

        assert "Input Contract" in attachment
        assert "url" in attachment

    def test_prompt_attachment_no_input_section_without_schema(
        self, mock_agent, sample_schema, tmp_path
    ):
        """prompt_attachment omits input section when no input schema."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        attachment = tool.prompt_attachment()

        assert "Input Contract" not in attachment


class TestAgentToolOpenAISchema:
    """Tests for to_openai_schema() inherited from BaseTool."""

    def test_to_openai_schema(self, mock_agent, sample_schema, tmp_path):
        """to_openai_schema returns valid OpenAI function schema."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "run_discovery_agent"
        assert "parameters" in schema["function"]


class TestAgentToolSchemaInjection:
    """Tests for agent_response_content field injection."""

    def test_output_schema_has_agent_response_content(
        self, mock_agent, sample_schema, tmp_path
    ):
        """Output schema should have agent_response_content injected."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert "agent_response_content" in tool.output_schema["properties"]
        field = tool.output_schema["properties"]["agent_response_content"]
        assert field["type"] == "string"
        assert "description" in field

    def test_execute_passes_schema_to_agent(self, mock_agent, sample_schema, tmp_path):
        """execute() should pass output_contract_schema to agent.run()."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))
        tool.execute(task="Test task")

        assert len(mock_agent._run_calls) == 1
        call = mock_agent._run_calls[0]
        assert call["output_contract_schema"] is not None
        assert "agent_response_content" in call["output_contract_schema"]["properties"]

    def test_input_schema_not_modified(
        self, mock_agent, sample_schema, sample_input_schema, tmp_path
    ):
        """Input schema should NOT have agent_response_content injected."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(sample_input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path)
        )

        # Input schema should NOT have the field
        assert "agent_response_content" not in tool.input_schema["properties"]
        # Output schema should have the field
        assert "agent_response_content" in tool.output_schema["properties"]
