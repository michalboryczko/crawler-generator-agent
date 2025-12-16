"""Integration tests for memory isolation and data flow.

These tests verify the new memory architecture where:
1. Each agent has an isolated MemoryService
2. Data flows explicitly via AgentResult and context parameters
3. Orchestration tools can optionally share data via shared memory service
"""

from unittest.mock import MagicMock

import pytest

from src.agents.result import AgentResult
from src.infrastructure import Container, init_container
from src.core.config import StorageConfig
from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService
from src.tools.orchestration import (
    RunAccessibilityAgentTool,
    RunBrowserAgentTool,
    RunDataPrepAgentTool,
    RunSelectorAgentTool,
    create_agent_runner_tool,
)


def create_mock_llm() -> MagicMock:
    """Create a mock LLM with spec to avoid factory detection."""
    mock_llm = MagicMock(spec=["chat"])
    mock_llm.chat.return_value = {"content": "Done", "tool_calls": []}
    return mock_llm


def create_mock_browser_session() -> MagicMock:
    """Create a mock browser session."""
    return MagicMock()


class MockRunnableAgent:
    """Mock agent that returns configurable results."""

    def __init__(self, result: AgentResult) -> None:
        self.result = result
        self.last_task: str | None = None
        self.last_context: dict | None = None

    def run(self, task: str, context: dict | None = None) -> AgentResult:
        self.last_task = task
        self.last_context = context
        return self.result


class TestContainerAndMemoryService:
    """Test Container and MemoryService integration."""

    def test_container_creates_memory_services(self):
        """Container creates isolated memory services per agent."""
        config = StorageConfig(backend_type="memory")
        container = init_container(config)

        service1 = container.memory_service("browser")
        service2 = container.memory_service("selector")

        # Both services use the same repository but different agent names
        service1.write("key", "value1")
        service2.write("key", "value2")

        assert service1.read("key") == "value1"
        assert service2.read("key") == "value2"

    def test_container_session_isolation(self):
        """Different containers have different sessions."""
        config = StorageConfig(backend_type="memory")
        container1 = init_container(config)
        container2 = init_container(config)

        service1 = container1.memory_service("agent")
        service2 = container2.memory_service("agent")

        service1.write("key", "value1")
        service2.write("key", "value2")

        # Different sessions, so data is isolated
        assert service1.read("key") == "value1"
        assert service2.read("key") == "value2"


class TestMemoryServiceIsolation:
    """Test that memory services provide proper isolation."""

    def test_agent_isolation_with_shared_repo(self):
        """Multiple services on same repo are isolated by agent name."""
        repo = InMemoryRepository()
        session_id = "test-session"

        browser_service = MemoryService(repo, session_id, "browser")
        selector_service = MemoryService(repo, session_id, "selector")
        accessibility_service = MemoryService(repo, session_id, "accessibility")
        data_prep_service = MemoryService(repo, session_id, "data_prep")

        # Write same key to each service
        browser_service.write("result", "browser_data")
        selector_service.write("result", "selector_data")
        accessibility_service.write("result", "accessibility_data")
        data_prep_service.write("result", "data_prep_data")

        # Each service sees only its own data
        assert browser_service.read("result") == "browser_data"
        assert selector_service.read("result") == "selector_data"
        assert accessibility_service.read("result") == "accessibility_data"
        assert data_prep_service.read("result") == "data_prep_data"

    def test_write_to_one_service_doesnt_affect_others(self):
        """Writing to one service doesn't leak to others."""
        repo = InMemoryRepository()

        service1 = MemoryService(repo, "session", "agent1")
        service2 = MemoryService(repo, "session", "agent2")

        service1.write("secret", "agent1_data")

        assert service1.read("secret") == "agent1_data"
        assert service2.read("secret") is None


class TestExplicitDataFlow:
    """Test explicit data passing between agents via context."""

    def test_context_flows_through_orchestration_tool(self):
        """Context passed to tool reaches the agent."""
        result = AgentResult.ok(final_selectors={"article": "div.article"})
        result.iterations = 1

        agent = MockRunnableAgent(result)
        tool = RunSelectorAgentTool(agent)

        context = {"article_links": ["link1", "link2"], "target_url": "http://example.com"}
        tool.execute(task="Find selectors", context=context)

        assert agent.last_context == context

    def test_agent_result_data_returned_in_tool_response(self):
        """Tool response includes full structured data from AgentResult."""
        result = AgentResult.ok(
            extracted_articles=[{"href": "/a1"}, {"href": "/a2"}],
            pagination_type="numbered",
            pagination_max_pages=50,
        )
        result.iterations = 3

        agent = MockRunnableAgent(result)
        tool = RunBrowserAgentTool(agent)

        response = tool.execute(task="Extract articles")

        assert response["success"] is True
        assert response["data"]["extracted_articles"] == [{"href": "/a1"}, {"href": "/a2"}]
        assert response["data"]["pagination_type"] == "numbered"
        assert response["data"]["pagination_max_pages"] == 50
        assert response["iterations"] == 3


class TestOrchestratorMemorySharing:
    """Test optional memory sharing through orchestrator."""

    def test_specified_keys_stored_in_orchestrator_memory(self):
        """Store_keys parameter stores specified results in shared memory."""
        repo = InMemoryRepository()
        orchestrator_memory = MemoryService(repo, "session", "orchestrator")

        result = AgentResult.ok(
            pagination_type="infinite_scroll",
            extracted_count=100,
            internal_state="not exported",
        )
        result.iterations = 1

        agent = MockRunnableAgent(result)
        tool = RunBrowserAgentTool(
            agent,
            orchestrator_memory=orchestrator_memory,
            store_keys=["pagination_type", "extracted_count"],
        )

        tool.execute(task="Analyze page")

        # Specified keys should be in orchestrator memory
        assert orchestrator_memory.read("pagination_type") == "infinite_scroll"
        assert orchestrator_memory.read("extracted_count") == 100
        # Non-specified keys should not be stored
        assert orchestrator_memory.read("internal_state") is None

    def test_orchestrator_memory_persists_across_tools(self):
        """Data stored by one tool is available for other tools."""
        repo = InMemoryRepository()
        shared_memory = MemoryService(repo, "session", "orchestrator")

        # Browser agent stores pagination type
        browser_result = AgentResult.ok(pagination_type="numbered", total_pages=10)
        browser_result.iterations = 1
        browser_agent = MockRunnableAgent(browser_result)
        browser_tool = RunBrowserAgentTool(
            browser_agent,
            orchestrator_memory=shared_memory,
            store_keys=["pagination_type", "total_pages"],
        )
        browser_tool.execute(task="Analyze site")

        # Selector agent stores selectors
        selector_result = AgentResult.ok(article_selector="div.article")
        selector_result.iterations = 1
        selector_agent = MockRunnableAgent(selector_result)
        selector_tool = RunSelectorAgentTool(
            selector_agent,
            orchestrator_memory=shared_memory,
            store_keys=["article_selector"],
        )
        selector_tool.execute(task="Find selectors")

        # Both results should be in shared memory
        assert shared_memory.read("pagination_type") == "numbered"
        assert shared_memory.read("total_pages") == 10
        assert shared_memory.read("article_selector") == "div.article"


class TestDataFlowWorkflow:
    """End-to-end workflow tests for data passing."""

    def test_browser_to_selector_workflow(self):
        """Simulate browser agent results flowing to selector agent."""
        # Step 1: Browser agent extracts article links
        browser_result = AgentResult.ok(
            extracted_articles=[
                {"href": "/article/1", "text": "Article 1"},
                {"href": "/article/2", "text": "Article 2"},
            ],
            pagination_type="numbered",
            base_url="http://example.com",
        )
        browser_result.iterations = 2
        browser_agent = MockRunnableAgent(browser_result)

        # Step 2: Execute browser tool and get result
        browser_tool = RunBrowserAgentTool(browser_agent)
        browser_response = browser_tool.execute(task="Extract articles from page")

        # Step 3: Extract data to pass to selector agent
        context_for_selector = {
            "article_links": browser_response["data"]["extracted_articles"],
            "pagination_info": browser_response["data"]["pagination_type"],
        }

        # Step 4: Selector agent runs with context
        selector_result = AgentResult.ok(
            article_link_selector="a.article-link",
            pagination_selector="div.pagination a",
        )
        selector_result.iterations = 1
        selector_agent = MockRunnableAgent(selector_result)
        selector_tool = RunSelectorAgentTool(selector_agent)

        selector_response = selector_tool.execute(
            task="Find CSS selectors", context=context_for_selector
        )

        # Verify data flowed correctly
        assert selector_agent.last_context["article_links"] == browser_response["data"]["extracted_articles"]
        assert selector_response["data"]["article_link_selector"] == "a.article-link"

    def test_full_agent_chain_with_shared_memory(self):
        """Test complete workflow: browser -> selector -> accessibility."""
        repo = InMemoryRepository()
        shared_memory = MemoryService(repo, "session", "main")

        # Browser agent
        browser_result = AgentResult.ok(
            url="http://example.com",
            link_count=25,
            pagination_type="next_button",
        )
        browser_result.iterations = 1
        browser_agent = MockRunnableAgent(browser_result)
        browser_tool = RunBrowserAgentTool(
            browser_agent,
            orchestrator_memory=shared_memory,
            store_keys=["url", "pagination_type"],
        )

        # Selector agent
        selector_result = AgentResult.ok(
            article_selector="article.post",
            link_selector="article.post a",
        )
        selector_result.iterations = 1
        selector_agent = MockRunnableAgent(selector_result)
        selector_tool = RunSelectorAgentTool(
            selector_agent,
            orchestrator_memory=shared_memory,
            store_keys=["article_selector", "link_selector"],
        )

        # Accessibility agent
        accessibility_result = AgentResult.ok(
            http_accessible=True,
            no_js_required=True,
        )
        accessibility_result.iterations = 1
        accessibility_agent = MockRunnableAgent(accessibility_result)
        accessibility_tool = RunAccessibilityAgentTool(
            accessibility_agent,
            orchestrator_memory=shared_memory,
            store_keys=["http_accessible", "no_js_required"],
        )

        # Execute chain
        browser_tool.execute(task="Analyze site")
        selector_tool.execute(
            task="Find selectors", context={"url": shared_memory.read("url")}
        )
        accessibility_tool.execute(
            task="Check accessibility",
            context={"selector": shared_memory.read("article_selector")},
        )

        # Verify final shared memory state
        assert shared_memory.read("url") == "http://example.com"
        assert shared_memory.read("pagination_type") == "next_button"
        assert shared_memory.read("article_selector") == "article.post"
        assert shared_memory.read("link_selector") == "article.post a"
        assert shared_memory.read("http_accessible") is True
        assert shared_memory.read("no_js_required") is True


class TestFactoryFunctionWithMemory:
    """Test create_agent_runner_tool with memory features."""

    def test_factory_creates_tool_with_memory_support(self):
        """Factory function creates tool that supports memory storage."""
        repo = InMemoryRepository()
        shared_memory = MemoryService(repo, "session", "test")

        result = AgentResult.ok(important_key="important_value", other="data")
        result.iterations = 1
        agent = MockRunnableAgent(result)

        tool = create_agent_runner_tool(
            tool_name="test_agent",
            agent=agent,
            description="Test agent",
            orchestrator_memory=shared_memory,
            store_keys=["important_key"],
        )

        tool.execute(task="do work")

        assert shared_memory.read("important_key") == "important_value"
        assert shared_memory.read("other") is None
