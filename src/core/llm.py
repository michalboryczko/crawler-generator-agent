"""OpenAI LLM client wrapper."""
import json
import logging
from typing import Any

from openai import OpenAI

from .config import OpenAIConfig
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
        tool_choice: str | dict = "auto"
    ) -> dict[str, Any]:
        """Send chat completion request.

        Args:
            messages: List of message dicts with role/content
            tools: Optional list of BaseTool instances
            tool_choice: "auto", "none", or specific tool

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

        logger.debug(f"LLM request with {len(messages)} messages")
        response = self.client.chat.completions.create(**kwargs)
        logger.debug(f"LLM response: {response.choices[0].finish_reason}")

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
