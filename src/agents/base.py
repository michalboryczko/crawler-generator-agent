"""Base agent class with reasoning loop."""
import logging
from typing import Any

from ..core.llm import LLMClient
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 20


class BaseAgent:
    """Base agent with thought→action→observation loop."""

    name: str = "base_agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, llm: LLMClient, tools: list[BaseTool] | None = None):
        self.llm = llm
        self.tools = tools or []
        self._tool_map = {t.name: t for t in self.tools}

    def run(self, task: str) -> dict[str, Any]:
        """Execute agent task with tool loop.

        Args:
            task: The task description to complete

        Returns:
            dict with 'success', 'result', and 'history'
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task}
        ]

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"Agent {self.name} iteration {iteration + 1}")

            response = self.llm.chat(messages, tools=self.tools if self.tools else None)

            if response["tool_calls"]:
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response["content"],
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": str(tc["arguments"])
                            }
                        }
                        for tc in response["tool_calls"]
                    ]
                })

                # Execute each tool call
                for tool_call in response["tool_calls"]:
                    result = self._execute_tool(tool_call["name"], tool_call["arguments"])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": str(result)
                    })
            else:
                # No tool calls - agent is done
                return {
                    "success": True,
                    "result": response["content"],
                    "history": messages,
                    "iterations": iteration + 1
                }

        # Max iterations reached
        return {
            "success": False,
            "error": f"Max iterations ({MAX_ITERATIONS}) reached",
            "history": messages,
            "iterations": MAX_ITERATIONS
        }

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name with arguments."""
        if name not in self._tool_map:
            return {"success": False, "error": f"Unknown tool: {name}"}

        tool = self._tool_map[name]
        try:
            logger.debug(f"Executing tool {name} with {arguments}")
            result = tool.execute(**arguments)
            logger.debug(f"Tool {name} result: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"success": False, "error": str(e)}
