"""Tests for AgentTool class."""

import json
from unittest.mock import MagicMock

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
        self._run_calls.append(
            {
                "task": task,
                "context": context,
                "expected_outputs": expected_outputs,
                "run_identifier": run_identifier,
                "output_contract_schema": output_contract_schema,
            }
        )
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


class TestAgentToolCreation:
    """Tests for AgentTool initialization."""

    def test_create_with_mock_agent(self, mock_agent, sample_schema, tmp_path):
        """Create AgentTool with mock agent and schema."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.name == "run_discovery_agent"
        assert "discovery_agent" in tool.description

    def test_create_with_custom_description(self, mock_agent, sample_schema, tmp_path):
        """Create AgentTool with custom description."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(schema_path),
            description="Custom description for discovery",
        )

        assert tool.description == "Custom description for discovery"


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


class TestAgentToolTemplateMethods:
    """Tests for template-accessed methods (used by sub_agents_section.md.j2)."""

    def test_get_agent_name(self, mock_agent, sample_schema, tmp_path):
        """get_agent_name returns the wrapped agent's name."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.get_agent_name() == "discovery_agent"

    def test_get_agent_description(self, mock_agent, sample_schema, tmp_path):
        """get_agent_description returns agent's formatted description."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.get_agent_description() == "discovery_agent - Test agent for unit tests"

    def test_get_tool_name(self, mock_agent, sample_schema, tmp_path):
        """get_tool_name returns run_{agent.name}."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        assert tool.get_tool_name() == "run_discovery_agent"


class TestAgentToolExecute:
    """Tests for AgentTool.execute()."""

    def test_execute_delegates_to_agent(self, mock_agent, sample_schema, tmp_path):
        """execute() calls agent.run() with task."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        tool.execute(task="Find all article URLs on the page")

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

    def test_execute_passes_schema_to_agent(self, mock_agent, sample_schema, tmp_path):
        """execute() passes output_contract_schema to agent.run()."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))
        tool.execute(task="Test task")

        assert len(mock_agent._run_calls) == 1
        call = mock_agent._run_calls[0]
        assert call["output_contract_schema"] is not None
        # Schema should have agent_response_content injected
        assert "agent_response_content" in call["output_contract_schema"]["properties"]


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


class TestAgentToolKwargsMerging:
    """Tests for kwargs merging into context (Task 2)."""

    def test_execute_merges_extra_kwargs_into_context(self, mock_agent, sample_schema, tmp_path):
        """Extra kwargs beyond reserved keys are merged into context."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        # Pass extra kwargs like parent agent would
        tool.execute(
            task="Generate plan",
            target_url="https://example.com",
            collected_information=[{"agent_name": "discovery", "output": {}}],
        )

        assert len(mock_agent._run_calls) == 1
        context = mock_agent._run_calls[0]["context"]
        assert context["target_url"] == "https://example.com"
        assert context["collected_information"] == [{"agent_name": "discovery", "output": {}}]

    def test_execute_preserves_explicit_context(self, mock_agent, sample_schema, tmp_path):
        """Explicit context dict is preserved when passed."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        explicit_context = {"existing_key": "existing_value"}
        tool.execute(task="Test", context=explicit_context)

        context = mock_agent._run_calls[0]["context"]
        assert context["existing_key"] == "existing_value"

    def test_execute_merges_explicit_and_extra_kwargs(self, mock_agent, sample_schema, tmp_path):
        """Both explicit context and extra kwargs are combined."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        tool.execute(
            task="Test",
            context={"existing": "value"},
            new_field="new_value",
        )

        context = mock_agent._run_calls[0]["context"]
        assert context["existing"] == "value"
        assert context["new_field"] == "new_value"

    def test_extra_kwargs_override_explicit_context(self, mock_agent, sample_schema, tmp_path):
        """Extra kwargs override same keys in explicit context."""
        schema_path = tmp_path / "output.schema.json"
        schema_path.write_text(json.dumps(sample_schema))

        tool = AgentTool(agent=mock_agent, output_schema_path=str(schema_path))

        tool.execute(
            task="Test",
            context={"target_url": "old_url"},
            target_url="new_url",  # Should override
        )

        context = mock_agent._run_calls[0]["context"]
        assert context["target_url"] == "new_url"


class TestAgentToolInputValidation:
    """Tests for input contract validation (Task 3)."""

    @pytest.fixture
    def input_schema(self):
        """Input schema with required fields."""
        return {
            "type": "object",
            "required": ["target_url", "collected_information"],
            "properties": {
                "target_url": {"type": "string", "format": "uri"},
                "collected_information": {"type": "array", "minItems": 1},
            },
        }

    def test_validate_input_returns_none_when_valid(
        self, mock_agent, sample_schema, input_schema, tmp_path
    ):
        """Validation passes when all required fields present."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path),
        )

        result = tool._validate_input(
            {"target_url": "https://example.com", "collected_information": [{"data": "test"}]}
        )

        assert result is None  # None means valid

    def test_validate_input_returns_error_when_missing_required(
        self, mock_agent, sample_schema, input_schema, tmp_path
    ):
        """Validation fails when required fields missing."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path),
        )

        result = tool._validate_input({"target_url": "https://example.com"})

        assert result is not None
        assert result["success"] is False
        assert result["error"] == "Input contract validation failed"
        assert "collected_information" in result["missing_fields"]

    def test_validate_input_returns_error_with_helpful_hints(
        self, mock_agent, sample_schema, input_schema, tmp_path
    ):
        """Error response includes helpful hints for retry."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path),
        )

        result = tool._validate_input({})

        assert "hint" in result
        assert "target_url" in result["hint"]
        assert "collected_information" in result["hint"]
        assert result["required_fields"] == ["target_url", "collected_information"]
        assert result["provided_fields"] == []

    def test_execute_returns_validation_error_when_input_invalid(
        self, mock_agent, sample_schema, input_schema, tmp_path
    ):
        """execute() returns validation error without calling agent."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path),
        )

        result = tool.execute(task="Generate plan")  # Missing required fields

        assert result["success"] is False
        assert result["error"] == "Input contract validation failed"
        # Agent should NOT have been called
        assert len(mock_agent._run_calls) == 0

    def test_execute_proceeds_when_input_valid(
        self, mock_agent, sample_schema, input_schema, tmp_path
    ):
        """execute() proceeds to call agent when input is valid."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path),
        )

        result = tool.execute(
            task="Generate plan",
            target_url="https://example.com",
            collected_information=[{"agent": "discovery", "output": {}}],
        )

        assert result["success"] is True
        assert len(mock_agent._run_calls) == 1

    def test_execute_skips_validation_when_no_input_schema(
        self, mock_agent, sample_schema, tmp_path
    ):
        """No validation when input_schema_path not provided."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))

        # No input schema provided
        tool = AgentTool(agent=mock_agent, output_schema_path=str(output_path))

        result = tool.execute(task="Test without input schema")

        # Should succeed even without any context
        assert result["success"] is True
        assert len(mock_agent._run_calls) == 1

    def test_validate_input_with_none_context(
        self, mock_agent, sample_schema, input_schema, tmp_path
    ):
        """Validation handles None context by treating as empty dict."""
        output_path = tmp_path / "output.schema.json"
        output_path.write_text(json.dumps(sample_schema))
        input_path = tmp_path / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        tool = AgentTool(
            agent=mock_agent,
            output_schema_path=str(output_path),
            input_schema_path=str(input_path),
        )

        result = tool._validate_input(None)

        assert result is not None
        assert result["success"] is False
        assert "target_url" in result["missing_fields"]
        assert "collected_information" in result["missing_fields"]
