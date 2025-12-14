"""OpenAI LLM client wrapper.

This module uses the new observability decorators for automatic logging.
The @traced_llm_client decorator handles all LLM call instrumentation.
"""
import json
from typing import Any

from openai import OpenAI

from .config import OpenAIConfig
from ..tools.base import BaseTool
from ..observability.decorators import traced_llm_client


# LLM cost lookup table (per 1K tokens)
# Used for cost estimation in metrics
# Updated: December 2025, Standard tier pricing
# Source: https://platform.openai.com/docs/pricing
MODEL_COSTS: dict[str, dict[str, float]] = {
    # OpenAI GPT-5 Series
    "gpt-5.2": {"input": 0.00175, "output": 0.014},
    "gpt-5.1": {"input": 0.00125, "output": 0.01},
    "gpt-5": {"input": 0.00125, "output": 0.01},
    "gpt-5-mini": {"input": 0.00025, "output": 0.002},
    "gpt-5-nano": {"input": 0.00005, "output": 0.0004},
    "gpt-5.2-pro": {"input": 0.021, "output": 0.168},
    "gpt-5-pro": {"input": 0.015, "output": 0.12},

    # OpenAI GPT-4.1 Series
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},

    # OpenAI GPT-4o Series
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-2024-05-13": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},

    # OpenAI o-Series (Reasoning)
    "o1": {"input": 0.015, "output": 0.06},
    "o1-pro": {"input": 0.15, "output": 0.6},
    "o1-mini": {"input": 0.0011, "output": 0.0044},
    "o3": {"input": 0.002, "output": 0.008},
    "o3-pro": {"input": 0.02, "output": 0.08},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
    "o4-mini": {"input": 0.0011, "output": 0.0044},

    # OpenAI Legacy Models
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-32k": {"input": 0.06, "output": 0.12},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},

    # Anthropic models
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},

    # Embeddings
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}


def estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    """Estimate API cost for an LLM call.

    Args:
        model: Model name (e.g., "gpt-4o", "gpt-4o-mini")
        tokens_input: Number of input tokens
        tokens_output: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    costs = MODEL_COSTS.get(model, {"input": 0, "output": 0})
    return (
        (tokens_input / 1000) * costs["input"] +
        (tokens_output / 1000) * costs["output"]
    )


class LLMClient:
    """Wrapper for OpenAI API with tool support."""

    def __init__(self, config: OpenAIConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key)

    @traced_llm_client(provider="openai")
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[BaseTool] | None = None,
        tool_choice: str | dict = "auto",
        parallel_tool_calls: bool = False,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Send chat completion request.

        Instrumented by @traced_llm_client for automatic logging.
        All LLM call metrics (tokens, cost, duration) are captured automatically.

        Args:
            messages: List of message dicts with role/content
            tools: Optional list of BaseTool instances
            tool_choice: "auto", "none", or specific tool
            parallel_tool_calls: If False, force sequential tool execution
            model: Optional model override (for decorator metrics extraction)

        Returns:
            OpenAI response dict with token metrics for decorator extraction
        """
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }

        if tools:
            kwargs["tools"] = [t.to_openai_schema() for t in tools]
            kwargs["tool_choice"] = tool_choice
            kwargs["parallel_tool_calls"] = parallel_tool_calls

        # Make API call
        response = self.client.chat.completions.create(**kwargs)

        # Parse response
        result = self._parse_response(response)

        # Add metrics to result for decorator to extract
        if response.usage:
            result["tokens_input"] = response.usage.prompt_tokens
            result["tokens_output"] = response.usage.completion_tokens
            result["tokens_total"] = response.usage.total_tokens
            result["estimated_cost_usd"] = estimate_cost(
                self.config.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        return result

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
