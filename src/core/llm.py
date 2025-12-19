"""OpenAI-compatible LLM client wrapper with multi-provider support.

This module provides:
- LLMClient: A client that works with any OpenAI-compatible API
- LLMClientFactory: A factory for creating clients per component

Uses the new observability decorators for automatic logging.
The @traced_llm_client decorator handles all LLM call instrumentation.
"""
import json
import logging
from typing import Any

from openai import OpenAI

from ..observability.decorators import traced_llm_client
from ..tools.base import BaseTool
from .component_models import ComponentModelConfig
from .config import OpenAIConfig
from .model_registry import ModelConfig, ModelRegistry

logger = logging.getLogger(__name__)


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

    # Kimi/Moonshot models (pricing per 1K tokens, converted from per 1M)
    # Source: https://platform.moonshot.cn/docs/pricing
    # Using cache miss pricing for input
    "kimi-k2-0905-preview": {"input": 0.0006, "output": 0.0025},
    "kimi-k2-0711-preview": {"input": 0.0006, "output": 0.0025},
    "kimi-k2-turbo-preview": {"input": 0.00115, "output": 0.008},
    "kimi-k2-thinking": {"input": 0.0006, "output": 0.0025},
    "kimi-k2-thinking-turbo": {"input": 0.00115, "output": 0.008},

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
    """OpenAI-compatible LLM client that can connect to multiple providers.

    All providers must support the OpenAI API standard.

    This client supports both the legacy OpenAIConfig and the new ModelConfig,
    allowing for gradual migration.

    Args:
        config: Either OpenAIConfig (legacy) or ModelConfig (new)
        component_name: Optional name for logging/tracking

    Example:
        # Legacy usage
        config = OpenAIConfig.from_env()
        client = LLMClient(config)

        # New usage with ModelConfig
        model_config = registry.get("gpt-5.1")
        client = LLMClient(model_config, component_name="main_agent")
    """

    def __init__(
        self,
        config: OpenAIConfig | ModelConfig,
        component_name: str | None = None,
    ):
        self.component_name = component_name

        # Handle both config types for backward compatibility
        if isinstance(config, ModelConfig):
            self.model_config = config
            self.model = config.model_id
            self.temperature = config.temperature
            self._extra_params = config.extra_params

            # Initialize OpenAI client with provider-specific settings
            client_kwargs: dict[str, Any] = {
                "api_key": config.get_api_key(),
            }

            base_url = config.get_api_base()
            if base_url:
                client_kwargs["base_url"] = base_url

            self.client = OpenAI(**client_kwargs)

            # Store for backward compatibility
            self.config = config  # type: ignore

        else:
            # Legacy OpenAIConfig support
            self.config = config
            self.model = config.model
            self.temperature = config.temperature
            self._extra_params = {}
            self.model_config = None
            self.client = OpenAI(api_key=config.api_key)

    @traced_llm_client(provider="openai")
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[BaseTool] | None = None,
        tool_choice: str | dict = "auto",
        parallel_tool_calls: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send chat completion request.

        Uses OpenAI API standard, compatible with all configured providers.
        Instrumented by @traced_llm_client for automatic logging.
        All LLM call metrics (tokens, cost, duration) are captured automatically.

        Args:
            messages: List of message dicts with role/content
            tools: Optional list of BaseTool instances
            tool_choice: "auto", "none", or specific tool
            parallel_tool_calls: If False, force sequential tool execution
            **kwargs: Additional call-specific parameters that override defaults

        Returns:
            Parsed response dict with role, content, finish_reason, tool_calls
        """
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            **self._extra_params,  # Provider-specific params from config
            **kwargs,  # Call-specific overrides
        }

        # Handle max_tokens if set in config
        if self.model_config and self.model_config.max_tokens:
            request_kwargs["max_tokens"] = self.model_config.max_tokens

        if tools:
            request_kwargs["tools"] = [t.to_openai_schema() for t in tools]
            request_kwargs["tool_choice"] = tool_choice
            request_kwargs["parallel_tool_calls"] = parallel_tool_calls

        # Make API call
        response = self.client.chat.completions.create(**request_kwargs)

        # Parse response
        result = self._parse_response(response)

        # Add metrics to result for decorator to extract
        # Always include model for observability decorator
        result["model"] = self.model

        if response.usage:
            result["tokens_input"] = response.usage.prompt_tokens
            result["tokens_output"] = response.usage.completion_tokens
            result["tokens_total"] = response.usage.total_tokens
            result["estimated_cost_usd"] = estimate_cost(
                self.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

        return result

    def _parse_response(self, response: Any) -> dict[str, Any]:
        """Parse OpenAI response into structured dict."""
        choice = response.choices[0]
        message = choice.message

        result: dict[str, Any] = {
            "role": "assistant",
            "content": message.content,
            "finish_reason": choice.finish_reason,
            "tool_calls": None,
        }

        # Include usage info
        if response.usage:
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # Include actual model used (useful for routing/logging)
        if hasattr(response, "model"):
            result["model"] = response.model

        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError as e:
                    # Some providers may return malformed JSON
                    logger.warning(
                        f"Failed to parse tool arguments for {tc.function.name}: {e}. "
                        f"Raw arguments: {tc.function.arguments[:200]}"
                    )
                    arguments = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": arguments
                })
            result["tool_calls"] = tool_calls

        return result


class LLMClientFactory:
    """Factory for creating LLM clients for specific components.

    Manages the model registry and component assignments, creating
    appropriately configured clients on demand.

    The factory caches clients by component name to avoid creating
    duplicate clients.

    Example:
        factory = LLMClientFactory.from_env()
        main_llm = factory.get_client("main_agent")
        discovery_llm = factory.get_client("discovery_agent")
    """

    def __init__(
        self,
        registry: ModelRegistry,
        component_config: ComponentModelConfig,
    ):
        """Initialize the factory.

        Args:
            registry: ModelRegistry with available model configurations
            component_config: ComponentModelConfig with component-to-model mappings
        """
        self.registry = registry
        self.component_config = component_config
        self._clients: dict[str, LLMClient] = {}

        # Validate that all assigned models exist in registry
        self._validate_assignments()

    def _validate_assignments(self) -> None:
        """Validate that all component model assignments exist in registry."""
        models_in_use = self.component_config.get_models_in_use()
        available_models = set(self.registry.list_models())

        missing = models_in_use - available_models
        if missing:
            logger.warning(
                f"Some assigned models are not in registry: {missing}. "
                f"Available models: {sorted(available_models)}"
            )

    def get_client(self, component_name: str) -> LLMClient:
        """Get or create an LLM client for a specific component.

        Clients are cached by component name.

        Args:
            component_name: Name of the agent or tool

        Returns:
            Configured LLMClient instance

        Example:
            llm = factory.get_client("main_agent")
            response = llm.chat(messages)
        """
        if component_name not in self._clients:
            model_id = self.component_config.get_model_for_component(component_name)
            model_config = self.registry.get(model_id)

            self._clients[component_name] = LLMClient(
                config=model_config,
                component_name=component_name,
            )

            logger.debug(
                f"Created LLM client for '{component_name}' using model '{model_id}'"
            )

        return self._clients[component_name]

    def get_client_for_model(
        self,
        model_id: str,
        component_name: str | None = None
    ) -> LLMClient:
        """Get client for a specific model (bypassing component mapping).

        Useful for tools that need to create isolated LLM contexts or
        when you need to use a specific model regardless of configuration.

        Note: These clients are NOT cached by the factory.

        Args:
            model_id: The model to use
            component_name: Optional name for logging

        Returns:
            A new LLMClient configured for the specified model
        """
        model_config = self.registry.get(model_id)
        return LLMClient(
            config=model_config,
            component_name=component_name,
        )

    def get_default_client(self) -> LLMClient:
        """Get a client using the global default model.

        Returns:
            LLMClient configured with the default model
        """
        return self.get_client("main_agent")

    def list_components(self) -> list[str]:
        """List all configurable component names.

        Returns:
            List of component names
        """
        return self.component_config.list_components()

    def get_component_model(self, component_name: str) -> str:
        """Get the model ID assigned to a component.

        Args:
            component_name: The component to look up

        Returns:
            Model ID string
        """
        return self.component_config.get_model_for_component(component_name)

    @classmethod
    def from_env(cls) -> "LLMClientFactory":
        """Create factory with environment-based configuration.

        Loads the default model registry and component configuration
        from environment variables.

        Returns:
            Configured LLMClientFactory

        Example:
            factory = LLMClientFactory.from_env()
            llm = factory.get_client("main_agent")
        """
        from .default_models import get_default_registry

        registry = get_default_registry()
        component_config = ComponentModelConfig.from_env()

        logger.info(
            f"Created LLMClientFactory with {len(registry)} models, "
            f"{len(component_config.get_models_in_use())} unique models in use"
        )

        return cls(registry, component_config)

    def __repr__(self) -> str:
        return (
            f"LLMClientFactory("
            f"models={len(self.registry)}, "
            f"cached_clients={len(self._clients)})"
        )
