"""Tests for isolated memory architecture."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.accessibility_agent import AccessibilityAgent
from src.agents.browser_agent import BrowserAgent
from src.agents.data_prep_agent import DataPrepAgent
from src.agents.selector_agent import SelectorAgent
from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService
from src.infrastructure import Container, init_container
from src.core.config import StorageConfig


def create_mock_llm() -> MagicMock:
    """Create a mock LLM with spec to avoid factory detection."""
    mock_llm = MagicMock(spec=["chat"])
    mock_llm.chat.return_value = {"content": "Done", "tool_calls": []}
    return mock_llm


def create_mock_browser_session() -> MagicMock:
    """Create a mock browser session."""
    return MagicMock()


class TestAgentIsolatedMemory:
    """Tests for isolated memory services per agent."""

    def test_agents_with_container_have_isolated_memory(self):
        """Test agents created with container have isolated memory services."""
        mock_llm = create_mock_llm()
        mock_browser = create_mock_browser_session()

        config = StorageConfig(backend_type="memory")
        container = init_container(config)

        browser_service = container.memory_service("browser")
        selector_service = container.memory_service("selector")

        browser_agent = BrowserAgent(mock_llm, mock_browser, memory_service=browser_service)
        selector_agent = SelectorAgent(mock_llm, mock_browser, memory_service=selector_service)

        # Different agent names provide isolation
        browser_service.write("key", "browser_value")
        selector_service.write("key", "selector_value")

        assert browser_service.read("key") == "browser_value"
        assert selector_service.read("key") == "selector_value"

    def test_agents_use_provided_memory_service(self):
        """Test agents use provided memory service."""
        mock_llm = create_mock_llm()
        mock_browser = create_mock_browser_session()

        repo = InMemoryRepository()
        custom_service = MemoryService(repo, "test-session", "custom")

        agent = BrowserAgent(mock_llm, mock_browser, memory_service=custom_service)

        assert agent.memory_service is custom_service

    def test_two_agents_same_type_different_services_are_independent(self):
        """Test two agents of same type with different services don't share data."""
        mock_llm = create_mock_llm()
        mock_browser = create_mock_browser_session()

        repo = InMemoryRepository()
        service1 = MemoryService(repo, "session1", "browser")
        service2 = MemoryService(repo, "session2", "browser")

        agent1 = BrowserAgent(mock_llm, mock_browser, memory_service=service1)
        agent2 = BrowserAgent(mock_llm, mock_browser, memory_service=service2)

        service1.write("key", "value1")
        service2.write("key", "value2")

        assert service1.read("key") == "value1"
        assert service2.read("key") == "value2"


class TestAgentResultDataFlow:
    """Tests for data flow via AgentResult."""

    def test_agent_run_returns_agent_result(self):
        """Test agent run() returns AgentResult."""
        from src.agents.result import AgentResult

        mock_llm = create_mock_llm()
        mock_browser = create_mock_browser_session()

        repo = InMemoryRepository()
        service = MemoryService(repo, "session", "browser")
        agent = BrowserAgent(mock_llm, mock_browser, memory_service=service)
        result = agent.run("Test task")

        assert isinstance(result, AgentResult)
        assert result.success is True

    def test_agent_result_includes_memory_snapshot(self):
        """Test AgentResult includes memory snapshot if store exists."""
        mock_llm = MagicMock(spec=["chat"])
        # Agent writes to memory before completing
        call_count = [0]

        def mock_chat(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: trigger memory write tool
                return {
                    "content": "",
                    "tool_calls": [
                        {"id": "1", "name": "memory_write", "arguments": {"key": "test", "value": "data"}}
                    ]
                }
            # Second call: done
            return {"content": "Done", "tool_calls": []}

        mock_llm.chat.side_effect = mock_chat
        mock_browser = create_mock_browser_session()

        repo = InMemoryRepository()
        service = MemoryService(repo, "session", "browser")
        agent = BrowserAgent(mock_llm, mock_browser, memory_service=service)
        result = agent.run("Test task")

        assert result.memory_snapshot is not None
        assert result.memory_snapshot.get("test") == "data"

    def test_context_parameter_passed_to_agent(self):
        """Test context dict is available in agent system message."""
        mock_llm = create_mock_llm()
        mock_browser = create_mock_browser_session()

        repo = InMemoryRepository()
        service = MemoryService(repo, "session", "browser")
        agent = BrowserAgent(mock_llm, mock_browser, memory_service=service)
        context = {"target_url": "https://example.com", "max_pages": 5}

        agent.run("Test task", context=context)

        # Verify context was included in system message
        call_args = mock_llm.chat.call_args_list[0]
        messages = call_args[0][0]
        system_message = messages[0]

        assert "Context from orchestrator" in system_message["content"]
        assert "https://example.com" in system_message["content"]
        assert "max_pages" in system_message["content"]


class TestMemoryServiceMergeWorkflow:
    """Tests for memory merging between services."""

    def test_merge_agent_results_to_main_service(self):
        """Test merging sub-agent results into main service."""
        repo = InMemoryRepository()

        # Simulate sub-agent completing with some data
        sub_agent_service = MemoryService(repo, "session", "browser")
        sub_agent_service.write("extracted_links", ["link1", "link2"])
        sub_agent_service.write("page_title", "Test Page")

        # Main agent receives result and merges specific keys
        main_service = MemoryService(repo, "session", "main")
        count = main_service.merge_from(sub_agent_service, keys=["extracted_links"])

        assert count == 1
        assert main_service.read("extracted_links") == ["link1", "link2"]
        assert main_service.read("page_title") is None  # Not merged

    def test_export_keys_for_context_passing(self):
        """Test exporting keys to pass as context to next agent."""
        repo = InMemoryRepository()
        browser_service = MemoryService(repo, "session", "browser")
        browser_service.write("url", "https://example.com")
        browser_service.write("links", ["l1", "l2", "l3"])
        browser_service.write("internal_state", "should not export")

        # Export only relevant keys for selector agent
        context = browser_service.export_keys(["url", "links"])

        assert context == {
            "url": "https://example.com",
            "links": ["l1", "l2", "l3"]
        }
        assert "internal_state" not in context
