"""Tests for BaseAgent class."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.agents.base import BaseAgent, MAX_ITERATIONS
from src.agents.result import AgentResult
from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService


def create_mock_llm(responses: list[dict[str, Any]] | None = None) -> MagicMock:
    """Create a mock LLM with given responses.

    Args:
        responses: List of response dicts. Each dict should have 'content' and 'tool_calls'.
                  If None, returns a single "Done" response with no tool calls.

    Note:
        Uses spec=['chat'] to prevent MagicMock from auto-creating 'get_client',
        which would make BaseAgent treat this as an LLMClientFactory.
    """
    # Use spec to prevent auto-creation of 'get_client' attribute
    # which would make BaseAgent think this is a factory
    mock_llm = MagicMock(spec=['chat'])

    if responses is None:
        responses = [{"content": "Done", "tool_calls": []}]

    call_count = [0]  # Use list to allow mutation in closure

    def mock_chat(*args, **kwargs):
        if call_count[0] < len(responses):
            result = responses[call_count[0]]
            call_count[0] += 1
            return result
        # Return last response if we've exhausted the list
        return responses[-1]

    mock_llm.chat.side_effect = mock_chat
    return mock_llm


class TestBaseAgentRunReturnsAgentResult:
    """Test that BaseAgent.run() returns AgentResult."""

    def test_run_returns_agent_result_on_success(self) -> None:
        """Test run() returns AgentResult with success=True when agent completes."""
        mock_llm = create_mock_llm([
            {"content": "Task completed successfully", "tool_calls": []}
        ])

        agent = BaseAgent(mock_llm)
        result = agent.run("Test task")

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.get("result") == "Task completed successfully"
        assert result.iterations == 1

    def test_run_returns_agent_result_on_max_iterations(self) -> None:
        """Test run() returns AgentResult with failure on max iterations."""
        # Always return a tool call to trigger max iterations
        mock_llm = create_mock_llm([
            {"content": "", "tool_calls": [{"id": "1", "name": "unknown_tool", "arguments": {}}]}
        ])

        agent = BaseAgent(mock_llm)
        result = agent.run("Test task")

        assert isinstance(result, AgentResult)
        assert result.success is False
        assert result.failed is True
        assert f"Max iterations ({MAX_ITERATIONS}) reached" in result.errors
        assert result.iterations == MAX_ITERATIONS


class TestBaseAgentContextInjection:
    """Test context parameter injection into system message."""

    def test_context_injected_to_system_message(self) -> None:
        """Test that context dict is injected into system message."""
        mock_llm = create_mock_llm([
            {"content": "Done", "tool_calls": []}
        ])

        agent = BaseAgent(mock_llm)
        context = {"target_url": "https://example.com", "max_pages": 10}

        agent.run("Test task", context=context)

        # Check the system message in the first call
        call_args = mock_llm.chat.call_args_list[0]
        messages = call_args[0][0]

        system_message = messages[0]
        assert system_message["role"] == "system"
        assert "Context from orchestrator" in system_message["content"]
        assert "https://example.com" in system_message["content"]
        assert "max_pages" in system_message["content"]

    def test_no_context_injection_when_none(self) -> None:
        """Test that system message is unchanged when context is None."""
        mock_llm = create_mock_llm([
            {"content": "Done", "tool_calls": []}
        ])

        agent = BaseAgent(mock_llm)
        original_prompt = agent.system_prompt

        agent.run("Test task", context=None)

        call_args = mock_llm.chat.call_args_list[0]
        messages = call_args[0][0]
        system_message = messages[0]

        assert system_message["content"] == original_prompt
        assert "Context from orchestrator" not in system_message["content"]


class TestBaseAgentMemorySnapshot:
    """Test memory snapshot functionality."""

    def test_memory_snapshot_included_when_service_exists(self) -> None:
        """Test memory_snapshot is populated when agent has memory service."""
        mock_llm = create_mock_llm([
            {"content": "Done", "tool_calls": []}
        ])

        repo = InMemoryRepository()
        memory_service = MemoryService(repo, "test-session", "test-agent")
        memory_service.write("key1", "value1")
        memory_service.write("key2", {"nested": "data"})

        agent = BaseAgent(mock_llm, memory_service=memory_service)
        result = agent.run("Test task")

        assert result.memory_snapshot is not None
        assert result.memory_snapshot["key1"] == "value1"
        assert result.memory_snapshot["key2"] == {"nested": "data"}

    def test_memory_snapshot_none_when_no_service(self) -> None:
        """Test memory_snapshot is None when agent has no memory service."""
        mock_llm = create_mock_llm([
            {"content": "Done", "tool_calls": []}
        ])

        agent = BaseAgent(mock_llm, memory_service=None)
        result = agent.run("Test task")

        assert result.memory_snapshot is None


class TestBaseAgentExtractResultData:
    """Test _extract_result_data method."""

    def test_default_extract_result_data(self) -> None:
        """Test default implementation wraps content in result key."""
        mock_llm = create_mock_llm()
        agent = BaseAgent(mock_llm)

        data = agent._extract_result_data("Test content")

        assert data == {"result": "Test content"}

    def test_extract_result_data_can_be_overridden(self) -> None:
        """Test subclasses can override _extract_result_data."""

        class CustomAgent(BaseAgent):
            def _extract_result_data(self, content: str) -> dict:
                return {"custom_key": content, "parsed": True}

        mock_llm = create_mock_llm([
            {"content": "Custom response", "tool_calls": []}
        ])

        agent = CustomAgent(mock_llm)
        result = agent.run("Test task")

        assert result.get("custom_key") == "Custom response"
        assert result.get("parsed") is True


class TestBaseAgentIterationCount:
    """Test iteration counting."""

    def test_iterations_count_is_correct(self) -> None:
        """Test iterations count reflects actual iterations."""
        # Two iterations with tool calls, then complete on third
        mock_llm = create_mock_llm([
            {"content": "", "tool_calls": [{"id": "1", "name": "test_tool", "arguments": {}}]},
            {"content": "", "tool_calls": [{"id": "2", "name": "test_tool", "arguments": {}}]},
            {"content": "Done", "tool_calls": []}
        ])

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.execute.return_value = {"success": True}

        agent = BaseAgent(mock_llm, tools=[mock_tool])
        result = agent.run("Test task")

        assert result.iterations == 3


class TestBaseAgentToolExecution:
    """Test tool execution."""

    def test_execute_unknown_tool_returns_error(self) -> None:
        """Test that executing an unknown tool returns an error dict."""
        mock_llm = create_mock_llm()
        agent = BaseAgent(mock_llm)

        result = agent._execute_tool("unknown_tool", {})

        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_execute_tool_handles_exception(self) -> None:
        """Test that tool exceptions are caught and returned as error."""
        mock_llm = create_mock_llm()
        mock_tool = MagicMock()
        mock_tool.name = "failing_tool"
        mock_tool.execute.side_effect = ValueError("Tool failed")

        agent = BaseAgent(mock_llm, tools=[mock_tool])
        result = agent._execute_tool("failing_tool", {})

        assert result["success"] is False
        assert "Tool failed" in result["error"]

    def test_tool_execution_in_loop(self) -> None:
        """Test that tool is executed during run loop."""
        mock_llm = create_mock_llm([
            {"content": "", "tool_calls": [{"id": "1", "name": "my_tool", "arguments": {"arg": "val"}}]},
            {"content": "Final result", "tool_calls": []}
        ])

        mock_tool = MagicMock()
        mock_tool.name = "my_tool"
        mock_tool.execute.return_value = {"success": True, "data": "tool output"}

        agent = BaseAgent(mock_llm, tools=[mock_tool])
        result = agent.run("Test task")

        # Verify tool was called
        mock_tool.execute.assert_called_once()
        assert result.success is True
        assert result.get("result") == "Final result"


class TestBaseAgentFactoryDetection:
    """Test LLMClientFactory detection."""

    def test_direct_llm_client_used(self) -> None:
        """Test that direct LLM client (no get_client) is used directly."""
        mock_llm = create_mock_llm()

        agent = BaseAgent(mock_llm)

        assert agent.llm is mock_llm
        assert agent.llm_factory is None

    def test_factory_creates_client(self) -> None:
        """Test that LLMClientFactory creates client via get_client."""
        mock_factory = MagicMock()
        mock_client = create_mock_llm()
        mock_factory.get_client.return_value = mock_client

        agent = BaseAgent(mock_factory)

        mock_factory.get_client.assert_called_once_with("base_agent")
        assert agent.llm is mock_client
        assert agent.llm_factory is mock_factory
