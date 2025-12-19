"""Orchestration tools for coordinating agents.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.

Tools now support:
- Explicit context parameter for data passing between agents
- Full AgentResult data in responses
- Optional orchestrator memory for cross-tool data sharing
"""

from typing import TYPE_CHECKING, Any, Protocol

from ..observability.decorators import traced_tool
from .base import BaseTool

if TYPE_CHECKING:
    from ..agents.result import AgentResult
    from ..services.memory_service import MemoryService


class RunnableAgent(Protocol):
    """Protocol for agents that can be run with a task."""

    def run(self, task: str, context: dict[str, Any] | None = None) -> "AgentResult": ...


def _extract_result_info(result: "AgentResult") -> dict[str, Any]:
    """Extract standard info from AgentResult for tool response.

    Args:
        result: AgentResult from agent execution

    Returns:
        Dictionary with success, data, errors, and iterations
    """
    response: dict[str, Any] = {
        "success": result.success,
        "iterations": result.iterations,
        "data": result.data,  # Full structured data from agent
    }

    if result.success:
        # For backward compatibility, also set 'result' from data
        response["result"] = result.get("result", "")
    else:
        # Include errors for failed results
        response["errors"] = result.errors
        response["error"] = result.errors[0] if result.errors else "Unknown error"
        response["result"] = response["error"]

    return response


def create_agent_runner_tool(
    tool_name: str,
    agent: RunnableAgent,
    description: str,
    task_description: str = "Task description for the agent",
    orchestrator_memory: "MemoryService | None" = None,
    store_keys: list[str] | None = None,
) -> BaseTool:
    """Factory function to create agent runner tools.

    Reduces boilerplate by generating tools with consistent structure.

    Args:
        tool_name: Name of the tool (e.g., "run_discovery_agent")
        agent: The agent instance to run
        description: Tool description for LLM
        task_description: Description for the task parameter
        orchestrator_memory: Optional shared memory store for cross-tool data
        store_keys: Keys to automatically store in orchestrator_memory after execution

    Returns:
        A configured BaseTool instance

    Example:
        tool = create_agent_runner_tool(
            tool_name="run_discovery_agent",
            agent=discovery_agent,
            description="Run discovery agent",
            orchestrator_memory=shared_store,
            store_keys=["extracted_articles", "pagination_type"]
        )
    """
    # Alias parameters to avoid class attribute name conflicts
    _tool_name = tool_name
    _description = description
    _task_description = task_description
    _agent = agent
    _orchestrator_memory = orchestrator_memory
    _store_keys = store_keys or []

    class AgentRunnerTool(BaseTool):
        name = _tool_name
        description = _description

        def __init__(self) -> None:
            self.agent = _agent
            self.orchestrator_memory = _orchestrator_memory

        @traced_tool(name=_tool_name)
        def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
            """Run the agent with given task. Instrumented by @traced_tool."""
            result = self.agent.run(task, context=context)
            response = _extract_result_info(result)

            # Store specified keys in orchestrator memory
            if self.orchestrator_memory and result.success:
                for key in _store_keys:
                    if result.has(key):
                        self.orchestrator_memory.write(key, result.get(key))

            return response

        def get_parameters_schema(self) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": _task_description},
                    "context": {
                        "type": "object",
                        "description": "Optional context data to pass to the agent",
                    },
                },
                "required": ["task"],
            }

    return AgentRunnerTool()


# Pre-defined tool creators for backward compatibility
def create_discovery_agent_tool(discovery_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Discovery Agent."""
    return create_agent_runner_tool(
        tool_name="run_discovery_agent",
        agent=discovery_agent,
        description="""Run the Discovery Agent to navigate to a URL and extract article links.
    The agent will return results in its AgentResult.""",
        task_description="Task description for the discovery agent",
    )


def create_selector_agent_tool(selector_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Selector Agent."""
    return create_agent_runner_tool(
        tool_name="run_selector_agent",
        agent=selector_agent,
        description="""Run the Selector Agent to find and verify CSS selectors.
    The agent receives context data and returns final selectors.""",
        task_description="Task description for the selector agent",
    )


def create_accessibility_agent_tool(accessibility_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Accessibility Agent."""
    return create_agent_runner_tool(
        tool_name="run_accessibility_agent",
        agent=accessibility_agent,
        description="""Run the Accessibility Agent to check if the site works without JavaScript.
    The agent tests HTTP requests and returns accessibility results.""",
        task_description="Task description for the accessibility agent",
    )


def create_data_prep_agent_tool(data_prep_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Data Preparation Agent."""
    return create_agent_runner_tool(
        tool_name="run_data_prep_agent",
        agent=data_prep_agent,
        description="""Run the Data Prep Agent to create test datasets.
    The agent fetches sample pages and returns test data.""",
        task_description="Task description for the data prep agent",
    )


# Backward-compatible class aliases that use the factory
class RunDiscoveryAgentTool(BaseTool):
    """Run the Discovery Agent to analyze a webpage."""

    name = "run_discovery_agent"
    description = """Run the Discovery Agent to navigate to a URL and extract article links.
    Returns structured data including extracted_articles, pagination_type, and selectors."""

    def __init__(
        self,
        discovery_agent: RunnableAgent,
        orchestrator_memory: "MemoryService | None" = None,
        store_keys: list[str] | None = None,
    ) -> None:
        self.agent = discovery_agent
        self.orchestrator_memory = orchestrator_memory
        self.store_keys = store_keys or []

    @traced_tool(name="run_discovery_agent")
    def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run discovery agent. Instrumented by @traced_tool."""
        result = self.agent.run(task, context=context)
        response = _extract_result_info(result)

        # Store specified keys in orchestrator memory
        if self.orchestrator_memory and result.success:
            for key in self.store_keys:
                if result.has(key):
                    self.orchestrator_memory.write(key, result.get(key))

        return response

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the discovery agent",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context data to pass to the agent",
                },
            },
            "required": ["task"],
        }


class RunSelectorAgentTool(BaseTool):
    """Run the Selector Agent to find CSS selectors."""

    name = "run_selector_agent"
    description = """Run the Selector Agent to find and verify CSS selectors.
    Returns structured data including final_selectors and selector_candidates."""

    def __init__(
        self,
        selector_agent: RunnableAgent,
        orchestrator_memory: "MemoryService | None" = None,
        store_keys: list[str] | None = None,
    ) -> None:
        self.agent = selector_agent
        self.orchestrator_memory = orchestrator_memory
        self.store_keys = store_keys or []

    @traced_tool(name="run_selector_agent")
    def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run selector agent. Instrumented by @traced_tool."""
        result = self.agent.run(task, context=context)
        response = _extract_result_info(result)

        if self.orchestrator_memory and result.success:
            for key in self.store_keys:
                if result.has(key):
                    self.orchestrator_memory.write(key, result.get(key))

        return response

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the selector agent",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context data to pass to the agent",
                },
            },
            "required": ["task"],
        }


class RunAccessibilityAgentTool(BaseTool):
    """Run the Accessibility Agent to check HTTP accessibility."""

    name = "run_accessibility_agent"
    description = """Run the Accessibility Agent to check if the site works without JavaScript.
    Returns structured data including http_accessible flag and test_results."""

    def __init__(
        self,
        accessibility_agent: RunnableAgent,
        orchestrator_memory: "MemoryService | None" = None,
        store_keys: list[str] | None = None,
    ) -> None:
        self.agent = accessibility_agent
        self.orchestrator_memory = orchestrator_memory
        self.store_keys = store_keys or []

    @traced_tool(name="run_accessibility_agent")
    def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run accessibility agent. Instrumented by @traced_tool."""
        result = self.agent.run(task, context=context)
        response = _extract_result_info(result)

        if self.orchestrator_memory and result.success:
            for key in self.store_keys:
                if result.has(key):
                    self.orchestrator_memory.write(key, result.get(key))

        return response

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the accessibility agent",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context data to pass to the agent",
                },
            },
            "required": ["task"],
        }


class RunDataPrepAgentTool(BaseTool):
    """Run the Data Preparation Agent to create test datasets."""

    name = "run_data_prep_agent"
    description = """Run the Data Prep Agent to create test datasets.
    Returns structured data including test_data and sample_pages."""

    def __init__(
        self,
        data_prep_agent: RunnableAgent,
        orchestrator_memory: "MemoryService | None" = None,
        store_keys: list[str] | None = None,
    ) -> None:
        self.agent = data_prep_agent
        self.orchestrator_memory = orchestrator_memory
        self.store_keys = store_keys or []

    @traced_tool(name="run_data_prep_agent")
    def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run data prep agent. Instrumented by @traced_tool."""
        result = self.agent.run(task, context=context)
        response = _extract_result_info(result)

        if self.orchestrator_memory and result.success:
            for key in self.store_keys:
                if result.has(key):
                    self.orchestrator_memory.write(key, result.get(key))

        return response

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the data prep agent",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context data to pass to the agent",
                },
            },
            "required": ["task"],
        }
