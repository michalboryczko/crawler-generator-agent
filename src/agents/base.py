"""Base agent class with reasoning loop.

This module uses the new observability decorators for automatic logging.
The @traced_agent decorator handles all agent instrumentation.
"""
import logging
from typing import Any

from ..core.llm import LLMClient
from ..observability.decorators import traced_agent
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 100


class BaseAgent:
    """Base agent with thought→action→observation loop."""

    name: str = "base_agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, llm: LLMClient, tools: list[BaseTool] | None = None):
        self.llm = llm
        self.tools = tools or []
        self._tool_map = {t.name: t for t in self.tools}

    @traced_agent(name="base_agent")
    def run(self, task: str) -> dict[str, Any]:
        """Execute agent task with tool loop.

        Instrumented by @traced_agent - logs agent lifecycle, iterations, and results.

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
                # IMPORTANT: Only process ONE tool call at a time to ensure sequential execution
                # Even if model returns multiple tool calls, we only execute the first one
                # This forces navigate→wait→getHTML sequence instead of batching
                tool_calls_to_process = response["tool_calls"][:1]  # Only first tool call

                if len(response["tool_calls"]) > 1:
                    logger.warning(
                        f"Model returned {len(response['tool_calls'])} tool calls, "
                        f"but only processing first one to ensure sequential execution"
                    )

                # Add assistant message with only the tool call we're processing
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
                        for tc in tool_calls_to_process
                    ]
                })

                # Execute the single tool call
                for tool_call in tool_calls_to_process:
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
        """Execute a tool by name with arguments.

        Tool execution is instrumented by the tool's own @traced_tool decorator.
        """
        if name not in self._tool_map:
            return {"success": False, "error": f"Unknown tool: {name}"}

        tool = self._tool_map[name]
        try:
            arg_summary = str(arguments)[:200] + "..." if len(str(arguments)) > 200 else str(arguments)
            logger.info(f"[{self.name}] Executing tool: {name} with args: {arg_summary}")

            result = tool.execute(**arguments)

            result_summary = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
            logger.info(f"[{self.name}] Tool {name} completed: {result_summary}")

            return result
        except Exception as e:
            logger.error(f"[{self.name}] Tool {name} failed: {e}")
            return {"success": False, "error": str(e)}
