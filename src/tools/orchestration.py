"""Orchestration tools for coordinating agents."""
import logging
from typing import Any

from .base import BaseTool

logger = logging.getLogger(__name__)


class RunBrowserAgentTool(BaseTool):
    """Run the Browser Agent to analyze a webpage."""

    name = "run_browser_agent"
    description = """Run the Browser Agent to navigate to a URL and extract article links.
    The agent will store results in shared memory."""

    def __init__(self, browser_agent):
        self.browser_agent = browser_agent

    def execute(self, task: str) -> dict[str, Any]:
        try:
            result = self.browser_agent.run(task)
            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
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
        try:
            result = self.selector_agent.run(task)
            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
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
        try:
            result = self.accessibility_agent.run(task)
            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
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
        try:
            logger.info(f"=== STARTING DATA PREP AGENT ===")
            logger.info(f"Task: {task[:200]}...")
            result = self.data_prep_agent.run(task)
            logger.info(f"=== DATA PREP AGENT FINISHED ===")
            logger.info(f"Success: {result['success']}, Iterations: {result.get('iterations', 0)}")
            return {
                "success": result["success"],
                "result": result.get("result", result.get("error")),
                "iterations": result.get("iterations", 0)
            }
        except Exception as e:
            logger.error(f"=== DATA PREP AGENT FAILED: {e} ===")
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
