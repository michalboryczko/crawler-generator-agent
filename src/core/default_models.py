"""Default model configurations for multi-provider LLM support.

This module defines the default model registry with configurations for
various LLM providers. All providers use OpenAI-compatible API endpoints.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model_registry import ModelRegistry


# Default model configurations for common providers
DEFAULT_MODELS: list[dict] = [
    # ==========================================================================
    # OpenAI GPT-5 Series
    # ==========================================================================
    {
        "model_id": "gpt-5.2",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,  # Uses OpenAI default
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-5.1",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-5",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-5-mini",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-5-nano",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-5.2-pro",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-5-pro",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    # ==========================================================================
    # Anthropic Models (via OpenAI-compatible endpoint or proxy)
    # ==========================================================================
    {
        "model_id": "claude-4-5-sonnet",
        "api_key_env": "ANTHROPIC_KEY",
        "api_base_url": "https://api.anthropic.com/v1",
        "temperature": 0.0,
    },
    # ==========================================================================
    # Kimi (Moonshot AI) - OpenAI-compatible
    # https://platform.moonshot.ai/docs/guide/start-using-kimi-api
    # ==========================================================================
    {
        "model_id": "kimi-k2-0905-preview",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.ai/v1",
        "temperature": 0.0,
        "max_tokens": 262144,
    },
    {
        "model_id": "kimi-k2-0711-preview",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.ai/v1",
        "temperature": 0.0,
        "max_tokens": 131072,
    },
    {
        "model_id": "kimi-k2-turbo-preview",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.ai/v1",
        "temperature": 0.0,
        "max_tokens": 262144,
    },
    {
        "model_id": "kimi-k2-thinking",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.ai/v1",
        "temperature": 0.0,
        "max_tokens": 262144,
    },
    {
        "model_id": "kimi-k2-thinking-turbo",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.ai/v1",
        "temperature": 0.0,
        "max_tokens": 262144,
    },
    # ==========================================================================
    # Local/Self-hosted Models (vLLM, Ollama, etc.)
    # ==========================================================================
    {
        "model_id": "local-llama-3-70b",
        "api_key_env": "LOCAL_LLM_KEY",
        "api_base_url": "http://localhost:8000/v1",
        "temperature": 0.0,
    },
    # ==========================================================================
    # Google (via OpenAI-compatible proxy or Vertex AI)
    # ==========================================================================
    {
        "model_id": "gemini-2.5-pro",
        "api_key_env": "GOOGLE_API_KEY",
        "api_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "temperature": 0.0,
    },
]


def get_default_registry() -> "ModelRegistry":
    """Create registry with default model configurations.

    Returns:
        A ModelRegistry populated with all default model configurations

    Example:
        registry = get_default_registry()
        config = registry.get("gpt-4o")
    """
    from .model_registry import ModelRegistry

    return ModelRegistry.from_config(DEFAULT_MODELS)


def add_custom_model(
    model_id: str,
    api_key_env: str,
    api_base_url: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    extra_params: dict | None = None,
) -> dict:
    """Create a model configuration dictionary for a custom model.

    Use this to add models not in the default list.

    Args:
        model_id: Unique identifier for the model
        api_key_env: Environment variable name containing API key
        api_base_url: Optional base URL for the API
        temperature: Default temperature
        max_tokens: Optional token limit
        extra_params: Provider-specific parameters

    Returns:
        Model configuration dictionary

    Example:
        custom = add_custom_model(
            model_id="my-fine-tuned-gpt4",
            api_key_env="OPENAI_KEY",
            temperature=0.7
        )
        DEFAULT_MODELS.append(custom)
    """
    return {
        "model_id": model_id,
        "api_key_env": api_key_env,
        "api_base_url": api_base_url,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "extra_params": extra_params or {},
    }
