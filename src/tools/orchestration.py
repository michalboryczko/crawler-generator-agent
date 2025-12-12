"""Orchestration tools for coordinating agents."""
import logging
import time
from typing import Any

from .base import BaseTool
from ..core.log_context import get_logger
from ..core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)

logger = logging.getLogger(__name__)


class RunBrowserAgentTool(BaseTool):
    """Run the Browser Agent to analyze a webpage."""

    name = "run_browser_agent"
    description = """Run the Browser Agent to navigate to a URL and extract article links.
    The agent will store results in shared memory."""

    def __init__(self, browser_agent):
        self.browser_agent = browser_agent

    def execute(self, task: str) -> dict[str, Any]:
        slog = get_logger()
        start_time = time.perf_counter()

        # Log sub-agent invocation start
        if slog:
            slog.info(
                event=LogEvent(
                    category=EventCategory.AGENT_LIFECYCLE,
                    event_type="agent.subagent.start",
                    name="Browser agent started",
                ),
                message=f"Starting browser agent: {task[:100]}...",
                data={"agent_type": "BrowserAgent", "task_preview": task[:200]},
                tags=["agent", "subagent", "browser", "start"],
            )

        try:
            result = self.browser_agent.run(task)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log sub-agent completion
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.complete",
                        name="Browser agent completed",
                    ),
                    message=f"Browser agent completed: success={result['success']}, iterations={result.get('iterations', 0)}",
                    data={
                        "agent_type": "BrowserAgent",
                        "success": result["success"],
                        "iterations": result.get("iterations", 0),
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "browser", "complete"],
                )

            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.error",
                        name="Browser agent failed",
                    ),
                    message=f"Browser agent failed: {e}",
                    data={"agent_type": "BrowserAgent", "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "browser", "error"],
                )

            return {"success": False, "error": str(e)}

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
    """Run the Selector Agent to find CSS selectors."""

    name = "run_selector_agent"
    description = """Run the Selector Agent to find and verify CSS selectors.
    The agent reads extracted articles from memory and stores final selectors."""

    def __init__(self, selector_agent):
        self.selector_agent = selector_agent

    def execute(self, task: str) -> dict[str, Any]:
        slog = get_logger()
        start_time = time.perf_counter()

        # Log sub-agent invocation start
        if slog:
            slog.info(
                event=LogEvent(
                    category=EventCategory.AGENT_LIFECYCLE,
                    event_type="agent.subagent.start",
                    name="Selector agent started",
                ),
                message=f"Starting selector agent: {task[:100]}...",
                data={"agent_type": "SelectorAgent", "task_preview": task[:200]},
                tags=["agent", "subagent", "selector", "start"],
            )

        try:
            result = self.selector_agent.run(task)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log sub-agent completion
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.complete",
                        name="Selector agent completed",
                    ),
                    message=f"Selector agent completed: success={result['success']}, iterations={result.get('iterations', 0)}",
                    data={
                        "agent_type": "SelectorAgent",
                        "success": result["success"],
                        "iterations": result.get("iterations", 0),
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "selector", "complete"],
                )

            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.error",
                        name="Selector agent failed",
                    ),
                    message=f"Selector agent failed: {e}",
                    data={"agent_type": "SelectorAgent", "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "selector", "error"],
                )

            return {"success": False, "error": str(e)}

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
    """Run the Accessibility Agent to check HTTP accessibility."""

    name = "run_accessibility_agent"
    description = """Run the Accessibility Agent to check if the site works without JavaScript.
    The agent tests HTTP requests and stores results in memory."""

    def __init__(self, accessibility_agent):
        self.accessibility_agent = accessibility_agent

    def execute(self, task: str) -> dict[str, Any]:
        slog = get_logger()
        start_time = time.perf_counter()

        # Log sub-agent invocation start
        if slog:
            slog.info(
                event=LogEvent(
                    category=EventCategory.AGENT_LIFECYCLE,
                    event_type="agent.subagent.start",
                    name="Accessibility agent started",
                ),
                message=f"Starting accessibility agent: {task[:100]}...",
                data={"agent_type": "AccessibilityAgent", "task_preview": task[:200]},
                tags=["agent", "subagent", "accessibility", "start"],
            )

        try:
            result = self.accessibility_agent.run(task)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log sub-agent completion
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.complete",
                        name="Accessibility agent completed",
                    ),
                    message=f"Accessibility agent completed: success={result['success']}, iterations={result.get('iterations', 0)}",
                    data={
                        "agent_type": "AccessibilityAgent",
                        "success": result["success"],
                        "iterations": result.get("iterations", 0),
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "accessibility", "complete"],
                )

            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.error",
                        name="Accessibility agent failed",
                    ),
                    message=f"Accessibility agent failed: {e}",
                    data={"agent_type": "AccessibilityAgent", "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "accessibility", "error"],
                )

            return {"success": False, "error": str(e)}

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
    """Run the Data Preparation Agent to create test datasets."""

    name = "run_data_prep_agent"
    description = """Run the Data Prep Agent to create test datasets.
    The agent fetches sample pages using browser and stores test data in memory."""

    def __init__(self, data_prep_agent):
        self.data_prep_agent = data_prep_agent

    def execute(self, task: str) -> dict[str, Any]:
        slog = get_logger()
        start_time = time.perf_counter()

        # Log sub-agent invocation start
        if slog:
            slog.info(
                event=LogEvent(
                    category=EventCategory.AGENT_LIFECYCLE,
                    event_type="agent.subagent.start",
                    name="Data prep agent started",
                ),
                message=f"Starting data prep agent: {task[:100]}...",
                data={"agent_type": "DataPrepAgent", "task_preview": task[:200]},
                tags=["agent", "subagent", "data_prep", "start"],
            )

        try:
            logger.info(f"=== STARTING DATA PREP AGENT ===")
            logger.info(f"Task: {task[:200]}...")
            result = self.data_prep_agent.run(task)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"=== DATA PREP AGENT FINISHED ===")
            logger.info(f"Success: {result['success']}, Iterations: {result.get('iterations', 0)}")

            # Log sub-agent completion
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.complete",
                        name="Data prep agent completed",
                    ),
                    message=f"Data prep agent completed: success={result['success']}, iterations={result.get('iterations', 0)}",
                    data={
                        "agent_type": "DataPrepAgent",
                        "success": result["success"],
                        "iterations": result.get("iterations", 0),
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "data_prep", "complete"],
                )

            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"=== DATA PREP AGENT FAILED: {e} ===")

            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.subagent.error",
                        name="Data prep agent failed",
                    ),
                    message=f"Data prep agent failed: {e}",
                    data={"agent_type": "DataPrepAgent", "error": str(e)},
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["agent", "subagent", "data_prep", "error"],
                )

            return {"success": False, "error": str(e)}

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
