"""Base agent class with reasoning loop."""
import logging
import time
from typing import Any

from ..core.llm import LLMClient
from ..core.log_context import get_logger, span
from ..core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)
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

        # Get structured logger and create agent span
        slog = get_logger()
        start_time = time.perf_counter()

        # Log agent start
        if slog:
            slog.log_agent_lifecycle(
                agent_name=self.name,
                event_type="agent.start",
                message=f"Agent {self.name} started with task: {task[:100]}...",
            )

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"Agent {self.name} iteration {iteration + 1}")

            # Log iteration
            if slog:
                slog.debug(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.iteration",
                        name=f"{self.name} iteration",
                    ),
                    message=f"Agent {self.name} iteration {iteration + 1}",
                    data={"iteration": iteration + 1, "max_iterations": MAX_ITERATIONS},
                    tags=["agent", self.name, "iteration"],
                )

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
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Log agent completion
                if slog:
                    slog.log_agent_lifecycle(
                        agent_name=self.name,
                        event_type="agent.complete",
                        message=f"Agent {self.name} completed successfully after {iteration + 1} iterations",
                        duration_ms=duration_ms,
                        iterations=iteration + 1,
                        success=True,
                    )

                return {
                    "success": True,
                    "result": response["content"],
                    "history": messages,
                    "iterations": iteration + 1
                }

        # Max iterations reached
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log max iterations reached
        if slog:
            slog.log_agent_lifecycle(
                agent_name=self.name,
                event_type="agent.error",
                message=f"Agent {self.name} reached max iterations ({MAX_ITERATIONS})",
                duration_ms=duration_ms,
                iterations=MAX_ITERATIONS,
                success=False,
            )

        return {
            "success": False,
            "error": f"Max iterations ({MAX_ITERATIONS}) reached",
            "history": messages,
            "iterations": MAX_ITERATIONS
        }

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name with arguments."""
        slog = get_logger()

        if name not in self._tool_map:
            # Log unknown tool error
            if slog:
                slog.log_tool_execution(
                    tool_name=name,
                    success=False,
                    duration_ms=0,
                    error=f"Unknown tool: {name}",
                )
            return {"success": False, "error": f"Unknown tool: {name}"}

        tool = self._tool_map[name]
        try:
            # Log at INFO level so tool calls are visible
            arg_summary = str(arguments)[:200] + "..." if len(str(arguments)) > 200 else str(arguments)
            logger.info(f"[{self.name}] Executing tool: {name} with args: {arg_summary}")

            # Log tool start
            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.execute.start",
                        name=f"{name} started",
                    ),
                    message=f"Tool {name} execution started",
                    data={"tool_name": name, "input_preview": arg_summary},
                    tags=["tool", name, "start"],
                )

            # Execute with timing
            start_time = time.perf_counter()
            result = tool.execute(**arguments)
            duration_ms = (time.perf_counter() - start_time) * 1000

            result_summary = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
            logger.info(f"[{self.name}] Tool {name} completed: {result_summary}")

            # Log tool completion
            if slog:
                slog.log_tool_execution(
                    tool_name=name,
                    success=True,
                    duration_ms=duration_ms,
                    input_preview=arg_summary,
                    output_preview=result_summary,
                )

            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000 if 'start_time' in locals() else 0
            logger.error(f"[{self.name}] Tool {name} failed: {e}")

            # Log tool failure
            if slog:
                slog.log_tool_execution(
                    tool_name=name,
                    success=False,
                    duration_ms=duration_ms,
                    input_preview=arg_summary if 'arg_summary' in locals() else None,
                    error=str(e),
                )

            return {"success": False, "error": str(e)}
