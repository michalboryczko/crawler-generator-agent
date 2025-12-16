"""Tests for orchestration tools with explicit data passing."""

from typing import Any

from src.agents.result import AgentResult
from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService
from src.tools.orchestration import (
    RunAccessibilityAgentTool,
    RunBrowserAgentTool,
    RunDataPrepAgentTool,
    RunSelectorAgentTool,
    _extract_result_info,
    create_agent_runner_tool,
)


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, result: AgentResult) -> None:
        self.result = result
        self.last_task: str | None = None
        self.last_context: dict | None = None

    def run(self, task: str, context: dict | None = None) -> AgentResult:
        self.last_task = task
        self.last_context = context
        return self.result


class TestExtractResultInfo:
    """Tests for _extract_result_info helper."""

    def test_extracts_success_result(self):
        """Extract info from successful result."""
        result = AgentResult.ok(result="done", items=[1, 2, 3])
        result.iterations = 5
        info = _extract_result_info(result)

        assert info["success"] is True
        assert info["iterations"] == 5
        assert info["data"] == {"result": "done", "items": [1, 2, 3]}
        assert info["result"] == "done"

    def test_extracts_full_data_dict(self):
        """Full data dict is included in response."""
        result = AgentResult.ok(
            extracted_articles=[{"text": "Article 1"}],
            pagination_type="numbered",
            pagination_max_pages=10
        )
        result.iterations = 3
        info = _extract_result_info(result)

        assert info["data"]["extracted_articles"] == [{"text": "Article 1"}]
        assert info["data"]["pagination_type"] == "numbered"
        assert info["data"]["pagination_max_pages"] == 10

    def test_extracts_failure_result(self):
        """Extract info from failed result."""
        result = AgentResult.failure("Connection timeout")
        result.add_error("Retry failed")
        result.iterations = 2
        info = _extract_result_info(result)

        assert info["success"] is False
        assert info["iterations"] == 2
        assert info["error"] == "Connection timeout"
        assert info["errors"] == ["Connection timeout", "Retry failed"]
        assert info["result"] == "Connection timeout"

    def test_failure_with_empty_errors(self):
        """Handle failure with empty error list."""
        result = AgentResult(
            success=False,
            data={},
            iterations=1,
            errors=[]
        )
        info = _extract_result_info(result)

        assert info["success"] is False
        assert info["error"] == "Unknown error"


def _make_success_result(**data: Any) -> AgentResult:
    """Helper to create success result with iterations."""
    result = AgentResult.ok(**data)
    result.iterations = data.pop("iterations", 1) if "iterations" in data else 1
    return result


class TestCreateAgentRunnerTool:
    """Tests for create_agent_runner_tool factory."""

    def test_creates_tool_with_name(self):
        """Factory creates tool with correct name."""
        result = AgentResult.ok()
        result.iterations = 1
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test description"
        )
        assert tool.name == "test_tool"

    def test_tool_accepts_context(self):
        """Context parameter passes through to agent."""
        result = AgentResult.ok(result="ok")
        result.iterations = 1
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test description"
        )

        context = {"previous_results": [1, 2, 3]}
        tool.execute(task="do something", context=context)

        assert agent.last_context == context

    def test_tool_returns_structured_data(self):
        """Response includes full data dict."""
        result = AgentResult.ok(
            articles=[{"title": "Test"}],
            count=1,
            result="found 1 article"
        )
        result.iterations = 3
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test"
        )

        response = tool.execute(task="find articles")

        assert response["success"] is True
        assert response["data"]["articles"] == [{"title": "Test"}]
        assert response["iterations"] == 3

    def test_tool_stores_to_orchestrator_memory(self):
        """Specified keys are stored in orchestrator memory."""
        repo = InMemoryRepository()
        orchestrator_memory = MemoryService(repo, "test-session", "orchestrator")
        result = AgentResult.ok(
            extracted_articles=[{"text": "Article"}],
            pagination_type="numbered",
            other_data="not stored"
        )
        result.iterations = 1
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test",
            orchestrator_memory=orchestrator_memory,
            store_keys=["extracted_articles", "pagination_type"]
        )

        tool.execute(task="analyze page")

        assert orchestrator_memory.read("extracted_articles") == [{"text": "Article"}]
        assert orchestrator_memory.read("pagination_type") == "numbered"
        assert orchestrator_memory.read("other_data") is None

    def test_tool_handles_agent_failure(self):
        """Errors propagated correctly on failure."""
        result = AgentResult.failure("Page not found")
        result.iterations = 1
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test"
        )

        response = tool.execute(task="navigate")

        assert response["success"] is False
        assert response["error"] == "Page not found"
        assert "errors" in response

    def test_no_storage_on_failure(self):
        """Keys not stored to memory on failure."""
        repo = InMemoryRepository()
        orchestrator_memory = MemoryService(repo, "test-session", "orchestrator")
        result = AgentResult.failure("Error")
        result.iterations = 1
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test",
            orchestrator_memory=orchestrator_memory,
            store_keys=["key1"]
        )

        tool.execute(task="fail")

        assert orchestrator_memory.list_keys() == []

    def test_parameters_schema(self):
        """Tool has correct parameters schema."""
        result = AgentResult.ok()
        result.iterations = 1
        agent = MockAgent(result)
        tool = create_agent_runner_tool(
            tool_name="test_tool",
            agent=agent,
            description="Test",
            task_description="Custom task desc"
        )

        schema = tool.get_parameters_schema()

        assert schema["type"] == "object"
        assert "task" in schema["properties"]
        assert "context" in schema["properties"]
        assert schema["properties"]["task"]["description"] == "Custom task desc"
        assert schema["required"] == ["task"]


class TestRunBrowserAgentTool:
    """Tests for RunBrowserAgentTool class."""

    def test_basic_execution(self):
        """Tool executes agent and returns structured result."""
        result = AgentResult.ok(extracted_articles=[], result="done")
        result.iterations = 2
        agent = MockAgent(result)
        tool = RunBrowserAgentTool(agent)

        response = tool.execute(task="extract articles")

        assert response["success"] is True
        assert response["data"]["extracted_articles"] == []
        assert agent.last_task == "extract articles"

    def test_with_orchestrator_memory(self):
        """Tool stores specified keys to orchestrator memory."""
        repo = InMemoryRepository()
        memory = MemoryService(repo, "test-session", "browser")
        result = AgentResult.ok(pagination_type="infinite_scroll")
        result.iterations = 1
        agent = MockAgent(result)
        tool = RunBrowserAgentTool(
            agent,
            orchestrator_memory=memory,
            store_keys=["pagination_type"]
        )

        tool.execute(task="analyze")

        assert memory.read("pagination_type") == "infinite_scroll"


class TestRunSelectorAgentTool:
    """Tests for RunSelectorAgentTool class."""

    def test_passes_context_to_agent(self):
        """Context data passes through to selector agent."""
        result = AgentResult.ok()
        result.iterations = 1
        agent = MockAgent(result)
        tool = RunSelectorAgentTool(agent)

        context = {"html_sample": "<div>test</div>"}
        tool.execute(task="find selector", context=context)

        assert agent.last_context == context


class TestRunAccessibilityAgentTool:
    """Tests for RunAccessibilityAgentTool class."""

    def test_stores_accessibility_results(self):
        """Accessibility results stored in memory."""
        repo = InMemoryRepository()
        memory = MemoryService(repo, "test-session", "accessibility")
        result = AgentResult.ok(http_accessible=True)
        result.iterations = 1
        agent = MockAgent(result)
        tool = RunAccessibilityAgentTool(
            agent,
            orchestrator_memory=memory,
            store_keys=["http_accessible"]
        )

        tool.execute(task="check accessibility")

        assert memory.read("http_accessible") is True


class TestRunDataPrepAgentTool:
    """Tests for RunDataPrepAgentTool class."""

    def test_returns_test_data(self):
        """Tool returns test data in structured format."""
        result = AgentResult.ok(test_data=[{"url": "http://example.com"}])
        result.iterations = 1
        agent = MockAgent(result)
        tool = RunDataPrepAgentTool(agent)

        response = tool.execute(task="prepare test data")

        assert response["data"]["test_data"] == [{"url": "http://example.com"}]
