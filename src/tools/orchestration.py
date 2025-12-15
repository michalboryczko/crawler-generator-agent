"""Orchestration tools for coordinating agents.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.
"""
from typing import Any, Protocol

from ..observability.decorators import traced_tool
from .base import BaseTool


class RunnableAgent(Protocol):
    """Protocol for agents that can be run with a task."""

    def run(self, task: str) -> dict[str, Any]: ...


def create_agent_runner_tool(
    tool_name: str,
    agent: RunnableAgent,
    description: str,
    task_description: str = "Task description for the agent"
) -> BaseTool:
    """Factory function to create agent runner tools.

    Reduces boilerplate by generating tools with consistent structure.

    Args:
        tool_name: Name of the tool (e.g., "run_browser_agent")
        agent: The agent instance to run
        description: Tool description for LLM
        task_description: Description for the task parameter

    Returns:
        A configured BaseTool instance
    """

    class AgentRunnerTool(BaseTool):
        name = tool_name
        description = description

        def __init__(self) -> None:
            self.agent = agent

        @traced_tool(name=tool_name)
        def execute(self, task: str) -> dict[str, Any]:
            """Run the agent with given task. Instrumented by @traced_tool."""
            result = self.agent.run(task)
            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }

        def get_parameters_schema(self) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": task_description
                    }
                },
                "required": ["task"]
            }

    return AgentRunnerTool()


# Pre-defined tool creators for backward compatibility
def create_browser_agent_tool(browser_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Browser Agent."""
    return create_agent_runner_tool(
        tool_name="run_browser_agent",
        agent=browser_agent,
        description="""Run the Browser Agent to navigate to a URL and extract article links.
    The agent will store results in shared memory.""",
        task_description="Task description for the browser agent"
    )


def create_selector_agent_tool(selector_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Selector Agent."""
    return create_agent_runner_tool(
        tool_name="run_selector_agent",
        agent=selector_agent,
        description="""Run the Selector Agent to find and verify CSS selectors.
    The agent reads extracted articles from memory and stores final selectors.""",
        task_description="Task description for the selector agent"
    )


def create_accessibility_agent_tool(accessibility_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Accessibility Agent."""
    return create_agent_runner_tool(
        tool_name="run_accessibility_agent",
        agent=accessibility_agent,
        description="""Run the Accessibility Agent to check if the site works without JavaScript.
    The agent tests HTTP requests and stores results in memory.""",
        task_description="Task description for the accessibility agent"
    )


def create_data_prep_agent_tool(data_prep_agent: RunnableAgent) -> BaseTool:
    """Create a tool to run the Data Preparation Agent."""
    return create_agent_runner_tool(
        tool_name="run_data_prep_agent",
        agent=data_prep_agent,
        description="""Run the Data Prep Agent to create test datasets.
    The agent fetches sample pages using browser and stores test data in memory.""",
        task_description="Task description for the data prep agent"
    )


# Backward-compatible class aliases that use the factory
class RunBrowserAgentTool(BaseTool):
    """Run the Browser Agent to analyze a webpage.

    Note: Consider using create_browser_agent_tool() instead for new code.
    """

    name = "run_browser_agent"
    description = """Run the Browser Agent to navigate to a URL and extract article links.
    The agent will store results in shared memory."""

    def __init__(self, browser_agent: RunnableAgent) -> None:
        self.agent = browser_agent

    @traced_tool(name="run_browser_agent")
    def execute(self, task: str) -> dict[str, Any]:
        """Run browser agent. Instrumented by @traced_tool."""
        result = self.agent.run(task)
        return {
            "success": result["success"],
            "result": result.get("result", result.get("error")),
            "iterations": result.get("iterations", 0)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the browser agent"
                }
            },
            "required": ["task"]
        }


class RunSelectorAgentTool(BaseTool):
    """Run the Selector Agent to find CSS selectors.

    Note: Consider using create_selector_agent_tool() instead for new code.
    """

    name = "run_selector_agent"
    description = """Run the Selector Agent to find and verify CSS selectors.
    The agent reads extracted articles from memory and stores final selectors."""

    def __init__(self, selector_agent: RunnableAgent) -> None:
        self.agent = selector_agent

    @traced_tool(name="run_selector_agent")
    def execute(self, task: str) -> dict[str, Any]:
        """Run selector agent. Instrumented by @traced_tool."""
        result = self.agent.run(task)
        return {
            "success": result["success"],
            "result": result.get("result", result.get("error")),
            "iterations": result.get("iterations", 0)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the selector agent"
                }
            },
            "required": ["task"]
        }


class RunAccessibilityAgentTool(BaseTool):
    """Run the Accessibility Agent to check HTTP accessibility.

    Note: Consider using create_accessibility_agent_tool() instead for new code.
    """

    name = "run_accessibility_agent"
    description = """Run the Accessibility Agent to check if the site works without JavaScript.
    The agent tests HTTP requests and stores results in memory."""

    def __init__(self, accessibility_agent: RunnableAgent) -> None:
        self.agent = accessibility_agent

    @traced_tool(name="run_accessibility_agent")
    def execute(self, task: str) -> dict[str, Any]:
        """Run accessibility agent. Instrumented by @traced_tool."""
        result = self.agent.run(task)
        return {
            "success": result["success"],
            "result": result.get("result", result.get("error")),
            "iterations": result.get("iterations", 0)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the accessibility agent"
                }
            },
            "required": ["task"]
        }


class RunDataPrepAgentTool(BaseTool):
    """Run the Data Preparation Agent to create test datasets.

    Note: Consider using create_data_prep_agent_tool() instead for new code.
    """

    name = "run_data_prep_agent"
    description = """Run the Data Prep Agent to create test datasets.
    The agent fetches sample pages using browser and stores test data in memory."""

    def __init__(self, data_prep_agent: RunnableAgent) -> None:
        self.agent = data_prep_agent

    @traced_tool(name="run_data_prep_agent")
    def execute(self, task: str) -> dict[str, Any]:
        """Run data prep agent. Instrumented by @traced_tool."""
        result = self.agent.run(task)
        return {
            "success": result["success"],
            "result": result.get("result", result.get("error")),
            "iterations": result.get("iterations", 0)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description for the data prep agent"
                }
            },
            "required": ["task"]
        }
