"""Tests for BaseAgent contract system support."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agents.base import BaseAgent
from src.agents.result import AgentResult
from src.tools.agent_tools import AgentTool
from src.tools.base import BaseTool


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: list[dict] | None = None):
        """Initialize mock with canned responses."""
        self._responses = responses or []
        self._call_count = 0
        self.chat_calls = []

    def chat(self, messages: list[dict], tools: list | None = None) -> dict[str, Any]:
        """Return canned response and record call."""
        self.chat_calls.append({"messages": messages, "tools": tools})

        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
            self._call_count += 1
            return response

        # Default: return done response
        return {"content": "Done", "tool_calls": []}


class MockAgent:
    """Mock agent for AgentTool testing."""

    def __init__(self, agent_name: str = "mock_agent"):
        """Initialize mock agent."""
        self.name = agent_name
        self.description = f"Mock {agent_name} for testing"

    def get_description(self) -> str:
        """Return formatted agent description."""
        return f"{self.name} - {self.description}"

    def run(self, task: str, **kwargs) -> MagicMock:
        """Mock run that returns success."""
        result = MagicMock()
        result.success = True
        result.data = {}
        result.errors = []
        result.iterations = 1
        return result


class MockRegularTool(BaseTool):
    """Mock regular tool (not AgentTool) for testing auto-detection."""

    def __init__(self, tool_name: str = "mock_tool"):
        """Initialize mock tool."""
        self._name = tool_name

    @property
    def name(self) -> str:
        """Tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Tool description."""
        return f"Mock tool: {self._name}"

    def get_parameters_schema(self) -> dict[str, Any]:
        """Return empty parameters schema."""
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool."""
        return {"success": True}


@pytest.fixture
def sample_schema_path(tmp_path: Path) -> str:
    """Create a sample schema file for AgentTool testing."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"result": {"type": "string", "description": "Test result"}},
        "required": ["result"],
    }
    schema_file = tmp_path / "test_output.schema.json"
    schema_file.write_text(json.dumps(schema))
    return str(schema_file)


def create_agent_tool(
    agent_name: str, schema_path: str, description: str | None = None
) -> AgentTool:
    """Helper to create AgentTool with mock agent."""
    mock_agent = MockAgent(agent_name)
    return AgentTool(
        agent=mock_agent,
        output_schema_path=schema_path,
        description=description or f"Test {agent_name} tool",
    )


class TestBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_agent_without_agent_tools_works(self):
        """Agent without agent_tools works as before."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm, tools=[])

        # Should not fail
        assert agent.agent_tools == []

    def test_existing_run_signature_works(self):
        """Existing run() call signature still works."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        result = agent.run(task="test task")

        assert isinstance(result, AgentResult)

    def test_run_with_context_only_works(self):
        """run() with context parameter works."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        result = agent.run(task="test task", context={"key": "value"})

        assert result.success is True


class TestAgentToolsAutoDetection:
    """Tests for agent_tools auto-detection from tools list."""

    def test_agent_tools_auto_detected(self, sample_schema_path):
        """AgentTool instances auto-detected from tools list."""
        llm = MockLLMClient()
        agent_tool = create_agent_tool("test_agent", sample_schema_path)

        agent = BaseAgent(llm=llm, tools=[agent_tool])

        assert len(agent.agent_tools) == 1
        assert agent.agent_tools[0] is agent_tool

    def test_agent_tools_added_to_tool_map(self, sample_schema_path):
        """AgentTools accessible by name in tool map."""
        llm = MockLLMClient()
        agent_tool = create_agent_tool("discovery_agent", sample_schema_path)

        agent = BaseAgent(llm=llm, tools=[agent_tool])

        assert "run_discovery_agent" in agent._tool_map
        assert agent._tool_map["run_discovery_agent"] is agent_tool

    def test_multiple_agent_tools(self, sample_schema_path):
        """Multiple agent tools detected correctly."""
        llm = MockLLMClient()
        agent_tool1 = create_agent_tool("agent_a", sample_schema_path)
        agent_tool2 = create_agent_tool("agent_b", sample_schema_path)

        agent = BaseAgent(llm=llm, tools=[agent_tool1, agent_tool2])

        assert len(agent.agent_tools) == 2
        assert "run_agent_a" in agent._tool_map
        assert "run_agent_b" in agent._tool_map

    def test_non_agent_tools_not_detected(self, sample_schema_path):
        """Regular tools not included in agent_tools."""
        llm = MockLLMClient()
        agent_tool = create_agent_tool("my_agent", sample_schema_path)
        regular_tool = MockRegularTool("regular_tool")

        agent = BaseAgent(llm=llm, tools=[regular_tool, agent_tool])

        # Only AgentTool in agent_tools
        assert len(agent.agent_tools) == 1
        assert agent.agent_tools[0] is agent_tool

        # Both in tool_map
        assert "run_my_agent" in agent._tool_map
        assert "regular_tool" in agent._tool_map

    def test_mixed_tools_detection(self, sample_schema_path):
        """Mixed tools list correctly separates AgentTools."""
        llm = MockLLMClient()
        regular1 = MockRegularTool("tool1")
        agent1 = create_agent_tool("agent1", sample_schema_path)
        regular2 = MockRegularTool("tool2")
        agent2 = create_agent_tool("agent2", sample_schema_path)

        agent = BaseAgent(llm=llm, tools=[regular1, agent1, regular2, agent2])

        # Check agent_tools
        assert len(agent.agent_tools) == 2
        assert agent1 in agent.agent_tools
        assert agent2 in agent.agent_tools

        # Check all tools in tools list (4 original + 1 auto-attached DescribeOutputContractTool)
        assert len(agent.tools) == 5

        # Check tool_map has all (including auto-attached describe_output_contract)
        assert "tool1" in agent._tool_map
        assert "tool2" in agent._tool_map
        assert "run_agent1" in agent._tool_map
        assert "run_agent2" in agent._tool_map
        assert "describe_output_contract" in agent._tool_map


class TestBuildFinalPrompt:
    """Tests for _build_final_prompt() method."""

    def test_build_final_prompt_basic(self):
        """Returns system_prompt when no contract params."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)
        agent.system_prompt = "Test system prompt."

        prompt = agent._build_final_prompt()

        assert prompt == "Test system prompt."

    def test_build_final_prompt_with_context(self):
        """Context JSON injected into prompt."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)
        agent.system_prompt = "Base prompt."

        prompt = agent._build_final_prompt(context={"key": "value"})

        assert "Base prompt." in prompt
        assert "Context" in prompt
        assert '"key"' in prompt
        assert '"value"' in prompt

    def test_build_final_prompt_with_agent_tools(self, sample_schema_path):
        """Sub-agents section added when agent_tools present."""
        llm = MockLLMClient()
        agent_tool = create_agent_tool("discovery_agent", sample_schema_path)
        agent = BaseAgent(llm=llm, tools=[agent_tool])
        agent.system_prompt = "Base prompt."

        prompt = agent._build_final_prompt()

        assert "Base prompt." in prompt
        assert "Available agents" in prompt
        assert "discovery_agent" in prompt

    def test_build_final_prompt_with_validation_context(self):
        """Response rules included when validation params provided."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)
        agent.system_prompt = "Base prompt."

        prompt = agent._build_final_prompt(
            expected_outputs=["article_urls"], run_identifier="uuid-123"
        )

        assert "Base prompt." in prompt
        assert "uuid-123" in prompt
        assert "validate_response" in prompt

    def test_build_final_prompt_all_sections(self, sample_schema_path):
        """All sections combined in correct order."""
        llm = MockLLMClient()
        agent_tool = create_agent_tool("test_agent", sample_schema_path)
        agent = BaseAgent(llm=llm, tools=[agent_tool])
        agent.system_prompt = "Base prompt."

        prompt = agent._build_final_prompt(
            expected_outputs=["field1"], run_identifier="uuid-456", context={"data": "test"}
        )

        # All sections present
        assert "Base prompt." in prompt
        assert "Available agents" in prompt
        assert "uuid-456" in prompt
        assert '"data"' in prompt


class TestBuildSubAgentsSection:
    """Tests for _build_sub_agents_section() method."""

    def test_build_sub_agents_section_empty(self):
        """Returns empty string when no agent_tools."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        section = agent._build_sub_agents_section()

        assert section == ""

    def test_build_sub_agents_section_with_tools(self, sample_schema_path):
        """Returns formatted section with agent tools."""
        llm = MockLLMClient()
        agent_tool1 = create_agent_tool("agent_a", sample_schema_path)
        agent_tool2 = create_agent_tool("agent_b", sample_schema_path)
        agent = BaseAgent(llm=llm, tools=[agent_tool1, agent_tool2])

        section = agent._build_sub_agents_section()

        assert "Available agents" in section
        assert "agent_a" in section
        assert "agent_b" in section


class TestBuildResponseRules:
    """Tests for _build_response_rules() method."""

    def test_build_response_rules_basic(self):
        """Returns formatted response rules."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        rules = agent._build_response_rules(
            expected_outputs=["field1", "field2"], run_identifier="test-uuid"
        )

        assert "test-uuid" in rules
        assert "validate_response" in rules

    def test_build_response_rules_includes_fields(self):
        """Response rules mention expected fields."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        rules = agent._build_response_rules(
            expected_outputs=["article_urls", "pagination_type"], run_identifier="uuid-123"
        )

        assert "article_urls" in rules
        assert "pagination_type" in rules


class TestInjectContext:
    """Tests for _inject_context() method."""

    def test_inject_context_formats_json(self):
        """Context formatted as JSON."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        context_section = agent._inject_context({"key": "value", "num": 42})

        assert "Context" in context_section
        assert '"key"' in context_section
        assert '"value"' in context_section
        assert "42" in context_section


class TestRunWithValidationParams:
    """Tests for run() with validation parameters."""

    def test_run_accepts_expected_outputs_param(self):
        """run() accepts expected_outputs parameter."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        # Should not raise
        result = agent.run(task="test", expected_outputs=["field1"])

        assert isinstance(result, AgentResult)

    def test_run_accepts_run_identifier_param(self):
        """run() accepts run_identifier parameter."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        # Should not raise
        result = agent.run(task="test", run_identifier="uuid-123")

        assert isinstance(result, AgentResult)

    def test_run_passes_params_to_build_prompt(self):
        """run() passes validation params to _build_final_prompt."""
        llm = MockLLMClient()
        agent = BaseAgent(llm=llm)

        # Capture what _build_final_prompt receives
        original_build = agent._build_final_prompt
        build_calls = []

        def capture_build(**kwargs):
            build_calls.append(kwargs)
            return original_build(**kwargs)

        agent._build_final_prompt = capture_build

        agent.run(
            task="test",
            expected_outputs=["field1"],
            run_identifier="uuid-123",
            context={"key": "value"},
        )

        assert len(build_calls) == 1
        assert build_calls[0]["expected_outputs"] == ["field1"]
        assert build_calls[0]["run_identifier"] == "uuid-123"
        assert build_calls[0]["context"] == {"key": "value"}

    def test_run_uses_built_prompt_in_messages(self, sample_schema_path):
        """run() uses _build_final_prompt result in system message."""
        llm = MockLLMClient()
        agent_tool = create_agent_tool("test_agent", sample_schema_path)
        agent = BaseAgent(llm=llm, tools=[agent_tool])
        agent.system_prompt = "Base prompt."

        agent.run(task="test task")

        # Check first chat call's system message
        system_msg = llm.chat_calls[0]["messages"][0]
        assert system_msg["role"] == "system"
        assert "Available agents" in system_msg["content"]


class MockValidateResponseTool(BaseTool):
    """Mock validate_response tool for testing code-level validation."""

    def __init__(self, validation_results: list[dict[str, Any]] | None = None):
        """Initialize with canned validation results.

        Args:
            validation_results: List of results to return on each execute() call.
                               Each result should have 'valid' (bool) and optionally
                               'validation_errors' (list of dicts with 'message').
        """
        self._results = validation_results or []
        self._call_count = 0
        self.execute_calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "validate_response"

    @property
    def description(self) -> str:
        return "Validate response JSON"

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "run_identifier": {"type": "string"},
                "response_json": {"type": "object"},
            },
            "required": ["run_identifier", "response_json"],
        }

    def execute(self, **kwargs) -> dict[str, Any]:
        self.execute_calls.append(kwargs)
        if self._call_count < len(self._results):
            result = self._results[self._call_count]
            self._call_count += 1
            return result
        # Default: valid
        return {"success": True, "valid": True}


class TestCodeLevelValidationRetry:
    """Tests for code-level validation with retry in run()."""

    def test_run_validates_output_when_run_identifier_provided(self):
        """run() validates output when run_identifier provided."""
        # First response: invalid (missing required field)
        # Second response: valid
        responses = [
            {"content": '{"wrong_field": "value"}', "tool_calls": []},
            {"content": '{"name": "correct"}', "tool_calls": []},
        ]
        llm = MockLLMClient(responses=responses)

        # Mock validate_response tool that fails first, then passes
        validate_tool = MockValidateResponseTool([
            {"success": True, "valid": False, "validation_errors": [{"message": "Missing required field: name"}]},
            {"success": True, "valid": True},
        ])
        agent = BaseAgent(llm=llm, tools=[validate_tool])

        result = agent.run(task="test", run_identifier="test-uuid-123")

        # Should have retried and succeeded
        assert result.success is True
        # Should have been called twice (first invalid, then valid)
        assert len(llm.chat_calls) == 2
        # Validate tool should have been called twice
        assert len(validate_tool.execute_calls) == 2
        assert validate_tool.execute_calls[0]["run_identifier"] == "test-uuid-123"

    def test_run_skips_validation_when_no_run_identifier(self):
        """run() skips validation when no run_identifier provided."""
        responses = [{"content": "any content", "tool_calls": []}]
        llm = MockLLMClient(responses=responses)

        validate_tool = MockValidateResponseTool([
            {"success": True, "valid": False, "validation_errors": [{"message": "Error"}]},
        ])
        agent = BaseAgent(llm=llm, tools=[validate_tool])

        result = agent.run(task="test")  # No run_identifier

        assert result.success is True
        # Should only be called once
        assert len(llm.chat_calls) == 1
        # Validate tool should NOT have been called (no run_identifier)
        assert len(validate_tool.execute_calls) == 0

    def test_run_injects_error_message_on_validation_failure(self):
        """run() injects error message when validation fails."""
        responses = [
            {"content": '{"wrong": "value"}', "tool_calls": []},
            {"content": '{"name": "fixed"}', "tool_calls": []},
        ]
        llm = MockLLMClient(responses=responses)

        validate_tool = MockValidateResponseTool([
            {"success": True, "valid": False, "validation_errors": [{"message": "Missing required field: name"}]},
            {"success": True, "valid": True},
        ])
        agent = BaseAgent(llm=llm, tools=[validate_tool])

        agent.run(task="test", run_identifier="test-uuid-456")

        # Second call should have validation error message in messages
        second_call_messages = llm.chat_calls[1]["messages"]
        user_messages = [m for m in second_call_messages if m.get("role") == "user"]

        # Should have original task + validation error
        assert len(user_messages) >= 2
        assert "VALIDATION FAILED" in user_messages[-1]["content"]

    def test_run_skips_validation_when_tool_not_available(self):
        """run() skips validation when validate_response tool not available."""
        responses = [{"content": '{"any": "content"}', "tool_calls": []}]
        llm = MockLLMClient(responses=responses)
        # No validate_response tool provided
        agent = BaseAgent(llm=llm, tools=[])

        result = agent.run(task="test", run_identifier="test-uuid-789")

        assert result.success is True
        # Should only be called once (no retry since tool not available)
        assert len(llm.chat_calls) == 1
