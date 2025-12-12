"""OpenAI LLM client wrapper."""
import json
import logging
import time
from typing import Any

from openai import OpenAI

from .config import OpenAIConfig
from .log_config import estimate_cost
from .log_context import get_logger
from .structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)
from ..tools.base import BaseTool

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper for OpenAI API with tool support."""

    def __init__(self, config: OpenAIConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[BaseTool] | None = None,
        tool_choice: str | dict = "auto",
        parallel_tool_calls: bool = False
    ) -> dict[str, Any]:
        """Send chat completion request.

        Args:
            messages: List of message dicts with role/content
            tools: Optional list of BaseTool instances
            tool_choice: "auto", "none", or specific tool
            parallel_tool_calls: If False, force sequential tool execution (one at a time)

        Returns:
            OpenAI response dict
        """
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }

        if tools:
            kwargs["tools"] = [t.to_openai_schema() for t in tools]
            kwargs["tool_choice"] = tool_choice
            # Disable parallel tool calls to ensure sequential execution
            # This is important for browser operations: navigate → wait → getHTML
            kwargs["parallel_tool_calls"] = parallel_tool_calls

        # Get structured logger if available
        slog = get_logger()

        # Log LLM call start
        logger.debug(f"LLM request with {len(messages)} messages")
        if slog:
            slog.info(
                event=LogEvent(
                    category=EventCategory.LLM_INTERACTION,
                    event_type="llm.call.start",
                    name="LLM call started",
                ),
                message=f"LLM call to {self.config.model} with {len(messages)} messages",
                data={
                    "model": self.config.model,
                    "message_count": len(messages),
                    "has_tools": bool(tools),
                    "tool_count": len(tools) if tools else 0,
                    "tool_choice": str(tool_choice),
                },
                tags=["llm", self.config.model, "start"],
            )

        # Make API call with timing
        start_time = time.perf_counter()
        response = self.client.chat.completions.create(**kwargs)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Extract token usage
        tokens_input = response.usage.prompt_tokens if response.usage else 0
        tokens_output = response.usage.completion_tokens if response.usage else 0
        tokens_total = response.usage.total_tokens if response.usage else 0

        # Estimate cost
        cost_usd = estimate_cost(self.config.model, tokens_input, tokens_output)

        # Get finish reason and tool info
        finish_reason = response.choices[0].finish_reason
        tool_called = None
        if response.choices[0].message.tool_calls:
            tool_called = response.choices[0].message.tool_calls[0].function.name

        logger.debug(f"LLM response: {finish_reason}")

        # Log LLM call completion with metrics
        if slog:
            slog.log_llm_call(
                model=self.config.model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                duration_ms=duration_ms,
                estimated_cost_usd=cost_usd,
                finish_reason=finish_reason,
                tool_called=tool_called,
            )

        return self._parse_response(response)

    def _parse_response(self, response) -> dict[str, Any]:
        """Parse OpenAI response into structured dict."""
        choice = response.choices[0]
        message = choice.message

        result = {
            "role": "assistant",
            "content": message.content,
            "finish_reason": choice.finish_reason,
            "tool_calls": None
        }

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
                }
                for tc in message.tool_calls
            ]

        return result
