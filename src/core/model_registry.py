"""Model registry for multi-provider LLM configuration.

This module provides a central registry for defining available models and their
connection details. Each model configuration includes API key environment variable,
base URL, and provider-specific parameters.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model.

    Attributes:
        model_id: Unique identifier (e.g., "gpt-4o", "claude-3-opus")
        api_key_env: Environment variable name for API key (e.g., "OPENAI_KEY")
        api_base_url: Base URL (None = provider default)
        temperature: Default temperature for this model
        max_tokens: Optional max tokens limit
        extra_params: Provider-specific parameters (e.g., reasoning_effort for o1)
    """

    model_id: str
    api_key_env: str
    api_base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    def get_api_key(self) -> str:
        """Resolve API key from environment variable.

        For OpenAI, also checks OPENAI_API_KEY as fallback for backward compatibility.

        Returns:
            The API key string

        Raises:
            ValueError: If the environment variable is not set
        """
        key = os.getenv(self.api_key_env)

        # Fallback for OpenAI: also check OPENAI_API_KEY
        if not key and self.api_key_env == "OPENAI_KEY":
            key = os.getenv("OPENAI_API_KEY")

        if not key:
            hint = ""
            if self.api_key_env == "OPENAI_KEY":
                hint = " (or OPENAI_API_KEY)"
            raise ValueError(
                f"API key not found. Set environment variable: {self.api_key_env}{hint}"
            )
        return key

    def get_api_base(self) -> str | None:
        """Get API base URL, checking for override env var.

        Allows runtime override via {MODEL_ID}_API_BASE environment variable.
        For example, GPT_4O_API_BASE can override gpt-4o's base URL.

        Returns:
            The base URL or None for provider default
        """
        # Allow override via {MODEL_ID}_API_BASE env var
        override_env = f"{self.model_id.upper().replace('-', '_')}_API_BASE"
        return os.getenv(override_env, self.api_base_url)

    def __repr__(self) -> str:
        return (
            f"ModelConfig(model_id={self.model_id!r}, "
            f"api_key_env={self.api_key_env!r}, "
            f"api_base_url={self.api_base_url!r})"
        )


@dataclass
class ModelRegistry:
    """Registry of all available models.

    The registry maintains a mapping of model IDs to their configurations.
    Models must be registered before they can be used by components.

    Example:
        registry = ModelRegistry()
        registry.register(ModelConfig(
            model_id="gpt-4o",
            api_key_env="OPENAI_KEY"
        ))
        config = registry.get("gpt-4o")
    """

    models: dict[str, ModelConfig] = field(default_factory=dict)

    def register(self, config: ModelConfig) -> None:
        """Register a model configuration.

        Args:
            config: The ModelConfig to register
        """
        if config.model_id in self.models:
            logger.warning(f"Overwriting existing model configuration: {config.model_id}")
        self.models[config.model_id] = config
        logger.debug(f"Registered model: {config.model_id}")

    def get(self, model_id: str) -> ModelConfig:
        """Get configuration for a model.

        Args:
            model_id: The unique model identifier

        Returns:
            The ModelConfig for the specified model

        Raises:
            ValueError: If the model is not registered
        """
        if model_id not in self.models:
            available = ", ".join(sorted(self.models.keys()))
            raise ValueError(f"Unknown model: {model_id}. Available models: [{available}]")
        return self.models[model_id]

    def list_models(self) -> list[str]:
        """List all registered model IDs.

        Returns:
            Sorted list of model identifiers
        """
        return sorted(self.models.keys())

    def has_model(self, model_id: str) -> bool:
        """Check if a model is registered.

        Args:
            model_id: The model identifier to check

        Returns:
            True if the model is registered
        """
        return model_id in self.models

    @classmethod
    def from_config(cls, config_data: list[dict[str, Any]]) -> "ModelRegistry":
        """Create registry from configuration data.

        Args:
            config_data: List of model configuration dictionaries

        Returns:
            A new ModelRegistry with all models registered

        Example:
            registry = ModelRegistry.from_config([
                {"model_id": "gpt-4o", "api_key_env": "OPENAI_KEY"},
                {"model_id": "gpt-4o-mini", "api_key_env": "OPENAI_KEY"},
            ])
        """
        registry = cls()
        for item in config_data:
            config = ModelConfig(
                model_id=item["model_id"],
                api_key_env=item["api_key_env"],
                api_base_url=item.get("api_base_url"),
                temperature=item.get("temperature", 0.0),
                max_tokens=item.get("max_tokens"),
                extra_params=item.get("extra_params", {}),
            )
            registry.register(config)
        return registry

    def __len__(self) -> int:
        return len(self.models)

    def __repr__(self) -> str:
        return f"ModelRegistry(models={list(self.models.keys())})"
